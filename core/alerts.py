"""
Auto-alert engine: candlestick patterns, reversal signals, entry signals.
Scans all watchlist symbols and returns actionable alerts sorted by strength.
"""
import time
import math
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

import config as cfg
from core.ohlcv_cache import OHLCVCache


# ── Helpers ──────────────────────────────────────────────────────
def _safe(v):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    return float(v)


def _body(o, c):
    return abs(c - o)


def _range(h, l):
    return h - l if h > l else 1e-12


def _is_bullish(o, c):
    return c > o


def _is_bearish(o, c):
    return o > c


# ── Candlestick Patterns ─────────────────────────────────────────
def detect_candlestick_patterns(df: pd.DataFrame) -> List[Dict]:
    """Detect basic Japanese candlestick patterns on last 5 bars."""
    if df is None or len(df) < 5:
        return []
    alerts = []
    bars = []
    for i in range(max(0, len(df) - 5), len(df)):
        row = df.iloc[i]
        bars.append({
            "o": float(row["open"]), "h": float(row["high"]),
            "l": float(row["low"]), "c": float(row["close"]),
        })
    last = bars[-1]
    prev = bars[-2] if len(bars) >= 2 else None
    prev2 = bars[-3] if len(bars) >= 3 else None

    # ── Doji ──
    body = _body(last["o"], last["c"])
    rng = _range(last["h"], last["l"])
    if body < rng * 0.1 and rng > 0:
        alerts.append({"pattern": "Doji", "type": "reversal", "direction": "NEUTRAL",
                        "strength": 0.5, "desc": "Nến Doji — indecision, chờ xác nhận"})

    # ── Hammer (bullish reversal) ──
    if prev and _is_bearish(prev["o"], prev["c"]):
        lower_wick = min(last["o"], last["c"]) - last["l"]
        upper_wick = last["h"] - max(last["o"], last["c"])
        body_val = _body(last["o"], last["c"])
        if lower_wick > body_val * 2 and upper_wick < body_val * 0.3 and body_val > 0:
            alerts.append({"pattern": "Hammer", "type": "reversal", "direction": "BULLISH",
                            "strength": 0.7, "desc": "Hammer — đảo chiều tăng sau downtrend"})

    # ── Inverted Hammer / Shooting Star ──
    if prev and _is_bearish(prev["o"], prev["c"]):
        upper_wick = last["h"] - max(last["o"], last["c"])
        lower_wick = min(last["o"], last["c"]) - last["l"]
        body_val = _body(last["o"], last["c"])
        if upper_wick > body_val * 2 and lower_wick < body_val * 0.3 and body_val > 0:
            alerts.append({"pattern": "Shooting Star", "type": "reversal", "direction": "BEARISH",
                            "strength": 0.7, "desc": "Shooting Star — đảo chiều giảm sau uptrend"})

    # ── Bullish Engulfing ──
    if prev and _is_bearish(prev["o"], prev["c"]) and _is_bullish(last["o"], last["c"]):
        if last["c"] > prev["o"] and last["o"] <= prev["c"]:
            alerts.append({"pattern": "Bullish Engulfing", "type": "reversal", "direction": "BULLISH",
                            "strength": 0.8, "desc": "Bullish Engulfing — nến xanh bao trùm nến đỏ trước"})

    # ── Bearish Engulfing ──
    if prev and _is_bullish(prev["o"], prev["c"]) and _is_bearish(last["o"], last["c"]):
        if last["c"] < prev["o"] and last["o"] >= prev["c"]:
            alerts.append({"pattern": "Bearish Engulfing", "type": "reversal", "direction": "BEARISH",
                            "strength": 0.8, "desc": "Bearish Engulfing — nến đỏ bao trùm nến xanh trước"})

    # ── Morning Star (3-bar bullish reversal) ──
    if prev2 and prev and _is_bearish(prev2["o"], prev2["c"]):
        small_body = _body(prev["o"], prev["c"])
        big_body = _body(prev2["o"], prev2["c"])
        if small_body < big_body * 0.3 and _is_bullish(last["o"], last["c"]):
            if last["c"] > (prev2["o"] + prev2["c"]) / 2:
                alerts.append({"pattern": "Morning Star", "type": "reversal", "direction": "BULLISH",
                                "strength": 0.9, "desc": "Morning Star — mô hình 3 nến đảo chiều tăng mạnh"})

    # ── Evening Star (3-bar bearish reversal) ──
    if prev2 and prev and _is_bullish(prev2["o"], prev2["c"]):
        small_body = _body(prev["o"], prev["c"])
        big_body = _body(prev2["o"], prev2["c"])
        if small_body < big_body * 0.3 and _is_bearish(last["o"], last["c"]):
            if last["c"] < (prev2["o"] + prev2["c"]) / 2:
                alerts.append({"pattern": "Evening Star", "type": "reversal", "direction": "BEARISH",
                                "strength": 0.9, "desc": "Evening Star — mô hình 3 nến đảo chiều giảm mạnh"})

    # ── Three White Soldiers ──
    if len(bars) >= 3:
        b1, b2, b3 = bars[-3], bars[-2], bars[-1]
        if _is_bullish(b1["o"], b1["c"]) and _is_bullish(b2["o"], b2["c"]) and _is_bullish(b3["o"], b3["c"]):
            if b2["c"] > b1["c"] and b3["c"] > b2["c"]:
                alerts.append({"pattern": "Three White Soldiers", "type": "reversal", "direction": "BULLISH",
                                "strength": 0.85, "desc": "Three White Soldiers — 3 nến xanh tăng liên tục"})

    # ── Three Black Crows ──
    if len(bars) >= 3:
        b1, b2, b3 = bars[-3], bars[-2], bars[-1]
        if _is_bearish(b1["o"], b1["c"]) and _is_bearish(b2["o"], b2["c"]) and _is_bearish(b3["o"], b3["c"]):
            if b2["c"] < b1["c"] and b3["c"] < b2["c"]:
                alerts.append({"pattern": "Three Black Crows", "type": "reversal", "direction": "BEARISH",
                                "strength": 0.85, "desc": "Three Black Crows — 3 nến đỏ giảm liên tục"})

    # ── Piercing Line ──
    if prev and _is_bearish(prev["o"], prev["c"]) and _is_bullish(last["o"], last["c"]):
        mid = (prev["o"] + prev["c"]) / 2
        if last["o"] < prev["c"] and last["c"] > mid and last["c"] < prev["o"]:
            alerts.append({"pattern": "Piercing Line", "type": "reversal", "direction": "BULLISH",
                            "strength": 0.7, "desc": "Piercing Line — giá xuyên lên giữa nến đỏ trước"})

    # ── Dark Cloud Cover ──
    if prev and _is_bullish(prev["o"], prev["c"]) and _is_bearish(last["o"], last["c"]):
        mid = (prev["o"] + prev["c"]) / 2
        if last["o"] > prev["c"] and last["c"] < mid and last["c"] > prev["o"]:
            alerts.append({"pattern": "Dark Cloud Cover", "type": "reversal", "direction": "BEARISH",
                            "strength": 0.7, "desc": "Dark Cloud Cover — nến đỏ đè xuống vùng giữa nến xanh trước"})

    return alerts


