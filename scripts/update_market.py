import datetime
import json
import math
from pathlib import Path

import yfinance as yf

TICKERS = ['QQQ', 'SOXX', 'NVDA', 'MSFT', 'AMZN', 'GOOGL', 'META', 'CRWV', 'NBIS', '^TNX',
           '^SOX', '^TWII', '2330.TW', 'TSM']

# Two-year histories used by the research layer (Greenwood-Shleifer-You run-up and crash tests).
RESEARCH_SERIES = {'SOX': '^SOX', 'TWII': '^TWII', 'SPX': '^GSPC'}
CHART_DAYS = 260  # about one trading year kept for the charts


def clean_json(value):
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def valid_closes(history):
    """Return [(date, close)] with missing or non-positive closes removed."""
    rows = []
    for stamp, value in history['Close'].dropna().items():
        value = float(value)
        if math.isfinite(value) and value > 0:
            rows.append((stamp.date().isoformat(), value))
    return rows


def market_row(ticker, history):
    # Yahoo may return trailing rows with no closing price.
    closes = [value for _, value in valid_closes(history)]
    if len(closes) < 2:
        raise ValueError('Fewer than two valid closing prices')
    close, prev, high = closes[-1], closes[-2], max(closes)
    return {'ticker': ticker, 'price': round(close, 2),
            'day_pct': round((close / prev - 1) * 100, 2),
            'drawdown_52w_pct': round((close / high - 1) * 100, 2)}


def research_metrics(series):
    """Compute run-up and drawdown measures from two-year daily closes.

    series: {'SOX': [(date, close)], 'TWII': [...], 'SPX': [...]} (any may be missing)
    """
    out = {}

    def two_year_return(rows):
        return (rows[-1][1] / rows[0][1] - 1) * 100

    def drawdown(rows):
        peak_date, peak = max(rows, key=lambda r: r[1])
        last_date, last = rows[-1]
        return {'peak': round(peak, 2), 'peak_date': peak_date, 'last': round(last, 2),
                'last_date': last_date, 'dd_pct': round((1 - last / peak) * 100, 1)}

    sox, twii, spx = series.get('SOX'), series.get('TWII'), series.get('SPX')
    if sox and len(sox) > 20:
        out['sox_drawdown'] = drawdown(sox)
        out['sox_2y_return_pct'] = round(two_year_return(sox), 1)
        if spx and len(spx) > 20:
            out['spx_2y_return_pct'] = round(two_year_return(spx), 1)
            # GSY measure: industry return net of the market over the prior two years.
            out['sox_2y_excess_pct'] = round(out['sox_2y_return_pct'] - out['spx_2y_return_pct'], 1)
        out['window_start'] = sox[0][0]
    if twii and len(twii) > 20:
        out['twii_drawdown'] = drawdown(twii)
        out['twii_2y_return_pct'] = round(two_year_return(twii), 1)
    return out


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

    series = {}
    for name, ticker in RESEARCH_SERIES.items():
        try:
            closes = valid_closes(yf.Ticker(ticker).history(period='2y', auto_adjust=False))
            if len(closes) > 20:
                series[name] = closes
        except Exception as error:
            print('research warning', ticker, error)

    research = data.setdefault('research', {})
    metrics = research_metrics(series)
    if metrics:
        metrics['updated_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        research['auto'] = metrics
    charts = research.setdefault('series', {})
    for name in ('SOX', 'TWII'):
        if name in series:
            charts[name] = [[d, round(v, 2)] for d, v in series[name][-CHART_DAYS:]]

    data['market_updated_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # Serialize before writing so invalid numbers cannot corrupt the live feed.
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(payload + '\n', encoding='utf-8')
    temporary.replace(path)
    print('updated', sum(row['price'] is not None for row in rows), 'market series;',
          'research series:', ', '.join(series) or 'none')


if __name__ == '__main__':
    main()
