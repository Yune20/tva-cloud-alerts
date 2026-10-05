"""
Market Psychology Module

Classifies current market state into psychological zones using composite
scoring from multiple indicators. Detects market phases (Accumulation,
Markup, Distribution, Markdown) and provides sentiment labels.

Composite Fear/Greed Score (0-100):
  - RSI(14): 25%
  - MFI(14): 25%
  - ADX(14): 15%
  - Volatility regime: 15%
  - Volume trend: 10%
  - Price momentum: 10%

Zones: EXTREME_FEAR(0-20), FEAR(20-40), NEUTRAL(40-60), GREED(60-80), EXTREME_GREED(80-100)
Phases: ACCUMULATION, MARKUP, DISTRIBUTION, MARKDOWN
"""
import numpy as np
import pandas as pd


ZONES = {
    (0, 20): {"zone": "EXTREME_FEAR", "label_vi": "SỢ HÃI CỰC ĐỘ", "color": "#b71c1c", "emoji": "😱"},
    (20, 40): {"zone": "FEAR", "label_vi": "SỢ HÃI", "color": "#ef5350", "emoji": "😰"},
    (40, 60): {"zone": "NEUTRAL", "label_vi": "TRUNG TÍNH", "color": "#78909c", "emoji": "😐"},
    (60, 80): {"zone": "GREED", "label_vi": "THAM LAM", "color": "#66bb6a", "emoji": "贪婪"},
    (80, 100): {"zone": "EXTREME_GREED", "label_vi": "THAM LAM CỰC ĐỘ", "color": "#1b5e20", "emoji": "🤑"},
}

PHASES = {
    "ACCUMULATION": {"label_vi": "TÍCH LŨY", "desc": "Smart money mua dần, giá đi ngang", "color": "#42a5f5"},
    "MARKUP": {"label_vi": "TĂNG TRƯỞNG", "desc": "Xu hướng lên, volume tăng", "color": "#66bb6a"},
    "DISTRIBUTION": {"label_vi": "PHÂN PHỐI", "desc": "Smart money bán dần, giá đi ngang", "color": "#ffa726"},
    "MARKDOWN": {"label_vi": "GIẢM MẠNH", "desc": "Xu hướng xuống, panic selling", "color": "#ef5350"},
}


def _map_range(value, in_min, in_max, out_min=0, out_max=100):
    """Linearly map a value from one range to another, clamped."""
    if in_max == in_min:
        return (out_min + out_max) / 2
    mapped = (value - in_min) / (in_max - in_min) * (out_max - out_min) + out_min
    return max(out_min, min(out_max, mapped))


def _rsi_score(rsi):
    """RSI → 0-100 score. RSI 30→25, RSI 50→50, RSI 70→75."""
    return _map_range(rsi, 0, 100, 0, 100)


def _mfi_score(mfi):
    """MFI → 0-100 score. MFI 20→20, MFI 80→80."""
    return _map_range(mfi, 0, 100, 0, 100)


def _adx_score(adx):
    """ADX → 0-100. High ADX = strong trend = higher greed (direction-agnostic)."""
    if adx > 40:
        return 75
    elif adx > 25:
        return 65
    elif adx > 20:
        return 50
    else:
        return 35


def _volatility_score(vol_regime):
    """Volatility regime → 0-100. HIGH=fear, LOW=complacency."""
    return {"HIGH": 20, "NORMAL": 50, "LOW": 70}.get(vol_regime, 50)


def _volume_score(df):
    """Volume trend → 0-100. Increasing volume = conviction."""
    if len(df) < 20:
        return 50
    vol = df["volume"].values if "volume" in df.columns else df["Volume"].values if "Volume" in df.columns else None
    if vol is None:
        return 50
    recent = np.mean(vol[-5:])
    avg = np.mean(vol[-20:])
    if avg == 0:
        return 50
    ratio = recent / avg
    return min(100, max(0, _map_range(ratio, 0.3, 2.5, 0, 100)))


def _momentum_score(df):
    """Price momentum (10-bar ROC) → 0-100."""
    if len(df) < 11:
        return 50
    close = df["close"].values if "close" in df.columns else df["Close"].values
    roc = (close[-1] - close[-11]) / close[-11] * 100
    return min(100, max(0, _map_range(roc, -10, 10, 0, 100)))


