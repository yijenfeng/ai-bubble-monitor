import json, datetime
from pathlib import Path
p=Path("data/scoreboard.json"); d=json.loads(p.read_text(encoding="utf-8"))
weights={"AI Demand":.20,"CapEx Intensity":.25,"FCF Conversion":.25,"Credit / Leverage":.20,"Profitability":.10}
score=round(sum(x["score"]*weights[x["name"]] for x in d["pillars"]))
d["score"]=score
d["status"]="LOW" if score<35 else "WATCH" if score<65 else "HIGH" if score<80 else "EXTREME"
today=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
if not d["history"] or d["history"][-1]["date"]!=today:
    d["history"].append({"date":today,"score":score})
else:
    d["history"][-1]["score"]=score
d["as_of"]=today
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
