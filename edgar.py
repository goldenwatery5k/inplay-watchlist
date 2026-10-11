"""SEC EDGAR filing index per ticker (form type + 8-K items + acceptance time). Cached in data/edgar/."""
import json, os, sys, time, threading
import requests
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "edgar"); os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": os.environ.get("SEC_UA", "personal-research inplay-study admin@example.com"), "Accept-Encoding": "gzip, deflate"}
_lock = threading.Lock(); _last = [0.0]

def get(url):
    with _lock:
        w = 0.12 - (time.time() - _last[0])
        if w > 0: time.sleep(w)
        _last[0] = time.time()
    for _ in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=30)
        except Exception:
            time.sleep(3); continue
        if r.status_code == 200: return r.json()
        if r.status_code in (429, 503): time.sleep(3)
        elif r.status_code == 404: return None
    return None

def tickers_map():
    p = os.path.join(CACHE, "_tickers.json")
    if not os.path.exists(p):
        j = get("https://www.sec.gov/files/company_tickers.json")
        json.dump(j, open(p, "w"))
    j = json.load(open(p))
    return {v["ticker"]: int(v["cik_str"]) for v in j.values()}

def filings(cik):
    p = os.path.join(CACHE, f"{cik}.json")
    if os.path.exists(p): return json.load(open(p))
    j = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    if j is None: out = []
    else:
        rec = j["filings"]["recent"]
        out = [dict(form=rec["form"][i], date=rec["filingDate"][i], acc=rec["acceptanceDateTime"][i], items=rec["items"][i])
               for i in range(len(rec["form"]))]
        # older files, only if recent list doesn't reach back to 2023-05
        if out and out[-1]["date"] > "2023-05-01":
            for f in j["filings"].get("files", []):
                jj = get("https://data.sec.gov/submissions/" + f["name"])
                if not jj: continue
                out += [dict(form=jj["form"][i], date=jj["filingDate"][i], acc=jj["acceptanceDateTime"][i], items=jj["items"][i]) for i in range(len(jj["form"]))]
    json.dump(out, open(p, "w")); return out

if __name__ == "__main__":
    import pandas as pd
    nd = pd.read_pickle(os.path.join(HERE, "out", "namedays.pkl"))
    tm = tickers_map()
    need = [(t, tm[t]) for t in sorted(nd.ticker.unique()) if t in tm]
    print(len(need), "of", nd.ticker.nunique(), "tickers have a CIK", flush=True)
    from concurrent.futures import ThreadPoolExecutor
    t0 = time.time()
    with ThreadPoolExecutor(6) as ex:
        for k, _ in enumerate(ex.map(lambda x: filings(x[1]), need), 1):
            if k % 300 == 0: print(f"  {k}/{len(need)} ({time.time()-t0:.0f}s)", flush=True)
    print("done")
