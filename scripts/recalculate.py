"""Recompute the composite risk score, the valuation/momentum pillar and the burst index.

Composite = weighted fundamental pillars (verified by hand) + a Valuation / Momentum pillar
built from the research signal lights (some verified by hand, some computed from market data).
The burst index is separate: how far SOX and TAIEX have fallen from their two-year highs,
relative to a crash threshold (SOX uses the Greenwood-Shleifer-You 40% definition).
"""
import datetime
import json
from pathlib import Path

PATH = Path('data/scoreboard.json')

WEIGHTS = {'AI Demand': .15, 'CapEx Intensity': .20, 'FCF Conversion': .20,
           'Credit / Leverage': .20, 'Profitability': .10, 'Valuation / Momentum': .15}

# Signal lights computed from research['auto'] each run: (id, name, key, unit, warn, hot)
AUTO_SIGNALS = [
    ('sox_2y_excess', '費城半導體兩年超額報酬（扣 S&P 500）', 'sox_2y_excess_pct', '%', 100, 150),
    ('twii_2y_return', '台股加權指數兩年漲幅', 'twii_2y_return_pct', '%', 100, 150),
]

# Burst thresholds: drawdown from the two-year high that counts as a crash.
CRASH = {'sox_drawdown': ('費城半導體指數', 40), 'twii_drawdown': ('台股加權指數', 20)}


def light(value, warn, hot):
    return 2 if value >= hot else 1 if value >= warn else 0


def build_signals(research):
    signals = []
    for row in research.get('indicators', []):
        if row.get('value') is None:
            continue
        signals.append({**row, 'status': light(row['value'], row['warn'], row['hot']), 'auto': False})
    auto = research.get('auto', {})
    as_of = (auto.get('sox_drawdown') or auto.get('twii_drawdown') or {}).get('last_date')
    for sid, name, key, unit, warn, hot in AUTO_SIGNALS:
        if auto.get(key) is None:
            continue
        signals.append({'id': sid, 'name': name, 'value': auto[key], 'unit': unit, 'warn': warn,
                        'hot': hot, 'asof': as_of, 'source': 'Yahoo Finance via yfinance（自動）',
                        'status': light(auto[key], warn, hot), 'auto': True})
    signals.sort(key=lambda s: -s['status'])
    return signals


def build_burst(research):
    auto = research.get('auto', {})
    parts = []
    for key, (name, crash) in CRASH.items():
        dd = auto.get(key)
        if not dd:
            continue
        parts.append({'id': key, 'name': name, 'dd_pct': dd['dd_pct'], 'crash_pct': crash,
                      'peak': dd['peak'], 'peak_date': dd['peak_date'], 'last': dd['last'],
                      'last_date': dd['last_date'],
                      'progress': round(min(1, max(0, dd['dd_pct'] / crash)) * 100)})
    score = round(sum(p['progress'] for p in parts) / len(parts)) if parts else None
    return {'score': score, 'parts': parts}


def main():
    d = json.loads(PATH.read_text(encoding='utf-8'))
    research = d.setdefault('research', {})

    signals = build_signals(research)
    research['signals'] = signals
    if signals:
        val = round(sum(s['status'] for s in signals) / len(signals) / 2 * 100)
        pillars = [p for p in d['pillars'] if p['name'] != 'Valuation / Momentum']
        pillars.append({'name': 'Valuation / Momentum', 'score': val})
        d['pillars'] = pillars

    research['burst'] = build_burst(research)

    available = [p for p in d['pillars'] if p['name'] in WEIGHTS]
    total_w = sum(WEIGHTS[p['name']] for p in available)
    score = round(sum(p['score'] * WEIGHTS[p['name']] for p in available) / total_w)
    d['score'] = score
    d['status'] = 'LOW' if score < 35 else 'WATCH' if score < 65 else 'HIGH' if score < 80 else 'EXTREME'

    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    entry = {'date': today, 'score': score, 'burst': research['burst']['score']}
    if not d['history'] or d['history'][-1]['date'] != today:
        d['history'].append(entry)
    else:
        d['history'][-1].update(entry)
    d['as_of'] = today
    d['version'] = 'V4'
    PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print('score', score, d['status'], '| burst', research['burst']['score'], '| signals', len(signals))


if __name__ == '__main__':
    main()
