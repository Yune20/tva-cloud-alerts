"""
Custom TradingView-style indicators:
1. Winners Scalper Pro — Bull/Bear scalping signals
2. Entry-to-Exit Tool — ATR-based entry/exit levels
3. Volume Profile — volume distribution + high/low zones
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional


def winners_scalper_pro(df: pd.DataFrame, period: int = 14, sensitivity: float = 1.5) -> dict:
    """
    Winners Scalper Pro — detects Bull/Bear scalping signals.
    Uses RSI + Stochastic + EMA alignment + ATR volatility.
    
    Returns:
        signal: "BULL", "BEAR", "NEUTRAL"
        strength: 0-100
        entries: list of signal bars with price/color/text
    """
    if df is None or len(df) < period + 10:
        return {"signal": "NEUTRAL", "strength": 0, "entries": []}

    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    n = len(df)

    # Compute indicators
    # RSI
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = pd.Series(gains).rolling(period).mean().values
    avg_loss = pd.Series(losses).rolling(period).mean().values
    rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100)
    rsi = 100 - (100 / (1 + rs))
    rsi = np.concatenate([[np.nan] * period, rsi])

    # Stochastic
    low_min = pd.Series(low).rolling(period).min().values
    high_max = pd.Series(high).rolling(period).max().values
    stoch_k = np.where(high_max - low_min > 0,
                       (close - low_min) / (high_max - low_min) * 100, 50)
    stoch_d = pd.Series(stoch_k).rolling(3).mean().values

    # EMA 9 & 21
    ema9 = pd.Series(close).ewm(span=9).mean().values
    ema21 = pd.Series(close).ewm(span=21).mean().values

    # ATR
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - close[:-1]),
                               np.abs(low[1:] - close[:-1])))
    tr = np.concatenate([[np.nan], tr])
    atr = pd.Series(tr).rolling(period).mean().values

    # Detect signals
    entries = []
    bull_count = 0
    bear_count = 0

    for i in range(period + 5, n):
        score = 0
        # RSI conditions
        if rsi[i] < 30:
            score += 2
        elif rsi[i] < 45:
            score += 1
        elif rsi[i] > 70:
            score -= 2
        elif rsi[i] > 55:
            score -= 1

        # Stochastic cross
        if stoch_k[i] > stoch_d[i] and stoch_k[i-1] <= stoch_d[i-1] and stoch_k[i] < 30:
            score += 3
        elif stoch_k[i] < stoch_d[i] and stoch_k[i-1] >= stoch_d[i-1] and stoch_k[i] > 70:
            score -= 3

        # EMA alignment
        if ema9[i] > ema21[i] and close[i] > ema9[i]:
            score += 2
        elif ema9[i] < ema21[i] and close[i] < ema9[i]:
            score -= 2

        # Price vs EMA
        if close[i] > ema21[i] and close[i-1] <= ema21[i-1]:
            score += 2
        elif close[i] < ema21[i] and close[i-1] >= ema21[i-1]:
            score -= 2

        # ATR expansion (volatility increasing)
        if i >= period and atr[i] > atr[i-1] * sensitivity:
            score = int(score * 1.2)

        # Record signal
        if score >= 4:
            bar_time = int(df.index[i].timestamp()) if hasattr(df.index[i], 'timestamp') else i
            entries.append({
                "time": bar_time,
                "position": "belowBar",
                "color": "#1b8a5a",
                "shape": "arrowUp",
                "text": f"BULL {score}",
                "type": "BULL",
                "score": score,
                "price": float(close[i]),
            })
            bull_count += 1
        elif score <= -4:
            bar_time = int(df.index[i].timestamp()) if hasattr(df.index[i], 'timestamp') else i
            entries.append({
                "time": bar_time,
                "position": "aboveBar",
                "color": "#d32f2f",
                "shape": "arrowDown",
                "text": f"BEAR {abs(score)}",
                "type": "BEAR",
                "score": abs(score),
                "price": float(close[i]),
            })
            bear_count += 1

    # Current signal
    total = bull_count + bear_count
    if bull_count > bear_count and bull_count > 2:
        signal = "BULL"
        strength = min(100, int(bull_count / max(total, 1) * 100))
    elif bear_count > bull_count and bear_count > 2:
        signal = "BEAR"
        strength = min(100, int(bear_count / max(total, 1) * 100))
    else:
        signal = "NEUTRAL"
        strength = 0

    return {
        "signal": signal,
        "strength": strength,
        "bull_count": bull_count,
        "bear_count": bear_count,
        "entries": entries[-20:],  # Last 20 signals
    }


def entry_exit_tool(df: pd.DataFrame, atr_period: int = 14, rr_ratio: float = 2.0) -> dict:
    """
    Entry-to-Exit Tool — ATR-based entry, stop loss, take profit levels.
    
    Returns:
        entry, stop_loss, take_profit_1, take_profit_2
        risk_reward ratio
        atr_value, atr_percent
    """
    if df is None or len(df) < atr_period + 5:
        return {}

    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    n = len(df)

    # ATR
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - close[:-1]),
                               np.abs(low[1:] - close[:-1])))
    tr = np.concatenate([[np.nan], tr])
    atr = pd.Series(tr).rolling(atr_period).mean().values

    # EMA 9 & 21
    ema9 = pd.Series(close).ewm(span=9).mean().values
    ema21 = pd.Series(close).rolling(21).mean().values

    last_close = float(close[-1])
    last_atr = float(atr[-1]) if not np.isnan(atr[-1]) else last_close * 0.01
    last_ema9 = float(ema9[-1])
    last_ema21 = float(ema21[-1]) if not np.isnan(ema21[-1]) else last_close

    # Determine trend
    if last_close > last_ema9 > last_ema21:
        trend = "UPTREND"
    elif last_close < last_ema9 < last_ema21:
        trend = "DOWNTREND"
    else:
        trend = "SIDEWAYS"

    # Entry levels
    if trend == "UPTREND":
        entry = last_close - last_atr * 0.3  # Pullback entry
        stop_loss = entry - last_atr * 1.5
        tp1 = entry + last_atr * rr_ratio
        tp2 = entry + last_atr * rr_ratio * 1.5
    elif trend == "DOWNTREND":
        entry = last_close + last_atr * 0.3  # Rally entry
        stop_loss = entry + last_atr * 1.5
        tp1 = entry - last_atr * rr_ratio
        tp2 = entry - last_atr * rr_ratio * 1.5
    else:
        entry = last_close
        stop_loss = last_close - last_atr * 1.5
        tp1 = last_close + last_atr * rr_ratio
        tp2 = last_close - last_atr * 1.5

    risk = abs(entry - stop_loss)
    reward = abs(tp1 - entry)
    rr = reward / risk if risk > 0 else 0

    return {
        "trend": trend,
        "entry": round(entry, 6),
        "stop_loss": round(stop_loss, 6),
        "take_profit_1": round(tp1, 6),
        "take_profit_2": round(tp2, 6),
        "risk_reward": round(rr, 2),
        "atr_value": round(last_atr, 6),
        "atr_percent": round(last_atr / last_close * 100, 2) if last_close > 0 else 0,
        "ema9": round(last_ema9, 6),
        "ema21": round(last_ema21, 6),
    }


def volume_profile(df: pd.DataFrame, num_bins: int = 20) -> dict:
    """
    Volume Profile — volume distribution at price levels.
    Identifies high/low volume zones.
    
    Returns:
        poc: Point of Control (highest volume price)
        value_area_high: upper value area
        value_area_low: lower value area
        zones: list of {price, volume, pct} for each bin
        high_volume_zones: list of prices with high volume
        low_volume_zones: list of prices with low volume
        current_volume_ratio: current volume vs average
    """
    if df is None or len(df) < 10:
        return {}

    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    volume = df["volume"].values
    n = len(df)

    # Price range
    price_min = float(low.min())
    price_max = float(high.max())
    price_range = price_max - price_min
    if price_range <= 0:
        return {}

    bin_size = price_range / num_bins
    bins = np.linspace(price_min, price_max, num_bins + 1)
    bin_centers = (bins[:-1] + bins[1:]) / 2

    # Volume per bin
    bin_volumes = np.zeros(num_bins)
    for i in range(n):
        bar_mid = (high[i] + low[i]) / 2
        bin_idx = min(int((bar_mid - price_min) / bin_size), num_bins - 1)
        bin_volumes[bin_idx] += volume[i]

    # Normalize
    total_vol = bin_volumes.sum()
    if total_vol > 0:
        bin_pct = bin_volumes / total_vol * 100
    else:
        bin_pct = np.zeros(num_bins)

    # POC (highest volume bin)
    poc_idx = np.argmax(bin_volumes)
    poc = float(bin_centers[poc_idx])

    # Value Area (70% of volume around POC)
    sorted_idx = np.argsort(-bin_volumes)
    cumvol = 0
    va_indices = []
    for idx in sorted_idx:
        cumvol += bin_volumes[idx]
        va_indices.append(idx)
        if cumvol >= total_vol * 0.7:
            break
    va_indices.sort()
    value_area_low = float(bin_centers[va_indices[0]]) if va_indices else poc
    value_area_high = float(bin_centers[va_indices[-1]]) if va_indices else poc

    # Zones
    zones = []
    for i in range(num_bins):
        zones.append({
            "price": round(float(bin_centers[i]), 6),
            "volume": round(float(bin_volumes[i]), 0),
            "pct": round(float(bin_pct[i]), 1),
        })

    # High/Low volume zones (above/below average)
    avg_vol = bin_volumes.mean()
    high_vol = [z["price"] for z in zones if z["volume"] > avg_vol * 1.5]
    low_vol = [z["price"] for z in zones if z["volume"] < avg_vol * 0.5]

    # Current volume vs 20-bar average
    avg_vol_20 = volume[-20:].mean() if n >= 20 else volume.mean()
    current_ratio = volume[-1] / avg_vol_20 if avg_vol_20 > 0 else 1

    return {
        "poc": round(poc, 6),
        "value_area_high": round(value_area_high, 6),
        "value_area_low": round(value_area_low, 6),
        "zones": zones,
        "high_volume_zones": high_vol[:5],
        "low_volume_zones": low_vol[:5],
        "current_volume_ratio": round(current_ratio, 2),
        "avg_volume_20": round(avg_vol_20, 0),
    }
