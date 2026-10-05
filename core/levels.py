"""
Structural Levels: Fibonacci, Support/Resistance, Trendlines, Confluence Zones.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import config as cfg


def find_fibonacci_levels(df: pd.DataFrame, lookback: int = None) -> dict:
    """Calculate Fibonacci retracement + extension levels from recent swing high/low."""
    if df is None or len(df) < 10:
        return {}

    lb = lookback or cfg.FIB_LOOKBACK
    window = df.tail(lb)
    swing_high = float(window["high"].max())
    swing_low = float(window["low"].min())
    diff = swing_high - swing_low

    if diff <= 0:
        return {}

    levels = {}
    for fib in cfg.FIB_LEVELS:
        price = swing_low + fib * diff
        label = f"fib_{str(fib).replace('.', '')}"
        levels[label] = round(price, 6)

    for ext in cfg.FIB_EXTENSIONS:
        price = swing_high + (ext - 1.0) * diff
        label = f"fib_{str(ext).replace('.', '')}"
        levels[label] = round(price, 6)

    levels["swing_high"] = swing_high
    levels["swing_low"] = swing_low
    return levels


def find_nearest_fib(price: float, fib_levels: dict) -> dict:
    """Find the nearest Fibonacci level to current price."""
    if not fib_levels:
        return {"nearest": None, "distance_pct": None, "level": None}

    candidates = []
    for key, val in fib_levels.items():
        if key.startswith("fib_") and val and price:
            dist_pct = abs(price - val) / price * 100
            candidates.append((key, val, dist_pct))

    if not candidates:
        return {"nearest": None, "distance_pct": None, "level": None}

    candidates.sort(key=lambda x: x[2])
    best = candidates[0]
    return {
        "nearest": best[1],
        "distance_pct": round(best[2], 3),
        "level": best[0],
    }


def find_support_resistance(df: pd.DataFrame, lookback: int = 100) -> list:
    """Find S/R levels using pivot points with touch count and strength."""
    if df is None or len(df) < 10:
        return []

    lb = min(lookback, len(df))
    window = df.tail(lb).reset_index(drop=True)
    high = window["high"].values
    low = window["low"].values
    close = window["close"].values
    n = len(window)

    # Find pivot points
    pivots = []
    for i in range(2, n - 2):
        if high[i] >= high[i-1] and high[i] >= high[i+1] and high[i] >= high[i-2] and high[i] >= high[i+2]:
            pivots.append(("resistance", float(high[i])))
        if low[i] <= low[i-1] and low[i] <= low[i+1] and low[i] <= low[i-2] and low[i] <= low[i+2]:
            pivots.append(("support", float(low[i])))

    if not pivots:
        # Fallback: use recent high/low
        return [
            {"price": float(low.min()), "type": "support", "strength": 50, "touches": 1},
            {"price": float(high.max()), "type": "resistance", "strength": 50, "touches": 1},
        ]

    # Cluster nearby pivots
    tolerance = cfg.SR_TOLERANCE
    clusters = []
    used = set()
    for i, (stype, price) in enumerate(pivots):
        if i in used:
            continue
        cluster_prices = [price]
        cluster_types = [stype]
        for j, (stype2, price2) in enumerate(pivots):
            if j != i and j not in used:
                if abs(price - price2) / max(price, 0.0001) < tolerance:
                    cluster_prices.append(price2)
                    cluster_types.append(stype2)
                    used.add(j)
        used.add(i)
        avg_price = np.mean(cluster_prices)
        touches = len(cluster_prices)
        # Determine type by majority
        res_count = cluster_types.count("resistance")
        sup_count = cluster_types.count("support")
        final_type = "resistance" if res_count >= sup_count else "support"
        # Strength based on touches
        strength = min(100, touches * 20 + 10)
        clusters.append({
            "price": round(float(avg_price), 6),
            "type": final_type,
            "strength": strength,
            "touches": touches,
        })

    # Sort by strength
    clusters.sort(key=lambda x: x["strength"], reverse=True)
    return clusters[:10]


def find_trendlines(df: pd.DataFrame, lookback: int = 60) -> list:
    """Detect trendlines by connecting pivot points with linear regression."""
    if df is None or len(df) < 10:
        return []

    lb = min(lookback, len(df))
    window = df.tail(lb).reset_index(drop=True)
    high = window["high"].values
    low = window["low"].values
    n = len(window)

    # Find pivot highs and lows
    pivot_highs = [(i, float(high[i])) for i in range(2, n-2)
                   if high[i] >= high[i-1] and high[i] >= high[i+1]]
    pivot_lows = [(i, float(low[i])) for i in range(2, n-2)
                  if low[i] <= low[i-1] and low[i] <= low[i+1]]

    trendlines = []

    # Check ascending trendlines (connect 2+ pivot lows)
    if len(pivot_lows) >= 2:
        # Try connecting first and last pivot low
        pts = pivot_lows
        if len(pts) >= 2:
            x = np.array([p[0] for p in pts], dtype=float)
            y = np.array([p[1] for p in pts], dtype=float)
            if len(x) >= 2:
                coeffs = np.polyfit(x, y, 1)
                slope = coeffs[0]
                # Calculate how well points fit the line
                predicted = np.polyval(coeffs, x)
                r_squared = 1 - np.sum((y - predicted)**2) / max(np.sum((y - np.mean(y))**2), 1e-10)
                if r_squared > 0.5 and slope > 0:
                    # Extrapolate to current bar
                    current_price = float(low[-1])
                    tl_price = float(np.polyval(coeffs, n - 1))
                    confidence = min(1.0, r_squared * len(pts) / 3)
                    trendlines.append({
                        "type": "ascending",
                        "slope": round(float(slope), 6),
                        "confidence": round(confidence, 2),
                        "support_price": round(tl_price, 6),
                        "r_squared": round(float(r_squared), 3),
                        "points": len(pts),
                    })

    # Check descending trendlines (connect 2+ pivot highs)
    if len(pivot_highs) >= 2:
        pts = pivot_highs
        if len(pts) >= 2:
            x = np.array([p[0] for p in pts], dtype=float)
            y = np.array([p[1] for p in pts], dtype=float)
            if len(x) >= 2:
                coeffs = np.polyfit(x, y, 1)
                slope = coeffs[0]
                predicted = np.polyval(coeffs, x)
                r_squared = 1 - np.sum((y - predicted)**2) / max(np.sum((y - np.mean(y))**2), 1e-10)
                if r_squared > 0.5 and slope < 0:
                    tl_price = float(np.polyval(coeffs, n - 1))
                    confidence = min(1.0, r_squared * len(pts) / 3)
                    trendlines.append({
                        "type": "descending",
                        "slope": round(float(slope), 6),
                        "confidence": round(confidence, 2),
                        "resistance_price": round(tl_price, 6),
                        "r_squared": round(float(r_squared), 3),
                        "points": len(pts),
                    })

    return trendlines


def get_confluence_zones(fib_levels: dict, sr_levels: list, trendlines: list,
                         price: float = None, tolerance: float = None) -> list:
    """Find zones where multiple levels align (confluence)."""
    tol = tolerance or cfg.CONFLUENCE_TOLERANCE
    if not price or price <= 0:
        return []

    # Collect all level prices
    all_levels = []
    if fib_levels:
        for key, val in fib_levels.items():
            if key.startswith("fib_") and val:
                all_levels.append({"price": val, "source": f"Fib {key.replace('fib_', '')}", "weight": 2})

    for sr in sr_levels:
        all_levels.append({"price": sr["price"], "source": f"S/R {sr['type'][:3].upper()} {sr['touches']}t", "weight": sr["strength"] / 20})

    for tl in trendlines:
        p = tl.get("support_price") or tl.get("resistance_price")
        if p:
            all_levels.append({"price": p, "source": f"TL {tl['type'][:3]}", "weight": tl["confidence"] * 2})

    if not all_levels:
        return []

    # Cluster nearby levels
    zones = []
    used = set()
    for i, lvl in enumerate(all_levels):
        if i in used:
            continue
        cluster = [lvl]
        for j, lvl2 in enumerate(all_levels):
            if j != i and j not in used:
                if abs(lvl["price"] - lvl2["price"]) / max(lvl["price"], 0.0001) < tol:
                    cluster.append(lvl2)
                    used.add(j)
        used.add(i)

        if len(cluster) >= 2:
            avg_price = np.mean([c["price"] for c in cluster])
            total_weight = sum(c["weight"] for c in cluster)
            strength = min(100, int(total_weight * 15))
            sources = [c["source"] for c in cluster]
            dist_pct = abs(avg_price - price) / price * 100 if price else 0
            zones.append({
                "price": round(float(avg_price), 6),
                "strength": strength,
                "levels": sources,
                "distance_pct": round(dist_pct, 2),
            })

    zones.sort(key=lambda x: x["strength"], reverse=True)
    return zones[:5]


def analyze_structure(df: pd.DataFrame) -> dict:
    """Complete structural analysis: Fibonacci + S/R + Trendline + Confluence."""
    if df is None or df.empty:
        return {}

    price = float(df["close"].iloc[-1])
    fib = find_fibonacci_levels(df)
    fib_info = find_nearest_fib(price, fib)
    sr = find_support_resistance(df)
    tl = find_trendlines(df)
    zones = get_confluence_zones(fib, sr, tl, price)

    # Nearest S/R
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
