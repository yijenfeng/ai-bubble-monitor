import json, datetime
from pathlib import Path
import yfinance as yf

TICKERS=["QQQ","SOXX","NVDA","MSFT","AMZN","GOOGL","META","CRWV","NBIS","^TNX"]
p=Path("data/scoreboard.json")
d=json.loads(p.read_text(encoding="utf-8"))
rows=[]
for t in TICKERS:
    try:
        x=yf.Ticker(t).history(period="1y",auto_adjust=False)
        if x.empty: continue
        close=float(x["Close"].iloc[-1]); high=float(x["Close"].max())
        prev=float(x["Close"].iloc[-2]) if len(x)>1 else close
        rows.append({"ticker":t,"price":round(close,2),"day_pct":round((close/prev-1)*100,2) if prev else None,"drawdown_52w_pct":round((close/high-1)*100,2) if high else None})
    except Exception as e:
        print("market warning",t,e)
d["market"]=rows
d["market_updated_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
print("updated",len(rows),"market series")
