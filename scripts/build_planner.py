"""Build websummit_planner.html (+ websummit_2026_sessies_actueel.csv) from the 7 Nov baseline
plus one or more check dirs produced by check_update.py (later dirs override earlier ones).
Usage (repo root): python3 scripts/build_planner.py <checkdir> [<checkdir> ...]"""
import sys, os, json, csv, glob
from datetime import datetime
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF={"2026-11-10","2026-11-11","2026-11-12"}
TRACKTYPE={"meetup":"meetup","women in tech":"meetup","stand events":"stand event","masterclasses":"masterclass","startup masterclass":"masterclass",
 "investor masterclass":"masterclass","pitch":"pitch","press conference":"press conference","startup showcase":"startup showcase","night summit":"night summit"}
def stype(track,title):
    t=(track or "").lower().strip()
    if t in TRACKTYPE: return TRACKTYPE[t]
    if t=="centre stage" or t.endswith("summit") or t=="moneyconf": return "stage session"
    tl=title.lower()
    for k,v in [("meetup","meetup"),("book signing","book signing"),("hackathon","hackathon"),("masterclass","masterclass"),("workshop","workshop")]:
        if k in tl: return v
    return ""
def card_hm(t):
    try: return datetime.strptime(t.replace(".",":"),"%I:%M%p").strftime("%H:%M")
    except Exception: return t or ""
rows={}
for r in csv.DictReader(open(os.path.join(REPO,"websummit_2026_sessies.csv"),encoding="utf-8-sig")):
    rows[r["sessie_id"]]=dict(dag=r["dag"],start=r["start"],eind=r["eind"],stage=r["stage"],track=r["track"],type=r["type"],titel=r["titel"],
        beschrijving=r["beschrijving"],sprekers=r["sprekers"],organisaties=r["organisaties"],host_partner=r["host_partner"],url=r["url"],status="")
for d in sys.argv[1:]:
    lst=json.load(open(f"{d}/out/listing.json")) if os.path.exists(f"{d}/out/listing.json") else {}
    diff=json.load(open(f"{d}/out/diff.json"))
    for f in glob.glob(f"{d}/raw/*.json"):
        s=json.load(open(f)); i=s["id"]; st=s.get("starts_at") or ""
        if st[:10] not in CONF and i not in lst: continue
        parts=s.get("timeslot_participations") or []; spk=[]; orgs=[]
        for p in parts:
            n=(p.get("name") or "").strip(); ex=", ".join(x for x in [(p.get("job_title") or "").strip(),(p.get("company_name") or "").strip()] if x)
            spk.append(n+(f" ({ex})" if ex else "")); c=(p.get("company_name") or "").strip()
            if c and c not in orgs: orgs.append(c)
        old=rows.get(i,{})
        track=(lst.get(i) or {}).get("track") or old.get("track") or (s.get("schedule_track") or {}).get("name","")
        url=(lst.get(i) or {}).get("url") or old.get("url") or f"https://websummit.com/sessions/lis26/{i}/{s.get('slug','')}/"
        title=s.get("title") or old.get("titel","")
        c=lst.get(i)   # overview card wins for day/time/stage (session pages lag behind)
        day,stt,ent,stg=(c["day"],card_hm(c["start_card"]),card_hm(c["end_card"]),c["stage_card"].strip()) if c else (st[:10],st[11:16],(s.get("ends_at") or "")[11:16],(s.get("location") or {}).get("name",""))
        rows[i]=dict(dag=day,start=stt,eind=ent,stage=stg,track=track,
            type=stype(track,title),titel=title,beschrijving=(s.get("description") or "").strip(),sprekers="; ".join(spk),organisaties="; ".join(orgs),
            host_partner=(s.get("appearance_name") or "").strip(),url=url,status="")
    for k in ("new","moved_in"):
        for x in diff.get(k,[]):
            if x.get("nopage"):
                it=lst.get(x["id"],{}); old=rows.get(x["id"],{})
                rows[x["id"]]=dict(old) if old else dict(beschrijving="",sprekers="",organisaties="",host_partner="",track=it.get("track",""),url=it.get("url",""))
                rows[x["id"]].update(dag=x["day"],start=card_hm(x["start"]),eind=card_hm(x["end"]),stage=x["stage"],titel=x["title"],status="alleen in overzicht")
                rows[x["id"]]["type"]=stype(rows[x["id"]].get("track",""),x["title"])
    for x in diff.get("gone",[]):
        if x["now"].startswith("no page") and x["id"] in rows: rows[x["id"]]["status"]="niet meer gevonden"
cols=["dag","start","eind","stage","track","titel","beschrijving","sprekers","organisaties","host_partner","type","url","status","sessie_id"]
out=sorted(({**v,"sessie_id":k} for k,v in rows.items()),key=lambda r:(r["dag"],r["start"],r["stage"]))
with open(os.path.join(REPO,"websummit_2026_sessies_actueel.csv"),"w",newline="",encoding="utf-8-sig") as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(out)
lists=json.load(open(os.path.join(REPO,"scripts","planner_lists.json")))
data=[[r["sessie_id"][:8],r["dag"][8:],r["start"],r["eind"],r["stage"],r["track"],r["type"],
       r["titel"]+(" ⚠ "+r["status"] if r["status"] else ""),' '.join(r["beschrijving"].split()),r["sprekers"],r["host_partner"],r["url"]] for r in out]
js=json.dumps({"s":data,**lists},ensure_ascii=False,separators=(",",":")).replace("</","<\\/")
t=open(os.path.join(REPO,"scripts","planner_template.html")).read()
assert "/*DATA*/null" in t
open(os.path.join(REPO,"websummit_planner.html"),"w").write(t.replace("/*DATA*/null",js))
from collections import Counter
print("sessions:",len(out),dict(sorted(Counter(r["dag"] for r in out).items())),"flagged:",Counter(r["status"] for r in out if r["status"]))
