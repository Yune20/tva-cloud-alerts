"""Watchlist: fetch live data for multiple symbols in parallel."""
import concurrent.futures as futures
import time
from typing import Dict, List

import config as cfg

from core.ohlcv_cache import get_cache

_YF_CACHE: Dict = {}
_CACHE_TTL = 30.0


def fetch_single(item: dict) -> dict:
    """Fetch price + change for one symbol. Returns dict or fallback."""
    try:
        import yfinance as yf
        now = time.time()
        cache_key = item["yf"]

        # Persistent SQL quote cache — reloads don't hammer yfinance (429).
        cached = get_cache().get_kv("quote:" + cache_key, max_age=_CACHE_TTL)
        if cached is not None:
            return cached

        hit = _YF_CACHE.get(cache_key)
        if hit and (now - hit["ts"]) < _CACHE_TTL:
            return hit["data"]

        ticker = yf.Ticker(item["yf"])
        info = ticker.fast_info
        price = float(info.last_price) if hasattr(info, "last_price") else None
        prev = float(info.previous_close) if hasattr(info, "previous_close") else None

        if price is None:
            hist = ticker.history(period="2d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price

        change_pct = 0.0
        if price and prev:
            change_pct = (price - prev) / prev * 100

        trend = "up" if change_pct > 0.05 else "down" if change_pct < -0.05 else "flat"
        result = {
            "symbol": item["tv"].split(":")[-1],
            "name": item["name"],
            "icon": item["icon"],
            "cat": item["cat"],
            "price": price,
            "change_pct": round(change_pct, 2),
            "trend": trend,
            "yf_symbol": item["yf"],
        }
        _YF_CACHE[cache_key] = {"data": result, "ts": now}
        get_cache().put_kv("quote:" + cache_key, result)
        return result
    except Exception:
        return {
            "symbol": item["tv"].split(":")[-1],
            "name": item["name"],
            "icon": item["icon"],
            "cat": item["cat"],
            "price": None,
            "change_pct": 0,
            "trend": "flat",
            "yf_symbol": item["yf"],
        }


def fetch_watchlist(symbols: list = None) -> List[dict]:
    """Fetch data for all watchlist symbols in parallel."""
    items = symbols or cfg.WATCHLIST
    with futures.ThreadPoolExecutor(max_workers=min(len(items), 8)) as ex:
        results = list(ex.map(fetch_single, items))
    return results


def compute_market_breadth(watchlist_data: List[dict]) -> dict:
    """Compute overall market bullish/bearish percentage."""
    valid = [d for d in watchlist_data if d.get("price") is not None]
    if not valid:
        return {"direction": "NEUTRAL", "bullish_pct": 50, "trend_strength": 50}

    bullish = sum(1 for d in valid if d["change_pct"] > 0)
    total = len(valid)
    bullish_pct = int(bullish / total * 100) if total else 50

    if bullish_pct >= 60:
        direction = "BULLISH"
    elif bullish_pct <= 40:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    strength = min(100, max(0, bullish_pct + (10 if bullish_pct > 50 else -10)))
    return {
        "direction": direction,
        "bullish_pct": bullish_pct,
        "trend_strength": strength,
        "total": total,
        "bullish": bullish,
        "bearish": total - bullish,
    }
