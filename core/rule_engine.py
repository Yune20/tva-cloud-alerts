"""
Rule-based trading analysis engine — instant, no LLM needed.
Reads indicators + psychology + darvas + structure → generates specific recommendation.
"""
from typing import Dict, Optional


def _score_direction(signals: dict, psychology: dict, darvas: dict, mtf_consensus: dict) -> dict:
    """Score LONG vs SHORT vs NEUTRAL from multiple sources."""
    bull = 0
    bear = 0
    reasons = []

    # RSI
    rsi = signals.get("RSI", {})
    rsi_val = rsi.get("value", 50)
    rsi_sig = rsi.get("signal", "NEUTRAL")
    if rsi_sig == "OVERSOLD":
        bull += 2
        reasons.append(f"RSI {rsi_val:.0f} oversold → bullish")
    elif rsi_sig == "OVERBOUGHT":
        bear += 2
        reasons.append(f"RSI {rsi_val:.0f} overbought → bearish")
    elif rsi_val < 45:
        bull += 1
        reasons.append(f"RSI {rsi_val:.0f} dưới 50")
    elif rsi_val > 55:
        bear += 1
        reasons.append(f"RSI {rsi_val:.0f} trên 50")

    # MACD
    macd = signals.get("MACD", {})
    macd_dir = macd.get("direction", "")
    hist = macd.get("histogram", 0)
    if macd_dir == "BULLISH":
        bull += 2
        reasons.append("MACD bullish")
    elif macd_dir == "BEARISH":
        bear += 2
        reasons.append("MACD bearish")
    if hist > 0:
        bull += 1
    elif hist < 0:
        bear += 1

    # EMA Cross
    ema = signals.get("EMA_Cross", {})
    ema_sig = ema.get("signal", "")
    if ema_sig == "GOLDEN":
        bull += 2
        reasons.append("EMA golden cross")
    elif ema_sig == "DEATH":
        bear += 2
        reasons.append("EMA death cross")

    # Bollinger
    bb = signals.get("Bollinger", {})
    bb_sig = bb.get("signal", "NEUTRAL")
    if bb_sig == "OVERSOLD":
        bull += 2
        reasons.append("BB oversold")
    elif bb_sig == "OVERBOUGHT":
        bear += 2
        reasons.append("BB overbought")

    # Supertrend
    st = signals.get("Supertrend", {})
    st_dir = st.get("direction", "")
    if st_dir == "BULL":
        bull += 2
        reasons.append("Supertrend BULL")
    elif st_dir == "BEAR":
        bear += 2
        reasons.append("Supertrend BEAR")

    # Stochastic
    stoch = signals.get("Stochastic", {})
    stoch_sig = stoch.get("signal", "NEUTRAL")
    k_val = stoch.get("K", 50)
    if stoch_sig == "OVERSOLD":
        bull += 1
        reasons.append(f"Stoch K={k_val:.0f} oversold")
    elif stoch_sig == "OVERBOUGHT":
        bear += 1
        reasons.append(f"Stoch K={k_val:.0f} overbought")

    # MFI
    mfi = signals.get("MFI", {})
    mfi_sig = mfi.get("signal", "NEUTRAL")
    if mfi_sig == "OVERSOLD":
        bull += 1
        reasons.append("MFI oversold")
    elif mfi_sig == "OVERBOUGHT":
        bear += 1
        reasons.append("MFI overbought")

    # ADX trend strength
    adx = signals.get("ADX", {})
    adx_val = adx.get("value", 0)
    adx_strong = adx_val > 25

    # Psychology
    psych_score = psychology.get("score", 50) if psychology else 50
    if psych_score < 30:
        bull += 2
        reasons.append(f"Psych fear {psych_score:.0f}/100")
    elif psych_score > 70:
        bear += 2
        reasons.append(f"Psych greed {psych_score:.0f}/100")
    elif psych_score < 45:
        bull += 1
    elif psych_score > 55:
        bear += 1

    # Darvas
    darvas_trend = darvas.get("trend", "SIDEWAYS") if darvas else "SIDEWAYS"
    if darvas_trend == "UPTREND":
        bull += 1
        reasons.append("Darvas uptrend")
    elif darvas_trend == "DOWNTREND":
        bear += 1
        reasons.append("Darvas downtrend")

    # MTF consensus
    mtf_dir = mtf_consensus.get("direction", "NEUTRAL") if mtf_consensus else "NEUTRAL"
    mtf_strength = mtf_consensus.get("strength", 0) if mtf_consensus else 0
    if mtf_dir == "LONG":
        bull += 3
        reasons.append(f"MTF consensus LONG ({mtf_strength:.0%})")
    elif mtf_dir == "SHORT":
        bear += 3
        reasons.append(f"MTF consensus SHORT ({mtf_strength:.0%})")

    total = bull + bear
    if total == 0:
        direction = "STAND_ASIDE"
        confidence = 0
    elif bull > bear:
        direction = "LONG"
        confidence = bull / total
    elif bear > bull:
        direction = "SHORT"
        confidence = bear / total
    else:
        direction = "STAND_ASIDE"
        confidence = 0

    if confidence > 0.7:
        conf_label = "high"
    elif confidence > 0.55:
        conf_label = "medium"
    else:
        conf_label = "low"

    return {
        "direction": direction,
        "confidence": conf_label,
        "confidence_pct": round(confidence * 100),
        "bull_score": bull,
        "bear_score": bear,
        "reasons": reasons,
    }


