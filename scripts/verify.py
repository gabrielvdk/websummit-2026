# Second full listing pass; in-range empty/404 pages retried up to 6x with growing delay.
import json, time, sys
sys.argv=[sys.argv[0]]
import scrape as S
j=json.load(open("out/listing.json")); listing=j["listing"]
before=set(listing)
stillempty=[]
for day,n in S.DAYS.items():
    p=1
    while True:
        url=f"{S.BASE}/schedule/date/{day}/page/{p}/"
        items=[]
        for a in range(6):
            h=S.get(url)
            items=S.parse_list(h) if h else []
            if items or p>n: break
            S.L("V retry empty in-range",url,"attempt",a+1); time.sleep(5*(a+1))
        S.L("V",day,"page",p,"items",len(items))
        if not items and p<=n: stillempty.append(url)
        for it in items:
            if it["id"] not in listing:
                it["day"]=day; it["page"]=p; listing[it["id"]]=it; S.L("V NEW",it["id"],it["title"])
        if not items and p>n: S.L("V",day,"end at page",p); break
        p+=1
new=set(listing)-before
S.L("V new sessions found:",len(new),"still-empty in-range pages:",stillempty)
json.dump(dict(listing=listing,pagefail=stillempty),open("out/listing.json","w"),indent=1)
bad=S.step2(listing)
json.dump(dict(pagefail=stillempty,sessionfail=bad),open("out/failures.json","w"),indent=1)
S.L("V DONE session failures:",bad)
# extra rounds for session pages that 404'd (site returns transient 404s)
for rnd in range(4):
    if not bad: break
    time.sleep(20*(rnd+1))
    S.L("V extra round",rnd+1,"for",len(bad))
    bad=[u for u in bad if not S.fetch_session(next(it for it in listing.values() if it["url"]==u))]
json.dump(dict(pagefail=stillempty,sessionfail=bad),open("out/failures.json","w"),indent=1)
S.L("V FINAL session failures:",bad)
