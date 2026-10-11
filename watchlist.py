"""Daily human-aided watchlist (NOT a signal generator): in-play names + EDGAR event label + daily structure, bucketed by what the study found.
python watchlist.py [--refresh]  -> out/watchlist.html + out/watchlist.json"""
import os, sys, json, html, re, numpy as np, pandas as pd
from zoneinfo import ZoneInfo
import data, inplay, edgar, events
HERE = os.path.dirname(os.path.abspath(__file__))
d = data.load(max_age_h=0 if "--refresh" in sys.argv else 12); F = inplay.build(d)
C, H, L = F["C"], F["H"], F["L"]; i = len(C) - 1; day = C.index[i]
ET = ZoneInfo("America/New_York")
events.alltd = C.index
ns = {"react_date": events.react_date, "label": events.label}

mask = F["mask"].iloc[i] & (C.iloc[i] >= 3) & (F["dvol"].iloc[i] >= 5e6)
big = (F["r_ret"].iloc[i] <= 80) | (F["r_vol"].iloc[i] <= 80)
pool = [t for t in C.columns[(mask & big).values]]
tm = edgar.tickers_map()
def fresh(t):
    if t not in tm: return []
    p = os.path.join(edgar.CACHE, f"{tm[t]}.json")
    if os.path.exists(p): os.remove(p)                     # force fresh filing list
    out = []
    for r in edgar.filings(tm[t]):
        if r["date"] < str((day - pd.Timedelta(days=5)).date()): continue
        try: dd = ns["react_date"](r["acc"])
        except Exception: continue
        if dd == day: out.append((r["form"], r["items"]))
    return out
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(6) as ex: evs = dict(zip(pool, ex.map(fresh, pool)))

rows = []
for t in pool:
    c = C[t]; cl = float(c.iloc[i])
    h20 = float(H[t].iloc[i-19:i+1].max()); h252 = float(H[t].iloc[max(0,i-251):i+1].max())
    l60 = float(L[t].iloc[i-59:i+1].min()); h60 = float(H[t].iloc[i-59:i+1].max())
    ma50 = float(c.iloc[i-49:i+1].mean()); ma20 = float(c.iloc[i-19:i+1].mean())
    ev = ns["label"](evs[t]) if evs[t] else "無 SEC 申報"
    rows.append(dict(ticker=t, name=d["names"].get(t, ""), close=round(cl, 2), ret=float(F["ret"][t].iloc[i]) * 100, gap=float(F["gap"][t].iloc[i]) * 100,
                     rvol=float(F["rvol"][t].iloc[i]), dvol_m=float(F["dvol"][t].iloc[i]) / 1e6, ext20=(cl / ma20 - 1) * 100,
                     from50=(cl / ma50 - 1) * 100, off_hi=(cl / h252 - 1) * 100, pos60=(cl - l60) / max(h60 - l60, 1e-9) * 100,
                     pull20=(cl / h20 - 1) * 100, event=ev, rank=int(min(F["r_ret"][t].iloc[i], F["r_vol"][t].iloc[i]))))
df = pd.DataFrame(rows)
BAD = {"發股/招股", "章程/反向拆股", "退市/不合規通知", "破產"}
def bucket(r):
    if r.event in BAD and r.ret >= 8: return "C 避開 / 反向觀察"
    if r.ret <= -10 and r.dvol_m >= 20 and r.event not in {"破產", "退市/不合規通知"}: return "B 超跌反彈觀察"
    if r.ret >= 5 and r.event not in BAD and r.from50 > 0 and r.off_hi >= -20 and r.ext20 <= 40 and r.dvol_m >= 20: return "A 強勢 + 結構完整(等回調/續勢)"
    return "D 其他 in-play(只睇)"
df["bucket"] = df.apply(bucket, axis=1)
df = df.sort_values(["bucket", "rank"])
df.to_json(os.path.join(HERE, "out", "watchlist.json"), orient="records", force_ascii=False)
NOTE = {"A": "研究結果:當日大升之後「收市追入」平均 5 日係負(2024 年例外)。呢組唔係追入名單,係「隔日等回調/確認」嘅備選。",
        "B": "研究結果:當日跌 ≥10% 之後 1–5 日平均小幅反彈(+0.3% 至 +3%),但未計止蝕/成本,破產/退市通知已剔除。",
        "C": "研究結果:發股/反向拆股/退市通知 + 大升,之後 1–5 日平均明顯回吐(−2% 至 −8%)。避開做多;沽空要睇借貨同 halt 風險。",
        "D": "未達上面條件嘅 in-play 名單,只作背景。"}
def tbl(g):
    return "<table><tr><th>股票</th><th>事件</th><th class=r>收市</th><th class=r>升跌</th><th class=r>跳空</th><th class=r>量比</th><th class=r>成交額</th><th class=r>離20日線</th><th class=r>離50日線</th><th class=r>離52週高</th><th class=r>近60日位置</th></tr>" + "".join(
        f"<tr><td><b>{r.ticker}</b><div class=n>{html.escape(str(r['name'])[:34])}</div></td><td>{r.event}</td><td class=r>{r.close}</td><td class=r>{r.ret:+.1f}%</td><td class=r>{r.gap:+.1f}%</td>"
        f"<td class=r>{r.rvol:.1f}×</td><td class=r>${r.dvol_m:,.0f}M</td><td class=r>{r.ext20:+.0f}%</td><td class=r>{r.from50:+.0f}%</td><td class=r>{r.off_hi:+.0f}%</td><td class=r>{r.pos60:.0f}%</td></tr>"
        for _, r in g.iterrows()) + "</table>"
body = "".join(f"<h3>{b} <span class=n>({len(g)})</span></h3><p class=n>{NOTE[b[0]]}</p>{tbl(g)}" for b, g in df.groupby("bucket"))
open(os.path.join(HERE, "out", "watchlist.html"), "w").write(f"""<meta charset=utf-8><title>每日睇盤清單</title><style>
body{{font:14px -apple-system,system-ui,'PingFang HK',sans-serif;margin:24px;max-width:1100px;color:#1c2420}}table{{border-collapse:collapse;width:100%}}
td,th{{padding:6px 8px;border-bottom:1px solid #ddd;text-align:left}}th{{font-size:12px;color:#666}}.r{{text-align:right;font-variant-numeric:tabular-nums}}.n{{font-size:12px;color:#777}}
.box{{background:#f3f6f4;padding:12px 16px;border-radius:8px}}</style><h2>每日睇盤清單({day.date()})</h2>
<div class=box>人手輔助清單,唔係買賣信號。事件標籤來自 SEC EDGAR 當日申報(收市後申報算次日);日線資料,無日內結構。回測顯示「新聞 gap 追入」扣成本後冇穩定 edge,故此清單只用嚟縮窄要睇嘅股票。</div>{body}""")
print(day.date(), len(df), df.bucket.value_counts().to_dict())
print(df[df.bucket.str.startswith(("A","B","C"))][["ticker","event","close","ret","ext20","from50","off_hi","bucket"]].round(1).to_string(index=False))