def analyze(symbol: str, signals: dict = None, psychology: dict = None,
            darvas: dict = None, structure: dict = None,
            mtf_consensus: dict = None, entry_exit: dict = None) -> dict:
    """Generate instant trading recommendation from analysis data."""
    sig = signals or {}
    ee = entry_exit or {}
    psych = psychology or {}
    darv = darvas or {}
    st = structure or {}
    mtf = mtf_consensus or {}

    # Direction scoring
    scoring = _score_direction(sig, psych, darv, mtf)
    direction = scoring["direction"]

    # Entry / SL / TP from structure
    last_price = ee.get("last_price", 0)
    sup = ee.get("nearest_support")
    res = ee.get("nearest_resistance")

    entry = sl = tp1 = tp2 = None
    if direction == "LONG" and sup:
        entry = sup
        sl = sup * 0.985
        if res:
            tp1 = res
            tp2 = res + (res - sl) * 0.5
    elif direction == "SHORT" and res:
        entry = res
        sl = res * 1.015
        if sup:
            tp1 = sup
            tp2 = sup - (sl - sup) * 0.5
    elif direction == "LONG" and res:
        entry = last_price
        sl = last_price * 0.98
        tp1 = res
        tp2 = res + (res - sl) * 0.5
    elif direction == "SHORT" and sup:
        entry = last_price
        sl = last_price * 1.02
        tp1 = sup
        tp2 = sup - (sl - sup) * 0.5

    rr = None
    if entry and sl and tp1:
        risk = abs(entry - sl)
        reward = abs(tp1 - entry)
        if risk > 0:
            rr = f"{reward/risk:.1f}:1"

    # Risk management
    atr_pct = sig.get("ATR", {}).get("percent", 1)
    pos_size = "5%" if atr_pct > 2 else "10%" if atr_pct > 1 else "15%"

    # Warnings
    warnings = []
    adx_val = sig.get("ADX", {}).get("value", 0)
    if adx_val < 20:
        warnings.append("ADX yếu (<20) — thị trường sideway")
    if scoring["confidence_pct"] < 55:
        warnings.append("Confidence thấp — chờ thêm xác nhận")
    if darv.get("trend") == "SIDEWAYS":
        warnings.append("Darvas sideway — có thể false breakout")
    psych_val = psych.get("score", 50)
    if 40 < psych_val < 60:
        warnings.append("Tâm lý trung tính — thiếuensus rõ ràng")

    return {
        "symbol": symbol,
        "direction": direction,
        "confidence": scoring["confidence"],
        "confidence_pct": scoring["confidence_pct"],
        "bull_score": scoring["bull_score"],
        "bear_score": scoring["bear_score"],
        "reasons": scoring["reasons"],
        "entry": round(entry, 6) if entry else None,
        "stop_loss": round(sl, 6) if sl else None,
        "take_profit_1": round(tp1, 6) if tp1 else None,
        "take_profit_2": round(tp2, 6) if tp2 else None,
        "risk_reward": rr,
        "position_size": pos_size,
        "warnings": warnings,
        "last_price": last_price,
        "support": sup,
        "resistance": res,
    }
