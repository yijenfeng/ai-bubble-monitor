# AI Bubble Monitor V3

GitHub Pages dashboard with a verified fundamental layer plus automated weekday market monitoring.

## Publish
Enable **Settings → Pages → Deploy from branch → main / root**.

## Automation
GitHub Actions installs `yfinance` and refreshes QQQ, SOXX, NVDA, MSFT, AMZN, GOOGL, META, CRWV, NBIS and ^TNX on weekdays, then recalculates and stores the composite history.

## Design choice
Market data is automated. Fundamental earnings are intentionally verified/source-controlled in V3 to prevent an unreliable parser from silently changing the risk score.