def _detect_phase(df, signals):
    """Detect market phase from price structure + volume.
    
    Phases:
      ACCUMULATION: low vol, sideways, MFI rising, OBV rising
      MARKUP: trending up, volume increasing
      DISTRIBUTION: high vol, sideways, MFI falling, OBV falling
      MARKDOWN: trending down, volume spike
    """
    if len(df) < 20:
        return "NEUTRAL", "Không đủ dữ liệu"

    close = df["close"].values if "close" in df.columns else df["Close"].values
    vol = df["volume"].values if "volume" in df.columns else df["Volume"].values if "Volume" in df.columns else np.ones(len(df))

    # Price trend (20-bar linear regression slope)
    x = np.arange(20)
    slope = np.polyfit(x, close[-20:], 1)[0]
    price_trend = "UP" if slope > 0 else "DOWN" if slope < 0 else "FLAT"

    # Volatility (normalized)
    returns = np.diff(np.log(close[-21:]))
    vol_current = np.std(returns[-10:]) if len(returns) >= 10 else 0
    vol_avg = np.std(returns) if len(returns) > 0 else 1
    vol_ratio = vol_current / vol_avg if vol_avg > 0 else 1

    # Volume trend
    vol_recent = np.mean(vol[-5:])
    vol_avg_v = np.mean(vol[-20:])
    vol_trend = "INCREASING" if vol_recent > vol_avg_v * 1.1 else "DECREASING" if vol_recent < vol_avg_v * 0.9 else "FLAT"

    # Price range (sideways detection)
    high_20 = np.max(close[-20:])
    low_20 = np.min(close[-20:])
    range_pct = (high_20 - low_20) / low_20 * 100 if low_20 > 0 else 0
    sideways = range_pct < 3  # less than 3% range = sideways

    # OBV trend
    obv_signal = signals.get("OBV", "FLAT")

    # MFI trend
    mfi = signals.get("MFI", {})
    mfi_val = mfi.get("value", 50) if isinstance(mfi, dict) else 50

    # Phase classification
    if sideways and vol_ratio < 1.1:
        if obv_signal == "RISING" and price_trend != "DOWN":
            return "ACCUMULATION", "Giá đi ngang, OBV tăng — smart money tích lũy"
        elif obv_signal == "FALLING" and price_trend != "UP":
            return "DISTRIBUTION", "Giá đi ngang, OBV giảm — smart money phân phối"
        else:
            return "NEUTRAL", "Giá đi ngang, chờ breakout"
    elif price_trend == "UP" and vol_trend in ("INCREASING", "FLAT"):
        return "MARKUP", "Xu hướng tăng, volume ủng hộ"
    elif price_trend == "DOWN" and vol_ratio > 1.2:
        return "MARKDOWN", "Xu hướng giảm, volume cao — panic selling"
    elif price_trend == "UP":
        return "MARKUP", "Xu hướng tăng"
    elif price_trend == "DOWN":
        return "MARKDOWN", "Xu hướng giảm"
    else:
        return "NEUTRAL", "Chưa rõ phase"


def _get_signals_text(score, zone_info, phase, phase_desc, signals_detail):
    """Generate human-readable analysis text in Vietnamese."""
    lines = []
    z = zone_info
    lines.append(f"{z['emoji']} Tâm lý thị trường: {z['label_vi']} ({score:.0f}/100)")
    lines.append(f"📊 Phase: {PHASES.get(phase, {}).get('label_vi', phase)} — {phase_desc}")

    # Key driver signals
    if signals_detail:
        lines.append("Tín hiệu chính:")
        for s in signals_detail[:4]:
            lines.append(f"  • {s}")

    return lines