# ── Indicator-based signals ──────────────────────────────────────
def detect_indicator_signals(df: pd.DataFrame) -> List[Dict]:
    """Detect RSI, MACD, EMA cross, Bollinger signals using `ta` library."""
    if df is None or len(df) < 30:
        return []
    alerts = []
    try:
        from ta.momentum import RSIIndicator
        from ta.trend import MACD, EMAIndicator
        from ta.volatility import BollingerBands
    except ImportError:
        return alerts

    close = df["close"]
    high = df["high"]
    low = df["low"]

    # ── RSI ──
    try:
        rsi_ind = RSIIndicator(close, window=14)
        rsi = rsi_ind.rsi()
        r = _safe(rsi.iloc[-1])
        r_prev = _safe(rsi.iloc[-2])
        if r is not None:
            if r <= 30:
                alerts.append({"pattern": "RSI Oversold", "type": "entry", "direction": "BULLISH",
                                "strength": 0.75, "desc": f"RSI {r:.1f} — vùng oversold, có thể đảo chiều tăng"})
            elif r >= 70:
                alerts.append({"pattern": "RSI Overbought", "type": "entry", "direction": "BEARISH",
                                "strength": 0.75, "desc": f"RSI {r:.1f} — vùng overbought, có thể đảo chiều giảm"})
            if r_prev is not None:
                if r_prev < 30 and r > 30:
                    alerts.append({"pattern": "RSI Exit Oversold", "type": "entry", "direction": "BULLISH",
                                    "strength": 0.8, "desc": f"RSI thoát vùng oversold ({r_prev:.1f} → {r:.1f}) — tín hiệu mua"})
                elif r_prev > 70 and r < 70:
                    alerts.append({"pattern": "RSI Exit Overbought", "type": "entry", "direction": "BEARISH",
                                    "strength": 0.8, "desc": f"RSI thoát vùng overbought ({r_prev:.1f} → {r:.1f}) — tín hiệu bán"})
    except Exception:
        pass

    # ── MACD crossover ──
    try:
        macd_ind = MACD(close, window_slow=26, window_fast=12, window_sign=9)
        macd_line = macd_ind.macd()
        signal_line = macd_ind.macd_signal()
        hist = macd_ind.macd_diff()
        if hist is not None and len(hist) >= 2:
            h1 = _safe(hist.iloc[-2])
            h2 = _safe(hist.iloc[-1])
            if h1 is not None and h2 is not None:
                if h1 < 0 and h2 > 0:
                    alerts.append({"pattern": "MACD Bullish Cross", "type": "entry", "direction": "BULLISH",
                                    "strength": 0.7, "desc": "MACD histogram cắt lên trên 0 — momentum tăng"})
                elif h1 > 0 and h2 < 0:
                    alerts.append({"pattern": "MACD Bearish Cross", "type": "entry", "direction": "BEARISH",
                                    "strength": 0.7, "desc": "MACD histogram cắt xuống dưới 0 — momentum giảm"})
    except Exception:
        pass

    # ── EMA Crossover (21/50) ──
    try:
        ema21 = EMAIndicator(close, window=21).ema_indicator()
        ema50 = EMAIndicator(close, window=50).ema_indicator()
        if ema21 is not None and ema50 is not None and len(ema21) >= 2:
            e21_now = _safe(ema21.iloc[-1])
            e21_prev = _safe(ema21.iloc[-2])
            e50_now = _safe(ema50.iloc[-1])
            e50_prev = _safe(ema50.iloc[-2])
            if all(v is not None for v in [e21_now, e21_prev, e50_now, e50_prev]):
                if e21_prev <= e50_prev and e21_now > e50_now:
                    alerts.append({"pattern": "EMA 21/50 Golden Cross", "type": "entry", "direction": "BULLISH",
                                    "strength": 0.75, "desc": "EMA21 cắt lên trên EMA50 — xu hướng tăng"})
                elif e21_prev >= e50_prev and e21_now < e50_now:
                    alerts.append({"pattern": "EMA 21/50 Death Cross", "type": "entry", "direction": "BEARISH",
                                    "strength": 0.75, "desc": "EMA21 cắt xuống dưới EMA50 — xu hướng giảm"})
    except Exception:
        pass

    # ── Bollinger Squeeze ──
    try:
        bb = BollingerBands(close, window=20, window_dev=2)
        bbu = bb.bollinger_hband()
        bbl = bb.bollinger_lband()
        if bbu is not None and bbl is not None and len(bbu) >= 5:
            width_now = _safe(bbu.iloc[-1]) - _safe(bbl.iloc[-1])
            width_prev = _safe(bbu.iloc[-5]) - _safe(bbl.iloc[-5])
            if width_now is not None and width_prev is not None and width_prev > 0:
                ratio = width_now / width_prev
                if ratio < 0.5:
                    alerts.append({"pattern": "BB Squeeze", "type": "reversal", "direction": "NEUTRAL",
                                    "strength": 0.6, "desc": f"Bollinger co lại mạnh ({ratio:.0%}) — chuẩn bị breakout"})
    except Exception:
        pass

    # ── EMA proximity to price (trend strength) ──
    try:
        ema200 = EMAIndicator(close, window=200).ema_indicator()
        if ema200 is not None and len(ema200) >= 1:
            price_now = _safe(close.iloc[-1])
            ema_val = _safe(ema200.iloc[-1])
            if price_now is not None and ema_val is not None and ema_val > 0:
                pct = (price_now - ema_val) / ema_val * 100
                if pct > 5:
                    alerts.append({"pattern": "Price > EMA200", "type": "reversal", "direction": "BULLISH",
                                    "strength": 0.55, "desc": f"Giá trên EMA200 {pct:.1f}% — xu hướng tăng dài hạn"})
                elif pct < -5:
                    alerts.append({"pattern": "Price < EMA200", "type": "reversal", "direction": "BEARISH",
                                    "strength": 0.55, "desc": f"Giá dưới EMA200 {abs(pct):.1f}% — xu hướng giảm dài hạn"})
    except Exception:
        pass

    # ── Volume spike ──
    try:
        vol = df["volume"]
        if len(vol) >= 20:
            avg_vol = vol.iloc[-21:-1].mean()
            last_vol = vol.iloc[-1]
            if avg_vol > 0 and last_vol > avg_vol * 2:
                pct = (last_vol / avg_vol - 1) * 100
                alerts.append({"pattern": "Volume Spike", "type": "entry", "direction": "NEUTRAL",
                                "strength": 0.65, "desc": f"Volume tăng {pct:.0f}% so với TB 20 phiên — chú ý breakout"})
    except Exception:
        pass

    return alerts


