#!/usr/bin/env python3
"""
Lightweight Cloud Alerts - runs on VPS with minimal dependencies.
Fetches market data, computes indicators, sends to Telegram bots.
Only requires: requests
"""
import os
import sys
import time
import json
import hmac
import hashlib
import urllib.parse
from datetime import datetime, timezone
import requests

# ─── CONFIG ───────────────────────────────────────────────────────────────────
CONFIG = {
    # Telegram Bots
    "bot1_token": os.getenv("BOT1_TOKEN", ""),
    "bot1_chat": os.getenv("BOT1_CHAT", ""),
    "bot2_token": os.getenv("BOT2_TOKEN", ""),
    "bot2_chat": os.getenv("BOT2_CHAT", ""),
    "bot3_token": os.getenv("BOT3_TOKEN", ""),
    "bot3_chat": os.getenv("BOT3_CHAT", ""),
    "bot4_token": os.getenv("BOT4_TOKEN", ""),
    "bot4_chat": os.getenv("BOT4_CHAT", ""),

    # Intervals (seconds)
    "analysis_interval": int(os.getenv("ANALYSIS_INTERVAL", "300")),  # 5 min
    "news_interval": int(os.getenv("NEWS_INTERVAL", "300")),  # 5 min
    "bot4_interval": int(os.getenv("BOT4_INTERVAL", "600")),  # chart+plan cadence
    # Per-run menu long-poll budget (seconds from process start). GitHub's
    # step runs `timeout 240 python cloud_alerts.py --once`, so keep this
    # below 225 to leave the kill window unused.
    "menu_poll_sec": int(os.getenv("MENU_POLL_SEC", "215")),

    # Priority symbols: (display_name, coingecko_id, yahoo_symbol, tv_symbol)
    "symbols": [
        ("Gold",      "pax-gold",   "GC=F",        "OANDA:XAUUSD"),
        ("USOIL",     None,         "CL=F",        "NYMEX:CL1!"),
        ("Bitcoin",   "bitcoin",    "BTC-USD",     "BINANCE:BTCUSDT"),
        ("Ethereum",  "ethereum",   "ETH-USD",     "BINANCE:ETHUSDT"),
        ("US30",      None,         "^DJI",        "TVC:DJI"),
        ("GBP/USD",   None,         "GBPUSD=X",    "FX:GBPUSD"),
        ("EUR/USD",   None,         "EURUSD=X",    "FX:EURUSD"),
        ("USD/JPY",   None,         "USDJPY=X",    "FX:USDJPY"),
        ("DXY",       None,         "DX-Y.NYB",    "TVC:DXY"),
        ("JPY Index", None,         "JPY=X",       "TVC:JPY"),
        ("US 10Y",    None,         "^TNX",        "TVC:US10Y"),
    ],

    # Extra symbols offered in the Telegram menu (display, yahoo, tv).
    # On-demand chart/plan only — not part of the periodic BOT1/BOT2 sweep.
    "menu_extra": [
        ("Silver",     "SI=F",    "TVC:SILVER"),
        ("S&P 500",    "^GSPC",   "TVC:SPX"),
        ("NASDAQ 100", "^NDX",    "TVC:NDX"),
        ("VIX",        "^VIX",    "TVC:VIX"),
        ("Brent",      "BZ=F",    "NYMEX:BRN1!"),
        ("AAPL",       "AAPL",    "NASDAQ:AAPL"),
        ("TSLA",       "TSLA",    "NASDAQ:TSLA"),
        ("NVDA",       "NVDA",    "NASDAQ:NVDA"),
    ],

    # Symbols BOT4 tracks when the user has not customized the menu yet
    "default_watch": ["Gold", "Bitcoin", "US30"],

    # News keywords (used for tagging; feeds are finance-specific so all new
    # items are sent even without a keyword match)
    "news_keywords": [
        "XAUUSD", "XAU", "GOLD", "DXY", "USD", "WTI", "OIL", "BRENT", "OPEC",
        "FED", "FOMC", "ECB", "BOJ", "BOE", "POWELL", "CPI", "PPI", "NFP",
        "JOBS", "UNEMPLOYMENT", "RATE", "RATES", "INFLATION", "GDP", "PCE",
        "RECESSION", "TARIFF", "TRADE", "STOCK", "STOCKS", "NASDAQ", "S&P",
        "DOW", "RALLY", "CRASH", "YIELD", "TREASURY", "BOND", "DOLLAR",
        "EURO", "POUND", "YEN", "BTC", "BITCOIN", "ETH", "ETHEREUM", "CRYPTO",
        "BANK", "BANKING", "EARNINGS", "MARKET", "ECONOMY", "ECONOMIC",
        "GROWTH", "DEBT", "ENERGY", "GAS", "SILVER", "COMMODITY", "FOREX",
        "CURRENCY", "STIMULUS", "SANCTIONS", "ETF", "FUTURES",
    ],
    "news_feeds": [
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://oilprice.com/rss/main",
        "https://www.investing.com/rss/news_1.rss",
        "https://www.investing.com/rss/news_25.rss",
        "https://www.investing.com/rss/news_14.rss",
        "https://www.fxstreet.com/rss/news",
        "https://www.forexlive.com/feed",
        "https://www.forexlive.com/feed/news",
        # Vietnamese sources + TradingView news (via Google News site queries —
        # cafef has native RSS; vietstock/TV have no working public RSS)
        "https://cafef.vn/home.rss",
        "https://news.google.com/rss/search?q=site%3Afinance.vietstock.vn&hl=vi&gl=VN&ceid=VN%3Avi",
        "https://news.google.com/rss/search?q=site%3Atradingview.com%2Fnews%20when%3A2d&hl=en&gl=US&ceid=US%3Aen",
    ],
}

# ─── STATE ────────────────────────────────────────────────────────────────────
state = {
    "last_analysis": 0,
    "last_news": 0,
    "seen_news": [],
    # Bot4 / menu state (persisted across GitHub Actions runs via state.json)
    "last_bot4": 0,
    "watch_symbols": [],          # user-selected symbols from the menu
    "sym_report_ts": {},          # per-symbol last chart+plan send (unix ts)
    "bot_chats": {},              # chat ids discovered via /start per bot key
    "tg_offsets": {},             # getUpdates offsets per bot key
}

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")


