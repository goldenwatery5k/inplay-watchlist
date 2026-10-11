"""Daily 'in-play' scanner (Lance Breitstein-style catch-alls: biggest % movers + biggest volume vs ADV, plus gap / extension tags).
Run:  python inplay.py [YYYY-MM-DD]   -> prints top lists, writes out/inplay.json"""
import json, os, sys
import numpy as np, pandas as pd
import data

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
MIN_PRICE, MIN_VOL, MIN_DVOL = 0.5, 200_000, 1_000_000          # micro-caps allowed, but must trade
LARGE_N = 500                                # "large/liquid" subset = top-N by $ volume that day

def build(d):
    px = d["px"]
    idx = px["SPY"].index
    def mat(col):
        return pd.DataFrame({t: x[col] for t, x in px.items()}).reindex(idx)
    C, O, H, L, V = (mat(c) for c in ("Close", "Open", "High", "Low", "Volume"))
    prev = C.shift(1)
    adv = V.shift(1).rolling(50, min_periods=30).mean()
    F = dict(C=C, O=O, H=H, L=L, V=V,
             ret=(C / prev - 1).fillna(C / O - 1), gap=(O / prev - 1).fillna(0), rvol=V / adv, dvol=C * V,
             ext20=C / C.rolling(20).mean() - 1, rng=(H - L) / prev)
    # new listings (IPO day / first weeks): no ADV yet -> keep them, rvol NaN, ranked by |ret| / $volume only
    first = C.notna().cumsum() <= 30
    # SPAC shells: ~$10, almost no daily movement
    spac = ((C >= 9.0) & (C <= 11.5)) & ((C / prev - 1).rolling(20, min_periods=10).std() < 0.01)
    F["mask"] = (C >= MIN_PRICE) & (V >= MIN_VOL) & (C * V >= MIN_DVOL) & (adv.notna() | first) & ~spac
    m = F["mask"]
    F["r_ret"] = F["ret"].abs().where(m).rank(axis=1, ascending=False)        # 1 = biggest mover
    F["r_vol"] = F["rvol"].where(m).rank(axis=1, ascending=False)             # 1 = highest rvol
    F["n"] = m.sum(axis=1)
    big = F["dvol"].where(m).rank(axis=1, ascending=False) <= LARGE_N
    F["large"] = big
    F["r_ret_L"] = F["ret"].abs().where(big).rank(axis=1, ascending=False)
    F["r_vol_L"] = F["rvol"].where(big).rank(axis=1, ascending=False)
    F["nL"] = big.sum(axis=1)
    return F

def scan(F, names, date=None, top=40):
    i = len(F["C"]) - 1 if date is None else int(F["C"].index.searchsorted(pd.Timestamp(date)))
    day = F["C"].index[i]
    rows = []
    cand = set(F["r_ret"].iloc[i].nsmallest(top).index) | set(F["r_vol"].iloc[i].nsmallest(top).index)
    for t in cand:
        rr, rv = F["r_ret"].at[day, t], F["r_vol"].at[day, t]
        tags = []
        if rr <= top: tags.append("大升跌")
        if rv <= top: tags.append("量爆")
        g = F["gap"].at[day, t]
        if abs(g) >= 0.05: tags.append("跳空" + ("上" if g > 0 else "下"))
        e = F["ext20"].at[day, t]
        if e >= 0.25: tags.append("極端延伸")
        if e <= -0.20: tags.append("恐慌下破")
        if F["H"].iloc[:i + 1][t].tail(252).max() <= F["H"].at[day, t] * 1.0001: tags.append("52週新高")
        rows.append(dict(ticker=t, name=names.get(t, ""), close=round(float(F["C"].at[day, t]), 2),
                         ret=round(float(F["ret"].at[day, t]) * 100, 1), gap=round(float(g) * 100, 1),
                         rvol=round(float(F["rvol"].at[day, t]), 1), dvol_m=round(float(F["dvol"].at[day, t]) / 1e6, 1),
                         ext20=round(float(e) * 100, 0), rank_ret=int(rr), rank_vol=int(rv), tags=tags,
                         score=float(min(rr, rv))))
    df = pd.DataFrame(rows).sort_values("score")
    return str(day.date()), int(F["n"].iloc[i]), df

if __name__ == "__main__":
    d = data.load()
    F = build(d)
    day, n, df = scan(F, d["names"], sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"{day}: universe {n} stocks; top in-play")
    pd.set_option("display.width", 200, "display.max_colwidth", 30)
    print(df.head(40).to_string(index=False))
    df.to_json(os.path.join(OUT, "inplay.json"), orient="records", force_ascii=False)
