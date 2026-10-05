"""
Realtime quote engine.

Pipelines
  • crypto  → Binance REST ticker/24hr (1 request cho toàn bộ, ~1.5s)
  • forex + stocks → TradingView scanner (forex / america)
  • metals (spot) → TradingView CFD scanner (OANDA:XAUUSD, TVC:GOLD, ...)
  • metals (futures) + energy → TradingView futures scanner (COMEX:GC1!, NYMEX:CL1!, ...)
  • yfinance fallback cho mã scanner bỏ sót

All updates land in a shared in-memory state dict; clients pull snapshots over
/ws/quotes (client-driven loop). A SQL kv-cache persists the latest quote so a
reboot paints instantly instead of waiting for the first poll.
"""
import json
import threading
import time

import httpx

import config as cfg
from core.ohlcv_cache import get_cache

SCANNER_URLS = {
    "forex": "https://scanner.tradingview.com/forex/scan",
    "crypto": "https://scanner.tradingview.com/crypto/scan",
    "america": "https://scanner.tradingview.com/america/scan",
    "cfd": "https://scanner.tradingview.com/cfd/scan",
    "futures": "https://scanner.tradingview.com/futures/scan",
    "europe": "https://scanner.tradingview.com/europe/scan",
    "asia": "https://scanner.tradingview.com/asia/scan",
    "vietnam": "https://scanner.tradingview.com/vietnam/scan",
}

CAT_TO_MARKETS = {
    "forex": ["forex"],
    "stock": ["america"],
    "metal": ["cfd", "futures"],
    "energy": ["futures"],
    "index": ["cfd", "america"],
    "vnstock": ["vietnam"],
}
SCANNER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}
COLUMNS = ["close", "change"]
CFD_COLUMNS = ["close", "change", "bid", "ask"]

SCANNER_INTERVAL = 6.0
BINANCE_INTERVAL = 1.5
BINANCE_24HR_URL = "https://api.binance.com/api/v3/ticker/24hr"
FALLBACK_STALE_AFTER = 25.0


# Symbols that stay on the board by default ("focus mode").
FOCUS_SYMS = {
    "OANDA:XAUUSD", "OANDA:XAGUSD", "OANDA:XAUUSDT", "COMEX:GC1!",
    "BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT", "BINANCE:BNBUSDT",
    "BINANCE:XRPUSDT", "BINANCE:ADAUSDT",
    "FX:EURUSD", "FX:GBPUSD", "FX:USDJPY", "FX:AUDUSD",
    "NYMEX:CL1!", "ICE:BZ1!", "NYMEX:NG1!",
    "TVC:NDX", "TVC:SPX", "TVC:IXIC", "TVC:DJI", "TVC:HSI", "TVC:NKY",
    "NASDAQ:AAPL", "NASDAQ:MSFT", "NASDAQ:NVDA", "NASDAQ:GOOGL",
    "NASDAQ:AMZN", "NASDAQ:META", "NASDAQ:TSLA",
}

def build_groups() -> list:
    """watched groups derived from cfg.WATCHLIST (order preserved per cat)."""
    order = ["metal", "crypto", "forex", "energy", "index", "stock", "vnstock"]
    labels = {
        "metal": "KIM LOẠI", "crypto": "CRYPTO", "forex": "NGOẠI HỐI",
        "energy": "NĂNG LƯỢNG", "index": "CHỈ SỐ", "stock": "CỔ PHIẾU US",
        "vnstock": "CP VIỆT NAM",
    }
    icons = {"metal": "🥇", "crypto": "₿", "forex": "💱", "energy": "🛢", "index": "📊", "stock": "💹", "vnstock": "🇻🇳"}
    groups = []
    for c in order:
        items = [i for i in cfg.WATCHLIST if i.get("cat") == c]
        if not items:
            continue
        groups.append({
            "id": c,
            "label": labels.get(c, c),
            "icon": icons.get(c, ""),
            "focus": [it["tv"] for it in items if it["tv"] in FOCUS_SYMS],
            "items": [{"sym": it["tv"], "name": it.get("name", it["tv"]), "icon": it.get("icon", "")} for it in items],
        })
    return groups


def yf_of(tv: str) -> str:
    for item in cfg.WATCHLIST:
        if item["tv"] == tv:
            return item["yf"]
    return tv