def load_state():
    """Load state from state.json so seen_news persists across runs (GitHub Actions)."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["seen_news"] = list(data.get("seen_news", []))
            state.update(data)
            print(f"Loaded state: {len(state['seen_news'])} seen news")
    except Exception as e:
        print(f"Failed to load state: {e}")


def save_state():
    """Save state to state.json (committed by GitHub Actions).

    Preserves extra keys such as chain_lease_until (workflow self-chain lease)
    so periodic saves never break the chain.
    """
    try:
        data = {
            k: v
            for k, v in state.items()
            if k not in ("last_analysis", "last_news", "seen_news")
        }
        data.update(
            {
                "last_analysis": state["last_analysis"],
                "last_news": state["last_news"],
                "seen_news": list(state["seen_news"])[-500:],
            }
        )
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Failed to save state: {e}")

# ─── DATA FETCHERS ────────────────────────────────────────────────────────────

def fetch_coingecko_ohlc(coin_id: str, vs_currency: str = "usd", days: int = 7):
    """Fetch OHLC from CoinGecko (free, no API key, works from US IPs)."""
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {"vs_currency": vs_currency, "days": days}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # CoinGecko returns [[timestamp, open, high, low, close], ...]
        if not data or len(data) < 30:
            print(f"CoinGecko insufficient data for {coin_id}: {len(data) if data else 0} points")
            return None
        return {
            "open": [float(c[1]) for c in data],
            "high": [float(c[2]) for c in data],
            "low": [float(c[3]) for c in data],
            "close": [float(c[4]) for c in data],
            "volume": [0] * len(data),  # CoinGecko OHLC doesn't include volume
        }
    except Exception as e:
        print(f"CoinGecko fetch error {coin_id}: {e}")
        return None


def fetch_yahoo_chart(symbol: str, interval: str = "1h", range_: str = "5d"):
    """Fetch OHLCV from Yahoo Finance chart API."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
        params = {"interval": interval, "range": range_}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        chart = data.get("chart", {})
        if chart.get("error"):
            print(f"Yahoo error for {symbol}: {chart['error']}")
            return None

        result = chart.get("result", [{}])[0]
        indicators = result.get("indicators", {}).get("quote", [{}])[0]

        opens = indicators.get("open", [])
        highs = indicators.get("high", [])
        lows = indicators.get("low", [])
        closes = indicators.get("close", [])
        volumes = indicators.get("volume", [])

        # Filter None values
        valid = [(o, h, l, c, v) for o, h, l, c, v in zip(opens, highs, lows, closes, volumes)
                 if o is not None and h is not None and l is not None and c is not None]

        if not valid:
            print(f"Yahoo no valid data for {symbol}")
            return None

        return {
            "open": [v[0] for v in valid],
            "high": [v[1] for v in valid],
            "low": [v[2] for v in valid],
            "close": [v[3] for v in valid],
            "volume": [v[4] or 0 for v in valid],
        }
    except Exception as e:
        print(f"Yahoo fetch error {symbol}: {e}")
        return None


# ─── INDICATORS (pure Python) ────────────────────────────────────────────────

def calc_ema(data: list, period: int):
    """Calculate EMA."""
    if len(data) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(data[:period]) / period
    for price in data[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


def calc_rsi(data: list, period: int = 14):
    """Calculate RSI."""
    if len(data) < period + 1:
        return None
    deltas = [data[i] - data[i-1] for i in range(1, len(data))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_macd(data: list, fast=12, slow=26, signal=9):
    """Calculate MACD line, signal line, histogram."""
    if len(data) < slow + signal:
        return None, None, None

    ema_fast = calc_ema(data, fast)
    ema_slow = calc_ema(data, slow)

    # Simplified - just get last values
    # For proper MACD we need full series, but this gives us the signal
    macd_line = ema_fast - ema_slow if ema_fast and ema_slow else None

    # Approximate signal as EMA of recent MACD values
    # For simplicity, use difference as signal indicator
    return macd_line, macd_line, macd_line  # placeholder


def calc_adx_simple(highs, lows, closes, period=14):
    """Simplified ADX calculation."""
    if len(closes) < period + 1:
        return None, None, None

    # Calculate +DM and -DM
    plus_dm = []
    minus_dm = []
    tr_list = []

    for i in range(1, len(closes)):
        high_diff = highs[i] - highs[i-1]
        low_diff = lows[i-1] - lows[i]

        plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0)
        minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0)

        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        tr_list.append(tr)

    # Smoothed averages
    atr = sum(tr_list[:period]) / period
    plus_di = 100 * (sum(plus_dm[:period]) / period / atr) if atr > 0 else 0
    minus_di = 100 * (sum(minus_dm[:period]) / period / atr) if atr > 0 else 0

    # DX and ADX
    if plus_di + minus_di == 0:
        dx = 0
    else:
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

    adx = dx  # Simplified

    return adx, plus_di, minus_di


# ─── ANALYSIS ─────────────────────────────────────────────────────────────────

def compute_analysis(name: str, tv_symbol: str, data: dict):
    """Compute all analysis values for a symbol. Returns a dict (or None).

    Shared by format_analysis (BOT1 classic text), build_detailed_plan
    (BOT4 detailed plan) and render_chart_png (BOT4 chart levels).
    """
    if not data or len(data.get("close", [])) < 30:
        return None

    closes = data["close"]
    highs = data["high"]
    lows = data["low"]

    price = closes[-1]
    prev = closes[-2] if len(closes) >= 2 else price
    chg = ((price - prev) / prev * 100) if prev > 0 else 0
    icon = "🟢" if chg >= 0 else "🔴"

    # Indicators
    ema21 = calc_ema(closes, 21)
    ema50 = calc_ema(closes, 50)
    rsi = calc_rsi(closes, 14)
    adx, plus_di, minus_di = calc_adx_simple(highs, lows, closes, 14)

    # Trend
    if ema21 and ema50:
        if price > ema21 > ema50:
            trend = "🟢 TĂNG"
            trend_dir = "LONG"
        elif price < ema21 < ema50:
            trend = "🔴 GIẢM"
            trend_dir = "SHORT"
        else:
            trend = "🟡 ĐI NGANG"
            trend_dir = "NEUTRAL"
    else:
        trend = "🟡 ĐI NGANG"
        trend_dir = "NEUTRAL"

    # MACD
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    macd_sig = "CHUYỂN"
    macd_hist = 0
    if ema12 and ema26:
        macd_hist = ema12 - ema26
        if macd_hist > 0:
            macd_sig = "BULL ✅"
        else:
            macd_sig = "BEAR ❌"

    # ADX strength
    adx_val = adx if adx else 0
    adx_sig = "MẠNH 💪" if adx_val > 25 else "YẾU ⚠️"

    # Support/Resistance (pivot points)
    recent_high = max(highs[-20:]) if len(highs) >= 20 else max(highs)
    recent_low = min(lows[-20:]) if len(lows) >= 20 else min(lows)
    pivot = (recent_high + recent_low + price) / 3
    r1 = 2 * pivot - recent_low
    s1 = 2 * pivot - recent_high
    r2 = pivot + (recent_high - recent_low)
    s2 = pivot - (recent_high - recent_low)

    # ATR for SL/TP calculation
    tr_list = []
    for i in range(1, min(20, len(closes))):
        tr = max(
            highs[-i] - lows[-i],
            abs(highs[-i] - closes[-i-1]),
            abs(lows[-i] - closes[-i-1])
        )
        tr_list.append(tr)
    atr = sum(tr_list) / len(tr_list) if tr_list else price * 0.005

    # Entry/SL/TP based on trend
    if trend_dir == "LONG":
        entry = s1  # Buy at support
        sl = entry - 1.5 * atr  # SL below support
        tp1 = r1  # TP at resistance
        tp2 = r2
        action = "🟢 MUA (LONG)"
        reason = f"Giá trên EMA21 > EMA50, hỗ trợ tại {s1:,.2f}"
    elif trend_dir == "SHORT":
        entry = r1  # Sell at resistance
        sl = entry + 1.5 * atr  # SL above resistance
        tp1 = s1  # TP at support
        tp2 = s2
        action = "🔴 BÁN (SHORT)"
        reason = f"Giá dưới EMA21 < EMA50, kháng cự tại {r1:,.2f}"
    else:
        entry = price
        sl = price - 1.5 * atr
        tp1 = r1
        tp2 = s1
        action = "🟡 ĐỨNG NGOÀI"
        reason = "Chưa có xu hướng rõ ràng"

    # Risk/Reward
    if entry != sl:
        risk = abs(entry - sl)
        reward1 = abs(tp1 - entry)
        rr1 = reward1 / risk if risk > 0 else 0
    else:
        rr1 = 0

    # Psychology
    if rsi:
        if rsi < 30:
            psyc = "QUÁ BÁN 🟢"
        elif rsi < 40:
            psyc = "SỢ HẠI"
        elif rsi < 60:
            psyc = "TRUNG TÍNH"
        elif rsi < 70:
            psyc = "THAM LAM"
        else:
            psyc = "QUÁ MUA 🔴"
    else:
        psyc = "N/A"

    # Signal strength score (0-100)
    score = 0
    if trend_dir != "NEUTRAL": score += 25
    if macd_hist > 0 and trend_dir == "LONG": score += 20
    if macd_hist < 0 and trend_dir == "SHORT": score += 20
    if adx_val > 25: score += 20
    if rsi and 30 < rsi < 70: score += 15
    if rr1 >= 2: score += 20

    signal_strength = "🟢 MẠNH" if score >= 70 else "🟡 TRUNG BÌNH" if score >= 40 else "🔴 YẾU"

    # Format prices
    def fmt_p(p):
        return f"{p:,.4f}" if p < 100 else f"{p:,.2f}"

    return {
        "name": name,
        "tv_symbol": tv_symbol,
        "price": price,
        "chg": chg,
        "icon": icon,
        "ema21": ema21,
        "ema50": ema50,
        "rsi": rsi,
        "adx_val": adx_val,
        "adx_sig": adx_sig,
        "plus_di": plus_di,
        "minus_di": minus_di,
        "trend": trend,
        "trend_dir": trend_dir,
        "macd_sig": macd_sig,
        "macd_hist": macd_hist,
        "recent_high": recent_high,
        "recent_low": recent_low,
        "pivot": pivot,
        "r1": r1,
        "r2": r2,
        "s1": s1,
        "s2": s2,
        "atr": atr,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "action": action,
        "reason": reason,
        "rr1": rr1,
        "psyc": psyc,
        "score": score,
        "signal_strength": signal_strength,
        "fmt_p": fmt_p,
    }


