"""Research-layer bubble indicators with thresholds taken from the literature or from each
series' own history (see the research document, section 11).

Automated here (each source independent; a failed source keeps its previous values):
  * Shiller monthly data (thetrading.tools mirror of Robert Shiller's dataset)
      - CAPE level and its percentile since 1881 and since 1990
      - PSY (Phillips-Shi-Yu 2015) BSADF test on the log real price/dividend ratio
      - Borio-Lowe equity price gap: real S&P 500 vs a one-sided HP trend (annual, lambda 1600)
  * BIS credit-to-GDP gap, United States (Basel III 2 / 10 percentage-point bounds)
  * Federal Reserve Z.1 margin accounts at brokers and dealers: year-over-year growth and its
    percentile since 1953
  * SOX relative to the S&P 500 (weekly, Yahoo Finance): PSY BSADF test
  * TWSE margin-loan balance (observation only, not scored)
"""
import csv
import datetime
import io
import json
import math
import time
import urllib.request
from pathlib import Path

import numpy as np

PATH = Path('data/scoreboard.json')
UA = {'User-Agent': 'ai-bubble-monitor (GitHub Actions; research dashboard)'}
SHILLER_CSV = 'https://www.thetrading.tools/data/indicators/shiller-cape.csv'
BIS_GAP_CSV = 'https://stats.bis.org/api/v1/data/WS_CREDIT_GAP/Q.US.P.A.C/all?format=csv'
FRED_MARGIN = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=BOGZ1FL663067003Q'
TWSE_MARGIN = 'https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={d}&selectType=MS&response=json'
SIM_REPS = 500
SEED = 20261025


