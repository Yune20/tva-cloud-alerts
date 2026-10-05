"""
Market Structure — BOS (Break of Structure) & ChoCh (Change of Character).

Detects swing highs/lows, then identifies:
- BOS: trend continuation break
- ChoCh: trend reversal break
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple


def find_swing_points(df: pd.DataFrame, lookback: int = 5) -> Tuple[List[dict], List[dict]]:
    """Find swing highs and swing lows using rolling window."""
    if df is None or len(df) < lookback * 2 + 1:
        return [], []

    n = len(df)
    highs = df["high"].values
    lows = df["low"].values
    times = df.index

    swing_highs = []
    swing_lows = []

    for i in range(lookback, n - lookback):
        # Swing high: highest high in window
        window_high = highs[i - lookback:i + lookback + 1]
        if highs[i] == window_high.max() and np.sum(window_high == highs[i]) == 1:
            swing_highs.append({
                "time": int(times[i].timestamp()) if hasattr(times[i], 'timestamp') else i,
                "price": float(highs[i]),
                "bar_idx": i,
                "type": "high",
            })

        # Swing low: lowest low in window
        window_low = lows[i - lookback:i + lookback + 1]
        if lows[i] == window_low.min() and np.sum(window_low == lows[i]) == 1:
            swing_lows.append({
                "time": int(times[i].timestamp()) if hasattr(times[i], 'timestamp') else i,
                "price": float(lows[i]),
                "bar_idx": i,
                "type": "low",
            })

    return swing_highs, swing_lows


def detect_bos_choch(df: pd.DataFrame, lookback: int = 5) -> dict:
    """
    Detect BOS and ChoCh from swing points.

    BOS (Break of Structure):
    - Bullish BOS: price breaks above previous swing high → trend continuation UP
    - Bearish BOS: price breaks below previous swing low → trend continuation DOWN

    ChoCh (Change of Character):
    - Bullish ChoCh: price breaks above swing high during downtrend → reversal UP
    - Bearish ChoCh: price breaks below swing low during uptrend → reversal DOWN
    """
    if df is None or len(df) < lookback * 3:
        return {"swing_highs": [], "swing_lows": [], "events": [], "structure": "NEUTRAL"}

    swing_highs, swing_lows = find_swing_points(df, lookback)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
            "events": [],
            "structure": "NEUTRAL",
        }

    events = []
    current_trend = "NEUTRAL"
    last_high = None
    last_low = None
    prev_high = None
    prev_low = None

    # Sort all swing points by bar index
    all_swings = sorted(swing_highs + swing_lows, key=lambda x: x["bar_idx"])

    for swing in all_swings:
        if swing["type"] == "high":
            if last_high is not None:
                prev_high = last_high
            last_high = swing
        else:
            if last_low is not None:
                prev_low = last_low
            last_low = swing

    # Scan bars after last swing to detect breaks
    if last_high is None or last_low is None:
        return {
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
            "events": [],
            "structure": "NEUTRAL",
        }

    # Determine initial trend from last two swings
    if len(all_swings) >= 2:
        s1 = all_swings[-2]
        s2 = all_swings[-1]
        if s1["type"] == "low" and s2["type"] == "high" and s2["price"] > s1["price"]:
            current_trend = "UPTREND"
        elif s1["type"] == "high" and s2["type"] == "low" and s2["price"] < s1["price"]:
            current_trend = "DOWNTREND"

    # Check each bar after the last major swing for breaks
    last_swing_idx = max(
        (last_high["bar_idx"] if last_high else 0),
        (last_low["bar_idx"] if last_low else 0)
    )

    for i in range(last_swing_idx + 1, len(df)):
        bar_high = float(df["high"].iloc[i])
        bar_low = float(df["low"].iloc[i])
        bar_close = float(df["close"].iloc[i])
        bar_time = int(df.index[i].timestamp()) if hasattr(df.index[i], 'timestamp') else i

        # Check break above swing high
        if last_high and bar_high > last_high["price"]:
            if current_trend == "DOWNTREND":
                # ChoCh: break above high during downtrend = reversal
                events.append({
                    "time": bar_time,
                    "type": "ChoCh",
                    "direction": "BULLISH",
                    "price": last_high["price"],
                    "bar_idx": i,
                    "detail": f"Break above {last_high['price']:.2f}",
                })
                current_trend = "UPTREND"
            elif current_trend == "UPTREND":
                # BOS: break above high during uptrend = continuation
                events.append({
                    "time": bar_time,
                    "type": "BOS",
                    "direction": "BULLISH",
                    "price": last_high["price"],
                    "bar_idx": i,
                    "detail": f"Break above {last_high['price']:.2f}",
                })
            # Update last_high
            last_high = {"time": bar_time, "price": bar_high, "bar_idx": i, "type": "high"}

        # Check break below swing low
        if last_low and bar_low < last_low["price"]:
            if current_trend == "UPTREND":
                # ChoCh: break below low during uptrend = reversal
                events.append({
                    "time": bar_time,
                    "type": "ChoCh",
                    "direction": "BEARISH",
                    "price": last_low["price"],
                    "bar_idx": i,
                    "detail": f"Break below {last_low['price']:.2f}",
                })
                current_trend = "DOWNTREND"
            elif current_trend == "DOWNTREND":
                # BOS: break below low during downtrend = continuation
                events.append({
                    "time": bar_time,
                    "type": "BOS",
                    "direction": "BEARISH",
                    "price": last_low["price"],
                    "bar_idx": i,
                    "detail": f"Break below {last_low['price']:.2f}",
                })
            # Update last_low
            last_low = {"time": bar_time, "price": bar_low, "bar_idx": i, "type": "low"}

    return {
        "swing_highs": swing_highs[-20:],  # Last 20 swing highs
        "swing_lows": swing_lows[-20:],    # Last 20 swing lows
        "events": events[-10:],            # Last 10 BOS/ChoCh events
        "structure": current_trend,
        "last_bos": next((e for e in reversed(events) if e["type"] == "BOS"), None),
        "last_choch": next((e for e in reversed(events) if e["type"] == "ChoCh"), None),
    }


def structure_summary(structure: dict) -> str:
    """Human-readable structure summary."""
    if not structure:
        return "Không xác định"

    trend = structure.get("structure", "NEUTRAL")
    events = structure.get("events", [])
    last_bos = structure.get("last_bos")
    last_choch = structure.get("last_choch")

    lines = [f"Structure: {trend}"]
    if last_bos:
        lines.append(f"BOS gần nhất: {last_bos['direction']} @ {last_bos['price']:.2f}")
    if last_choch:
        lines.append(f"ChoCh gần nhất: {last_choch['direction']} @ {last_choch['price']:.2f}")
    lines.append(f"Tổng sự kiện: {len(events)}")

    return " | ".join(lines)
