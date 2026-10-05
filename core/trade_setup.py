"""
Trade Setup Engine v2: partial TP/SL, position sizing, Fibonacci, S/R, Trendline.
"""
import config as cfg
import pandas as pd
import numpy as np
from core.levels import find_fibonacci_levels, find_nearest_fib, find_support_resistance, find_trendlines, get_confluence_zones


def detect_patterns(df: pd.DataFrame, lookback: int = 20) -> dict:
    if df is None or len(df) < 3:
        return {"patterns": [], "name": "Insufficient data", "direction": "neutral", "strength": 0.0}

    last = df.iloc[-1]
    prev = df.iloc[-2]
    o, h, l, c = last["open"], last["high"], last["low"], last["close"]
    body = abs(c - o)
    rng = h - l
    pats = []

    if body > 0:
        po, pc = prev["open"], prev["close"]
        pbody = abs(pc - po)
        if c > o and pc < po and o <= po and c >= pc and pbody > 0:
            pats.append(("Engulfing Bull", "bullish", 1.0))
        elif c < o and pc > po and o >= po and c <= pc and pbody > 0:
            pats.append(("Engulfing Bear", "bearish", 1.0))

    if rng > 0:
        lower_wick = min(o, c) - l
        upper_wick = h - max(o, c)
        if lower_wick >= 2 * body and upper_wick <= 0.4 * lower_wick:
            pats.append(("Hammer", "bullish", 0.8))
        if upper_wick >= 2 * body and lower_wick <= 0.4 * upper_wick:
            pats.append(("Shooting Star", "bearish", 0.8))

    if rng > 0 and body <= 0.1 * rng:
        pats.append(("Doji", "neutral", 0.3))

    if len(df) >= lookback + 2:
        window = df.iloc[-(lookback + 1):-1]
        high20 = window["high"].max()
        low20 = window["low"].min()
        if c > high20:
            pats.append(("Breakout 20-bar High", "bullish", 0.9))
        if c < low20:
            pats.append(("Breakdown 20-bar Low", "bearish", 0.9))

    if not pats:
        pats.append(("No pattern", "neutral", 0.2))

    best = max(pats, key=lambda x: x[2])
    return {"patterns": pats, "name": best[0], "direction": best[1], "strength": best[2]}


def find_swing_levels(df: pd.DataFrame, lookback: int = 8) -> dict:
    window = df.tail(lookback)
    return {"swing_low": float(window["low"].min()), "swing_high": float(window["high"].max())}


def _build_partial_tp(entry: float, risk: float, direction: str) -> list:
    """Build partial take-profit levels."""
    result = []
    for r_level, pct in cfg.PARTIAL_TP.items():
        if direction == "LONG":
            price = entry + r_level * risk
        else:
            price = entry - r_level * risk
        pnl_per_unit = r_level * risk * pct
        result.append({
            "level": f"TP{r_level}",
            "r_multiple": r_level,
            "price": round(price, 6),
            "pct_of_position": int(pct * 100),
            "pnl_per_unit": round(pnl_per_unit, 6),
        })
    return result


def _build_partial_sl(entry: float, risk: float, direction: str) -> list:
    """Build partial stop-loss levels."""
    result = []
    for r_level, pct in cfg.PARTIAL_SL.items():
        if direction == "LONG":
            price = entry - r_level * risk
        else:
            price = entry + r_level * risk
        loss_per_unit = r_level * risk * pct
        result.append({
            "level": f"SL{int(r_level * 10)}",
            "r_from_entry": r_level,
            "price": round(price, 6),
            "pct_of_position": int(pct * 100),
            "loss_per_unit": round(loss_per_unit, 6),
        })
    return result