def format_analysis(d: dict) -> str:
    """Format the analysis dict into the classic BOT1 Markdown text.

    Output is byte-identical to the original analyze_symbol() text.
    """
    fmt_p = d["fmt_p"]
    name = d["name"]
    tv_symbol = d["tv_symbol"]
    price = d["price"]
    chg = d["chg"]
    icon = d["icon"]
    ema21 = d["ema21"]
    ema50 = d["ema50"]
    rsi = d["rsi"]
    adx_val = d["adx_val"]
    adx_sig = d["adx_sig"]
    trend = d["trend"]
    macd_sig = d["macd_sig"]
    psyc = d["psyc"]
    r1, r2, s1, s2, atr = d["r1"], d["r2"], d["s1"], d["s2"], d["atr"]
    entry, sl, tp1, tp2 = d["entry"], d["sl"], d["tp1"], d["tp2"]
    action, reason, rr1 = d["action"], d["reason"], d["rr1"]
    score, signal_strength = d["score"], d["signal_strength"]

    lines = [
        f"*{name}* ({tv_symbol})",
        f"━━━━━━━━━━━━━━━━━━",
        f"💰 Giá: `{fmt_p(price)}` {icon} {chg:+.2f}%",
        f"",
        f"📊 *CHỈ BÁO KỸ THUẬT*",
        f"  • EMA21: `{fmt_p(ema21)}` | EMA50: `{fmt_p(ema50)}`" if ema21 and ema50 else "",
        f"  • RSI: `{rsi:.1f}` | MACD: {macd_sig} | ADX: `{adx_val:.0f}` ({adx_sig})" if rsi else "",
        f"  • Xu hướng: {trend}",
        f"  • Tâm lý: {psyc}",
        f"",
        f"📈 *VÙNG GIÁ*",
        f"  • Kháng cự R1: `{fmt_p(r1)}` | R2: `{fmt_p(r2)}`",
        f"  • Hỗ trợ S1: `{fmt_p(s1)}` | S2: `{fmt_p(s2)}`",
        f"  • ATR: `{fmt_p(atr)}`",
        f"",
        f"🎯 *GIAO DỊCH*",
        f"  • Hướng: {action}",
        f"  • Lý do: {reason}",
        f"  • Entry: `{fmt_p(entry)}`",
        f"  • Stop Loss: `{fmt_p(sl)}`",
        f"  • Take Profit 1: `{fmt_p(tp1)}`",
        f"  • Take Profit 2: `{fmt_p(tp2)}`",
        f"  • Risk/Reward: `1:{rr1:.1f}`",
        f"",
        f"⚡ *TÍN HIỆU*: {signal_strength} ({score}/100)",
        "",
    ]
    # Remove empty lines
    lines = [l for l in lines if l != ""]
    return "\n".join(lines)


def analyze_symbol(name: str, tv_symbol: str, data: dict):
    """Analyze a symbol with detailed trading plan (classic BOT1 text)."""
    d = compute_analysis(name, tv_symbol, data)
    return format_analysis(d) if d else None


def build_detailed_plan(name: str, tv_symbol: str, data: dict):
    """BOT4: comprehensive trading plan (dict + formatted text).

    Returns (details_dict, plan_text) or (None, None).
    """
    d = compute_analysis(name, tv_symbol, data)
    if not d:
        return None, None
    fmt = d["fmt_p"]
    bars = len(data["close"])

    # RSI zone wording for the momentum block
    rsi = d["rsi"]
    if rsi is None:
        rsi_zone = "N/A"
    elif rsi < 30:
        rsi_zone = "quá bán — vùng phản ứng tăng"
    elif rsi < 45:
        rsi_zone = "yếu, nghiêng bán"
    elif rsi < 55:
        rsi_zone = "trung tính — chưa cóedge"
    elif rsi < 70:
        rsi_zone = "mạnh, nghiêng mua"
    else:
        rsi_zone = "quá mua — cảnh báo điều chỉnh"

    # Scenarios depend on the active trend
    if d["trend_dir"] == "LONG":
        scenario = (
            f"• *Tiếp diễn:* giữ trên `{fmt(d['s1'])}` → hướng R1 `{fmt(d['r1'])}`, xa hơn R2 `{fmt(d['r2'])}`\n"
            f"• *Phá kháng cự:* đóng nến 1H trên `{fmt(d['r1'])}` → momentum tăng, target R2\n"
            f"• *Hủy setup:* mất `{fmt(d['s1'])}` (đặc biệt `{fmt(d['s2'])}`) → chuyển trung tính, đứng ngoài"
        )
    elif d["trend_dir"] == "SHORT":
        scenario = (
            f"• *Tiếp diễn:* giữ dưới `{fmt(d['r1'])}` → hướng S1 `{fmt(d['s1'])}`, xa hơn S2 `{fmt(d['s2'])}`\n"
            f"• *Phá hỗ trợ:* đóng nến 1H dưới `{fmt(d['s1'])}` → momentum giảm, target S2\n"
            f"• *Hủy setup:* vượt `{fmt(d['r1'])}` (đặc biệt `{fmt(d['r2'])}`) → chuyển trung tính, đứng ngoài"
        )
    else:
        scenario = (
            f"• *Biên:* dao động `{fmt(d['s1'])}` – `{fmt(d['r1'])}`, chưa có lệnh\n"
            f"• *Mua.breakout:* đóng nến 1H trên `{fmt(d['r1'])}` → target `{fmt(d['r2'])}`\n"
            f"• *Bán.breakdown:* đóng nến 1H dưới `{fmt(d['s1'])}` → target `{fmt(d['s2'])}`"
        )

    now = datetime.now(timezone.utc).strftime("%H:%M %d/%m/%Y")
    lines = [
        f"📋 *PLAN GIAO DỊCH CHI TIẾT*",
        f"*{name}* ({d['tv_symbol']}) · Khung 1H · {bars} nến",
        f"⏰ {now} UTC",
        f"━━━━━━━━━━━━━━━━━━",
        f"💰 Giá: `{fmt(d['price'])}` {d['icon']} {d['chg']:+.2f}%",
        f"🧭 Xu hướng: {d['trend']} | Điểm tín hiệu: `{d['score']}/100` {d['signal_strength']}",
        f"",
        f"📊 *ĐỘNG LƯỢNG*",
        f"  • RSI(14): `{rsi:.1f}` — {rsi_zone}" if rsi else "  • RSI(14): N/A",
        f"  • MACD: {d['macd_sig']} (hist `{d['macd_hist']:+.4f}`)",
        f"  • ADX: `{d['adx_val']:.0f}` ({d['adx_sig']}) | DI+: `{d['plus_di']:.0f}` | DI-: `{d['minus_di']:.0f}`",
        f"  • Tâm lý: {d['psyc']}",
        f"",
        f"📐 *VÙNG GIÁ (pivot 20 nến)*",
        f"  • R2 `{fmt(d['r2'])}` — R1 `{fmt(d['r1'])}` — pivot `{fmt(d['pivot'])}`",
        f"  • S1 `{fmt(d['s1'])}` — S2 `{fmt(d['s2'])}` | ATR `{fmt(d['atr'])}`",
        f"",
        f"🎯 *KẾ HOẠCH VÀO LỆNH*",
        f"  • Hướng: {d['action']}",
        f"  • Entry: `{fmt(d['entry'])}` ({d['reason']})",
        f"  • Stop Loss: `{fmt(d['sl'])}` (1.5×ATR)",
        f"  • Take Profit 1: `{fmt(d['tp1'])}`",
        f"  • Take Profit 2: `{fmt(d['tp2'])}`",
        f"  • Risk/Reward: `1:{d['rr1']:.1f}`",
        f"",
        f"🧩 *KỊCH BẢN*",
        scenario,
        f"",
        f"✅ *CHECKLIST*",
        f"  1. Chờ giá chạm vùng entry, không FOMO đuổi giá",
        f"  2. RSI chưa ở vùng cực trị ({rsi_zone})",
        f"  3. Cắt lỗ đúng SL tại `{fmt(d['sl'])}`, không kéo SL",
        f"  4. Rủi ro tối đa 1–2% vốn/lệnh",
        f"  5. Hủy lệnh nếu kịch bản Hủy setup kích hoạt",
        f"",
        f"⚠️ Phân tích tự động 1H — không phải tư vấn đầu tư.",
    ]
    return d, "\n".join(lines)


# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def send_telegram(token: str, chat_id: str, text: str, parse_mode: str = "Markdown"):
    """Send message via Telegram Bot API. Handles long messages by splitting."""
    if not token or not chat_id:
        print(f"  Telegram: missing token/chat_id (token={bool(token)}, chat={bool(chat_id)})")
        return False

    # Telegram limit is 4096 chars
    MAX_LEN = 4000

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        # Split if too long
        if len(text) > MAX_LEN:
            print(f"  Message too long ({len(text)} chars), splitting...")
            parts = []
            current = ""
            for line in text.split("\n"):
                if len(current) + len(line) + 1 > MAX_LEN:
                    parts.append(current)
                    current = line
                else:
                    current = current + "\n" + line if current else line
            if current:
                parts.append(current)

            all_ok = True
            for i, part in enumerate(parts, 1):
                payload = {"chat_id": chat_id, "text": part}
                if parse_mode:
                    payload["parse_mode"] = parse_mode
                resp = requests.post(url, json=payload, timeout=15)
                data = resp.json()
                if not data.get("ok"):
                    print(f"  Telegram part {i}/{len(parts)} error: {data.get('error_code')}: {data.get('description')}")
                    # Retry as plain text (key must be omitted, not null)
                    payload.pop("parse_mode", None)
                    resp2 = requests.post(url, json=payload, timeout=15)
                    data2 = resp2.json()
                    if not data2.get("ok"):
                        all_ok = False
                        print(f"  Telegram part {i}/{len(parts)} retry failed: {data2.get('error_code')}")
            return all_ok

        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if not data.get("ok"):
            print(f"  Telegram API error: {data.get('error_code')}: {data.get('description')}")
            # Retry as plain text (key must be omitted, not null)
            if parse_mode:
                payload.pop("parse_mode", None)
                resp2 = requests.post(url, json=payload, timeout=15)
                data2 = resp2.json()
                if data2.get("ok"):
                    return True
                print(f"  Telegram retry also failed: {data2.get('error_code')}: {data2.get('description')}")
            return False
        return True
    except Exception as e:
        print(f"Telegram send error: {e}")
        return False


# ─── BOT4: CHARTS, DETAILED PLANS, MENU ──────────────────────────────────────

MENU_TEXT = (
    "📋 MENU TÍN HIỆU\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "Chạm vào mã để CHỌN hoặc BỎ theo dõi:\n"
    "▫️ chưa chọn   ✅ đang theo dõi\n\n"
    "Mã đã ✅: BOT4 gửi BIỂU ĐỒ + PLAN phân tích chi tiết\n"
    "cho mã đó định kỳ (~10 phút) và gửi ngay khi bạn chọn.\n"
    "Chạm «📩 Gửi ngay» để nhận lại tất cả mã ✅.\n\n"
    "💬 Gõ /menu để mở lại bảng này."
)


def menu_entries():
    """(name, coingecko_id|None, yahoo, tv) for every symbol in the menu."""
    entries = [(n, cg, y, tv) for (n, cg, y, tv) in CONFIG["symbols"]]
    entries += [(n, None, y, tv) for (n, y, tv) in CONFIG["menu_extra"]]
    return entries


def find_menu_entry(name):
    for e in menu_entries():
        if e[0] == name:
            return e
    return None


