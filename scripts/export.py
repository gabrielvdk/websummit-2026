import json, os, csv
from datetime import datetime
from zoneinfo import ZoneInfo
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
TZ=ZoneInfo("Europe/Lisbon")
j=json.load(open("out/listing.json")); listing=j["listing"]
def hm(iso):
    if not iso: return ""
    return datetime.fromisoformat(iso.replace("Z","+00:00")).astimezone(TZ).strftime("%H:%M")
def card_hm(t):
    if not t: return ""
    try: return datetime.strptime(t.replace(".",":"),"%I:%M%p").strftime("%H:%M")
    except: return t
TRACKTYPE={"meetup":"meetup","women in tech":"meetup","stand events":"stand event","masterclasses":"masterclass",
 "startup masterclass":"masterclass","investor masterclass":"masterclass","pitch":"pitch","press conference":"press conference",
 "startup showcase":"startup showcase","night summit":"night summit"}
def stype(track,title):
    t=track.lower().strip()
    if t in TRACKTYPE: return TRACKTYPE[t]
    if t=="centre stage" or t.endswith("summit") or t=="moneyconf": return "stage session"
    tl=title.lower()
    for k,v in [("meetup","meetup"),("book signing","book signing"),("hackathon","hackathon"),("masterclass","masterclass"),("workshop","workshop")]:
        if k in tl: return v
    return ""
cols=["dag","start","eind","stage","track","titel","beschrijving","sprekers","organisaties","host_partner","type","url","sessie_id"]
rows=[]
for sid,it in listing.items():
    fn=f"raw/{sid}.json"; s=json.load(open(fn)) if os.path.exists(fn) else {}
    parts=s.get("timeslot_participations") or []
    spk=[]; orgs=[]
    for p in parts:
        name=(p.get("name") or "").strip()
        extra=", ".join(x for x in [(p.get("job_title") or "").strip(),(p.get("company_name") or "").strip()] if x)
        role=(p.get("role") or "").strip()
        spk.append(name+(f" ({extra})" if extra else "")+(f" [{role}]" if role else ""))
        c=(p.get("company_name") or "").strip()
        if c and c not in orgs: orgs.append(c)
    loc=(s.get("location") or {}).get("name") or it["stage_card"]
    track=it["track"] or ((s.get("schedule_track") or {}).get("name") or "")
    rows.append({"dag":it["day"],
      "start":hm(s.get("starts_at")) or card_hm(it["start_card"]),
      "eind":hm(s.get("ends_at")) or card_hm(it["end_card"]),
      "stage":loc.strip(),"track":track,"titel":s.get("title") or it["title"],
      "beschrijving":(s.get("description") or "").strip(),
      "sprekers":"; ".join(spk),"organisaties":"; ".join(orgs),
      "host_partner":(s.get("appearance_name") or "").strip(),
      "type":stype(track,s.get("title") or it["title"]),"url":it["url"],"sessie_id":sid,"_ok":bool(s)})
rows.sort(key=lambda r:(r["dag"],r["start"],r["stage"],r["titel"]))
with open("out/websummit_2026_sessies.csv","w",newline="",encoding="utf-8-sig") as f:
    w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore"); w.writeheader(); w.writerows(rows)
wb=Workbook(); ws=wb.active; ws.title="Sessies"; ws.append(cols)
for r in rows: ws.append([r[c] for c in cols])
for c in ws[1]: c.font=Font(bold=True)
ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
for i,wd in enumerate([11,7,7,24,20,45,70,60,35,25,12,60,38],1): ws.column_dimensions[get_column_letter(i)].width=wd
wb.save("out/websummit_2026_sessies.xlsx")
from collections import Counter
print("per dag:",dict(sorted(Counter(r["dag"] for r in rows).items())),"totaal:",len(rows))
print("zonder sessiepagina-data:",sum(not r["_ok"] for r in rows))
print("tracks:",Counter(r["track"] for r in rows).most_common())

with open("out/websummit_2026_zoekcorpus.txt","w",encoding="utf-8") as f:
    for r in rows:
        f.write(f"### {r['sessie_id'][:8]} | {r['dag']} {r['start']}-{r['eind']} | {r['stage']} | {r['track']} | {r['type']}\n")
        f.write(f"TITEL: {r['titel']}\n")
        if r['host_partner']: f.write(f"HOST/PARTNER: {r['host_partner']}\n")
        if r['sprekers']: f.write(f"SPREKERS: {r['sprekers']}\n")
        f.write(f"BESCHRIJVING: {' '.join(r['beschrijving'].split())}\n")
        f.write(f"URL: {r['url']}\n\n")
