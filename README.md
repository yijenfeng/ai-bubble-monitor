# AI Bubble Monitor V4.1

GitHub Pages dashboard that tracks how far the AI investment cycle looks like a bubble, and whether it is starting to burst.

## Publish
Enable **Settings → Pages → Deploy from branch → main / root**.

## Method (V4.1)
Every scored signal light uses a threshold taken from the literature or from the series' own history. Indicators that the evidence says do not predict crashes, or that have no history to calibrate against, are shown as observations and are not scored.

| Group (weight) | Signal | Warn / Hot | Basis |
| --- | --- | --- | --- |
| Price run-up & explosiveness (35%) | SOX two-year return net of the S&P 500 | 100% / 150% | Greenwood, Shleifer & You (2019): crash probability 53% / 80% |
| | PSY BSADF, SOX/S&P 500 price ratio (weekly) | 90% / 95% critical value | Phillips, Shi & Yu (2015); Monte Carlo critical values each run |
| | PSY BSADF, S&P 500 price/dividend (monthly, 1871–) | 90% / 95% critical value | Phillips, Shi & Yu (2015) |
| Credit & leverage (30%) | US private credit-to-GDP gap (BIS) | 2 / 10 pp | Basel III countercyclical buffer range |
| | US margin credit YoY growth (Fed Z.1, 1953–) | 80th / 95th percentile | Own history |
| Investment & issuance (20%) | US IPO average first-day return (Ritter, 1980–) | 80th / 95th percentile | Baker & Wurgler (2000); GSY issuance result |
| | Hyperscaler capex as % of US GDP | 0.9% / 1.2% | Historical analogue: 2000 telecom peak 1.2% (warn level is a judgement call) |
| Valuation (15%) | Shiller CAPE (1881–) | 80th / 95th percentile | Own history; Campbell & Shiller |
| | Real equity price gap vs one-sided HP trend | 40% / 60% | Borio & Lowe (60%); 40% is a judgement call |

Not scored (observations): US top-10 concentration, TSMC's TAIEX weight, Taiwan turnover, Taiwan margin balance and margin-to-market-cap, capex/cloud revenue, AI circular financing, tech bond issuance.

**Burst signal** (separate): SOX and TAIEX drawdown from their two-year highs relative to a crash threshold (SOX 40%, the GSY definition; TAIEX 20%), plus the JST 15% turn confirmation and the PSY collapse date of the SOX/S&P explosive episode.

**Composite**: AI Demand 15%, CapEx Intensity 20%, FCF Conversion 20%, Credit / Leverage 20%, Profitability 10%, Bubble Signals 15%. Scores before 2026-10-25 used earlier methods and are not directly comparable.

## Automation
GitHub Actions runs on weekdays (22:30 UTC, after the US close):
1. `scripts/update_market.py` — market cards (yfinance), SOX/TAIEX/S&P two-year closes, GSY run-up and drawdowns.
2. `scripts/research_indicators.py` — Shiller monthly data (CAPE, price/dividend PSY test, equity gap), BIS credit gap, Fed Z.1 margin accounts, SOX/S&P weekly PSY test, TWSE margin balance. Each source is independent; a failed source keeps its previous values.
3. `scripts/recalculate.py` — lights, group scores, pillars, composite and burst score, history.

Hand-verified inputs live in `research.manual` (IPO first-day returns, capex/GDP) and `research.observations`, each with a source URL and as-of date.

Research dashboard only; not investment advice.
