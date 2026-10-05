"""
Multi-Timeframe (MTF) Analysis Engine v2.
Fetches candles for several timeframes, computes trend + signals + structural levels per timeframe,
then aggregates into an MTF consensus.
"""
import concurrent.futures as futures
from typing import Dict, List, Optional

import pandas as pd

import config as cfg
from core.indicators import TechnicalAnalyzer
from core.levels import analyze_structure


# Higher timeframes rule (daily/4h are the "context").
TF_WEIGHTS = {
    "1m": 1, "5m": 1, "15m": 1, "30m": 1, "1H": 2, "4H": 3, "1D": 3,
}
_LABEL_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1H": "1H", "4H": "4H", "1D": "1D", "1W": "1W", "1M": "1M",
}


def tf_label(tf: str) -> str:
    return _LABEL_MAP.get(tf, tf)


def _detect_breakout(df: pd.DataFrame, signals: Dict, structure: dict) -> dict:
    """Detect breakout / breakdown conditions on a single timeframe."""
    if df is None or len(df) < 20:
        return {"type": "none", "level": None, "confidence": 0.0, "detail": ""}

    close = float(df["close"].iloc[-1])
    prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else close
    sr = structure.get("support_resistance", [])
    tl = structure.get("trendlines", [])
    fib_info = structure.get("fib_nearest", {})
    bb = signals.get("Bollinger", {})
    vol = df.get("volume")

    # 1) S/R breakout
    for s in sr:
        price = s["price"]
        if close > price and prev_close <= price and s["type"] == "resistance":
            return {"type": "BREAKOUT", "level": price, "confidence": 0.8, "detail": f"Above R {s['touches']}x"}
        if close < price and prev_close >= price and s["type"] == "support":
            return {"type": "BREAKDOWN", "level": price, "confidence": 0.8, "detail": f"Below S {s['touches']}x"}

    # 2) Bollinger squeeze breakout
    bb_upper = bb.get("upper")
    bb_lower = bb.get("lower")
    bb_mid = bb.get("mid")
    if bb_upper and bb_lower and bb_mid:
        bb_width = (bb_upper - bb_lower) / bb_mid if bb_mid > 0 else 0
        if close > bb_upper:
            return {"type": "BREAKOUT", "level": bb_upper, "confidence": 0.7, "detail": f"BB upper squeeze ({bb_width:.3f})"}
        if close < bb_lower:
            return {"type": "BREAKDOWN", "level": bb_lower, "confidence": 0.7, "detail": f"BB lower squeeze ({bb_width:.3f})"}

    # 3) Trendline break
    for t in tl:
        p = t.get("support_price") or t.get("resistance_price")
        if p and t.get("type") == "ascending" and close < p and prev_close >= p:
            return {"type": "BREAKDOWN", "level": p, "confidence": t.get("confidence", 0.5), "detail": "Trendline break"}
        if p and t.get("type") == "descending" and close > p and prev_close <= p:
            return {"type": "BREAKOUT", "level": p, "confidence": t.get("confidence", 0.5), "detail": "Trendline break"}

    # 4) 20-bar high/low breakout (already in detect_patterns but we duplicate for MTF)
    window = df.tail(20)
    high20 = float(window["high"].max())
    low20 = float(window["low"].min())
    if close > high20:
        return {"type": "BREAKOUT", "level": high20, "confidence": 0.6, "detail": "20-bar high"}
    if close < low20:
        return {"type": "BREAKDOWN", "level": low20, "confidence": 0.6, "detail": "20-bar low"}

    return {"type": "none", "level": None, "confidence": 0.0, "detail": ""}


