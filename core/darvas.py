"""
Darvas Box Detection Module

Identifies consolidation boxes (price contained within a range) and
detects breakouts when price closes above/below the box boundaries.

A Darvas Box is defined as:
  - Top: highest high in the consolidation period
  - Bottom: lowest low in the consolidation period
  - The range must be within a tolerance (default 3% of top)
  - Breakout: price closes above top (bullish) or below bottom (bearish)
"""
import numpy as np
import pandas as pd


def detect_boxes(df, lookback=20, tolerance_pct=3.0, min_bars=5):
    """Detect Darvas Boxes in OHLCV data.
    
    Args:
        df: OHLCV DataFrame with columns: open, high, low, close (or capitalized)
        lookback: number of bars to look back for box detection
        tolerance_pct: max range as % of top for consolidation
        min_bars: minimum bars to form a valid box
    
    Returns:
        list of dicts: [{ top, bottom, start_idx, end_idx, start_time, end_time,
                          bars_in_box, breakout, breakout_price }]
    """
    # Normalize column names
    cols = {c.lower(): c for c in df.columns}
    high_col = cols.get("high", "High")
    low_col = cols.get("low", "Low")
    close_col = cols.get("close", "Close")
    time_col = cols.get("time", "Time") if "time" in cols else None

    highs = df[high_col].values
    lows = df[low_col].values
    closes = df[close_col].values
    n = len(df)

    if n < lookback:
        return []

    boxes = []
    i = 0

    while i < n - min_bars:
        # Try to form a box starting at bar i
        window_highs = highs[i:i + lookback]
        window_lows = lows[i:i + lookback]

        box_top = np.max(window_highs)
        box_bottom = np.min(window_lows)

        if box_top <= 0:
            i += 1
            continue

        box_range_pct = (box_top - box_bottom) / box_top * 100

        if box_range_pct > tolerance_pct:
            # Range too wide, not a consolidation — skip forward
            i += 1
            continue

        # Extend the box forward as long as price stays inside
        end_idx = i + min_bars
        while end_idx < n:
            # Check if this bar stays inside the box
            if highs[end_idx] > box_top * 1.005 or lows[end_idx] < box_bottom * 0.995:
                break
            end_idx += 1

        # Check for breakout at end_idx (if within data)
        breakout = None
        breakout_price = None
        if end_idx < n:
            if closes[end_idx] > box_top:
                breakout = "UP"
                breakout_price = float(closes[end_idx])
            elif closes[end_idx] < box_bottom:
                breakout = "DOWN"
                breakout_price = float(closes[end_idx])

        bars_in = end_idx - i
        if bars_in >= min_bars:
            start_time = str(df.index[i]) if time_col is None else str(df[time_col].iloc[i])
            end_time = str(df.index[end_idx - 1]) if time_col is None else str(df[time_col].iloc[end_idx - 1])
            boxes.append({
                "top": round(float(box_top), 6),
                "bottom": round(float(box_bottom), 6),
                "start_idx": int(i),
                "end_idx": int(end_idx - 1),
                "start_time": start_time,
                "end_time": end_time,
                "bars_in_box": int(bars_in),
                "range_pct": round(box_range_pct, 2),
                "breakout": breakout,
                "breakout_price": breakout_price,
            })

        # Move past this box
        i = end_idx + 1 if end_idx < n else n

    return boxes


def get_current_box(boxes):
    """Get the most recent (or active) Darvas Box.
    
    Returns the latest box dict, or None if no boxes found.
    If the latest box has a breakout, also returns the breakout direction.
    """
    if not boxes:
        return None
    return boxes[-1]


def get_box_trend(boxes):
    """Determine trend from a series of Darvas Boxes.
    
    - Higher highs + higher lows = UPTREND
    - Lower highs + lower lows = DOWNTREND
    - Mixed = SIDEWAYS
    """
    if len(boxes) < 2:
        return "UNKNOWN"

    tops = [b["top"] for b in boxes]
    bottoms = [b["bottom"] for b in boxes]

    # Check if tops are rising
    tops_rising = all(tops[j] > tops[j - 1] * 0.99 for j in range(1, len(tops)))
    bottoms_rising = all(bottoms[j] > bottoms[j - 1] * 0.99 for j in range(1, len(bottoms)))

    tops_falling = all(tops[j] < tops[j - 1] * 1.01 for j in range(1, len(tops)))
    bottoms_falling = all(bottoms[j] < bottoms[j - 1] * 1.01 for j in range(1, len(bottoms)))

    if tops_rising and bottoms_rising:
        return "UPTREND"
    elif tops_falling and bottoms_falling:
        return "DOWNTREND"
    else:
        return "SIDEWAYS"


def summarize(boxes, current_price=None):
    """Generate a summary dict for frontend display.
    
    Returns:
        dict with: boxes (list), current_box, trend, summary_vi
    """
    current = get_current_box(boxes)
    trend = get_box_trend(boxes)

    trend_vi = {
        "UPTREND": "Xu hướng tăng — box cao dần",
        "DOWNTREND": "Xu hướng giảm — box thấp dần",
        "SIDEWAYS": "Đi ngang — box xen kẽ",
        "UNKNOWN": "Chưa đủ dữ liệu",
    }

    lines = []
    if current:
        if current["breakout"] == "UP":
            lines.append(f"Phát hiện breakout LÊN khỏi box ({current['bottom']:.2f}–{current['top']:.2f})")
            lines.append("Không đuổi — chờ retest box trên làm hỗ trợ mới")
        elif current["breakout"] == "DOWN":
            lines.append(f"Phát hiện breakout XUỐNG khỏi box ({current['bottom']:.2f}–{current['top']:.2f})")
            lines.append("Không đuổi — chờ retest box dưới làm kháng cự mới")
        else:
            lines.append(f"Đang trong box ({current['bottom']:.2f}–{current['top']:.2f}), {current['bars_in_box']} nến")

    lines.append(f"Box trend: {trend_vi.get(trend, trend)}")

    return {
        "boxes": boxes[-5:] if len(boxes) > 5 else boxes,  # last 5 boxes max
        "current_box": current,
        "trend": trend,
        "trend_vi": trend_vi.get(trend, trend),
        "summary_vi": lines,
        "box_count": len(boxes),
    }
