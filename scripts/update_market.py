import datetime
import json
import math
from pathlib import Path

import yfinance as yf

TICKERS = ['QQQ', 'SOXX', 'NVDA', 'MSFT', 'AMZN', 'GOOGL', 'META', 'CRWV', 'NBIS', '^TNX']


def clean_json(value):
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def market_row(ticker, history):
    # Yahoo may return trailing rows with no closing price.
    closes = [float(value) for value in history['Close'].dropna()]
    closes = [value for value in closes if math.isfinite(value) and value > 0]
    if len(closes) < 2:
        raise ValueError('Fewer than two valid closing prices')
    close, prev, high = closes[-1], closes[-2], max(closes)
    return {'ticker': ticker, 'price': round(close, 2),
            'day_pct': round((close / prev - 1) * 100, 2),
            'drawdown_52w_pct': round((close / high - 1) * 100, 2)}


def main():
    path = Path('data/scoreboard.json')
    data = clean_json(json.loads(path.read_text(encoding='utf-8')))
    rows = []
    for ticker in TICKERS:
        try:
            history = yf.Ticker(ticker).history(period='1y', auto_adjust=False)
            rows.append(market_row(ticker, history))
        except Exception as error:
            print('market warning', ticker, error)
            rows.append({'ticker': ticker, 'price': None, 'day_pct': None,
                         'drawdown_52w_pct': None})
    data['market'] = rows
    data['market_updated_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # Serialize before writing so invalid numbers cannot corrupt the live feed.
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(payload + '\n', encoding='utf-8')
    temporary.replace(path)
    print('updated', sum(row['price'] is not None for row in rows), 'market series')


if __name__ == '__main__':
    main()