def _trend_from_signals(signals: Dict, df: pd.DataFrame) -> Dict:
    """Classify trend direction from the per-timeframe indicator signals."""
    bull = 0
    bear = 0
    reasons = []

    macd = signals.get("MACD", {})
    if macd.get("direction") == "BULLISH":
        bull += 1; reasons.append("MACD+")
    elif macd.get("direction") == "BEARISH":
        bear += 1; reasons.append("MACD-")

    ema_cross = signals.get("EMA_Cross", {})
    if ema_cross.get("signal") == "GOLDEN":
        bull += 1; reasons.append("EMA golden")
    elif ema_cross.get("signal") == "DEATH":
        bear += 1; reasons.append("EMA death")

    rsi = signals.get("RSI", {})
    if rsi.get("value") is not None:
        v = rsi["value"]
        if v >= 55:
            bull += 1; reasons.append("RSI>=55")
        elif v <= 45:
            bear += 1; reasons.append("RSI<=45")

    adx = signals.get("ADX", {})
    if adx.get("trend_strength") == "STRONG":
        reasons.append("ADX strong")

    close = df["close"].dropna()
    if len(close) >= 1:
        last = float(close.iloc[-1])
        for col in ("SMA_20", "SMA_50", "SMA_200"):
            col_series = df[col].dropna()
            if not col_series.empty and pd.notna(col_series.iloc[-1]):
                v = float(col_series.iloc[-1])
                if last > v:
                    bull += 1; reasons.append(f"Price>{col}")
                else:
                    bear += 1; reasons.append(f"Price<{col}")

    stoch = signals.get("Stochastic", {})
    if stoch.get("K") is not None:
        k = stoch["K"]
        if k > 60:
            bull += 1; reasons.append("Stoch K>60")
        elif k < 40:
            bear += 1; reasons.append("Stoch K<40")

    total = bull + bear
    if total == 0:
        return {"direction": "NEUTRAL", "bull": 0, "bear": 0,
                "confidence": 0.0, "score": 0, "reasons": reasons}

    ratio = bull / total
    if bull > bear and bull >= 3 and ratio > 0.55:
        direction = "LONG"
    elif bear > bull and bear >= 3 and (1 - ratio) > 0.55:
        direction = "SHORT"
    else:
        direction = "NEUTRAL"
    confidence = round(max(bull, bear) / total, 2)
    return {"direction": direction, "bull": bull, "bear": bear,
            "confidence": confidence, "score": bull - bear, "reasons": reasons}


class MTFAnalyzer:
    """Analyze a symbol across several timeframes and produce a consensus."""

    def __init__(self, symbol: str, timeframes: Optional[List[str]] = None):
        self.symbol = symbol
        self.timeframes = timeframes or cfg.MTF_TIMEFRAMES

    def _analyze_one(self, scraper, tf: str) -> dict:
        """Fetch + analyze one timeframe. Returns result dict or None on failure."""
        try:
            df = scraper.scrape_yfinance(self.symbol, interval=tf)
            if df is None or df.empty:
                return None
            analyzer = TechnicalAnalyzer(df)
            df = analyzer.compute_all()
            signals = analyzer.get_latest_signals()
            trend = _trend_from_signals(signals, df)
            structure = analyze_structure(df)
            breakout = _detect_breakout(df, signals, structure)
            return {
                "interval": tf,
                "df": df,
                "signals": signals,
                "trend": trend,
                "structure": structure,
                "breakout": breakout,
                "bars": len(df),
                "last_close": float(df["close"].dropna().iloc[-1]) if not df["close"].dropna().empty else None,
            }
        except Exception:
            return None

    def run(self, scraper) -> Dict:
        """Fetch all timeframes (parallel), compute per-TF trend + structure, aggregate consensus."""
        results = {}
        with futures.ThreadPoolExecutor(max_workers=min(len(self.timeframes), 6)) as ex:
            for tf, res in zip(self.timeframes, ex.map(
                    lambda t: self._analyze_one(scraper, t), self.timeframes)):
                if res is not None:
                    results[tf] = res

        # Weighted consensus
        weighted = 0.0
        total_w = 0.0
        lean_by_tf = {}
        votes = {}
        for tf, res in results.items():
            w = TF_WEIGHTS.get(tf, 1)
            trend = res["trend"]
            bull, bear = trend["bull"], trend["bear"]
            total = bull + bear
            lean = (bull - bear) / total if total > 0 else 0.0
            weighted += w * lean
            total_w += w
            lean_by_tf[tf] = lean
            d = trend["direction"]
            votes[d] = votes.get(d, 0) + w

        if results and total_w > 0:
            score = weighted / total_w
        else:
            score = 0.0

        if score > 0.25:
            mdir = "LONG"
        elif score < -0.25:
            mdir = "SHORT"
        else:
            mdir = "NEUTRAL"

        strength = round(min(abs(score), 1.0), 2)
        aligned = sum(1 for tf, res in results.items() if res["trend"]["direction"] == mdir)
        total_tf = len(results)

        # Collect breakouts across TFs
        active_breakouts = []
        for tf, res in results.items():
            bk = res.get("breakout", {})
            if bk.get("type") and bk["type"] != "none":
                active_breakouts.append({"tf": tf, **bk})

        return {
            "symbol": self.symbol,
            "timeframes": sorted(results.keys(), key=lambda t: TF_WEIGHTS.get(t, 1)),
            "results": results,
            "consensus": {
                "direction": mdir,
                "strength": strength,
                "score": round(score, 2),
                "votes": votes,
                "lean_by_tf": lean_by_tf,
                "aligned": aligned,
                "total": total_tf,
                "active_breakouts": active_breakouts,
            },
        }