def menu_keyboard():
    """Inline keyboard: each symbol button toggles its watch state."""
    watch = set(state.get("watch_symbols") or [])
    rows = []
    row = []
    for name, *_ in menu_entries():
        mark = "✅ " if name in watch else "▫️ "
        row.append({"text": mark + name, "callback_data": f"m:{name}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "📩 Gửi ngay các mã ✅", "callback_data": "m:!now"}])
    return {"inline_keyboard": rows}


def render_chart_png(name: str, tv_symbol: str, data: dict, details: dict = None):
    """Dark-theme candlestick chart (PNG bytes) for Telegram sendPhoto.

    Returns bytes, or None when matplotlib is unavailable / render fails.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
        import io
    except Exception as e:
        print(f"  Chart skip (matplotlib unavailable): {e}")
        return None

    try:
        n = min(80, len(data["close"]))
        o = data["open"][-n:]
        h = data["high"][-n:]
        l = data["low"][-n:]
        c = data["close"][-n:]
        vol = data.get("volume") or []
        v = vol[-n:] if len(vol) >= n else [0] * n
        xs = list(range(n))

        BG, GRID, UP, DOWN = "#0e1117", "#2a2e39", "#26a69a", "#ef5350"
        EMA21C, EMA50C = "#f0b90b", "#e040fb"

        fig, (ax, axv) = plt.subplots(
            2, 1, figsize=(10, 6.2), sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},
        )
        fig.patch.set_facecolor(BG)
        for a in (ax, axv):
            a.set_facecolor(BG)
            a.grid(True, color=GRID, linewidth=0.5, alpha=0.6)
            for s in a.spines.values():
                s.set_color(GRID)
            a.tick_params(colors="#9aa0aa", labelsize=8)

        for i in xs:
            col = UP if c[i] >= o[i] else DOWN
            ax.vlines(i, l[i], h[i], color=col, linewidth=0.9, zorder=2)
            lo, hi = min(o[i], c[i]), max(o[i], c[i])
            body = max(hi - lo, (h[i] - l[i]) * 0.003)  # keep dojis visible
            ax.add_patch(Rectangle((i - 0.35, lo), 0.7, body,
                                   facecolor=col, edgecolor=col, zorder=3))

        ax.plot(xs, _ema_series(c, 21), color=EMA21C, linewidth=1.2, label="EMA21")
        ax.plot(xs, _ema_series(c, 50), color=EMA50C, linewidth=1.2, label="EMA50")

        if details:
            w_lo, w_hi = min(l), max(h)
            for lv, lab, col in ((details["r1"], "R1", DOWN),
                                 (details["s1"], "S1", UP)):
                if w_lo * 0.99 < lv < w_hi * 1.01:
                    ax.axhline(lv, color=col, linestyle="--", linewidth=0.9, alpha=0.85)
                    ax.text(0.5, lv, f" {lab} ", color=col, fontsize=8,
                            va="center", ha="left",
                            transform=ax.get_yaxis_transform())

        price = c[-1]
        chg = ((c[-1] - c[0]) / c[0] * 100) if c[0] else 0
        ax.set_title(
            f"{name} · 1H · {tv_symbol}    {price:,.2f} ({chg:+.2f}% · {n} bars)",
            color="#e6e9ef", fontsize=11, loc="left",
        )
        ax.legend(loc="upper left", fontsize=8, facecolor=BG,
                  edgecolor=GRID, labelcolor="#e6e9ef")
        ax.set_xlim(-1, n)

        vols = [UP if c[i] >= o[i] else DOWN for i in xs]
        axv.bar(xs, v, color=vols, width=0.7, alpha=0.75)
        axv.set_ylabel("Vol", color="#9aa0aa", fontsize=8)

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, facecolor=BG)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"  Chart render error: {e}")
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def _ema_series(vals, period):
    """EMA over a full series (chart overlay); None until warm-up completes."""
    if len(vals) < period:
        return [None] * len(vals)
    k = 2 / (period + 1)
    out = [None] * (period - 1)
    e = sum(vals[:period]) / period
    out.append(e)
    for v in vals[period:]:
        e = (v - e) * k + e
        out.append(e)
    return out


def send_telegram_photo(token: str, chat_id: str, photo_bytes: bytes, caption: str = ""):
    """Send a photo to Telegram (BOT4 charts)."""
    if not token or not chat_id:
        print(f"  Photo skip (token={bool(token)}, chat={bool(chat_id)})")
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload = {"chat_id": chat_id}
        if caption:
            payload["caption"] = caption[:1020]
        resp = requests.post(
            url, data=payload,
            files={"photo": ("chart.png", photo_bytes, "image/png")},
            timeout=30,
        )
        data = resp.json()
        if not data.get("ok"):
            print(f"  Photo API error: {data.get('error_code')}: {data.get('description')}")
            return False
        return True
    except Exception as e:
        print(f"  Photo send error: {e}")
        return False


def _tg_api(token: str, method: str, **params):
    """POST a Telegram Bot API method; returns parsed JSON ({} on error)."""
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/{method}",
            data=params, timeout=15,
        )
        return resp.json()
    except Exception as e:
        print(f"  TG {method} error: {e}")
        return {}


def send_symbol_report(token: str, chat, entry, force: bool = False) -> bool:
    """BOT4 report for one symbol: chart photo + detailed plan text."""
    name, cg, yahoo, tv = entry
    now = time.time()
    if not force:
        last = float((state.get("sym_report_ts") or {}).get(name, 0) or 0)
        if now - last < 900:
            print(f"  Report skip {name}: sent {int(now - last)}s ago (< 900s)")
            return False

    data = None
    if cg:
        data = fetch_coingecko_ohlc(cg, "usd", 7)
    if not data and yahoo:
        data = fetch_yahoo_chart(yahoo, "1h", "5d")
    if not data:
        print(f"  Report: no data for {name}")
        return False

    d, plan = build_detailed_plan(name, tv, data)
    if not plan or not d:
        print(f"  Report: analysis failed for {name}")
        return False

    chart = render_chart_png(name, tv, data, d)
    photo_ok = False
    if chart:
        caption = f"{name} · 1H · {d['price']:,.2f} {d['icon']} {d['chg']:+.2f}%"
        photo_ok = send_telegram_photo(token, chat, chart, caption)
    text_ok = send_telegram(token, chat, plan)
    print(f"  Report {name}: chart={'OK' if photo_ok else 'no'} plan={'OK' if text_ok else 'FAIL'}")
    if photo_ok or text_ok:
        state.setdefault("sym_report_ts", {})[name] = time.time()
        return True
    return False


def bot4_chats():
    """Chat ids BOT4 can post to: BOT4_CHAT env + /start discovery."""
    chats = []
    if CONFIG["bot4_chat"]:
        chats.append(str(CONFIG["bot4_chat"]))
    chats += [str(c) for c in (state.get("bot_chats") or {}).get("bot4", [])]
    out, seen = [], set()
    for c in chats:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def run_bot4():
    """Periodic BOT4: chart + detailed plan for the watched symbols."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Running bot4 chart/plan...")
    if not CONFIG["bot4_token"]:
        print("  BOT4_TOKEN not configured - skip")
        return
    chats = bot4_chats()
    if not chats:
        print("  Bot4: no chat yet - send /start to @Bantintaichinh25j_bot first")
        state["last_bot4"] = time.time()
        save_state()
        return
    watch = list(state.get("watch_symbols") or []) or list(CONFIG["default_watch"])
    watch = [n for n in watch if find_menu_entry(n)]
    if not watch:
        print("  Bot4: empty watch list - skip")
        state["last_bot4"] = time.time()
        save_state()
        return

    # Rotate the start symbol each interval so >2 watched symbols all get
    # covered within a few cycles (max 2 full reports per run).
    offset = int(time.time() // max(CONFIG["bot4_interval"], 1)) % len(watch)
    ordered = watch[offset:] + watch[:offset]
    sent = 0
    for name in ordered:
        if sent >= 2:
            break
        if send_symbol_report(CONFIG["bot4_token"], chats[0], find_menu_entry(name)):
            sent += 1
    print(f"  Bot4: {sent} report(s) sent, watch={watch}")
    state["last_bot4"] = time.time()
    save_state()


def _report_token(src_key: str, src_token: str, chat: str) -> str:
    """Prefer BOT4 for chart/plan replies when bot4 knows this chat."""
    if CONFIG["bot4_token"] and chat:
        known = [str(c) for c in (state.get("bot_chats") or {}).get("bot4", [])]
        if chat in known or chat == str(CONFIG["bot4_chat"]):
            return CONFIG["bot4_token"]
    return src_token


def _edit_menu(token: str, cb: dict):
    """Refresh the inline keyboard in place after a toggle."""
    msg = cb.get("message") or {}
    mid = msg.get("message_id")
    chat = str((msg.get("chat") or {}).get("id") or "")
    if not mid or not chat:
        return
    _tg_api(token, "editMessageText", chat_id=chat, message_id=mid,
            text=MENU_TEXT, reply_markup=json.dumps(menu_keyboard()))


def menu_update_handler(key: str, token: str, upd: dict):
    """Handle /menu commands and menu callback queries for one bot."""
    msg = upd.get("message") or {}
    chat = str((msg.get("chat") or {}).get("id") or "")
    text = (msg.get("text") or "").strip()

    if text in ("/start", "/menu", "/help", "menu"):
        if chat:
            chats = state.setdefault("bot_chats", {}).setdefault(key, [])
            if chat not in chats:
                chats.append(chat)
                save_state()
            if key == "bot4":
                print(f"  Bot4 chat discovered: {chat}")
        _tg_api(token, "sendMessage", chat_id=chat, text=MENU_TEXT,
                reply_markup=json.dumps(menu_keyboard()))
        return

    cb = upd.get("callback_query")
    if not cb:
        return
    data = cb.get("data") or ""
    cb_id = cb.get("id") or ""
    cb_msg = cb.get("message") or {}
    cb_chat = str((cb_msg.get("chat") or {}).get("id") or chat)
    if not data.startswith("m:"):
        if cb_id:
            _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id)
        return
    pick = data[2:]
    watch = list(state.get("watch_symbols") or [])

    if pick == "!now":
        if not watch:
            if cb_id:
                _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                        text="Bạn chưa chọn mã nào - chạm một mã để ✅", show_alert=True)
            return
        if cb_id:
            _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                    text="Đang gửi biểu đồ + plan...")
        rtoken = _report_token(key, token, cb_chat)
        for name in watch[:4]:
            e = find_menu_entry(name)
            if e:
                send_symbol_report(rtoken, cb_chat, e, force=True)
        _edit_menu(token, cb)
        return

    if pick not in [e[0] for e in menu_entries()]:
        return

    if pick in watch:
        watch.remove(pick)
        note = f"Đã bỏ theo dõi {pick}"
    else:
        watch.append(pick)
        note = f"Đang theo dõi {pick} - đang gửi báo cáo..."
    state["watch_symbols"] = watch
    save_state()
    _edit_menu(token, cb)
    if cb_id:
        _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id, text=note)
    if pick in watch:
        e = find_menu_entry(pick)
        if e:
            rtoken = _report_token(key, token, cb_chat)
            send_symbol_report(rtoken, cb_chat, e, force=True)


