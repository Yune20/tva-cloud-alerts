import httpx

# 1. Thử TradingView symbol info endpoint
headers = {
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}

# 2. Thử OANDA v20 free demo (không cần API key cho pricing endpoint?)
oanda_urls = [
    "https://api-fxpractice.oanda.com/v3/accounts/101-004-1234567-001/pricing?instruments=XAU_USD",
    "https://api-fxpractice.oanda.com/v3/accounts/pricing?instruments=XAU_USD",
]

# 3. Thử TradingView "mini chart" data endpoint (widget data)
tv_urls = [
    "https://symbol-search.tradingview.com/symbol_search/v3/?text=XAUUSD&type=exchange",
    "https://scanner.tradingview.com/forex/scan",
]

for url in oanda_urls:
    try:
        r = httpx.get(url, timeout=10, headers={"Authorization": "Bearer test"})
        print(f"OANDA {url.split('accounts/')[1][:20]}... -> {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"OANDA ERR: {e}")

# Thử TradingView mini chart widget
for url in tv_urls:
    try:
        if "scan" in url:
            r = httpx.post(url, json={"columns":["close","change"],"symbols":{"tickers":["OANDA:XAUUSD","TVC:XAUUSD"]}}, headers=headers, timeout=10)
        else:
            r = httpx.get(url, headers=headers, timeout=10)
        print(f"TV {url.split('/')[-1]} -> {r.status_code} {r.text[:300]}")
    except Exception as e:
        print(f"TV ERR: {e}")
