"""Recompute signal lights, the Bubble Signals pillar, the composite score and the burst index.

Every scored light uses a threshold from the literature or from the series' own history
(research document, section 11). Indicators without evidence of crash-predictive power, or
without a history to calibrate against, are shown as observations and are not scored.

Groups and weights inside the Bubble Signals pillar:
  price run-up / explosiveness 35%, credit and leverage 30%, investment and issuance 20%,
  valuation 15%.
"""
import datetime
import json
from pathlib import Path

import numpy as np

PATH = Path('data/scoreboard.json')

WEIGHTS = {'AI Demand': .15, 'CapEx Intensity': .20, 'FCF Conversion': .20,
           'Credit / Leverage': .20, 'Profitability': .10, 'Bubble Signals': .15}
GROUPS = {
    'price': ('價格急漲與爆炸性', .35),
    'credit': ('信用與槓桿', .30),
    'investment': ('投資熱潮與發行', .20),
    'valuation': ('估值', .15),
}
CRASH = {'sox_drawdown': ('費城半導體指數', 40), 'twii_drawdown': ('台股加權指數', 20)}
JST_TURN = 15  # JST: a decline of 15% or more marks a bubble as having turned


def light(value, warn, hot):
    return 2 if value >= hot else 1 if value >= warn else 0


def build_signals(d):
    R = d.get('research', {})
    A = R.get('auto', {})                 # market layer (update_market.py)
    I = R.get('indicators_auto', {})      # research layer (research_indicators.py)
    M = R.get('manual', {})               # hand-verified, sourced inputs
    out = []

    def add(sid, group, name, value, warn, hot, unit, asof, basis, source, extra=None):
        if value is None:
            return
        s = {'id': sid, 'group': group, 'name': name, 'value': value, 'warn': warn, 'hot': hot,
             'unit': unit, 'asof': asof, 'basis': basis, 'source': source,
             'status': light(value, warn, hot)}
        if extra:
            s.update(extra)
        out.append(s)

    add('gsy_sox', 'price', '費城半導體兩年報酬（扣 S&P 500）', A.get('sox_2y_excess_pct'), 100, 150, '%',
        (A.get('sox_drawdown') or {}).get('last_date'),
        'GSY (2019)：≥100% 時兩年內崩跌機率 53%，≥150% 時 80%', 'Yahoo Finance via yfinance（自動）')
    for key, sid, name in [('psy_sp500_pd', 'psy_sp500', 'S&P 500 價格／股利比爆炸性（BSADF）'),
                           ('psy_sox_rel', 'psy_sox', '費城半導體相對 S&P 500 爆炸性（BSADF）')]:
        p = I.get(key)
        if p:
            add(sid, 'price', name, p['stat'], p['cv90'], p['cv95'], '', p['last_date'],
                'PSY (2015)：超過 90%／95% 蒙地卡羅臨界值', p['source'],
                {'explosive_since': p.get('explosive_since')})

    g = I.get('credit_gap_us')
    if g:
        add('credit_gap', 'credit', '美國私部門信用缺口（占 GDP，百分點）', g['value'], 2, 10, 'pp', g['asof'],
            'Basel III 逆循環緩衝區間：2／10 個百分點', g['source'])
    m = I.get('margin_yoy_us')
    if m:
        add('margin_us', 'credit', '美國保證金融資年增率', m['value'], m['p80'], m['p95'], '%', m['asof'],
            f"{m['since'][:4]} 年以來第 80／95 百分位（目前第 {m['pct']} 百分位）", m['source'])

    c = I.get('cape')
    if c:
        add('cape', 'valuation', 'S&P 500 Shiller CAPE', c['value'], c['p80'], c['p95'], '倍', c['asof'],
            f"{c['since'][:4]} 年以來第 80／95 百分位（目前第 {c['pct_full']}，1990 年以來第 {c['pct_1990']}）", c['source'])
    e = I.get('equity_gap')
    if e:
        add('equity_gap', 'valuation', '實質股價缺口（S&P 500 相對趨勢）', e['value'], 40, 60, '%', e['asof'],
            'Borio–Lowe：60%（與 4 個百分點信用缺口並用）；40% 為自訂中間值', e['source'])

    ipo = M.get('ipo_first_day')
    if ipo:
        hist = [v for _, v in ipo['history']]
        p80, p95 = round(float(np.percentile(hist, 80)), 1), round(float(np.percentile(hist, 95)), 1)
        add('ipo', 'investment', '美國 IPO 平均首日報酬（年）', ipo['value'], p80, p95, '%', ipo['asof'],
            f"Ritter 1980 年以來第 80／95 百分位；Baker–Wurgler、GSY：發行熱度預示低報酬", ipo['source'])
    cg = M.get('capex_gdp')
    if cg:
        add('capex_gdp', 'investment', '雲端業者資本支出占美國 GDP', cg['value'], cg['warn'], cg['hot'], '%', cg['asof'],
            '歷史類比：2000 年電信投資高點 1.2%；警戒 0.9% 為自訂', cg['source'])

    order = {k: i for i, k in enumerate(GROUPS)}
    out.sort(key=lambda s: (order[s['group']], -s['status']))
    return out


def group_scores(signals):
    res = []
    for key, (name, w) in GROUPS.items():
        sig = [s for s in signals if s['group'] == key]
        if sig:
            res.append({'id': key, 'name': name, 'weight': w, 'n': len(sig),
                        'score': round(sum(s['status'] for s in sig) / len(sig) / 2 * 100)})
    return res


def build_burst(research):
    auto = research.get('auto', {})
    parts = []
    for key, (name, crash) in CRASH.items():
        dd = auto.get(key)
        if not dd:
            continue
        parts.append({'id': key, 'name': name, 'dd_pct': dd['dd_pct'], 'crash_pct': crash,
                      'peak': dd['peak'], 'peak_date': dd['peak_date'], 'last': dd['last'],
                      'last_date': dd['last_date'], 'jst_turned': dd['dd_pct'] >= JST_TURN,
                      'progress': round(min(1, max(0, dd['dd_pct'] / crash)) * 100)})
    score = round(sum(p['progress'] for p in parts) / len(parts)) if parts else None
    psy = (research.get('indicators_auto', {}).get('psy_sox_rel') or {}).get('last_episode')
    return {'score': score, 'parts': parts, 'jst_turn_pct': JST_TURN, 'psy_sox_episode': psy}


def main():
    d = json.loads(PATH.read_text(encoding='utf-8'))
    research = d.setdefault('research', {})

    signals = build_signals(d)
    groups = group_scores(signals)
    research['signals'] = signals
    research['groups'] = groups
    I = research.get('indicators_auto', {})
    gap, eq = (I.get('credit_gap_us') or {}).get('value'), (I.get('equity_gap') or {}).get('value')
    research['borio_lowe_joint'] = None if gap is None or eq is None else bool(gap >= 4 and eq >= 60)

    pillars = [p for p in d['pillars'] if p['name'] not in ('Valuation / Momentum', 'Bubble Signals')]
    if groups:
        total = sum(g['weight'] for g in groups)
        pillars.append({'name': 'Bubble Signals', 'score': round(sum(g['score'] * g['weight'] for g in groups) / total)})
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
    d['version'] = 'V4.1'
    PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print('score', score, d['status'], '| burst', research['burst']['score'],
          '| groups', [(g['id'], g['score']) for g in groups])


if __name__ == '__main__':
    main()