def analyze_psychology(df, signals=None):
    """Main entry point. Analyze market psychology from OHLCV data + indicators.
    
    Args:
        df: OHLCV DataFrame (must have close, volume columns)
        signals: dict from TechnicalAnalyzer.get_latest_signals() (optional)
    
    Returns:
        dict with: score, zone, zone_info, phase, phase_info, signals_detail, summary_vi
    """
    if signals is None:
        signals = {}

    # Extract indicator values
    rsi_val = 50
    mfi_val = 50
    adx_val = 20
    vol_regime = "NORMAL"

    if "RSI" in signals:
        r = signals["RSI"]
        rsi_val = r.get("value", 50) if isinstance(r, dict) else float(r) if r else 50

    if "MFI" in signals:
        m = signals["MFI"]
        mfi_val = m.get("value", 50) if isinstance(m, dict) else float(m) if m else 50

    if "ADX" in signals:
        a = signals["ADX"]
        adx_val = a.get("value", 20) if isinstance(a, dict) else float(a) if a else 20

    if "ATR" in signals:
        atr = signals["ATR"]
        atr_pct = (atr.get("value", 0) / (df["close"].iloc[-1] if "close" in df.columns else df["Close"].iloc[-1]) * 100) if isinstance(atr, dict) else 0
        vol_regime = "HIGH" if atr_pct > 2.0 else "LOW" if atr_pct < 0.5 else "NORMAL"

    # Compute component scores
    rsi_s = _rsi_score(rsi_val)
    mfi_s = _mfi_score(mfi_val)
    adx_s = _adx_score(adx_val)
    vol_s = _volatility_score(vol_regime)
    vol_trend_s = _volume_score(df)
    mom_s = _momentum_score(df)

    # Weighted composite
    score = (
        rsi_s * 0.25 +
        mfi_s * 0.25 +
        adx_s * 0.15 +
        vol_s * 0.15 +
        vol_trend_s * 0.10 +
        mom_s * 0.10
    )
    score = round(max(0, min(100, score)), 1)

    # Zone classification
    zone_info = ZONES[(0, 20)]  # default
    for (lo, hi), info in ZONES.items():
        if lo <= score < hi:
            zone_info = info
            break
    if score >= 100:
        zone_info = ZONES[(80, 100)]

    # Phase detection
    phase, phase_desc = _detect_phase(df, signals)
    phase_info = PHASES.get(phase, {"label_vi": phase, "desc": phase_desc, "color": "#78909c"})

    # Detailed signals
    signals_detail = []
    if rsi_val > 70:
        signals_detail.append(f"RSI overbought ({rsi_val:.0f}) — cảnh báo đỉnh")
    elif rsi_val < 30:
        signals_detail.append(f"RSI oversold ({rsi_val:.0f}) — cơ hội đáy")
    if mfi_val > 80:
        signals_detail.append(f"MFI overbought ({mfi_val:.0f}) — tiền vào quá nhiều")
    elif mfi_val < 20:
        signals_detail.append(f"MFI oversold ({mfi_val:.0f}) — tiền rút mạnh")
    if adx_val > 25:
        signals_detail.append(f"ADX mạnh ({adx_val:.0f}) — xu hướng rõ ràng")
    if vol_regime == "HIGH":
        signals_detail.append("Volatility cao — thận trọng, spread rộng")
    elif vol_regime == "LOW":
        signals_detail.append("Volatility thấp — chuẩn bị breakout")

    # RSI divergence
    rsi_div = signals.get("RSI_DIVERGENCE", {})
    if isinstance(rsi_div, dict) and rsi_div.get("type"):
        div_type = rsi_div["type"]
        if div_type == "BULLISH":
            signals_detail.append("Phân kỳ dương RSI — tiềm năng đảo chiều lên")
        elif div_type == "BEARISH":
            signals_detail.append("Phân kỳ âm RSI — tiềm năng đảo chiều xuống")

    # Summary
    summary_vi = _get_signals_text(score, zone_info, phase, phase_desc, signals_detail)

    return {
        "score": score,
        "zone": zone_info["zone"],
        "zone_info": zone_info,
        "phase": phase,
        "phase_info": phase_info,
        "phase_desc": phase_desc,
        "components": {
            "rsi_score": round(rsi_s, 1),
            "mfi_score": round(mfi_s, 1),
            "adx_score": round(adx_s, 1),
            "volatility_score": round(vol_s, 1),
            "volume_trend_score": round(vol_trend_s, 1),
            "momentum_score": round(mom_s, 1),
        },
        "signals_detail": signals_detail,
        "summary_vi": summary_vi,
    }
