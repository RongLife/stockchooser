#!/usr/bin/env python3
"""抓證交所公開資料，整理成借券／法人／營收篩選用的 data.json。

資料來源（皆為臺灣證券交易所公開資料）：
  - 每日收盤行情 MI_INDEX（成交股數、收盤價）
  - 三大法人買賣超日報 T86（投信、外資）
  - 信用額度總量管制餘額表 TWT93U（借券賣出、借券餘額、融券餘額）
  - 上市公司每月營業收入彙總表 t187ap05_L（單月、累計營收年增率）

用法： python3 fetch_twse.py [交易日數，預設 10]
"""
import json, os, sys, time, datetime, subprocess

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".twse_cache")
os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}


def get(url, cache_key=None, ttl=None):
    path = os.path.join(CACHE, cache_key) if cache_key else None
    if path and os.path.exists(path) and (ttl is None or time.time() - os.path.getmtime(path) < ttl):
        with open(path) as f:
            return json.load(f)
    for attempt in range(4):
        try:
            # 用系統 curl，避開 macOS Python 缺根憑證的問題
            raw = subprocess.run(["curl", "-s", "-m", "40", "-A", UA["User-Agent"], url],
                                 capture_output=True, check=True).stdout
            data = json.loads(raw.decode("utf-8"))
            break
        except Exception as e:  # 被限流時等久一點再試
            print("  retry", attempt + 1, e, file=sys.stderr)
            time.sleep(6 * (attempt + 1))
    else:
        raise RuntimeError("failed: " + url)
    time.sleep(3.2)  # 證交所限流，請求之間要停一下
    if path:
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False)
    return data


def num(s):
    s = str(s).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def is_stock(code):
    return len(code) == 4 and code.isdigit() and not code.startswith("0")


days = {}
d = datetime.date.today()
tries = 0
while len(days) < DAYS and tries < 40:
    ds = d.strftime("%Y%m%d")
    tries += 1
    if d.weekday() < 5:
        is_today = d == datetime.date.today()
        ttl = 1800 if is_today else None
        q = get(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ds}&type=ALLBUT0999&response=json",
                None if is_today else f"mi_{ds}.json", ttl)
        if q.get("stat") == "OK" and q.get("tables"):
            tbl = next((t for t in q["tables"] if t.get("fields") and t["fields"][0] == "證券代號" and "收盤價" in t["fields"]), None)
            if tbl:
                t86 = get(f"https://www.twse.com.tw/rwd/zh/fund/T86?date={ds}&selectType=ALLBUT0999&response=json",
                          None if is_today else f"t86_{ds}.json")
                sbl = get(f"https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U?date={ds}&response=json",
                          None if is_today else f"sbl_{ds}.json")
                ok = lambda j: j.get("stat") == "OK" and len(j.get("data") or []) >= 500  # 當天資料晚上才會補齊
                if ok(t86) and ok(sbl):
                    days[ds] = (tbl, t86, sbl)
                    print("got", ds, file=sys.stderr)
                else:
                    print("partial", ds, "skip", file=sys.stderr)
    d -= datetime.timedelta(days=1)

dates = sorted(days)
print("trading days:", dates, file=sys.stderr)

stocks = {}
for i, ds in enumerate(dates):
    tbl, t86, sbl = days[ds]
    for row in tbl["data"]:
        code = row[0].strip()
        if not is_stock(code):
            continue
        s = stocks.setdefault(code, {"code": code, "name": row[1].strip(), "series": {}})
        s["series"][ds] = {"vol": num(row[2]) or 0, "close": num(row[8])}
    f = t86["fields"]
    i_trust = f.index("投信買賣超股數")
    i_for = f.index("外陸資買賣超股數(不含外資自營商)")
    for row in t86["data"]:
        code = row[0].strip()
        if code in stocks and ds in stocks[code]["series"]:
            stocks[code]["series"][ds]["trust"] = num(row[i_trust]) or 0
            stocks[code]["series"][ds]["foreign"] = num(row[i_for]) or 0
    for row in sbl["data"]:
        code = row[0].strip()
        if code in stocks and ds in stocks[code]["series"]:
            sr = stocks[code]["series"][ds]
            sr["margin_bal"] = num(row[6]) or 0   # 融券今日餘額
            sr["sbl_sell"] = num(row[9]) or 0     # 借券當日賣出
            sr["sbl_bal"] = num(row[12]) or 0     # 借券當日餘額

rev = get("https://openapi.twse.com.tw/v1/opendata/t187ap05_L", "revenue.json", 6 * 3600)
rev_month = None
for r in rev:
    code = r["公司代號"].strip()
    if code in stocks:
        stocks[code]["industry"] = r["產業別"].strip()
        stocks[code]["rev_yoy"] = num(r["營業收入-去年同月增減(%)"])
        stocks[code]["rev_cum_yoy"] = num(r["累計營業收入-前期比較增減(%)"])
        stocks[code]["rev"] = num(r["營業收入-當月營收"])
        rev_month = r["資料年月"]

out = []
for s in stocks.values():
    ser = [dict(date=ds, **s["series"][ds]) for ds in dates if ds in s["series"]]
    if len(ser) < len(dates):
        continue
    rec = {k: v for k, v in s.items() if k != "series"}
    rec["d"] = [[x["vol"], x["close"], x.get("trust", 0), x.get("foreign", 0),
                 x.get("sbl_sell", 0), x.get("sbl_bal", 0), x.get("margin_bal", 0)] for x in ser]
    out.append(rec)

roc = lambda ym: f"{int(ym[:3]) + 1911}-{ym[3:]}" if ym else None
payload = {
    "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    "dates": dates,
    "revMonth": roc(rev_month),
    "fields": ["vol", "close", "trust", "foreign", "sblSell", "sblBal", "marginBal"],
    "stocks": out,
}
dst = os.path.join(HERE, "data.json")
with open(dst, "w") as f:
    json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
print(f"wrote {dst}: {len(out)} stocks, {len(dates)} days, revenue {payload['revMonth']}", file=sys.stderr)
