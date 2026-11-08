import re, json, time, html, threading, sys, os
from concurrent.futures import ThreadPoolExecutor
import requests
BASE="https://websummit.com"
DAYS={"2026-11-10":54,"2026-11-11":58,"2026-11-12":45}
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 (schedule export script)"
lock=threading.Lock(); last=[0.0]
failed=[]; log=open("out/log.txt","a")
def L(*a):
    msg=" ".join(map(str,a)); print(msg,flush=True); log.write(msg+"\n"); log.flush()
def throttle():
    with lock:
        w=last[0]+0.5-time.time()
        if w>0: time.sleep(w)
        last[0]=time.time()
def get(url):
    for i in range(3):
        throttle()
        try:
            r=S.get(url,timeout=30)
            if r.status_code==200: return r.text
            L("HTTP",r.status_code,url,"try",i+1)
            if r.status_code==404: return ""
        except Exception as e: L("ERR",type(e).__name__,e,url,"try",i+1)
        time.sleep(2*(i+1))
    return None
CARD=re.compile(r'<a href="(/sessions/lis26/([0-9a-f-]{36})/[^"]*)"[^>]*>(.*?)</a>',re.S)
def txt(x): return html.unescape(re.sub(r'<[^>]+>','',x)).strip()
def parse_list(h):
    out=[]
    for href,sid,body in CARD.findall(h):
        track=re.search(r'SessionTrackLabel[^>]*>(.*?)</span>',body,re.S)
        title=re.search(r'<h5[^>]*>(.*?)</h5>',body,re.S)
        times=re.findall(r'<time>(.*?)</time>',body,re.S)
        addr=re.search(r'<address[^>]*>(.*?)</address>',body,re.S)
        t=txt(times[1]) if len(times)>1 else ""
        st,_,en=t.partition(" - ")
        out.append(dict(id=sid,url=BASE+href,track=txt(track.group(1)) if track else "",
            title=txt(title.group(1)) if title else "",date_card=txt(times[0]) if times else "",
            start_card=st.strip(),end_card=en.strip(),stage_card=txt(addr.group(1)) if addr else ""))
    return out
def step1():
    listing={}; pagefail=[]
    for day,n in DAYS.items():
        p=1; empty_seen=False
        while True:
            url=f"{BASE}/schedule/date/{day}/page/{p}/"
            h=get(url)
            if h is None: pagefail.append(url); L("PAGEFAIL",url)
            else:
                items=parse_list(h)
                L(day,"page",p,"items",len(items))
                for it in items:
                    it["day"]=day; it["page"]=p
                    listing.setdefault(it["id"],it)
                if not items and p>n:
                    L(day,"end of list at page",p,"(404)" if h=="" else "(empty)"); break
                if not items and p<=n: L("WARNING empty page within expected range",url)
            if p>n+30: L("STOP safety",day); break
            p+=1
    # retry failed pages
    for url in list(pagefail):
        h=get(url)
        if h is not None:
            pagefail.remove(url); d=url.split("/date/")[1].split("/")[0]; pg=int(url.rstrip("/").split("/")[-1])
            for it in parse_list(h): it["day"]=d; it["page"]=pg; listing.setdefault(it["id"],it)
    json.dump(dict(listing=listing,pagefail=pagefail),open("out/listing.json","w"),indent=1)
    return listing,pagefail
def fetch_session(it):
    fn=f"raw/{it['id']}.json"
    if os.path.exists(fn): return True
    h=get(it["url"])
    if not h: return False
    m=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',h,re.S)
    if not m: L("NO NEXT_DATA",it["url"]); return False
    d=json.loads(m.group(1))
    try:
        tpl=d["props"]["pageProps"]["data"]["page"]["template"]["customPage"]["sessionDetailsTemplate"]
        sess=[x for x in tpl if x.get("session")][0]["session"]
    except Exception as e: L("PARSE",e,it["url"]); return False
    json.dump(sess,open(fn,"w")); return True
def step2(listing):
    items=list(listing.values()); bad=[]
    with ThreadPoolExecutor(3) as ex:
        for it,ok in zip(items,ex.map(fetch_session,items)):
            if not ok: bad.append(it["url"])
    L("session fetch failures first pass:",len(bad))
    for it in items:
        if it["url"] in bad and fetch_session(it): bad.remove(it["url"])
    return bad
if __name__=="__main__":
    if os.path.exists("out/listing.json") and "--relist" not in sys.argv:
        j=json.load(open("out/listing.json")); listing,pagefail=j["listing"],j["pagefail"]
    else: listing,pagefail=step1()
    L("unique sessions listed:",len(listing),"page failures:",pagefail)
    bad=step2(listing)
    json.dump(dict(pagefail=pagefail,sessionfail=bad),open("out/failures.json","w"),indent=1)
    L("DONE. permanent session failures:",bad)