# ── MTF Plan generation ──────────────────────────────────────────
_prev_plans: Dict = {}  # symbol -> last consensus direction

def generate_plans_all(symbols: List[str] = None, interval: str = "1H",
                       force: bool = False, limit: int = 30) -> List[Dict]:
    """Generate MTF plans for symbols. Returns list of plan dicts.
    force=True bypasses cache. limit=max symbols (default 30)."""
    global _plan_ts, _plan_cache
    now = time.time()
    if not force and now - _plan_ts < PLAN_INTERVAL and _plan_cache:
        return _plan_cache

    if symbols is None:
        wl = cfg.WATCHLIST[:limit]
        symbols = [s["tv"] for s in wl]

    from core.analysis_plans import build_action_plan, build_per_tf_plans
    from core.multi_timeframe import MTFAnalyzer
    from config import MTF_TIMEFRAMES

    plans = []
    for sym in symbols:
        try:
            df = _get_df(sym, interval)
            if df is None or len(df) < 20:
                continue
            scraper = _get_scraper()
            mtf = MTFAnalyzer(sym, MTF_TIMEFRAMES).run(scraper) if scraper else None
            if not mtf or not mtf.get("results"):
                continue
            action_plan = build_action_plan(mtf, None)
            tf_plans = build_per_tf_plans(mtf)
            consensus = mtf.get("consensus", {})
            price = _safe(df["close"].iloc[-1])

            # Change detection
            new_dir = consensus.get("direction", "NEUTRAL")
            old_dir = _prev_plans.get(sym, "NEUTRAL")
            changed = new_dir != old_dir
            _prev_plans[sym] = new_dir

            plans.append({
                "symbol": sym,
                "price": price,
                "interval": interval,
                "consensus": consensus,
                "action_plan": action_plan,
                "tf_plans": tf_plans,
                "time": now,
                "changed": changed,
                "prev_direction": old_dir,
            })
        except Exception:
            continue

    _plan_ts = now
    _plan_cache = plans
    return plans


