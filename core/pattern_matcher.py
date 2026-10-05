"""
Pattern Matcher: find similar historical trades, calculate similarity, track pattern stats.
"""
import json
from typing import Dict, List, Optional

import config as cfg


class PatternMatcher:
    def __init__(self, db=None):
        self.db = db

    def calculate_similarity(self, a: dict, b: dict) -> float:
        """Calculate similarity between two signal sets (0-1)."""
        scores = []

        # RSI similarity
        rsi_a = a.get("rsi") or 50
        rsi_b = b.get("rsi") or 50
        scores.append(("rsi", 1 - abs(rsi_a - rsi_b) / 100, 0.15))

        # MACD direction
        macd_a = a.get("macd_direction") or a.get("macd_hist", 0)
        macd_b = b.get("macd_direction") or b.get("macd_hist", 0)
        if isinstance(macd_a, str):
            macd_sim = 1.0 if macd_a == macd_b else 0.0
        else:
            macd_sim = 1.0 if (macd_a or 0) * (macd_b or 0) > 0 else 0.0
        scores.append(("macd", macd_sim, 0.12))

        # BB position
        bb_a = a.get("bb_position") or 50
        bb_b = b.get("bb_position") or 50
        scores.append(("bb", 1 - abs(bb_a - bb_b) / 100, 0.10))

        # ADX
        adx_a = a.get("adx") or 25
        adx_b = b.get("adx") or 25
        scores.append(("adx", 1 - min(abs(adx_a - adx_b) / 50, 1.0), 0.08))

        # Stoch K
        stoch_a = a.get("stoch_k") or 50
        stoch_b = b.get("stoch_k") or 50
        scores.append(("stoch", 1 - abs(stoch_a - stoch_b) / 100, 0.10))

        # Fib level proximity
        fib_a = a.get("fib_nearest") or 0.5
        fib_b = b.get("fib_nearest") or 0.5
        scores.append(("fib", 1 - min(abs(fib_a - fib_b), 1.0), 0.15))

        # S/R distance
        sr_a = a.get("sr_distance_pct") or 1.0
        sr_b = b.get("sr_distance_pct") or 1.0
        scores.append(("sr", 1 - min(abs(sr_a - sr_b) / 2.0, 1.0), 0.12))

        # Trendline
        tl_a = a.get("trendline_type") or "none"
        tl_b = b.get("trendline_type") or "none"
        scores.append(("trendline", 1.0 if tl_a == tl_b else 0.0, 0.08))

        # Pattern
        pat_a = a.get("pattern_name") or ""
        pat_b = b.get("pattern_name") or ""
        scores.append(("pattern", 1.0 if pat_a == pat_b else 0.0, 0.10))

        total_weight = sum(w for _, _, w in scores)
        weighted_sum = sum(s * w for _, s, w in scores)
        return weighted_sum / total_weight if total_weight > 0 else 0

    def find_similar(self, current_signals: dict, symbol: str = None,
                     interval: str = None, threshold: float = None,
                     max_results: int = None) -> list:
        """Find historically similar trades."""
        if not self.db:
            return []

        thr = threshold or cfg.PATTERN_SIMILARITY_THRESHOLD
        mx = max_results or cfg.PATTERN_MAX_RESULTS

        candidates = self.db.get_historical_trades(symbol, interval, limit=500)
        results = []
        for trade in candidates:
            hist_signals = {}
            for k in ("rsi", "macd_hist", "bb_position", "adx", "stoch_k",
                       "fib_nearest", "sr_distance_pct", "trendline_type", "pattern_name"):
                hist_signals[k] = trade.get(k)

            sim = self.calculate_similarity(current_signals, hist_signals)
            if sim >= thr:
                results.append({
                    "trade_id": trade.get("id"),
                    "symbol": trade.get("symbol"),
                    "interval": trade.get("interval"),
                    "direction": trade.get("direction"),
                    "entry_time": trade.get("entry_time"),
                    "exit_time": trade.get("exit_time"),
                    "total_pnl": trade.get("total_pnl", 0),
                    "total_pnl_pct": trade.get("total_pnl_pct", 0),
                    "r_multiple": trade.get("r_multiple", 0),
                    "status": trade.get("status", "CLOSED"),
                    "similarity": round(sim * 100, 1),
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:mx]

    def get_pattern_stats(self, results: list) -> dict:
        """Calculate stats from similar pattern results."""
        if not results:
            return {"count": 0, "win_rate": 0, "avg_pnl": 0, "avg_r": 0}

        total = len(results)
        wins = sum(1 for r in results if r.get("total_pnl", 0) > 0)
        avg_pnl = sum(r.get("total_pnl_pct", 0) for r in results) / total
        avg_r = sum(r.get("r_multiple", 0) for r in results) / total

        return {
            "count": total,
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            "avg_pnl": round(avg_pnl, 2),
            "avg_r": round(avg_r, 2),
        }
