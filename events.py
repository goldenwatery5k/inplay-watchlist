"""Map SEC filings to the session they hit + event label."""
import re, pandas as pd
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
alltd = None   # set by caller: pd.DatetimeIndex of trading days

def react_date(acc):
    t = pd.Timestamp(acc).tz_convert(ET)
    d = pd.Timestamp(t.date())
    if t.hour >= 16: d = d + pd.Timedelta(days=1)          # after the bell -> next session
    k = alltd.searchsorted(d)                               # roll weekends/holidays forward
    return alltd[k] if k < len(alltd) else None

def label(forms):
    """forms: list of (form, items) -> (label, set)"""
    f = [x[0] for x in forms]; it = set()
    for x in forms: it |= set(s.strip() for s in (x[1] or "").split(",") if s.strip())
    S = set()
    if "1.03" in it: S.add("破產")
    if "3.01" in it: S.add("退市/不合規通知")
    if any(re.match(r"(424B|S-1|S-3|F-1|F-3|424H|SB-2|FWP)", x) for x in f) or "3.02" in it: S.add("發股/招股")
    if "1.01" in it or "2.01" in it or any(x in ("SC TO-T", "SC TO-I", "SC 14D9", "DEFM14A", "425", "S-4", "SC 13E3") for x in f): S.add("併購/重大協議")
    if "2.02" in it: S.add("業績")
    if "5.03" in it or "3.03" in it: S.add("章程/反向拆股")
    if any(x.startswith("SC 13D") or x.startswith("SCHEDULE 13D") for x in f): S.add("13D 大股東")
    if "5.02" in it: S.add("管理層變動")
    if "7.01" in it or "8.01" in it: S.add("PR/Reg FD")
    if "6-K" in f: S.add("外國公司 6-K")
    order = ["破產", "退市/不合規通知", "發股/招股", "併購/重大協議", "業績", "章程/反向拆股", "13D 大股東", "管理層變動", "PR/Reg FD", "外國公司 6-K"]
    for o in order:
        if o in S: return o
    return "其他申報" if f else "無 SEC 申報"

