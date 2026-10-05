"""
Multi-School Consensus Module
Combines signals from 5 schools: Technical, Statistical, ML, Momentum, Volume.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class SchoolSignal:
    name: str
    direction: str   # "LONG", "SHORT", "NEUTRAL"
    confidence: float  # 0.0 - 1.0
    reason: str


class ConsensusEngine:
    """Combine signals from multiple analysis schools."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.signals: Dict[str, SchoolSignal] = {}

    def compute_all(
        self,
        indicators: Optional[Dict] = None,
        stats: Optional[Dict] = None,
        ml_prediction: Optional[Dict] = None,
    ) -> Dict:
        """Compute signals from all schools and reach consensus."""
        self.signals["technical"] = self._technical_signal(indicators)
        self.signals["statistical"] = self._statistical_signal(stats)
        self.signals["ml_prediction"] = self._ml_signal(ml_prediction)
        self.signals["momentum"] = self._momentum_signal()
        self.signals["volume"] = self._volume_signal()

        consensus = self._reach_consensus()

        return {
            "schools": {k: {
                "direction": v.direction,
                "confidence": v.confidence,
                "reason": v.reason,
            } for k, v in self.signals.items()},
            "consensus": consensus,
        }

    def _technical_signal(self, indicators: Optional[Dict] = None) -> SchoolSignal:
        """Generate signal from technical indicators."""
        df = self.df
        if df.empty or not indicators:
            return SchoolSignal("technical", "NEUTRAL", 0, "No indicator data")

        votes = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
        reasons = []

        # RSI
        rsi = indicators.get("RSI", {})
        if rsi:
            if rsi.get("signal") == "OVERSOLD":
                votes["LONG"] += 1
                reasons.append(f"RSI oversold ({rsi['value']})")
            elif rsi.get("signal") == "OVERBOUGHT":
                votes["SHORT"] += 1
                reasons.append(f"RSI overbought ({rsi['value']})")
            else:
                votes["NEUTRAL"] += 1

        # MACD
        macd = indicators.get("MACD", {})
        if macd:
            if macd.get("direction") == "BULLISH":
                votes["LONG"] += 1
                reasons.append("MACD bullish crossover")
            elif macd.get("direction") == "BEARISH":
                votes["SHORT"] += 1
                reasons.append("MACD bearish crossover")

        # Bollinger
        bb = indicators.get("Bollinger", {})
        if bb:
            if bb.get("signal") == "OVERSOLD":
                votes["LONG"] += 1
                reasons.append(f"Price near lower BB ({bb['position']:.0f}%)")
            elif bb.get("signal") == "OVERBOUGHT":
                votes["SHORT"] += 1
                reasons.append(f"Price near upper BB ({bb['position']:.0f}%)")

        # EMA Cross
        ema = indicators.get("EMA_Cross", {})
        if ema:
            if ema.get("signal") == "GOLDEN":
                votes["LONG"] += 1
                reasons.append("Golden cross (EMA)")
            elif ema.get("signal") == "DEATH":
                votes["SHORT"] += 1
                reasons.append("Death cross (EMA)")

        # ADX
        adx = indicators.get("ADX", {})
        if adx and adx.get("trend_strength") == "STRONG":
            reasons.append(f"Strong trend (ADX {adx['value']})")

        # Determine direction
        total = sum(votes.values())
        if total == 0:
            return SchoolSignal("technical", "NEUTRAL", 0, "No signals")

        if votes["LONG"] > votes["SHORT"]:
            conf = votes["LONG"] / total
            return SchoolSignal("technical", "LONG", conf, "; ".join(reasons[:3]))
        elif votes["SHORT"] > votes["LONG"]:
            conf = votes["SHORT"] / total
            return SchoolSignal("technical", "SHORT", conf, "; ".join(reasons[:3]))
        else:
            return SchoolSignal("technical", "NEUTRAL", 0, "Conflicting signals")

    def _statistical_signal(self, stats: Optional[Dict] = None) -> SchoolSignal:
        """Generate signal from statistical analysis."""
        if not stats:
            return SchoolSignal("statistical", "NEUTRAL", 0, "No statistical data")

        reasons = []
        conf = 0

        # Volatility regime
        vol = stats.get("volatility", {})
        if vol:
            regime = vol.get("vol_regime", "NORMAL")
            if regime == "LOW":
                reasons.append("Low volatility - potential breakout setup")
                conf += 0.2
            elif regime == "HIGH":
                reasons.append("High volatility - caution advised")
                conf += 0.1

        # Stationarity
        stat = stats.get("stationarity", {})
        returns_stat = stat.get("returns", {})
        if returns_stat.get("adf", {}).get("is_stationary"):
            reasons.append("Returns are stationary (mean-reverting)")
            conf += 0.2

        # Distribution
        dist = stats.get("distribution", {})
        if dist:
            skew = dist.get("skewness", 0)
            if skew > 0.5:
                reasons.append(f"Positive skew ({skew:.2f})")
                conf += 0.15
            elif skew < -0.5:
                reasons.append(f"Negative skew ({skew:.2f})")
                conf += 0.15

        # Autocorrelation
        auto = stats.get("autocorrelation", {})
        if auto.get("has_autocorrelation"):
            reasons.append("Autocorrelation detected - trend may persist")
            conf += 0.2

        direction = "NEUTRAL"
        if conf > 0.3:
            # Use recent price trend to determine direction
            if len(self.df) > 20:
                recent_return = (self.df["close"].iloc[-1] / self.df["close"].iloc[-20]) - 1
                direction = "LONG" if recent_return > 0 else "SHORT"
                reasons.append(f"Recent trend: {recent_return*100:.1f}%")

        return SchoolSignal("statistical", direction, min(conf, 1.0), "; ".join(reasons[:3]))

    def _ml_signal(self, ml_prediction: Optional[Dict] = None) -> SchoolSignal:
        """Generate signal from ML prediction."""
        if not ml_prediction or ml_prediction.get("error"):
            return SchoolSignal("ml_prediction", "NEUTRAL", 0, "ML model not available")

        direction = ml_prediction.get("prediction", "NEUTRAL")
        confidence = ml_prediction.get("confidence", 0)
        signal = ml_prediction.get("signal", "NEUTRAL")

        reasons = [
            f"Ensemble prediction: {direction}",
            f"Confidence: {confidence*100:.1f}%",
        ]

        if ml_prediction.get("probability_up"):
            reasons.append(f"P(up)={ml_prediction['probability_up']:.2f}, P(down)={ml_prediction['probability_down']:.2f}")

        final_dir = signal if signal != "NEUTRAL" else direction
        return SchoolSignal("ml_prediction", final_dir, confidence, "; ".join(reasons))

    def _momentum_signal(self) -> SchoolSignal:
        """Generate signal from momentum analysis."""
        df = self.df
        if len(df) < 20:
            return SchoolSignal("momentum", "NEUTRAL", 0, "Insufficient data")

        reasons = []
        votes = {"LONG": 0, "SHORT": 0}

        # Price momentum
        mom_5 = (df["close"].iloc[-1] / df["close"].iloc[-5]) - 1
        mom_10 = (df["close"].iloc[-1] / df["close"].iloc[-10]) - 1
        mom_20 = (df["close"].iloc[-1] / df["close"].iloc[-20]) - 1

        if mom_5 > 0.01:
            votes["LONG"] += 1
            reasons.append(f"5D momentum: {mom_5*100:.1f}%")
        elif mom_5 < -0.01:
            votes["SHORT"] += 1
            reasons.append(f"5D momentum: {mom_5*100:.1f}%")

        if mom_10 > 0.02:
            votes["LONG"] += 1
            reasons.append(f"10D momentum: {mom_10*100:.1f}%")
        elif mom_10 < -0.02:
            votes["SHORT"] += 1
            reasons.append(f"10D momentum: {mom_10*100:.1f}%")

        if mom_20 > 0.03:
            votes["LONG"] += 1
        elif mom_20 < -0.03:
            votes["SHORT"] += 1

        total = sum(votes.values())
        if total == 0:
            return SchoolSignal("momentum", "NEUTRAL", 0.1, "No strong momentum")

        if votes["LONG"] > votes["SHORT"]:
            return SchoolSignal("momentum", "LONG", votes["LONG"] / max(total, 1), "; ".join(reasons[:2]))
        elif votes["SHORT"] > votes["LONG"]:
            return SchoolSignal("momentum", "SHORT", votes["SHORT"] / max(total, 1), "; ".join(reasons[:2]))

        return SchoolSignal("momentum", "NEUTRAL", 0, "Mixed momentum")

    def _volume_signal(self) -> SchoolSignal:
        """Generate signal from volume analysis."""
        df = self.df
        if "volume" not in df.columns or len(df) < 20:
            return SchoolSignal("volume", "NEUTRAL", 0, "No volume data")

        reasons = []
        conf = 0

        # Volume trend
        vol_avg_20 = df["volume"].rolling(20).mean().iloc[-1]
        vol_current = df["volume"].iloc[-1]
        vol_ratio = vol_current / vol_avg_20 if vol_avg_20 > 0 else 1

        if vol_ratio > 1.5:
            reasons.append(f"Volume surge ({vol_ratio:.1f}x avg)")
            conf += 0.3
        elif vol_ratio > 1.2:
            reasons.append(f"Above average volume ({vol_ratio:.1f}x)")
            conf += 0.2
        elif vol_ratio < 0.5:
            reasons.append(f"Low volume ({vol_ratio:.1f}x)")
            conf += 0.1

        # OBV trend
        if "OBV" in df.columns and len(df) > 10:
            obv_recent = df["OBV"].iloc[-1]
            obv_prev = df["OBV"].iloc[-10]
            if obv_recent > obv_prev:
                reasons.append("OBV rising - accumulation")
                conf += 0.25
            else:
                reasons.append("OBV falling - distribution")
                conf += 0.25

        # MFI
        if "MFI" in df.columns:
            mfi_val = df["MFI"].iloc[-1]
            if mfi_val > 80:
                reasons.append(f"MFI overbought ({mfi_val:.0f})")
                conf += 0.2
            elif mfi_val < 20:
                reasons.append(f"MFI oversold ({mfi_val:.0f})")
                conf += 0.2

        # Determine direction from price + volume
        direction = "NEUTRAL"
        if conf > 0.2:
            price_change = df["close"].iloc[-1] - df["close"].iloc[-5]
            direction = "LONG" if price_change > 0 else "SHORT"

        return SchoolSignal("volume", direction, min(conf, 1.0), "; ".join(reasons[:3]))

    def _reach_consensus(self) -> Dict:
        """Majority vote with confidence weighting."""
        valid_signals = [s for s in self.signals.values() if s.direction != "NEUTRAL"]

        if not valid_signals:
            return {
                "direction": "NEUTRAL",
                "confidence": 0,
                "agreeing_schools": 0,
                "total_schools": len(self.signals),
                "verdict": "NO CLEAR SIGNAL - Stay out or wait",
            }

        # Weighted vote
        long_weight = sum(s.confidence for s in valid_signals if s.direction == "LONG")
        short_weight = sum(s.confidence for s in valid_signals if s.direction == "SHORT")
        total_weight = long_weight + short_weight

        long_schools = sum(1 for s in valid_signals if s.direction == "LONG")
        short_schools = sum(1 for s in valid_signals if s.direction == "SHORT")

        if long_weight > short_weight:
            direction = "LONG"
            confidence = long_weight / max(total_weight, 1)
            agreeing = long_schools
        elif short_weight > long_weight:
            direction = "SHORT"
            confidence = short_weight / max(total_weight, 1)
            agreeing = short_schools
        else:
            direction = "NEUTRAL"
            confidence = 0
            agreeing = 0

        # Generate verdict
        if confidence > 0.7 and agreeing >= 3:
            verdict = f"STRONG {direction} - {agreeing} schools agree with high confidence"
        elif confidence > 0.5 and agreeing >= 2:
            verdict = f"MODERATE {direction} - {agreeing} schools agree"
        elif confidence > 0.3:
            verdict = f"WEAK {direction} - Low agreement, consider waiting"
        else:
            verdict = "NEUTRAL - Insufficient conviction"

        return {
            "direction": direction,
            "confidence": round(confidence, 4),
            "agreeing_schools": agreeing,
            "total_schools": len(self.signals),
            "long_schools": long_schools,
            "short_schools": short_schools,
            "long_weight": round(long_weight, 4),
            "short_weight": round(short_weight, 4),
            "verdict": verdict,
        }