# ── Main scanner ─────────────────────────────────────────────────
_cache = OHLCVCache()
_scan_ts = 0.0
_scan_cache: List[Dict] = []
SCAN_INTERVAL = 30.0
PLAN_INTERVAL = 900.0  # 15 minutes
_plan_ts = 0.0
_plan_cache: List[Dict] = []
_scraper = None


def _get_scraper():
    global _scraper
    if _scraper is None:
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from tv_scraper_pro import TVScraperPro
            _scraper = TVScraperPro()
        except Exception:
            pass
    return _scraper


def _get_df(sym: str, interval: str) -> Optional[pd.DataFrame]:
    """Try cache first, then fallback to scraper."""
    df = _cache.get_frame(sym, interval, max_age=600)
    if df is not None and len(df) >= 20:
        return df
    scraper = _get_scraper()
    if scraper is None:
        return None
    try:
        df = scraper.scrape_yfinance(sym, interval=interval)
        if df is not None and len(df) >= 20:
            _cache.put_frame(sym, interval, df, source="alerts_fallback")
            return df
    except Exception:
        pass
    return None


def scan_all(symbols: List[str] = None, interval: str = "1H", full: bool = False) -> List[Dict]:
    """Scan symbols for alerts. Returns sorted list of alert dicts.
    Default: scan first 30 symbols (fast). full=True: scan all."""
    global _scan_ts, _scan_cache
    now = time.time()
    if now - _scan_ts < SCAN_INTERVAL and _scan_cache:
        return _scan_cache

    if symbols is None:
        wl = cfg.WATCHLIST
        if not full:
            wl = wl[:30]
        symbols = [s["tv"] for s in wl]

    all_alerts = []
    for sym in symbols:
        try:
            df = _get_df(sym, interval)
            if df is None or len(df) < 20:
                continue
            cs = detect_candlestick_patterns(df)
            ind = detect_indicator_signals(df)
            price = _safe(df["close"].iloc[-1])
            for a in cs + ind:
                a["symbol"] = sym
                a["price"] = price
                a["time"] = now
                a["interval"] = interval
                all_alerts.append(a)
        except Exception:
            continue

    all_alerts.sort(key=lambda x: x.get("strength", 0), reverse=True)
    _scan_ts = now
    _scan_cache = all_alerts
    return all_alerts
