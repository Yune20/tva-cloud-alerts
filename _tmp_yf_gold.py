import yfinance as yf

for sym in ["GC=F", "XAUUSD=X", "GLD", "IAU", "XAU=X"]:
    try:
        t = yf.Ticker(sym)
        fi = t.fast_info
        last = getattr(fi, "last_price", None)
        prev = getattr(fi, "previous_close", None)
        hist = t.history(period="5d")
        bars = len(hist) if hist is not None else 0
        last_bar = float(hist["Close"].iloc[-1]) if bars > 0 else None
        print(f"{sym:12s} fast_last={last}  prev={prev}  hist_bars={bars}  hist_last={last_bar}")
    except Exception as e:
        print(f"{sym:12s} ERR: {e}")