def poll_menu(deadline: float):
    """Long-poll getUpdates on every configured bot until `deadline` (unix ts).

    Answers /menu commands and inline-keyboard taps. GitHub Actions runs this
    every ~5 min so taps are typically answered within a minute. Concurrent
    runs collide with HTTP 409 (Telegram allows one getUpdates consumer per
    bot) - we back off briefly; no updates are lost because offsets advance
    only for updates we actually received.
    """
    bots = [(k, t) for k, t in [
        ("bot1", CONFIG["bot1_token"]),
        ("bot2", CONFIG["bot2_token"]),
        ("bot3", CONFIG["bot3_token"]),
        ("bot4", CONFIG["bot4_token"]),
    ] if t]
    if not bots:
        print("Menu poll: no bot tokens configured")
        return
    offsets = state.setdefault("tg_offsets", {})
    print(f"Menu poll: {len(bots)} bot(s), budget {max(0, int(deadline - time.time()))}s")
    while time.time() < deadline:
        for key, token in bots:
            if time.time() >= deadline:
                break
            off = int(offsets.get(key, 0) or 0)
            try:
                resp = requests.get(
                    f"https://api.telegram.org/bot{token}/getUpdates",
                    params={"timeout": 20, "offset": off},
                    timeout=28,
                )
            except Exception as e:
                print(f"  Poll {key} error: {e}")
                time.sleep(3)
                continue
            if resp.status_code == 409:
                print(f"  Poll {key}: 409 conflict (another poller active), pause 15s")
                time.sleep(15)
                continue
            if not resp.ok:
                print(f"  Poll {key}: HTTP {resp.status_code}")
                time.sleep(5)
                continue
            try:
                updates = resp.json().get("result", [])
            except Exception:
                updates = []
            if not updates:
                continue
            print(f"  Poll {key}: {len(updates)} update(s)")
            for upd in updates:
                offsets[key] = int(upd.get("update_id", 0)) + 1
                try:
                    menu_update_handler(key, token, upd)
                except Exception as e:
                    print(f"  Menu handler {key} error: {e}")
                save_state()
    print("Menu poll: done")


# ─── NEWS ─────────────────────────────────────────────────────────────────────

# English -> Vietnamese dictionary for common financial terms
VI_DICT = {
    "fed": "Fed (Cục Dự trữ Liên bang)",
    "fomc": "FOMC",
    "cpi": "CPI (chỉ số giá tiêu dùng)",
    "nfp": "NFP (bảng lương phi nông nghiệp)",
    "inflation": "lạm phát",
    "interest rate": "lãi suất",
    "recession": "suy thoái",
    "recession fears": "nỗi lo suy thoái",
    "rate hike": "tăng lãi suất",
    "rate cut": "giảm lãi suất",
    "hawkish": "diều hâu",
    "dovish": "bồ câu",
    "gold": "vàng",
    "oil": "dầu",
    "crude": "dầu thô",
    "wti": "dầu WTI",
    "brent": "dầu Brent",
    "bitcoin": "Bitcoin",
    "btc": "Bitcoin",
    "ethereum": "Ethereum",
    "eth": "Ethereum",
    "crypto": "tiền điện tử",
    "dollar": "đô la",
    "usd": "USD",
    "euro": "euro",
    "eur": "EUR",
    "pound": "bảng Anh",
    "gbp": "GBP",
    "yen": "yên Nhật",
    "jpy": "JPY",
    "yuan": "nhân dân tệ",
    "stocks": "cổ phiếu",
    "stock market": "thị trường chứng khoán",
    "wall street": "Phố Wall",
    "nasdaq": "Nasdaq",
    "sp 500": "S&P 500",
    "dow jones": "Dow Jones",
    "rally": "đà tăng",
    "surge": "tăng mạnh",
    "plunge": "sụt giảm mạnh",
    "rally rally": "đà tăng",
    "gain": "tăng",
    "fall": "giảm",
    "drop": "giảm",
    "rises": "tăng",
    "falls": "giảm",
    "climbs": "tăng",
    "slides": "giảm",
    "jumps": "tăng vọt",
    "tumbles": "sụp đổ",
    "soars": "bay cao",
    "sinks": "chìm xuống",
    "hikes": "tăng",
    "cuts": "giảm",
    "holds": "giữ nguyên",
    "pauses": "tạm dừng",
    "signals": " tín hiệu",
    "warns": "cảnh báo",
    "says": "cho biết",
    "report": "báo cáo",
    "data": "dữ liệu",
    "jobs": "việc làm",
    "employment": "việc làm",
    "unemployment": "thất nghiệp",
    "growth": "tăng trưởng",
    "gdp": "GDP",
    "economy": "kinh tế",
    "economic": "kinh tế",
    "market": "thị trường",
    "traders": "nhà giao dịch",
    "investors": "nhà đầu tư",
    "central bank": "ngân hàng trung ương",
    "treasury": "kho bạc",
    "bond": "trái phiếu",
    "yields": "lợi suất",
    "yield": "lợi suất",
    "dollar index": "chỉ số đô la",
    "safe haven": "tài sản trú ẩn an toàn",
    "risk": "rủi ro",
    "risk-on": "thích rủi ro",
    "risk-off": "tránh rủi ro",
    "volatility": "biến động",
    "rallied": "tăng",
    "plunged": "sụp",
    "slid": "giảm",
    "rose": "tăng",
    "fell": "giảm",
    "jumped": "tăng vọt",
    "dropped": "giảm",
    "extended": "mở rộng",
    "gained": "tăng",
    "lost": "mất",
    "adding": "thêm",
    "up": "lên",
    "down": "xuống",
    "higher": "cao hơn",
    "lower": "thấp hơn",
    "boosted": "được hỗ trợ",
    "weighed": "nặng",
    "pressure": "áp lực",
    "support": "hỗ trợ",
    "resistance": "kháng cự",
    "breakout": "phá vỡ",
    "breakdown": "sụp đổ",
    "target": "mục tiêu",
    "forecast": "dự báo",
    "outlook": "triển vọng",
    "expectations": "kỳ vọng",
    "expected": "dự kiến",
    "unexpected": "bất ngờ",
    "strong": "mạnh",
    "weak": "yếu",
    "record": "kỷ lục",
    "high": "cao",
    "low": "thấp",
    "close": "đóng cửa",
    "open": "mở cửa",
    "session": "phiên",
    "week": "tuần",
    "month": "tháng",
    "year": "năm",
    "today": "hôm nay",
    "yesterday": "hôm qua",
    "tomorrow": "ngày mai",
    "morning": "buổi sáng",
    "afternoon": "buổi chiều",
    "night": "đêm",
}