def compute_setup(df: pd.DataFrame, direction: str, signals: dict,
                  mtf_dir: str = None, mtf_strength: float = 0.0,
                  daily_capital: float = None, atr_mult: float = None) -> dict:
    """Build complete trade plan with partial TP/SL, structural levels, position sizing."""
    if df is None or df.empty or direction in (None, "NEUTRAL"):
        return None

    atr_mult = atr_mult or cfg.SL_ATR_MULT
    capital = daily_capital or cfg.DEFAULT_DAILY_CAPITAL
    close = df["close"].dropna()
    if close.empty:
        return None

    price = float(close.iloc[-1])

    # ATR
    atr = None
    for col in ["ATR", "atr"]:
        if col in df.columns:
            vals = df[col].dropna()
            if not vals.empty:
                atr = float(vals.iloc[-1])
                break
    if not atr or atr <= 0:
        atr = price * 0.004 if price else 1.0

    # Structural levels
    structure = find_structure(df, price)
    fib = structure.get("fibonacci", {})
    sr = structure.get("support_resistance", [])
    tl = structure.get("trendlines", [])
    zones = structure.get("confluence_zones", [])
    fib_info = structure.get("fib_nearest", {})
    nearest_sup = structure.get("nearest_support")
    nearest_res = structure.get("nearest_resistance")

    # Swing levels
    levels = find_swing_levels(df)
    swing_low = levels["swing_low"]
    swing_high = levels["swing_high"]

    # Base risk calculation
    if direction == "LONG":
        entry = price
        # SL: below swing low OR below nearest support, whichever is tighter
        sl_candidates = [price - atr_mult * atr, swing_low]
        if nearest_sup and nearest_sup["price"] < price:
            sl_candidates.append(nearest_sup["price"] - atr * 0.2)
        stop = max(sl_candidates)  # Highest = tightest
        risk = entry - stop
        if risk <= 0:
            risk = atr_mult * atr
            stop = entry - risk
    else:
        entry = price
        sl_candidates = [price + atr_mult * atr, swing_high]
        if nearest_res and nearest_res["price"] > price:
            sl_candidates.append(nearest_res["price"] + atr * 0.2)
        stop = min(sl_candidates)  # Lowest = tightest
        risk = stop - entry
        if risk <= 0:
            risk = atr_mult * atr
            stop = entry + risk

    # Partial TP/SL
    partial_tp = _build_partial_tp(entry, risk, direction)
    partial_sl = _build_partial_sl(entry, risk, direction)

    # Position sizing
    risk_per_trade = capital * cfg.MAX_RISK_PER_TRADE_PCT / 100
    position_size = risk_per_trade / risk if risk > 0 else 0

    # Calculate P/L in dollars
    for tp in partial_tp:
        tp["pnl_dollar"] = round(tp["pnl_per_unit"] * position_size, 2)
        tp["pnl_pct"] = round(tp["pnl_dollar"] / capital * 100, 2) if capital > 0 else 0

    for sl in partial_sl:
        sl["loss_dollar"] = round(sl["loss_per_unit"] * position_size, 2)
        sl["loss_pct"] = round(sl["loss_dollar"] / capital * 100, 2) if capital > 0 else 0

    total_tp_pnl = sum(tp["pnl_dollar"] for tp in partial_tp)
    total_sl_loss = sum(sl["loss_dollar"] for sl in partial_sl)

    # R:R ratios
    rr_ratios = {}
    for tp in partial_tp:
        rr_ratios[f"tp{tp['r_multiple']}"] = round(tp["r_multiple"], 1)
    avg_rr = np.mean([tp["r_multiple"] for tp in partial_tp]) if partial_tp else 0
    rr_ratios["avg"] = round(float(avg_rr), 1)

    # Scenarios
    scenarios = {
        "best_case": {"pnl": round(total_tp_pnl, 2), "pct": round(total_tp_pnl / capital * 100, 2) if capital > 0 else 0, "new_capital": round(capital + total_tp_pnl, 2)},
        "worst_case": {"pnl": round(-total_sl_loss, 2), "pct": round(-total_sl_loss / capital * 100, 2) if capital > 0 else 0, "new_capital": round(capital - total_sl_loss, 2)},
        "breakeven": {"pnl": 0, "pct": 0, "new_capital": capital},
    }

    # Reliability score
    score = 50
    reasons = []
    rsi = signals.get("RSI", {}) if signals else {}
    macd = signals.get("MACD", {}) if signals else {}
    adx = signals.get("ADX", {}) if signals else {}
    bb = signals.get("Bollinger", {}) if signals else {}

    macd_dir = macd.get("direction")
    if macd_dir == ("BULLISH" if direction == "LONG" else "BEARISH"):
        score += 8; reasons.append("MACD aligned")

    r = rsi.get("value")
    if r is not None:
        if direction == "LONG" and 50 < r < 70:
            score += 8; reasons.append("RSI bullish zone")
        elif direction == "SHORT" and 30 < r < 50:
            score += 8; reasons.append("RSI bearish zone")

    if adx.get("trend_strength") == "STRONG":
        score += 7; reasons.append("ADX strong trend")

    pos = bb.get("position")
    if pos is not None:
        if direction == "LONG" and pos < 40:
            score += 5; reasons.append("Price near BB lower")
        elif direction == "SHORT" and pos > 60:
            score += 5; reasons.append("Price near BB upper")

    if mtf_dir == direction:
        score += 10; reasons.append(f"MTF aligned ({mtf_strength*100:.0f}%)")
    elif mtf_dir and mtf_dir != "NEUTRAL":
        score -= 8; reasons.append("MTF counter-trend")

    # Volume surge
    vol = df.get("volume")
    if vol is not None and vol.notna().sum() >= 20:
        last_v = float(vol.iloc[-1])
        avg_v = float(vol.tail(20).mean())
        if avg_v > 0 and last_v > avg_v * 1.3:
            score += 6; reasons.append(f"Volume surge ({last_v/avg_v:.1f}x)")

    pattern = detect_patterns(df)
    pat_dir = pattern["direction"]
    if (pat_dir == "bullish" and direction == "LONG") or (pat_dir == "bearish" and direction == "SHORT"):
        score += 6; reasons.append(f"Pattern: {pattern['name']}")

    # Structural bonuses
    if fib_info.get("distance_pct") is not None and fib_info["distance_pct"] < 1.0:
        score += 5; reasons.append(f"Near Fib {fib_info['level']}")

    if zones:
        score += 3; reasons.append(f"Confluence zone ({len(zones)} levels)")

    score = int(max(0, min(100, score)))
    quality = "CAO" if score >= 75 else "TRUNG BÌNH" if score >= 55 else "THẤP"

    return {
        "direction": direction,
        "price": round(price, 6),
        "entry": round(entry, 6),
        "stop_loss": round(stop, 6),
        "risk_per_unit": round(risk, 6),
        "atr": round(atr, 6),

        # Partial exits
        "take_profits": partial_tp,
        "partial_stops": partial_sl,
        "total_tp_pnl": round(total_tp_pnl, 2),
        "total_sl_loss": round(total_sl_loss, 2),

        # Position sizing
        "position_size": round(position_size, 4),
        "risk_amount": round(risk_per_trade, 2),
        "daily_capital": round(capital, 2),

        # R:R
        "rr_ratios": rr_ratios,

        # Structural
        "fib_levels": fib,
        "fib_nearest": fib_info,
        "support_resistance": sr[:5],
        "nearest_support": nearest_sup,
        "nearest_resistance": nearest_res,
        "trendlines": tl,
        "confluence_zones": zones,

        # Scenarios
        "scenarios": scenarios,

        # Reliability
        "reliability": score,
        "quality": quality,
        "reasons": reasons,
        "pattern": pattern["name"],
        "mtf_dir": mtf_dir,

        # Trailing stop info
        "trailing_stop": {
            "activate_at_r": cfg.TRAILING_STOP_ACTIVATE,
            "offset_r": cfg.TRAILING_STOP_OFFSET,
        },
    }


def find_structure(df, price):
    """Wrapper to call levels module."""
    from core.levels import find_fibonacci_levels, find_nearest_fib, find_support_resistance, find_trendlines, get_confluence_zones

    fib = find_fibonacci_levels(df)
    fib_info = find_nearest_fib(price, fib)
    sr = find_support_resistance(df)
    tl = find_trendlines(df)
    zones = get_confluence_zones(fib, sr, tl, price)

    nearest_sup = None
    nearest_res = None
    for s in sr:
        if s["type"] == "support" and s["price"] < price:
            if not nearest_sup or s["price"] > nearest_sup["price"]:
                nearest_sup = s
        elif s["type"] == "resistance" and s["price"] > price:
            if not nearest_res or s["price"] < nearest_res["price"]:
                nearest_res = s

    return {
        "price": price,
        "fibonacci": fib,
        "fib_nearest": fib_info,
        "support_resistance": sr,
        "nearest_support": nearest_sup,
        "nearest_resistance": nearest_res,
        "trendlines": tl,
        "confluence_zones": zones,
    }
