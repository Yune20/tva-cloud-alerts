import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}

# Test scanner forex cho vàng spot
gold_symbols = [
    "OANDA:XAUUSD", "TVC:XAUUSD", "FX:XAUUSD", "FOREXCOM:XAUUSD",
    "OANDA:XAUUSDT", "TVC:GOLD", "TVC:XAU",
]

for market in ["forex", "crypto", "america"]:
    url = f"https://scanner.tradingview.com/{market}/scan"
    payload = {
        "columns": ["close", "change", "bid", "ask", "high", "low", "open", "prev_close_price"],
        "symbols": {"tickers": gold_symbols},
        "options": {"lang": "en"},
    }
    try:
        r = httpx.post(url, json=payload, headers=HEADERS, timeout=12)
        data = r.json()
        rows = data.get("data") or []
        if rows:
            print(f"\n=== {market} ({len(rows)} hits) ===")
            for row in rows:
                s = row.get("s", "")
                d = row.get("d") or []
                print(f"  {s:22s} close={d[0] if d else 'N/A'}  chg={d[1] if len(d)>1 else 'N/A'}  bid={d[2] if len(d)>2 else 'N/A'}  ask={d[3] if len(d)>3 else 'N/A'}")
    except Exception as e:
        print(f"{market}: ERR {e}")
