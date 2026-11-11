"""Re-check one conference day against the 7 Nov baseline (websummit_2026_sessies.csv).

Usage (from the repo root):  python3 scripts/check_update.py 2026-11-12 workdir/ [picks.txt]
- Scrapes the day's overview pages (several passes: the site repeats sessions across pages)
- Fetches every session page on that day, plus the session page of every baseline session
  of the day before/that day that the listing no longer shows (finds sessions hidden by pagination)
- Writes workdir/diff.json and prints a summary incl. impact on picks (8-char ids, one per line)
"""
import sys, os, json, csv, time, collections
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAY=sys.argv[1]; WD=os.path.abspath(sys.argv[2]); PICKS=sys.argv[3] if len(sys.argv)>3 else None
os.makedirs(WD+"/raw",exist_ok=True); os.makedirs(WD+"/out",exist_ok=True); os.chdir(WD)
sys.path.insert(0,os.path.join(REPO,"scripts"))
import scrape as S   # throttle 2 req/s, retries, parse_list, fetch_session -> raw/<id>.json

old={r['sessie_id']:r for r in csv.DictReader(open(os.path.join(REPO,'websummit_2026_sessies.csv'),encoding='utf-8-sig'))}
prevday=f"{DAY[:8]}{int(DAY[8:])-1:02d}"

def listing(day):
    found={}; p=1; emp=0
    while p<=90:
        url=f"{S.BASE}/schedule/date/{day}/page/{p}/"; items=[]
        for a in range(4):
            h=S.get(url); items=S.parse_list(h) if h else []
            if items: break
            time.sleep(3*(a+1))
        S.L(day,"page",p,"items",len(items))
        emp=emp+1 if not items else 0
        if emp>=2: break
        for it in items: it["day"]=day; found.setdefault(it["id"],it)
        p+=1
    return found,p-2
allf={}; lastpage=None
for n in range(4):
    f,lastpage=listing(DAY); new=set(f)-set(allf)
    for k,v in f.items(): allf.setdefault(k,v)
    S.L("PASS",n+1,"found",len(f),"new",len(new))
    if n>=1 and not new: break
items=list(allf.values())
for it in items: S.fetch_session(it)
extra=[{"id":k,"url":v["url"]} for k,v in old.items() if v["dag"] in (DAY,prevday) and k not in allf]
for it in extra: S.fetch_session(it)
def info(i):
    f=f"raw/{i}.json"
    if not os.path.exists(f): return None
    s=json.load(open(f)); st=s.get("starts_at") or ""; en=s.get("ends_at") or ""
    return dict(day=st[:10],start=st[11:16],end=en[11:16],stage=(s.get("location") or {}).get("name",""),title=s.get("title",""))
now={}
for it in items:
    now[it["id"]]=info(it["id"]) or dict(day=DAY,start=it["start_card"],end=it["end_card"],stage=it["stage_card"],title=it["title"],nopage=True)
for it in extra:
    x=info(it["id"])
    if x and x["day"]==DAY: x["hidden"]=True; now[it["id"]]=x
out=collections.defaultdict(list)
for i,x in now.items():
    o=old.get(i)
    if not o: out["new"].append(dict(id=i,**x)); continue
    if o["dag"]!=DAY: out["moved_in"].append(dict(id=i,from_day=o["dag"],from_start=o["start"],**x)); continue
    ch=[k for k,ok in (("start","start"),("end","eind"),("stage","stage")) if x.get(k) and x[k]!=o[ok]]
    if ch: out["changed"].append(dict(id=i,old=f'{o["start"]}-{o["eind"]} {o["stage"]}',fields=ch,**x))
for i,o in old.items():
    if o["dag"]==DAY and i not in now:
        x=info(i); out["gone"].append(dict(id=i,title=o["titel"],old=f'{o["start"]} {o["stage"]}',now=(f'{x["day"]} {x["start"]} {x["stage"]}' if x else "no page (404)")))
prevstill=collections.Counter()
for it in extra:
    if old[it["id"]]["dag"]==prevday:
        x=info(it["id"]); prevstill["still "+x["day"] if x else "404"]+=1
summary=dict(day=DAY,last_page=lastpage,unique_in_listing=len(allf),total_on_day=len(now),hidden_by_pagination=sum(1 for x in now.values() if x.get("hidden")),prev_day_sessions_elsewhere=dict(prevstill),counts={k:len(v) for k,v in out.items()})
pk=[]
if PICKS:
    for p in open(PICKS).read().split():
        full=[k for k in old if k.startswith(p)]
        if not full: continue
        o=old[full[0]]
        if o["dag"] not in (DAY,prevday): continue
        x=now.get(full[0]) or info(full[0])
        pk.append(dict(title=o["titel"],was=f'{o["dag"]} {o["start"]}-{o["eind"]} {o["stage"]}',now=(f'{x["day"]} {x["start"]}-{x["end"]} {x["stage"]}' if x else "no page (404)")))
json.dump(allf,open("out/listing.json","w"),indent=1,ensure_ascii=False)
json.dump(dict(summary=summary,picks=pk,**out),open("out/diff.json","w"),indent=1,ensure_ascii=False)
print(json.dumps(summary,indent=1))
for p in pk: print(("SAME " if p["was"]==p["now"] else "CHANGED ")+p["title"],"|",p["was"],"->",p["now"])