def translate_to_vietnamese(text: str) -> str:
    """Simple financial term translation EN -> VI."""
    if not text:
        return text
    result = text
    # Sort by length (longest first) to avoid partial replacements
    sorted_terms = sorted(VI_DICT.items(), key=lambda x: len(x[0]), reverse=True)
    for en, vi in sorted_terms:
        # Case-insensitive replacement
        import re
        pattern = re.compile(re.escape(en), re.IGNORECASE)
        result = pattern.sub(vi, result)
    return result


def fetch_rss_news():
    """Fetch news from RSS feeds with better error handling."""
    import xml.etree.ElementTree as ET

    items = []
    seen_titles = set()

    for feed_url in CONFIG["news_feeds"]:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            }
            # Google News SSL/timeout is flaky — retry a few times
            attempts = 3 if "google." in feed_url else 1
            resp = None
            last_err = None
            for _ in range(attempts):
                try:
                    resp = requests.get(feed_url, timeout=12, headers=headers)
                    resp.raise_for_status()
                    break
                except Exception as e:
                    last_err = e
                    resp = None
            if resp is None:
                raise last_err

            # Try to parse RSS/Atom
            root = ET.fromstring(resp.content)

            # Human-readable source: for Google News site: queries show the
            # target site instead of news.google.com
            feed_source = urllib.parse.urlparse(feed_url).netloc
            if "google." in feed_source:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(feed_url).query).get("q", [""])[0]
                if q.startswith("site:"):
                    feed_source = q[5:].split("/")[0].split(" ")[0]

            # RSS 2.0
            for item in root.iter("item"):
                title_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description")
                if title_el is not None and title_el.text:
                    title = title_el.text.strip()
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        items.append({
                            "title": title,
                            "url": link_el.text.strip() if link_el is not None and link_el.text else "",
                            "desc": (desc_el.text[:200] if desc_el is not None and desc_el.text else ""),
                            "source": feed_source,
                        })

            # Atom
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                title_el = entry.find("{http://www.w3.org/2005/Atom}title")
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
                if title_el is not None and title_el.text:
                    title = title_el.text.strip()
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        url = ""
                        if link_el is not None:
                            url = link_el.get("href", "")
                        items.append({
                            "title": title,
                            "url": url,
                            "desc": "",
                            "source": feed_source,
                        })

            print(f"  RSS OK: {feed_url} -> {len(items)} items")
        except Exception as e:
            print(f"  RSS error {feed_url}: {e}")

    return items


def filter_news(items: list, keywords: list, max_items: int = None):
    """Tag news with matched keywords (feeds are finance-specific, so all items
    pass through; keywords are only used for display tags)."""
    filtered = []
    for item in items:
        title_upper = item["title"].upper()
        matched = [kw for kw in keywords if kw.upper() in title_upper]
        item["title_vi"] = translate_to_vietnamese(item["title"])
        item["matched"] = matched[:3] or ["Thị trường"]
        filtered.append(item)
        if max_items and len(filtered) >= max_items:
            break
    return filtered


# ─── MAIN FUNCTIONS ───────────────────────────────────────────────────────────