def fetch(url, tries=3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode('utf-8', errors='replace')
        except Exception as error:  # network hiccups: retry with backoff
            last = error
            time.sleep(3 * (attempt + 1))
    raise last


def percentile_rank(history, value):
    a = np.asarray(history, dtype=float)
    a = a[np.isfinite(a)]
    return round(float((a <= value).mean() * 100), 1)


# ---------------------------------------------------------------- PSY / BSADF
def adf_t_by_start(y, end, min_start, max_start):
    """Lag-0 ADF t-statistics (regression dy_t = a + b*y_{t-1}) for samples y[s..end],
    for every start s in [min_start, max_start]. Vectorised with reverse cumulative sums."""
    x = y[:end]          # y_{t-1} for t = 1..end
    z = np.diff(y[:end + 1])  # dy_t for t = 1..end
    # sums over t = s+1..end  <=> indices s..end-1 of x and z
    rc = lambda v: np.cumsum(v[::-1])[::-1]
    n = np.arange(end, 0, -1, dtype=float)  # number of obs when starting at index i
    sx, sz, sxx, sxz, szz = rc(x), rc(z), rc(x * x), rc(x * z), rc(z * z)
    idx = np.arange(min_start, max_start + 1)
    n, sx, sz, sxx, sxz, szz = (v[idx] for v in (n, sx, sz, sxx, sxz, szz))
    den = n * sxx - sx * sx
    beta = (n * sxz - sx * sz) / den
    alpha = (sz - beta * sx) / n
    rss = szz - alpha * sz - beta * sxz
    sigma2 = np.maximum(rss, 1e-300) / (n - 2)
    se = np.sqrt(sigma2 * n / den)
    return beta / se


def bsadf_at(y, end, window):
    """Backward sup ADF statistic at observation `end` (0-based) with minimum window size."""
    max_start = end - window + 1
    if max_start < 0:
        return None
    return float(np.max(adf_t_by_start(y, end, 0, max_start)))


def bsadf_series(y, window, first_end):
    return [(e, bsadf_at(y, e, window)) for e in range(first_end, len(y))]


def psy_window(T):
    # PSY (2015) recommended minimum window: r0 = 0.01 + 1.8 / sqrt(T)
    return max(10, int(math.floor((0.01 + 1.8 / math.sqrt(T)) * T)))


def bsadf_critical_values(T, window, reps=SIM_REPS, seed=SEED):
    """90% and 95% critical values of the BSADF statistic at the last observation of a
    length-T random walk (the null of no bubble)."""
    rng = np.random.default_rng(seed + T)
    stats = []
    for _ in range(reps):
        y = np.cumsum(rng.standard_normal(T))
        stats.append(bsadf_at(y, T - 1, window))
    return float(np.quantile(stats, 0.90)), float(np.quantile(stats, 0.95))


def psy_summary(dates, values, label, keep_last=360):
    y = np.log(np.asarray(values, dtype=float))
    T = len(y)
    w = psy_window(T)
    cv90, cv95 = bsadf_critical_values(T, w)
    seq = bsadf_series(y, w, max(w - 1, T - keep_last))
    last = seq[-1][1]
    # Most recent run of consecutive observations above the 95% critical value (date-stamp).
    run_start = None
    for e, s in reversed(seq):
        if s is not None and s > cv95:
            run_start = e
        else:
            break
    # Last completed or ongoing explosive episode in the kept window (PSY date-stamping):
    # origination = first crossing above the 95% value, collapse = first fall back below it.
    episode = None
    above = [i for i, (_, s) in enumerate(seq) if s is not None and s > cv95]
    if above:
        end_i = above[-1]
        start_i = end_i
        while start_i - 1 >= 0 and seq[start_i - 1][1] is not None and seq[start_i - 1][1] > cv95:
            start_i -= 1
        peak_i = max(range(start_i, end_i + 1), key=lambda i: seq[i][1])
        episode = {'start': dates[seq[start_i][0]], 'last_above': dates[seq[end_i][0]],
                   'peak_date': dates[seq[peak_i][0]], 'peak_stat': round(seq[peak_i][1], 3),
                   'ongoing': end_i == len(seq) - 1,
                   'collapsed_on': None if end_i == len(seq) - 1 else dates[seq[end_i + 1][0]]}
    return {
        'label': label, 'stat': round(last, 3), 'cv90': round(cv90, 3), 'cv95': round(cv95, 3),
        'T': T, 'window': w, 'last_date': dates[-1],
        'explosive_since': dates[run_start] if run_start is not None else None,
        'last_episode': episode,
        'series': [[dates[e], round(s, 3)] for e, s in seq],
    }


# ---------------------------------------------------------------- HP filter
def hp_trend(y, lam):
    n = len(y)
    D = np.zeros((n - 2, n))
    for i in range(n - 2):
        D[i, i:i + 3] = [1, -2, 1]
    return np.linalg.solve(np.eye(n) + lam * D.T @ D, y)


def one_sided_hp_gap(values, lam=1600, min_obs=20):
    """Gap (%) of the last value from a recursive (one-sided) HP trend, as in Borio-Lowe."""
    y = np.asarray(values, dtype=float)
    out = []
    for t in range(min_obs, len(y) + 1):
        trend = hp_trend(y[:t], lam)[-1]
        out.append((t - 1, (y[t - 1] / trend - 1) * 100))
    return out


# ---------------------------------------------------------------- sources
def shiller_block():
    rows = list(csv.DictReader(io.StringIO(fetch(SHILLER_CSV))))
    rows = [r for r in rows if r.get('date')]
    dates = [r['date'][:7] for r in rows]

    def col(name):
        return [float(r[name]) if r.get(name) not in (None, '') else float('nan') for r in rows]

    cape, price, div, cpi = col('cape_value'), col('sp_price'), col('dividend'), col('cpi')
    out = {}

    # CAPE level and percentiles
    cape_pts = [(d, c) for d, c in zip(dates, cape) if math.isfinite(c)]
    last_d, last_c = cape_pts[-1]
    full = [c for _, c in cape_pts]
    since90 = [c for d, c in cape_pts if d >= '1990-01']
    out['cape'] = {
        'value': round(last_c, 2), 'asof': last_d,
        'pct_full': percentile_rank(full, last_c), 'pct_1990': percentile_rank(since90, last_c),
        'p80': round(float(np.percentile(full, 80)), 2), 'p95': round(float(np.percentile(full, 95)), 2),
        'median': round(float(np.median(full)), 2), 'since': cape_pts[0][0],
        'source': SHILLER_CSV,
    }

    # PSY on log real price / dividend (real terms cancel: P/D is the same nominal or real)
    pd_pts = [(d, p / q) for d, p, q in zip(dates, price, div) if math.isfinite(p) and math.isfinite(q) and q > 0]
    psy = psy_summary([d for d, _ in pd_pts], [v for _, v in pd_pts], 'S&P 500 價格／股利比（月，1871 起）')
    psy['source'] = SHILLER_CSV
    out['psy_sp500_pd'] = psy

    # Borio-Lowe equity gap: annual average real price, current year = latest month
    real = {}
    for d, p, c in zip(dates, price, cpi):
        if math.isfinite(p) and math.isfinite(c) and c > 0:
            real.setdefault(d[:4], []).append(p / c)
    years = sorted(real)
    series = [float(np.mean(real[y])) if y != years[-1] else real[y][-1] for y in years]
    gaps = one_sided_hp_gap(series, lam=1600, min_obs=20)
    out['equity_gap'] = {
        'value': round(gaps[-1][1], 1), 'asof': dates[-1],
        'history': [[years[i], round(g, 1)] for i, g in gaps[-60:]],
        'method': '實質 S&P 500（Shiller CPI 平減）年平均，當年以最新月份代入；單邊 HP 濾波 λ=1600，至少 20 年資料',
        'source': SHILLER_CSV,
    }
    # chart: CAPE yearly (January) since 1990 plus latest month
    chart = [[d, round(c, 2)] for d, c in cape_pts if d >= '1990-01' and d.endswith('-01')]
    if chart[-1][0] != last_d:
        chart.append([last_d, round(last_c, 2)])
    out['cape_chart'] = {'series': chart, 'source': SHILLER_CSV}
    return out


def bis_block():
    rows = list(csv.DictReader(io.StringIO(fetch(BIS_GAP_CSV))))
    pts = [(r['TIME_PERIOD'], float(r['OBS_VALUE'])) for r in rows if r.get('OBS_VALUE') not in (None, '')]
    pts.sort()
    q, v = pts[-1]
    peak = max(pts, key=lambda p: p[1])
    return {'credit_gap_us': {'value': round(v, 2), 'asof': q, 'peak': round(peak[1], 2), 'peak_q': peak[0],
                              'history': [[p, round(x, 2)] for p, x in pts if p >= '1990'], 'source': BIS_GAP_CSV}}


def margin_block():
    rows = list(csv.DictReader(io.StringIO(fetch(FRED_MARGIN))))
    key = [k for k in rows[0] if k != 'observation_date'][0]
    pts = [(r['observation_date'], float(r[key])) for r in rows if r[key] not in ('', '.')]
    by = dict(pts)
    yoy = []
    for d, v in pts:
        prev = by.get(str(int(d[:4]) - 1) + d[4:])
        if prev and prev > 0 and d >= '1953':
            yoy.append((d, (v / prev - 1) * 100))
    d, g = yoy[-1]
    hist = [x for _, x in yoy]
    return {'margin_yoy_us': {'value': round(g, 1), 'asof': d, 'level_musd': by[d],
                              'pct': percentile_rank(hist, g), 'p80': round(float(np.percentile(hist, 80)), 1),
                              'p95': round(float(np.percentile(hist, 95)), 1), 'since': yoy[0][0],
                              'history': [[p, round(x, 1)] for p, x in yoy if p >= '1990'], 'source': FRED_MARGIN}}


def sox_relative_block():
    import yfinance as yf
    sox = yf.Ticker('^SOX').history(period='max', interval='1wk', auto_adjust=False)['Close'].dropna()
    spx = yf.Ticker('^GSPC').history(period='max', interval='1wk', auto_adjust=False)['Close'].dropna()
    sox.index = sox.index.date
    spx.index = spx.index.date
    both = sorted(set(sox.index) & set(spx.index))
    vals = [(d.isoformat(), float(sox[d]) / float(spx[d])) for d in both if float(sox[d]) > 0 and float(spx[d]) > 0]
    if len(vals) < 300:
        raise ValueError('too few weekly observations: %d' % len(vals))
    psy = psy_summary([d for d, _ in vals], [v for _, v in vals], '費城半導體／S&P 500 價格比（週）', keep_last=260)
    psy['source'] = 'Yahoo Finance via yfinance（^SOX、^GSPC 週收盤）'
    return {'psy_sox_rel': psy}


def twse_margin_block():
    def balance(day):
        data = json.loads(fetch(TWSE_MARGIN.format(d=day.strftime('%Y%m%d'))))
        if data.get('stat') != 'OK':
            return None
        for row in data['tables'][0]['data']:
            if row[0].startswith('融資金額'):
                return int(row[5].replace(',', '')) / 1e5  # 仟元 -> 億元
        return None

    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
    latest = None
    for back in range(0, 10):
        d = today - datetime.timedelta(days=back)
        latest = balance(d)
        if latest:
            break
        time.sleep(2)
    if not latest:
        raise ValueError('no TWSE margin data in the last 10 days')
    year_ago = None
    for back in range(0, 10):
        d0 = d.replace(year=d.year - 1) - datetime.timedelta(days=back)
        time.sleep(2)
        year_ago = balance(d0)
        if year_ago:
            break
    out = {'value': round(latest, 1), 'asof': d.isoformat(), 'unit': '億元',
           'source': 'https://www.twse.com.tw/zh/trading/margin/mi-margn.html'}
    if year_ago:
        out['yoy'] = round((latest / year_ago - 1) * 100, 1)
    return {'tw_margin_balance': out}


def main():
    data = json.loads(PATH.read_text(encoding='utf-8'))
    research = data.setdefault('research', {})
    auto = research.setdefault('indicators_auto', {})
    status = {}
    for name, fn in [('shiller', shiller_block), ('bis', bis_block), ('margin', margin_block),
                     ('sox_relative', sox_relative_block), ('twse_margin', twse_margin_block)]:
        try:
            block = fn()
            stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            for key, value in block.items():
                value['updated_utc'] = stamp
                auto[key] = value
            status[name] = 'ok'
        except Exception as error:
            print('research warning', name, repr(error))
            status[name] = 'failed: ' + type(error).__name__
    research['indicators_auto_status'] = status
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    tmp = PATH.with_suffix('.tmp')
    tmp.write_text(payload + '\n', encoding='utf-8')
    tmp.replace(PATH)
    print('research indicators:', status)


if __name__ == '__main__':
    main()
