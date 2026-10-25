# AI Bubble Monitor V4

GitHub Pages dashboard that tracks how far the AI investment cycle looks like a bubble, and whether it is starting to burst.

## Publish
Enable **Settings → Pages → Deploy from branch → main / root**.

## What V4 adds
- **Valuation / Momentum pillar** — signal lights (green / yellow / red) for Shiller CAPE, Big Tech concentration, TSMC's TAIEX weight, hyperscaler CapEx vs cloud revenue, CapEx growth, AI circular-financing debt, Taiwan turnover, plus two lights computed daily:
  - SOX two-year return **net of the S&P 500** (Greenwood, Shleifer & You 2019 run-up test)
  - TAIEX two-year return
- **Burst signal** (separate from the composite) — SOX and TAIEX drawdown from their two-year highs, divided by a crash threshold (SOX 40%, the GSY crash definition; TAIEX 20%).
- **Charts** — SOX and TAIEX against their crash lines, TAIEX 1985–now (log) next to the 1990 bubble, Shiller CAPE since 1990, CapEx vs AI-lab revenue, composite and burst history.
- **Watch list** of catalysts and events.

Composite weights: AI Demand 15%, CapEx Intensity 20%, FCF Conversion 20%, Credit / Leverage 20%, Profitability 10%, Valuation / Momentum 15%. Scores before 2026-10-25 used the V3 five-pillar weights and are not directly comparable.

## Automation
GitHub Actions runs on weekdays (22:30 UTC, after the US close). `scripts/update_market.py` uses `yfinance` to refresh QQQ, SOXX, NVDA, MSFT, AMZN, GOOGL, META, CRWV, NBIS, ^TNX, ^SOX, ^TWII, 2330.TW and TSM, and two-year daily closes of ^SOX, ^TWII and ^GSPC for the research layer. `scripts/recalculate.py` then recomputes the lights, pillars, composite and burst score and appends to the history.

## Design choice
Market data is automated. Fundamentals and the hand-verified valuation indicators (`research.indicators` in `data/scoreboard.json`, each with its source URL and as-of date) are intentionally source-controlled, so an unreliable parser cannot silently change the risk score. To update one, edit its `value`, `asof` and `source`; thresholds (`warn`, `hot`) are part of the method.

Research dashboard only; not investment advice.