class RealtimeEngine:
    def __init__(self):
        self.groups = build_groups()
        self.all_items = [g for group in self.groups for g in group["items"]]
        self._cat_map = {it["sym"]: group["id"] for group in self.groups for it in group["items"]}
        self.state = {}           # sym -> quote dict
        self._lock = threading.Lock()
        self._dirty = threading.Event()
        self._http = httpx.Client(timeout=12, headers=SCANNER_HEADERS)
        self._binance_http = httpx.Client(timeout=12, headers={"User-Agent": SCANNER_HEADERS["User-Agent"]})
        self._seed_from_cache()
        self._stop = threading.Event()

    # ── lifecycle ───────────────────────────────────────────────
    def start(self):
        for fn in (self._binance_loop, self._scanner_loop):
            t = threading.Thread(target=fn, daemon=True)
            t.start()

    def stop(self):
        self._stop.set()

    # ── state helpers ───────────────────────────────────────────
    def _seed_from_cache(self):
        try:
            cache = get_cache()
            for it in self.all_items:
                q = cache.get_kv("quote:" + yf_of(it["sym"]), max_age=3600)
                if q and q.get("price"):
                    self.state[it["sym"]] = {
                        "sym": it["sym"], "name": it["name"], "cat": self._cat(it["sym"]),
                        "icon": it["icon"], "price": float(q["price"]),
                        "chg": float(q.get("change_pct") or 0),
                        "ts": time.time(), "src": "cache", "live": True,
                    }
        except Exception:
            pass

    def _cat(self, sym: str) -> str:
        return self._cat_map.get(sym, "")

    def _update(self, sym, price, chg, src):
        if price is None or price <= 0:
            return
        item = next((i for g in self.groups for i in g["items"] if i["sym"] == sym), None)
        if item is None:
            return
        prev = self.state.get(sym, {})
        prev_price = prev.get("price")
        if chg is None:
            chg = ((price / prev_price) - 1) * 100 if prev_price else 0.0
        trend = "up" if chg > 0.03 else "down" if chg < -0.03 else "flat"
        with self._lock:
            self.state[sym] = {
                "sym": sym, "name": item["name"], "cat": self._cat(sym),
                "icon": item["icon"], "price": round(float(price), 6),
                "chg": round(float(chg), 2), "trend": trend,
                "ts": time.time(), "src": src, "live": True,
            }
        self._dirty.set()
        self._persist(sym)

    def _persist(self, sym):
        q = self.state.get(sym)
        if not q:
            return
        try:
            get_cache().put_kv("quote:" + yf_of(sym), {
                "price": q["price"], "change_pct": q["chg"],
            })
        except Exception:
            pass

    def snapshot(self) -> list:
        with self._lock:
            return [dict(v) for v in self.state.values()]

    # ── Binance REST (crypto) ──────────────────────────────────
    def _binance_loop(self):
        pairs = [
            it["sym"][8:] for g in self.groups if g["id"] == "crypto" for it in g["items"]
        ]
        params = {"symbols": json.dumps(pairs, separators=(",", ":"))}
        while not self._stop.is_set():
            t0 = time.time()
            try:
                resp = self._binance_http.get(BINANCE_24HR_URL, params=params, timeout=12)
                rows = resp.json()
                if not isinstance(rows, list):
                    continue
                for x in rows:
                    tv = "BINANCE:" + (x.get("symbol") or "").upper()
                    p = x.get("lastPrice")
                    c = x.get("priceChangePercent")
                    if tv in self._cat_map and p:
                        try:
                            self._update(tv, float(p), float(c), "binance")
                        except (TypeError, ValueError):
                            pass
            except Exception:
                pass
            elapsed = time.time() - t0
            time.sleep(max(0.5, BINANCE_INTERVAL - elapsed))

    # ── TradingView scanner (all markets) ──────────────────────
    def _scanner_loop(self):
        while not self._stop.is_set():
            t0 = time.time()
            try:
                for market in ("forex", "america", "cfd", "futures"):
                    self._scan_market(market)
                self._fallback_stale()
            except Exception:
                pass
            elapsed = time.time() - t0
            time.sleep(max(0.5, SCANNER_INTERVAL - elapsed))

    def _scan_market(self, market: str) -> None:
        tickers = [
            it["sym"] for g in self.groups
            if market in CAT_TO_MARKETS.get(g["id"], [])
            for it in g["items"]
        ]
        if not tickers:
            return
        cols = CFD_COLUMNS if market == "cfd" else COLUMNS
        try:
            resp = self._http.post(
                SCANNER_URLS[market],
                json={"columns": cols, "symbols": {"tickers": tickers},
                      "options": {"lang": "en", "range": ["1M"]},
                      "markets": list(SCANNER_URLS.keys())},
            )
            data = resp.json()
        except Exception:
            return
        for row in (data.get("data") or []):
            s = row.get("s")
            d = row.get("d") or []
            if s and len(d) >= 2:
                self._update(s, d[0], d[1], "scanner")
                if market == "cfd" and len(d) >= 4:
                    bid, ask = d[2], d[3]
                    if bid and ask:
                        with self._lock:
                            if s in self.state:
                                self.state[s]["bid"] = round(float(bid), 6)
                                self.state[s]["ask"] = round(float(ask), 6)

    def _fallback_stale(self):
        """Nếu scanner bỏ sót mã → lấy giá bằng yfinance.
        
        Trigger khi:
          1. ts quá cũ (>FALLBACK_STALE_AFTER) — giá stale
          2. src=="cache" — chưa có live source nào cập nhật
        """
        import concurrent.futures as futures
        now = time.time()
        stale = []
        for g in self.groups:
            for it in g["items"]:
                q = self.state.get(it["sym"])
                if q is None:
                    stale.append(it["sym"])
                    continue
                age = now - q.get("ts", 0)
                if age > FALLBACK_STALE_AFTER or q.get("src") == "cache":
                    stale.append(it["sym"])
        if not stale:
            return
        with futures.ThreadPoolExecutor(max_workers=min(len(stale), 4)) as ex:
            list(ex.map(self._yf_one, stale))

    # ── yfinance fallback ─────────────────────────────────────
    def _yf_one(self, sym: str):
        import yfinance as yf
        yf_sym = yf_of(sym)
        try:
            ticker = yf.Ticker(yf_sym)
            info = ticker.fast_info
            price = float(info.last_price) if hasattr(info, "last_price") else None
            prev = float(info.previous_close) if hasattr(info, "previous_close") else None
        except Exception:
            return
        if price is None or price <= 0:
            return
        chg = ((price - prev) / prev * 100) if prev else None
        self._update(sym, price, chg, "yfinance")