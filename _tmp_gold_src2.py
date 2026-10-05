import httpx, json

headers = {
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}

# Test CFD + futures cho tất cả metal/energy symbols
all_syms = [
    "OANDA:XAUUSD", "OANDA:XAGUSD", "OANDA:XAUUSDT",
    "COMEX:GC1!", "COMEX:SI1!",
    "NYMEX:CL1!", "NYMEX:NG1!", "NYMEX:HO1!", "NYMEX:RB1!",
    "ICE:BZ1!", "ICE:GAS1!",
    "TVC:SPX", "TVC:NDX", "TVC:DJI", "TVC:IXIC",
    "TVC:DXY", "TVC:VIX", "TVC:HSI", "TVC:NKY",
    "TVC:US10Y", "TVC:US02Y", "TVC:US30Y",
]

for market in ["cfd", "futures", "america"]:
    url = f"https://scanner.tradingview.com/{market}/scan"
    r = httpx.post(url, json={"columns":["close","change","bid","ask"],"symbols":{"tickers":all_syms}}, headers=headers, timeout=12)
    data = r.json()
    rows = data.get("data") or []
    if rows:
        print(f"\n=== {market}: {len(rows)} hits ===")
        for row in rows:
            s = row.get("s","")
            d = row.get("d") or []
            bid = d[2] if len(d)>2 else "N/A"
            ask = d[3] if len(d)>3 else "N/A"
            print(f"  {s:20s} close={d[0]:>12}  chg={d[1]:>8}  bid={bid}  ask={ask}")
