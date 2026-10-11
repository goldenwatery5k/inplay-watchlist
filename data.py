"""Download daily OHLCV for every currently-listed US common stock (no price/volume filter: micro-caps matter here)."""
import io, os, re, sys, time
import pandas as pd, requests, yfinance as yf
HERE = os.path.dirname(os.path.abspath(__file__))
PKL = os.path.join(HERE, "prices.pkl")
H = {"User-Agent": "Mozilla/5.0"}

def listed_us():
    bad = re.compile(r"warrant|right|unit|preferred|note|debenture|trust|fund|etf|acquisition|depositary receipt|%", re.I)
    out = {}
    for url, sym in (("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", "Symbol"),
                     ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", "ACT Symbol")):
        df = pd.read_csv(io.StringIO(requests.get(url, headers=H, timeout=30).text), sep="|", dtype=str)
        df = df[df[sym].notna() & ~df[sym].str.contains("File Creation", na=False)]
        df = df[(df["ETF"] != "Y") & (df["Test Issue"] != "Y")]
        for t, nm in zip(df[sym], df["Security Name"]):
            if re.fullmatch(r"[A-Z]{1,5}", t) and not bad.search(nm or ""):
                out[t] = re.split(r" - | Common Stock| Ordinary Shares| Class [A-C]", nm or "")[0].strip()
    return out

def load(start=os.environ.get("INPLAY_START", "2023-05-01"), max_age_h=12):
    if os.path.exists(PKL) and time.time() - os.path.getmtime(PKL) < max_age_h * 3600:
        return pd.read_pickle(PKL)
    names = listed_us()
    tick = sorted(set(names) | {"SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA"})
    print(f"downloading {len(tick)} tickers from {start}", flush=True)
    out = {}
    n = 100
    for i in range(0, len(tick), n):
        ch = tick[i:i + n]
        try:
            df = yf.download(ch, start=start, interval="1d", auto_adjust=False, progress=False, group_by="ticker", threads=True)
        except Exception as e:
            print("chunk failed", e); continue
        for t in ch:
            try:
                d = df[t].dropna(subset=["Close"])
                if len(d) > 60:
                    out[t] = d[["Open", "High", "Low", "Close", "Volume"]].astype("float32")
            except Exception:
                pass
        if (i // n) % 10 == 0:
            print(f"  {min(i+n,len(tick))}/{len(tick)} ({len(out)} ok)", flush=True)
    pd.to_pickle({"px": out, "names": names}, PKL)
    return {"px": out, "names": names}

if __name__ == "__main__":
    d = load(max_age_h=0 if "--refresh" in sys.argv else 12)
    print(len(d["px"]), "series")