def save_dashboard_data(all_analysis):
    """Save analysis + OHLCV data to JSON for dashboard."""
    try:
        import os
        os.makedirs("cloud_data", exist_ok=True)
        
        # Save analysis data
        dashboard_data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "symbols": [],
        }
        
        for item in all_analysis:
            # Trim OHLCV to last 100 candles to keep file small
            ohlcv = item["ohlcv"]
            trim = 100
            dashboard_data["symbols"].append({
                "symbol": item["symbol"],
                "name": item["name"],
                "ohlcv": {
                    "open": ohlcv["open"][-trim:],
                    "high": ohlcv["high"][-trim:],
                    "low": ohlcv["low"][-trim:],
                    "close": ohlcv["close"][-trim:],
                    "volume": ohlcv["volume"][-trim:],
                },
                "analysis_text": item["analysis"],
            })
        
        # Write to cloud_data/dashboard.json
        filepath = os.path.join("cloud_data", "dashboard.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, ensure_ascii=False, indent=2)
        
        print(f"Dashboard data saved: {filepath} ({len(dashboard_data['symbols'])} symbols)")
    except Exception as e:
        print(f"Save dashboard data error: {e}")


def run_analysis():
    """Run analysis on all symbols and send to bots."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Running analysis...")

    all_analysis = []  # For dashboard
    sent_count = 0
    best_signals = []  # Collect strongest signals

    for name, coingecko_id, yahoo_sym, tv_sym in CONFIG["symbols"]:
        data = None

        # Try CoinGecko for crypto/gold
        if coingecko_id:
            data = fetch_coingecko_ohlc(coingecko_id, "usd", 7)

        # Fallback to Yahoo
        if not data and yahoo_sym:
            data = fetch_yahoo_chart(yahoo_sym, "1h", "5d")

        if data:
            analysis = analyze_symbol(name, tv_sym, data)
            if analysis:
                sent_count += 1
                print(f"  OK: {name}")
                # Store for dashboard
                all_analysis.append({
                    "symbol": tv_sym,
                    "name": name,
                    "ohlcv": data,
                    "analysis": analysis,
                })
                # Check if strong signal
                if "TÍN HIỆU*: 🟢 MẠNH" in analysis or "TÍN HIỆU*: 🟡 TRUNG BÌNH" in analysis:
                    best_signals.append((name, analysis))
            else:
                print(f"  Analyze failed: {name}")
        else:
            print(f"  No data: {name}")

    if sent_count == 0:
        print("No data fetched, skipping...")
        return

    # Build BOT1 message with strongest signals first
    lines = [
        "⚡ *PHÂN TÍCH GIAO DỊCH*",
        f"━" * 30,
        "",
    ]

    # Add top signals first
    if best_signals:
        lines.append("🔥 *TÍN HIỆU NỔI BẬT*")
        lines.append("")
        for name, analysis in best_signals[:3]:
            lines.append(analysis)
            lines.append("")
        lines.append("━" * 30)
        lines.append("📋 *TẤT CẢ MÃ*")
        lines.append("")

    # Add all analysis
    for item in all_analysis:
        lines.append(item["analysis"])

    lines.append("━" * 30)
    lines.append(f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S %d/%m/%Y')} UTC | {sent_count} mã")

    text = "\n".join(lines)
    print(f"Message length: {len(text)} chars")

    # Save data for dashboard
    save_dashboard_data(all_analysis)

    # Send to BOT1 (analysis)
    if CONFIG["bot1_token"] and CONFIG["bot1_chat"]:
        ok1 = send_telegram(CONFIG["bot1_token"], CONFIG["bot1_chat"], text)
        print(f"BOT1: {'OK' if ok1 else 'FAIL'}")

    # Send summary to BOT2 (price feed - shorter)
    if CONFIG["bot2_token"] and CONFIG["bot2_chat"]:
        summary_lines = ["📊 *BẢNG GIÁ*", "━" * 24, ""]
        for item in all_analysis[:8]:  # Top 8 only
            # Extract price line
            for line in item["analysis"].split("\n"):
                if "Giá:" in line:
                    summary_lines.append(line.replace("  ", " "))
                    break
        summary_lines.append("")
        summary_lines.append(f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
        summary_text = "\n".join(summary_lines)
        ok2 = send_telegram(CONFIG["bot2_token"], CONFIG["bot2_chat"], summary_text)
        print(f"BOT2: {'OK' if ok2 else 'FAIL'}")

    state["last_analysis"] = time.time()
    save_state()


def run_news():
    """Fetch and send news with Vietnamese translation."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Running news...")

    items = fetch_rss_news()
    tagged = filter_news(items, CONFIG["news_keywords"])

    # Dedup against seen_news FIRST, then cap — otherwise the cap would only
    # consider the first N pool items and miss fresh news deeper in the pool.
    # Round-robin across sources so one feed can't hog all slots (important now
    # that the pool spans EN + VN feeds). Only SELECTED items are marked seen.
    groups = {}
    for item in tagged:
        key = item["title"][:80]
        if key in state["seen_news"]:
            continue
        groups.setdefault(item["source"], []).append(item)

    # Rotate which source gets first pick each cycle so every feed (EN + VN)
    # gets priority over time instead of the first 6 feeds always winning.
    srcs = list(groups)
    if srcs:
        offset = int(time.time() // max(CONFIG["news_interval"], 1)) % len(srcs)
        srcs = srcs[offset:] + srcs[:offset]

    new_items = []
    while len(new_items) < 6 and any(groups.values()):
        for src in srcs:
            g = groups[src]
            if not g:
                continue
            it = g.pop(0)
            state["seen_news"].append(it["title"][:80])
            new_items.append(it)
            if len(new_items) >= 6:
                break

    # Keep only last 300 seen (newest last)
    if len(state["seen_news"]) > 300:
        state["seen_news"] = state["seen_news"][-300:]

    if not new_items:
        print("  No new news items")
        state["last_news"] = time.time()
        save_state()
        return

    lines = [
        "📰 TIN TỨC THỊ TRƯỜNG",
        "━" * 28,
        "",
    ]

    for i, item in enumerate(new_items, 1):
        keywords_str = ", ".join(item["matched"][:3])
        # Use Vietnamese title if available, otherwise original
        title = item.get("title_vi", item["title"])[:150]
        lines.append(f"{i}. {title}")
        lines.append(f"   🏷️ {keywords_str} | 📡 {item['source']}")
        if item.get("url"):
            # Bare URL: Telegram auto-linkifies plain text, so the link stays
            # clickable even when parse_mode Markdown fails and is dropped.
            lines.append(f"   🔗 {item['url']}")
        lines.append("")

    lines.append(f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S %d/%m/%Y')} UTC")

    text = "\n".join(lines)
    print(f"  News message: {len(text)} chars, {len(new_items)} items, sources: {[i['source'] for i in new_items]}")

    # Send to BOT3 (news) as plain text so bare URLs remain clickable
    if CONFIG["bot3_token"] and CONFIG["bot3_chat"]:
        ok = send_telegram(CONFIG["bot3_token"], CONFIG["bot3_chat"], text, parse_mode=None)
        print(f"  News -> BOT3: {'OK' if ok else 'FAIL'}")
    # Fallback to BOT1 if BOT3 not configured
    elif CONFIG["bot1_token"] and CONFIG["bot1_chat"]:
        ok = send_telegram(CONFIG["bot1_token"], CONFIG["bot1_chat"], text, parse_mode=None)
        print(f"  News -> BOT1: {'OK' if ok else 'FAIL'}")

    state["last_news"] = time.time()
    save_state()


def main():
    """Main loop. Supports --once flag for GitHub Actions."""
    load_state()
    once = "--once" in sys.argv
    no_poll = "--no-poll" in sys.argv
    start_ts = time.time()

    print("=" * 50)
    print("Cloud Alerts V2 - Starting...")
    print(f"Mode: {'Once (GitHub Actions)' if once else 'Continuous (VPS)'}")
    print(f"Analysis interval: {CONFIG['analysis_interval']}s")
    print(f"News interval: {CONFIG['news_interval']}s")
    print(f"Symbols: {len(CONFIG['symbols'])}")
    print("=" * 50)

    if once:
        # GitHub Actions mode: run analysis + news once, then exit
        # Interval gating: cron may fire often (redundant entries) — skip if too soon
        now = time.time()
        age_analysis = now - state["last_analysis"]
        if age_analysis >= CONFIG["analysis_interval"]:
            try:
                run_analysis()
            except Exception as e:
                print(f"Analysis error: {e}")
        else:
            print(f"Skip analysis: last run {int(age_analysis)}s ago (< {CONFIG['analysis_interval']}s)")
        age_news = now - state["last_news"]
        if age_news >= CONFIG["news_interval"]:
            try:
                run_news()
            except Exception as e:
                print(f"News error: {e}")
        else:
            print(f"Skip news: last run {int(age_news)}s ago (< {CONFIG['news_interval']}s)")

        # BOT4: chart + detailed plan for watched symbols
        age_bot4 = now - float(state.get("last_bot4", 0) or 0)
        if age_bot4 >= CONFIG["bot4_interval"]:
            try:
                run_bot4()
            except Exception as e:
                print(f"Bot4 error: {e}")
        else:
            print(f"Skip bot4: last run {int(age_bot4)}s ago (< {CONFIG['bot4_interval']}s)")

        # Menu poll: answer /menu + inline taps until close to the 240s
        # workflow timeout (analysis+news+bot4 typically eat the first ~60-90s)
        if not no_poll:
            deadline = min(start_ts + CONFIG["menu_poll_sec"], start_ts + 225)
            try:
                poll_menu(deadline)
            except Exception as e:
                print(f"Menu poll error: {e}")

        print("Done!")
        return

    # VPS mode: send startup message
    startup = "🚀 *Cloud Alerts V2 Started!*\n\n📊 Phân tích định kỳ\n📰 Tin tức thị trường\n\n⏰ Gửi mỗi 15 phút"
    if CONFIG["bot1_token"] and CONFIG["bot1_chat"]:
        send_telegram(CONFIG["bot1_token"], CONFIG["bot1_chat"], startup)
    if CONFIG["bot2_token"] and CONFIG["bot2_chat"]:
        send_telegram(CONFIG["bot2_token"], CONFIG["bot2_chat"], startup)

    # Main loop
    while True:
        now = time.time()

        if now - state["last_analysis"] >= CONFIG["analysis_interval"]:
            try:
                run_analysis()
            except Exception as e:
                print(f"Analysis error: {e}")
            time.sleep(5)

        if now - state["last_news"] >= CONFIG["news_interval"]:
            try:
                run_news()
            except Exception as e:
                print(f"News error: {e}")

        if now - float(state.get("last_bot4", 0) or 0) >= CONFIG["bot4_interval"]:
            try:
                run_bot4()
            except Exception as e:
                print(f"Bot4 error: {e}")

        # Serve menu taps briefly each loop iteration
        try:
            poll_menu(time.time() + 30)
        except Exception as e:
            print(f"Menu poll error: {e}")

        time.sleep(10)


if __name__ == "__main__":
    main()
