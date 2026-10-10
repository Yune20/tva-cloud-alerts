#!/usr/bin/env python3
"""
Lightweight Cloud Alerts - runs on VPS with minimal dependencies.
Fetches market data, computes indicators, sends to Telegram bots.
Only requires: requests
"""
import os
import re
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
    # 3-hourly stats report (window: last 3h → 7 days) via BOT3
    "news_report_interval": int(os.getenv("NEWS_REPORT_INTERVAL", "10800")),
    "bot4_interval": int(os.getenv("BOT4_INTERVAL", "600")),  # chart+plan cadence
    # Per-run menu long-poll budget (seconds from process start). GitHub's
    # step runs `timeout 300 python cloud_alerts.py --once`, so keep this
    # below 285 to leave the kill window unused.
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
    "last_news_report": 0,         # 3-hourly stats report (BOT3)
    "seen_news": [],
    # Bot4 / menu state (persisted across GitHub Actions runs via state.json)
    "last_bot4": 0,
    "watch_symbols": [],          # legacy global list (migrated to per-chat)
    "watch_by_chat": {},          # per-user watch lists: {chat: [names]}
    "default_quote_by_chat": {},  # per-user ⭐ bang-gia symbol: {chat: name}
    "sym_report_ts": {},          # per-symbol last chart+plan send (unix ts)
    "bot_chats": {},              # chat ids discovered via /start per bot key
    "tg_offsets": {},             # getUpdates offsets per bot key
    # Signal engine (BOT2 cảnh báo)
    "last_signals": 0,
    "signal_ts": {},              # per (symbol:pattern) last alert (unix ts)
    "sig_range": {},              # per-symbol last in/out-of-range state
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
            _migrate_per_chat_state()
            print(f"Loaded state: {len(state['seen_news'])} seen news")
    except Exception as e:
        print(f"Failed to load state: {e}")


def _migrate_per_chat_state():
    """One-time seed of per-chat watch/⭐ lists from the legacy globals."""
    if "watch_by_chat" not in state:
        legacy = list(state.get("watch_symbols") or [])
        wbc = {}
        for chats in (state.get("bot_chats") or {}).values():
            for c in chats:
                wbc.setdefault(str(c), list(legacy))
        if not wbc and legacy:
            wbc["5575146754"] = legacy
        state["watch_by_chat"] = wbc
    if "default_quote_by_chat" not in state:
        dq = state.get("default_quote_symbol")
        dqbc = {}
        if dq:
            for chats in (state.get("bot_chats") or {}).values():
                for c in chats:
                    dqbc.setdefault(str(c), dq)
            if not dqbc:
                dqbc["5575146754"] = dq
        state["default_quote_by_chat"] = dqbc


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


def format_analysis(d: dict, mtf_lines=None) -> str:
    """Format the analysis dict into the classic BOT1 Markdown text.

    mtf_lines = 🧭 D1/H4/H1 summary lines (from mtf_summary_lines) so the
    analysis always covers every timeframe, not just the base one.
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
        f"🧭 *KHUNG LỚN (MTF)*",
    ] + (mtf_lines or [
        "  🗓 D1: — (chưa đủ dữ liệu)",
        "  🕓 H4: — (chưa đủ dữ liệu)",
        "  🕐 H1: — (chưa đủ dữ liệu)",
    ]) + [
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


def analyze_symbol(name: str, tv_symbol: str, data: dict, data1d: dict = None):
    """Analyze a symbol with detailed trading plan (classic BOT1 text).

    Always includes the 🧭 MTF block (D1/H4/H1) — never a single timeframe.
    """
    d = compute_analysis(name, tv_symbol, data)
    if not d:
        return None
    tf = mtf_summary_lines(name, tv_symbol, data, data1d)
    return format_analysis(d, tf)


def resample_bars(data: dict, factor: int) -> dict:
    """Group consecutive bars factor-by-factor from the END (e.g. 4H from 1H).

    Chronological order kept; leftover older bars are dropped. Timestamps are
    not required by compute_analysis, so sequential grouping is enough.
    """
    n = len(data["close"])
    if factor <= 1 or n < factor * 2:
        return data
    vol = data.get("volume") or [0] * n
    out = {"open": [], "high": [], "low": [], "close": [], "volume": []}
    idx = n
    groups = []
    while idx >= factor:
        groups.append((idx - factor, idx))
        idx -= factor
    for a, b in reversed(groups):
        out["open"].append(data["open"][a])
        out["high"].append(max(data["high"][a:b]))
        out["low"].append(min(data["low"][a:b]))
        out["close"].append(data["close"][b - 1])
        out["volume"].append(sum(vol[a:b]))
    return out


def mtf_summary_lines(name: str, tv_symbol: str, data: dict,
                      data1d: dict = None):
    """🧭 All-timeframe summary lines (D1 / H4 / H1) shared by every plan
    AND every analysis text — no report ever ships a single timeframe.

    H4 = resampled 4x from the 1H series; D1 comes from data1d when given,
    else falls back to resampling 24x (usually 'chưa đủ dữ liệu' on short
    series — the label still shows so every khung is always present).
    """
    def _tf_line(label, series, factor=1):
        s = series
        if factor > 1 and s:
            s = resample_bars(s, factor)
        if not s or len(s.get("close", [])) < 30:
            return f"  {label}: — (chưa đủ dữ liệu)"
        td = compute_analysis(name, tv_symbol, s)
        if not td:
            return f"  {label}: —"
        fmt = td["fmt_p"]
        return (f"  {label}: {td['trend']} | "
                f"R `{fmt(td['r1'])}` · S `{fmt(td['s1'])}`")

    d1 = data1d if data1d else data
    d1_factor = 1 if data1d else 24
    return [
        _tf_line("🗓 D1", d1, d1_factor),
        _tf_line("🕓 H4", data, 4),
        _tf_line("🕐 H1", data),
    ]


def build_detailed_plan(name: str, tv_symbol: str, data: dict,
                        data4h: dict = None, data1d: dict = None):
    """BOT4: comprehensive MTF trading plan (dict + formatted text).

    data = 1H series (chart source); data4h/data1d = higher timeframes when
    available. Returns (details_dict, plan_text) or (None, None).

    The plan always contains actionable ENTRY ZONES (buy zone / sell-TP zone)
    plus where the current price sits relative to them — never a bare
    "stand aside" with price floating outside every level.
    """
    d = compute_analysis(name, tv_symbol, data)
    if not d:
        return None, None
    fmt = d["fmt_p"]
    bars = len(data["close"])
    atr = d["atr"] if d["atr"] > 0 else d["price"] * 0.005
    price = d["price"]

    # ── Entry zones from structure (pivots + 20-bar range) ────────────────
    hh, ll = d["recent_high"], d["recent_low"]
    # Buy zone: anchored on S1 (pullback support), always below current price
    if d["s1"] < price:
        buy_hi = d["s1"]
    else:
        buy_hi = min(ll, price - 0.3 * atr)
    buy_lo = buy_hi - 1.5 * atr
    # Sell/TP zone: anchored on R1, always above current price
    if d["r1"] > price:
        sell_lo = d["r1"]
    else:
        sell_lo = max(hh, price + 0.3 * atr)
    sell_hi = sell_lo + 1.5 * atr
    d["buy_zone"] = (buy_lo, buy_hi)
    d["sell_zone"] = (sell_lo, sell_hi)

    if buy_lo <= price <= buy_hi:
        st_buy = "🟢 GIÁ ĐANG TRONG VÙNG MUA"
    elif price > buy_hi:
        st_buy = (f"⏳ NGOÀI VÙNG (trên) {fmt(price - buy_hi)} "
                  f"({(price - buy_hi) / atr:.1f} ATR) → CHỜ retest, không chase")
    else:
        st_buy = "🔴 GIÁ DƯỚI VÙNG — hỗ trợ có thể đã vỡ, đợi cấu trúc lại"
    if sell_lo <= price <= sell_hi:
        st_sell = "🟢 GIÁ ĐANG TRONG VÙNG CHỐT/SHORT"
    elif price < sell_lo:
        st_sell = (f"⏳ NGOÀI VÙNG (dưới) {fmt(sell_lo - price)} "
                   f"({(sell_lo - price) / atr:.1f} ATR) → còn dư địa tăng")
    else:
        st_sell = "🔴 GIÁ ĐÃ VƯỢT VÙNG — chốt lời từng phần"

    entry_mid = (buy_lo + buy_hi) / 2
    sl = buy_lo - 0.75 * atr
    tp1 = sell_lo
    tp2 = sell_hi
    risk = abs(entry_mid - sl) or atr
    rr1 = abs(tp1 - entry_mid) / risk if risk else 0

    # ── Higher timeframe summaries (shared MTF block — all khung always) ──
    tf_lines = mtf_summary_lines(name, tv_symbol, data, data1d)

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
            f"• *Tiếp diễn:* giữ trên `{fmt(d['s1'])}` → hướng vùng chốt `{fmt(sell_lo)}`\n"
            f"• *Phá kháng cự:* đóng nến 1H trên `{fmt(sell_hi)}` → momentum, TP2 `{fmt(sell_hi + atr)}`\n"
            f"• *Hủy setup:* đóng 1H dưới `{fmt(buy_lo)}` → stop, chờ cấu trúc mới"
        )
    elif d["trend_dir"] == "SHORT":
        scenario = (
            f"• *Tiếp diễn:* giữ dưới `{fmt(d['r1'])}` → hướng vùng mua `{fmt(buy_hi)}`\n"
            f"• *Hạ tiếp:* đóng 1H dưới `{fmt(buy_lo)}` → momentum xuống\n"
            f"• *Hủy setup:* vượt `{fmt(sell_hi)}` → đảo chiều, cắt lỗ"
        )
    else:
        scenario = (
            f"• *Biên:* dao động `{fmt(ll)}` – `{fmt(hh)}` — MUA dưới `{fmt(buy_hi)}`, "
            f"BÁN trên `{fmt(sell_lo)}`\n"
            f"• *Phá lên:* đóng 1H trên `{fmt(sell_hi)}` → target `{fmt(sell_hi + atr)}`\n"
            f"• *Phá xuống:* đóng 1H dưới `{fmt(buy_lo)}` → dừng mua"
        )

    now = datetime.now(timezone.utc).strftime("%H:%M %d/%m/%Y")
    lines = [
        f"📋 *PLAN MTF · KẾ HOẠCH VÀO LỆNH*",
        f"*{name}* ({d['tv_symbol']}) · {bars} nến 1H · {now} UTC",
        f"━━━━━━━━━━━━━━━━━━",
        f"💰 Giá: `{fmt(price)}` {d['icon']} {d['chg']:+.2f}%",
        f"",
        f"🧭 *KHUNG LỚN (MTF)*",
        *tf_lines,
        f"  • Xu hướng 1H: {d['trend']} | Điểm tín hiệu: `{d['score']}/100` {d['signal_strength']}",
        f"",
        f"🎯 *VÙNG VÀO LỆNH*",
        f"  ▶ *MUA (retest):* `{fmt(buy_lo)}` – `{fmt(buy_hi)}`  (1.5×ATR)",
        f"    {st_buy}",
        f"    SL (hủy): `{fmt(sl)}` · TP1 `{fmt(tp1)}` · TP2 `{fmt(tp2)}` · RR `1:{rr1:.1f}`",
        f"  ▶ *CHỐT LỢI NHUẬN / SHORT:* `{fmt(sell_lo)}` – `{fmt(sell_hi)}`",
        f"    {st_sell}",
        f"",
        f"📊 *ĐỘNG LƯỢNG*",
        f"  • RSI(14): `{rsi:.1f}` — {rsi_zone}" if rsi else "  • RSI(14): N/A",
        f"  • MACD: {d['macd_sig']} | ADX `{d['adx_val']:.0f}` {d['adx_sig']} | ATR `{fmt(atr)}`",
        f"  • Tâm lý: {d['psyc']} | Pivot `{fmt(d['pivot'])}` · S2 `{fmt(d['s2'])}` · R2 `{fmt(d['r2'])}`",
        f"",
        f"🧩 *KỊCH BẢN*",
        scenario,
        f"",
        f"✅ *CHECKLIST*",
        f"  1. Chờ giá chạm vùng, không FOMO đuổi giá",
        f"  2. RSI: {rsi_zone}",
        f"  3. Cắt lỗ đúng SL `{fmt(sl)}`, không kéo SL",
        f"  4. Rủi ro tối đa 1–2% vốn/lệnh",
        f"",
        f"⚠️ Phân tích tự động (D1/H4/H1) — không phải tư vấn đầu tư.",
    ]
    return d, "\n".join(lines)


# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def send_telegram(token: str, chat_id: str, text: str, parse_mode: str = "Markdown",
                  extra: dict = None):
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
        if extra:
            payload.update(extra)
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

def _menu_price_map(refresh: bool = False):
    """name -> formatted price string, TTL-cached in state (300s).

    Uses short-timeout concurrent Yahoo chart meta lookups; symbols that
    fail show '—'. refresh=True forces a re-fetch (e.g. on /menu).
    """
    import concurrent.futures as cf

    ttl = 300
    cached = state.get("menu_prices") or {}
    if (not refresh and time.time() - float(cached.get("ts", 0) or 0) < ttl
            and cached.get("prices")):
        return cached["prices"]

    def get(e):
        name, yahoo = e
        if not yahoo:
            return name, None
        try:
            r = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/"
                f"{urllib.parse.quote(str(yahoo))}",
                params={"range": "1d", "interval": "1h"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=6,
            )
            meta = r.json()["chart"]["result"][0]["meta"]
            return name, meta.get("regularMarketPrice")
        except Exception:
            return name, None

    pairs = [(n, y) for (n, cg, y, tv) in menu_entries()]
    prices = {}
    try:
        with cf.ThreadPoolExecutor(max_workers=10) as ex:
            for name, p in ex.map(get, pairs):
                prices[name] = p
    except Exception as e:
        print(f"  menu price fetch error: {e}")
    out = {n: (f"{p:,.2f}" if isinstance(p, (int, float)) else "—")
           for n, p in prices.items()}
    state["menu_prices"] = {"ts": time.time(), "prices": out}
    save_state()
    return out


# Intelligent role allocation: each bot owns one specialty; the menu on ANY
# bot can trigger any action and the SPECIALIST bot's token replies (all 4
# bots can message the same user chat).
BOT_ROLES = {
    "bot1": ("📊", "PHÂN TÍCH ĐA KHUNG HÌNH",
             "Phân tích MTF đầy đủ + kế hoạch entry/SL/TP theo từng khung."),
    "bot2": ("💹", "BẢNG GIÁ + CẢNH BÁO",
             "Bảng giá realtime, mã + tên + giá, kèm cảnh báo thay đổi giá."),
    "bot3": ("📰", "TIN TỨC THỊ TRƯỜNG",
             "Tin tức đã dịch tiếng Việt + dải giá toàn thị trường."),
    "bot4": ("📈", "BIỂU ĐỒ + KẾ HOẠCH",
             "Chart nến + kế hoạch giao dịch chi tiết cho các mã ✅."),
}
ACTION_OWNERS = {"chart": "bot4", "analysis": "bot1", "bang": "bot2",
                 "news": "bot3", "bt": "bot1"}
# Role-pure routing: each bot only OFFERS and only SERVES its own services,
# and replies always come from the tapped bot into its own chat — no more
# answers jumping between bot windows ("chồng chéo chức năng").
ROLE_ACTIONS = {"bot1": {"analysis", "bt"},
                "bot2": {"bang"},
                "bot3": {"news"},
                "bot4": {"chart"}}
ROLE_MAIN = {"bot1": "analysis", "bot2": "bang",
             "bot3": "news", "bot4": "chart"}
ROLE_SVC_TEXT = {
    "bot1": "📊 Phân tích MTF đủ khung D1/H4/H1 + vùng vào/SL/TP",
    "bot2": "💹 Báo giá từng mã bạn chọn (chạm mã = gửi ngay) + tín hiệu mã theo dõi",
    "bot3": "📰 Tin tức mỗi tin 1 dòng (không link) + báo cáo thống kê 3 giờ",
    "bot4": "📈 Chart nến + kế hoạch giao dịch từng mã ✅",
}
ROLE_SVC_BTN = {
    "chart": ("📈 Chart+Plan", "a:chart"),
    "analysis": ("📊 Phân tích", "a:analysis"),
    "bang": ("💹 Bảng giá", "a:bang"),
    "news": ("📰 Tin tức", "a:news"),
}
ROLE_NOW_LABEL = {"bot1": "📩 Gửi phân tích ngay",
                  "bot2": "📩 Gửi bảng giá ngay",
                  "bot3": "📩 Gửi tin ngay",
                  "bot4": "📩 Gửi chart+plan ngay"}
# Per-symbol detail screen: which sa: services each bot owns/shows
ROLE_DETAIL = {"bot1": ["an", "bt"], "bot2": [], "bot3": [], "bot4": ["chart"]}
ROLE_DETAIL_TEXT = {
    "bot1": ["📊 Phân tích MTF — đủ khung", "🧪 Backtest EMA21/50"],
    "bot2": ["🎯 ⭐ Gửi làm mã bảng giá mặc định", "📋 Bảng đầy đủ ở menu chính"],
    "bot3": ["📰 Tin mới nhất — nút 📰 ở menu chính"],
    "bot4": ["📈 Chart nến + kế hoạch entry/SL/TP"],
}
SA_ACT_OWNER = {"chart": "chart", "an": "analysis", "bt": "bt"}
MENU_BTN = {"inline_keyboard": [[
    {"text": "📋 Menu tín hiệu", "callback_data": "m:!menu"},
]]}


def menu_btn_json() -> str:
    return json.dumps(MENU_BTN, ensure_ascii=False)


def _role_allowed(key: str, act: str) -> bool:
    """True when `act` belongs to bot `key`'s role (role-pure menus)."""
    return act in ROLE_ACTIONS.get(key, set())


def _role_redirect(key: str, act: str) -> str:
    """Toast when a stale keyboard offers another bot's service."""
    owner = ACTION_OWNERS.get(act, "")
    icon, role, _ = BOT_ROLES.get(owner, ("🤖", "", ""))
    return (f"📌 Tính năng này của {owner.upper()} {icon} {role} — "
            f"mở {owner.upper()} dùng nhé")


WATCH_CAP = 8  # symbols per user — keeps every personal list & message readable


def watch_for(chat) -> list:
    """This user's watched symbols (per-chat list, empty if none)."""
    return list(state.setdefault("watch_by_chat", {}).get(str(chat or ""), []))


def set_watch_for(chat, names):
    state.setdefault("watch_by_chat", {})[str(chat or "")] = [str(n) for n in names]


def default_quote_for(chat):
    """This user's ⭐ bang-gia symbol (per-chat)."""
    return state.setdefault("default_quote_by_chat", {}).get(str(chat or ""))


def set_default_quote_for(chat, name):
    state.setdefault("default_quote_by_chat", {})[str(chat or "")] = name


def menu_text(key: str = "bot4", refresh: bool = False, chat: str = ""):
    """Role-aware, compact menu: per-user prices + service map."""
    icon, role, role_desc = BOT_ROLES.get(key, ("🤖", "TÍN HIỆU", ""))
    bot_no = key.replace("bot", "BOT")
    try:
        prices = _menu_price_map(refresh=refresh)
    except Exception as e:
        print(f"  menu price error: {e}")
        prices = {}
    watch = watch_for(chat)
    a_min = max(1, int(CONFIG["analysis_interval"] // 60))
    n_min = max(1, int(CONFIG["news_interval"] // 60))
    c_min = max(1, int(CONFIG["bot4_interval"] // 60))
    lines = [
        f"📋 MENU — {icon} {role}",
        "━" * 26,
        f"{bot_no} · {role_desc}",
        f"⚙️ đang theo dõi {len(watch)}/{WATCH_CAP} mã · "
        f"bảng giá {a_min}' · tin {n_min}' · chart {c_min}'",
        "",
        "💹 GIÁ CỦA BẠN (mỗi người một danh sách):",
    ]
    dq = default_quote_for(chat)
    if watch:
        for name in watch:
            e = find_menu_entry(name)
            if not e:
                continue
            code = str(e[3]).split(":")[-1]
            star = " ⭐" if name == dq else ""
            lines.append(f"• {name} · {code}: {prices.get(name, '—')}{star}")
    else:
        lines.append("  Chưa chọn mã nào — bấm ▫️ bên dưới để theo dõi.")
    lines += [
        "",
        f"🎯 DỊCH VỤ {bot_no} (chỉ bot này trả lời):",
        f"  {ROLE_SVC_TEXT[key]}",
        "🔎 Chi tiết mã: dịch vụ riêng của từng bot (nút 🔎).",
        "👇 Bấm ▫️/✅ bên dưới để chọn mã cho riêng bạn.",
        "💬 /menu mở lại.",
    ]
    if key == "bot2":
        lines.append(f"🎯 Bảng giá mặc định: {dq or 'chưa đặt (⭐ ở 🔎 chi tiết mã)'}")
    return "\n".join(lines)


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


def menu_keyboard(key: str = "bot4", chat: str = ""):
    """Inline keyboard: toggles + per-symbol detail + services + management."""
    watch = watch_for(chat)
    wset = set(watch)
    rows = []
    row = []
    for name, *_ in menu_entries():
        mark = "✅ " if name in wset else "▫️ "
        row.append({"text": mark + name, "callback_data": f"m:{name}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    # Role-pure service row: only THIS bot's own service button(s).
    svc = [{"text": ROLE_SVC_BTN[a][0], "callback_data": ROLE_SVC_BTN[a][1]}
           for a in ("chart", "analysis", "bang", "news")
           if a in ROLE_ACTIONS.get(key, set())]
    if svc:
        rows.append(svc)
    if key == "bot2":
        rows.append([{"text": "📋 Bảng đầy đủ", "callback_data": "m:!full"}])
    # Per-symbol detail screens for watched symbols (max 8).
    drow = []
    for name in watch[:8]:
        drow.append({"text": f"🔎 {name}", "callback_data": f"d:{name}"})
        if len(drow) == 2:
            rows.append(drow)
            drow = []
    if drow:
        rows.append(drow)
    rows.append([
        {"text": ROLE_NOW_LABEL.get(key, "📩 Gửi ngay ✅"), "callback_data": "m:!now"},
        {"text": "🔄 Tải lại giá", "callback_data": "m:!refresh"},
    ])
    rows.append([{"text": "🗑️ Xóa tất cả theo dõi", "callback_data": "m:!clear"}])
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
            # Entry zones (buy / sell-TP) as shaded bands
            for zkey, zcol, zlab in (("buy_zone", "#26a69a", "VÙNG MUA"),
                                     ("sell_zone", "#ef5350", "VÙNG BÁN/TP")):
                z = details.get(zkey)
                if not z:
                    continue
                zlo, zhi = z
                if not (w_lo * 0.95 < (zlo + zhi) / 2 < w_hi * 1.05):
                    continue
                zlo = max(zlo, w_lo * 0.995)
                zhi = min(zhi, w_hi * 1.005)
                if zhi <= zlo:
                    continue
                ax.axhspan(zlo, zhi, color=zcol, alpha=0.13, zorder=1)
                ax.text(0.99, (zlo + zhi) / 2, f" {zlab} ",
                        color=zcol, fontsize=7.5, va="center", ha="right",
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


def send_telegram_photo(token: str, chat_id: str, photo_bytes: bytes, caption: str = "",
                        extra: dict = None):
    """Send a photo to Telegram (BOT4 charts)."""
    if not token or not chat_id:
        print(f"  Photo skip (token={bool(token)}, chat={bool(chat_id)})")
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload = {"chat_id": chat_id}
        if caption:
            payload["caption"] = caption[:1020]
        if extra:
            payload.update(extra)
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

    # 1H series: prefer Yahoo 2mo (supports H1 analysis + 4H resample from a
    # single fetch); CoinGecko 7d is a fallback when Yahoo is unavailable.
    data = None
    if yahoo:
        data = fetch_yahoo_chart(yahoo, "1h", "2mo")
    if not data and cg:
        data = fetch_coingecko_ohlc(cg, "usd", 7)
    if not data:
        print(f"  Report: no data for {name}")
        return False
    # Daily series for the D1 line of the MTF plan
    data1d = None
    if yahoo:
        data1d = fetch_yahoo_chart(yahoo, "1d", "6mo")

    d, plan = build_detailed_plan(name, tv, data, data1d=data1d)
    if not plan or not d:
        print(f"  Report: analysis failed for {name}")
        return False

    chart = render_chart_png(name, tv, data, d)
    photo_ok = False
    if chart:
        caption = (f"{name} · 1H · {d['price']:,.2f} {d['icon']} {d['chg']:+.2f}% "
                   f"· vùng mua {d['buy_zone'][0]:,.2f}–{d['buy_zone'][1]:,.2f}")
        photo_ok = send_telegram_photo(token, chat, chart, caption,
                                       extra={"reply_markup": menu_btn_json()})
    text_ok = send_telegram(token, chat, plan,
                            extra={"reply_markup": menu_btn_json()})
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

    # Rotate per chat so >2 watched symbols all get covered within a few
    # cycles (max 2 full reports per chat per run). Each user gets THEIR
    # own list only.
    for chat in chats:
        watch = [n for n in watch_for(chat) if find_menu_entry(n)]
        if not watch:
            print(f"  Bot4: chat {chat} has no watched symbols - skip")
            continue
        offset = int(time.time() // max(CONFIG["bot4_interval"], 1)) % len(watch)
        ordered = watch[offset:] + watch[:offset]
        sent = 0
        for name in ordered:
            if sent >= 2:
                break
            if send_symbol_report(CONFIG["bot4_token"], chat, find_menu_entry(name)):
                sent += 1
        print(f"  Bot4: chat {chat} sent {sent} report(s), watch={watch}")
    state["last_bot4"] = time.time()
    save_state()


def _edit_menu(token: str, cb: dict, refresh: bool = False, key: str = "bot4",
               force_edit: bool = False):
    """Refresh the menu in place after a toggle.

    If the tapped message IS the menu (or force_edit), edit it; otherwise
    (e.g. the menu button under BOT2's bảng giá) send a fresh menu message.
    """
    msg = cb.get("message") or {}
    mid = msg.get("message_id")
    chat = str((msg.get("chat") or {}).get("id") or "")
    if not mid or not chat:
        return
    text = menu_text(key, refresh=refresh, chat=chat)
    if force_edit or (msg.get("text") or "").startswith("📋 MENU"):
        _tg_api(token, "editMessageText", chat_id=chat, message_id=mid,
                text=text, reply_markup=json.dumps(menu_keyboard(key, chat), ensure_ascii=False))
    else:
        _tg_api(token, "sendMessage", chat_id=chat, text=text,
                reply_markup=json.dumps(menu_keyboard(key, chat), ensure_ascii=False))


# ─── Per-symbol detail view (menu level 2) ───────────────────────────────────

def _symbol_price(name: str, prices: dict = None) -> str:
    if prices is None:
        try:
            prices = _menu_price_map()
        except Exception:
            prices = {}
    return prices.get(name, "—")


def detail_text(name: str, key: str = "bot4", chat: str = ""):
    """Detail screen for one symbol: price, status, this bot's own services."""
    e = find_menu_entry(name)
    if not e:
        return f"🔎 {name}\n(Mã không còn trong menu)"
    n_, cg, yahoo, tv = e
    code = str(tv).split(":")[-1]
    watch = watch_for(chat)
    mark = "✅ đang theo dõi" if name in watch else "▫️ chưa theo dõi"
    svc = [f"  {t}" for t in ROLE_DETAIL_TEXT.get(key, ROLE_DETAIL_TEXT["bot4"])]
    return "\n".join([
        f"🔎 {name.upper()} · {code}",
        "━" * 22,
        f"💰 Giá: {_symbol_price(name)}",
        f"📌 Trạng thái: {mark}",
        "",
        f"🎯 DỊCH VỤ CỦA {key.upper()}:",
        *svc,
        "",
        "↩️ «Menu chính» để chọn mã khác.",
    ])


def detail_keyboard(name: str, key: str = "bot4", chat: str = ""):
    watch = watch_for(chat)
    tg_label = ("▫️ Bỏ theo dõi" if name in watch else "✅ Theo dõi")
    svc_defs = {"chart": ("📈 Chart+Plan", f"sa:chart:{name}"),
                "an": ("📊 Phân tích", f"sa:an:{name}"),
                "bt": ("🧪 Backtest", f"sa:bt:{name}")}
    rows = []
    svc_row = [{"text": svc_defs[s][0], "callback_data": svc_defs[s][1]}
               for s in ROLE_DETAIL.get(key, []) if s in svc_defs]
    if svc_row:
        rows.append(svc_row)
    if key == "bot2":
        dq = default_quote_for(chat)
        dq_label = "▫️ Bỏ mặc định" if dq == name else "⭐ Gửi mặc định"
        rows.append([{"text": dq_label, "callback_data": f"sa:dq:{name}"}])
    rows.append([{"text": tg_label, "callback_data": f"sa:tg:{name}"}])
    rows.append([{"text": "↩️ Menu chính", "callback_data": "sa:back:x"}])
    return {"inline_keyboard": rows}


def _show_symbol_detail(token: str, cb: dict, name: str, key: str):
    msg = cb.get("message") or {}
    mid = msg.get("message_id")
    chat = str((msg.get("chat") or {}).get("id") or "")
    if not mid or not chat:
        return
    _tg_api(token, "editMessageText", chat_id=chat, message_id=mid,
            text=detail_text(name, key, chat),
            reply_markup=json.dumps(detail_keyboard(name, key, chat),
                                    ensure_ascii=False))


def _ema_full(vals, period):
    """EMA over the full series (no warm-up None) for backtests."""
    k = 2.0 / (period + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def backtest_ema_report(name: str, entry) -> str:
    """EMA21/50 cross backtest on ~5d of 1H candles (pure cloud-safe)."""
    n_, cg, yahoo, tv = entry
    data = None
    try:
        if cg:
            data = fetch_coingecko_ohlc(cg, "usd", 7)
    except Exception:
        data = None
    if not data and yahoo:
        try:
            data = fetch_yahoo_chart(yahoo, "1h", "5d")
        except Exception:
            data = None
    c = (data or {}).get("close") or []
    if len(c) < 60:
        return (f"🧪 BACKTEST EMA21/50 · {name}\n"
                f"⏳ Dữ liệu chưa đủ (cần ≥60 nến 1H) — thử lại sau.")
    e21, e50 = _ema_full(c, 21), _ema_full(c, 50)
    trades, pos, entry_p = [], 0, 0.0
    for i in range(1, len(c)):
        up = e21[i - 1] <= e50[i - 1] and e21[i] > e50[i]
        dn = e21[i - 1] >= e50[i - 1] and e21[i] < e50[i]
        if pos == 0 and up:
            pos, entry_p = 1, c[i]
        elif pos == 1 and dn:
            trades.append((c[i] / entry_p - 1.0) * 100)
            pos = 0
    if pos == 1:  # open trade, mark-to-market
        trades.append((c[-1] / entry_p - 1.0) * 100)
    if not trades:
        return (f"🧪 BACKTEST EMA21/50 · {name}\n"
                "5 ngày · 1H · không có lệnh đóng (sideways).")
    wins = sum(1 for t in trades if t > 0)
    net = 1.0
    for t in trades:
        net *= 1 + t / 100
    return "\n".join([
        f"🧪 BACKTEST EMA21/50 · {name}",
        "━" * 22,
        f"• Khung: 5 ngày · nến 1H · {len(c)} nến",
        f"• Lệnh: {len(trades)} · Thắng: {wins}/{len(trades)} "
        f"({100 * wins / len(trades):.0f}%)",
        f"• Lợi nhuận gộp: {(net - 1) * 100:+.2f}% · "
        f"TB/lệnh: {sum(trades) / len(trades):+.2f}%",
        "",
        "⚠️ Thử nghiệm quá khứ, KHÔNG phải lời khuyên đầu tư.",
    ])


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
        _tg_api(token, "sendMessage", chat_id=chat,
                text=menu_text(key, refresh=True, chat=chat),
                reply_markup=json.dumps(menu_keyboard(key, chat), ensure_ascii=False))
        return

    cb = upd.get("callback_query")
    if not cb:
        return
    data = cb.get("data") or ""
    cb_id = cb.get("id") or ""
    cb_msg = cb.get("message") or {}
    cb_chat = str((cb_msg.get("chat") or {}).get("id") or chat)

    # Specialist actions — ROLE-PURE: only the owning bot offers & serves them.
    # A stale keyboard tapped on another bot gets a pointer alert + the menu
    # self-heals to role-pure (no cross-window replies anymore).
    if data.startswith("a:"):
        act = data[2:]
        if act in ACTION_OWNERS:
            if not _role_allowed(key, act):
                if cb_id:
                    _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                            text=_role_redirect(key, act), show_alert=True)
                _edit_menu(token, cb, key=key, force_edit=True)
                return
            if cb_id:
                _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                        text="Đang xử lý...")
            try:
                handle_menu_action(act, key, token, cb_chat)
            except Exception as e:
                print(f"  Action {act} error: {e}")
                send_telegram(token, cb_chat, f"⚠️ Lỗi {act}: {e}")
        return

    # Level-2 detail screen for one symbol.
    if data.startswith("d:"):
        sym = data[2:]
        if not find_menu_entry(sym):
            if cb_id:
                _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id)
            return
        if cb_id:
            _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id, text=sym)
        _show_symbol_detail(token, cb, sym, key)
        return

    # Per-symbol service actions from the detail screen.
    if data.startswith("sa:"):
        parts = data.split(":", 2)
        if len(parts) != 3:
            return
        _, sact, sname = parts
        if sact == "back":
            if cb_id:
                _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id)
            _edit_menu(token, cb, key=key, force_edit=True)
            return
        e = find_menu_entry(sname)
        if not e:
            return
        # Role-pure guard for service buttons (stale keyboards self-heal):
        # toast pointing to the owning bot + re-render this bot's detail screen.
        if sact in SA_ACT_OWNER and sact not in ROLE_DETAIL.get(key, []):
            if cb_id:
                _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                        text=_role_redirect(key, SA_ACT_OWNER[sact]),
                        show_alert=True)
            _show_symbol_detail(token, cb, sname, key)
            return
        if cb_id:
            _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                    text="Đang xử lý...")
        if sact == "chart":
            send_symbol_report(token, cb_chat, e, force=True)
        elif sact == "an":
            dash_names = {s.get("name") for s in load_dashboard_symbols()}
            if sname in dash_names:
                send_analysis_charts(token, cb_chat, [sname])
                txt = build_analysis_snapshot([sname])
            else:
                txt = (f"⏳ Chưa có phân tích MTF cho {sname} — mã ngoài "
                       f"11 cặp chính.\nDùng 📈 Chart+Plan hoặc 🧪 Backtest "
                       f"thay thế.")
            send_telegram(token, cb_chat, txt,
                          extra={"reply_markup": menu_btn_json()})
        elif sact == "bt":
            txt = backtest_ema_report(sname, e)
            send_telegram(token, cb_chat, txt,
                          extra={"reply_markup": menu_btn_json()})
        elif sact == "tg":
            watch2 = watch_for(cb_chat)
            if sname in watch2:
                watch2.remove(sname)
                note = f"Đã bỏ theo dõi {sname}"
            elif len(watch2) >= WATCH_CAP:
                if cb_id:
                    _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                            text=f"Đã đủ {WATCH_CAP} mã — bỏ bớt trước khi thêm {sname}.",
                            show_alert=True)
                _show_symbol_detail(token, cb, sname, key)
                return
            else:
                watch2.append(sname)
                note = f"Đang theo dõi {sname}"
            set_watch_for(cb_chat, watch2)
            save_state()
            if cb_id:
                _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                        text=note)
        elif sact == "dq":
            # ⭐ default bang-gia symbol (BOT2, per-user): bang button / !now
            # send this one symbol instead of the whole table / watch list.
            cur = default_quote_for(cb_chat)
            if cur == sname:
                set_default_quote_for(cb_chat, None)
                note = f"Đã bỏ {sname} khỏi báo giá mặc định"
            else:
                set_default_quote_for(cb_chat, sname)
                note = f"⭐ {sname} là mã báo giá mặc định"
            save_state()
            if cb_id:
                _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                        text=note)
        _show_symbol_detail(token, cb, sname, key)
        return

    if not data.startswith("m:"):
        if cb_id:
            _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id)
        return
    pick = data[2:]
    watch = watch_for(cb_chat)

    if pick == "!menu":
        if cb_id:
            _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                    text="Đang tải menu...")
        _edit_menu(token, cb, refresh=True, key=key)
        return

    if pick == "!clear":
        set_watch_for(cb_chat, [])
        save_state()
        if cb_id:
            _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                    text="Đã xóa toàn bộ theo dõi")
        _edit_menu(token, cb, key=key, force_edit=True)
        return

    if pick == "!refresh":
        if cb_id:
            _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                    text="Đang tải lại giá...")
        _edit_menu(token, cb, refresh=True, key=key, force_edit=True)
        return

    if pick == "!full":
        # Explicit full bang-gia table (the only path that shows ALL symbols).
        if cb_id:
            _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                    text="Đang gửi bảng đầy đủ...")
        text = build_banggia_dashboard()
        if not text:
            text = "⏳ Bảng giá chưa sẵn — thử lại sau 1-2 phút."
        send_telegram(token, cb_chat, text, extra={"reply_markup": menu_btn_json()})
        return

    if pick == "!now":
        act = ROLE_MAIN.get(key, "chart")
        dq = default_quote_for(cb_chat)
        if not watch and not (act == "bang" and dq and find_menu_entry(dq)):
            if cb_id:
                _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                        text="Bạn chưa chọn mã nào - chạm một mã để ✅", show_alert=True)
            return
        if cb_id:
            _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                    text=f"Đang gửi {ROLE_SVC_BTN[act][0].lower()}...")
        try:
            handle_menu_action(act, key, token, cb_chat)
        except Exception as e:
            print(f"  !now {act} error: {e}")
            send_telegram(token, cb_chat, f"⚠️ Lỗi: {e}")
        _edit_menu(token, cb, key=key)
        return

    if pick not in [e[0] for e in menu_entries()]:
        return

    if pick in watch:
        watch.remove(pick)
        note = f"Đã bỏ theo dõi {pick}"
    else:
        if len(watch) >= WATCH_CAP:
            if cb_id:
                _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id,
                        text=f"Đã đủ {WATCH_CAP} mã — bỏ bớt trước khi thêm {pick}.",
                        show_alert=True)
            _edit_menu(token, cb, key=key)
            return
        watch.append(pick)
        if key == "bot4":
            note = f"Đang theo dõi {pick} - đang gửi báo cáo..."
        elif key == "bot1":
            note = f"Đang theo dõi {pick} - đang gửi phân tích..."
        elif key == "bot2":
            note = f"Đang theo dõi {pick} - đang gửi báo giá..."
        else:
            note = f"Đang theo dõi {pick}"
    set_watch_for(cb_chat, watch)
    save_state()
    if cb_id:
        _tg_api(token, "answerCallbackQuery", callback_query_id=cb_id, text=note)
    _edit_menu(token, cb, key=key)
    if pick in watch:
        e = find_menu_entry(pick)
        if e and key == "bot4":
            # Bot4 auto-sends its own chart+plan (as before).
            send_symbol_report(token, cb_chat, e, force=True)
        elif e and key == "bot2":
            # Tap = send THIS symbol's compact quote card ("chọn mã nào
            # gửi mã đó") — one short message, never the whole table.
            qtext = build_banggia_for([pick],
                                      header=f"💹 BẢNG GIÁ · {pick.upper()}")
            if not qtext:
                qtext = (f"💹 {pick.upper()}\n⏳ Bảng giá chưa sẵn cho mã này — "
                         f"thử lại sau 1-2 phút.")
            send_telegram(token, cb_chat, qtext,
                          extra={"reply_markup": menu_btn_json()})
        elif key == "bot1":
            # Bot1 auto-sends its own MTF analysis snapshot (+ charts if cached).
            dash_names = {s.get("name") for s in load_dashboard_symbols()}
            if pick in dash_names:
                send_analysis_charts(token, cb_chat, [pick])
            send_telegram(token, cb_chat, build_analysis_snapshot([pick]),
                          extra={"reply_markup": menu_btn_json()})
        # bot3: toast already confirms the watch — no auto content.


def _menu_targets(key: str, chat, limit: int = 4):
    """This user's watched symbols valid in the menu (no silent defaults)."""
    names = [n for n in watch_for(chat) if find_menu_entry(n)]
    return names[:limit]


def load_dashboard_symbols():
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "cloud_data", "dashboard.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("symbols") or []
    except Exception as e:
        print(f"  dashboard load error: {e}")
        return []


def build_banggia(items, top=8):
    """BOT2-style bảng giá from dicts with name/symbol/analysis."""
    summary_lines = ["📊 *BẢNG GIÁ*", "━" * 24, ""]
    for item in items[:top]:
        code = str(item.get("symbol", "")).split(":")[-1]
        summary_lines.append(f"*{item.get('name')}* · `{code}`")
        found = False
        for line in str(item.get("analysis") or "").split("\n"):
            if "Giá:" in line:
                summary_lines.append(line.replace("  ", " "))
                found = True
                break
        if not found:
            summary_lines.append("  (giá tạm thời không có)")
        summary_lines.append("")
    summary_lines.append(f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
    return "\n".join(summary_lines)


def build_banggia_dashboard(top=8):
    items = [{"name": s.get("name"), "symbol": s.get("symbol"),
              "analysis": s.get("analysis_text") or ""}
             for s in load_dashboard_symbols()]
    items = [i for i in items if i.get("name")]
    if not items:
        return None
    return build_banggia(items, top=top)


def _dash_quote_line(s: dict) -> str:
    """Compact one-line quote from a dashboard symbol entry (OHLCV cache)."""
    code = str(s.get("symbol") or "").split(":")[-1]
    name = s.get("name") or code
    c = (s.get("ohlcv") or {}).get("close") or []
    if not c:
        return f"• {name} · `{code}`: —"
    price = c[-1]
    chg = ((c[-1] - c[-25]) / c[-25] * 100) if len(c) >= 25 and c[-25] else 0.0
    ico = "🟢" if chg >= 0 else "🔴"
    px = f"{price:,.4f}" if price < 100 else f"{price:,.2f}"
    return f"• {name} · `{code}`: {px} ({chg:+.1f}%) {ico}"


def build_banggia_for(names, header=None):
    """Compact bảng giá: ONE short line per symbol (easy to read, never a
    huge table). Data from the dashboard OHLCV cache."""
    by_name = {s.get("name"): s for s in load_dashboard_symbols()}
    lines = [header or "💹 BẢNG GIÁ", "━" * 22]
    used = 0
    for n in names:
        s = by_name.get(n)
        if s and s.get("name"):
            lines.append(_dash_quote_line(s))
            used += 1
    if not used:
        return None
    lines.append("")
    lines.append(f"⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC %d/%m')} · "
                 f"{used} mã")
    return "\n".join(lines)


def build_analysis_snapshot(names):
    """Full MTF analysis text for `names` from the fresh dashboard cache."""
    by_name = {s.get("name"): s for s in load_dashboard_symbols()}
    lines = ["📊 *PHÂN TÍCH THEO YÊU CẦU*", "━" * 26, ""]
    used = 0
    for n in names:
        at = (by_name.get(n) or {}).get("analysis_text")
        if at:
            lines.append(at)
            lines.append("")
            used += 1
    if not used:
        return "⏳ Chưa có dữ liệu phân tích — thử lại sau 1-2 phút."
    lines.append("📦 Nguồn: cache dashboard (cập nhật theo mỗi run ~5 phút).")
    return "\n".join(lines)


def send_analysis_charts(token: str, chat, names) -> int:
    """BOT1 helper: send one chart photo per symbol from the dashboard cache
    (no network fetch — OHLCV + R/S levels come straight from cache)."""
    if not token or not chat:
        return 0
    by_name = {s.get("name"): s for s in load_dashboard_symbols()}
    sent = 0
    for n in names:
        sym = by_name.get(n)
        if not sym or not sym.get("ohlcv"):
            continue
        tv = sym.get("symbol") or ""
        details = None
        try:
            d = compute_analysis(n, tv, sym["ohlcv"])
            if d and "r1" in d and "s1" in d:
                details = d
        except Exception:
            details = None
        png = render_chart_png(n, tv, sym["ohlcv"], details)
        if png and send_telegram_photo(
                token, chat, png,
                caption=f"📊 {n} · 1H — biểu đồ kèm phân tích MTF"):
            sent += 1
    return sent


def handle_menu_action(act: str, key: str, token: str, chat: str):
    """Serve a menu action with the TAPPED bot's own token (role-pure):
    the caller guarantees act ∈ ROLE_ACTIONS[key], so the reply always
    lands in this bot's own window — no cross-bot jumps."""
    if not chat:
        return
    otoken = token
    if act == "chart":
        sent = 0
        for name in _menu_targets(key, chat, 3):
            e = find_menu_entry(name)
            if e and send_symbol_report(otoken, chat, e, force=True):
                sent += 1
        if not sent:
            send_telegram(otoken, chat,
                          "⏳ Chưa gửi được chart — dữ liệu chưa sẵn, thử lại sau 1-2 phút.")
        print(f"  Action chart (via {key}): {sent} report(s)")
    elif act == "analysis":
        names = _menu_targets(key, chat, 3)
        nchart = send_analysis_charts(otoken, chat, names)
        text = build_analysis_snapshot(names)
        ok = send_telegram(otoken, chat, text, extra={"reply_markup": menu_btn_json()})
        print(f"  Action analysis (via {key}): {'OK' if ok else 'FAIL'} "
              f"({nchart} chart(s))")
    elif act == "bang":
        # Priority: ⭐ default symbol > watched symbols > guidance toast.
        # (Never auto-send the full table — unreadable. Explicit path: 📋.)
        dq = default_quote_for(chat)
        watch = [n for n in watch_for(chat) if find_menu_entry(n)]
        names, header = None, None
        if dq and find_menu_entry(dq):
            names, header = [dq], f"🎯 BẢNG GIÁ · {dq.upper()}"
        elif watch:
            names, header = watch, "📊 BẢNG GIÁ THEO DÕI"
        if names:
            text = build_banggia_for(names, header)
            if not text:
                text = "⏳ Bảng giá chưa sẵn — dashboard chưa có dữ liệu các mã này."
            ok = send_telegram(otoken, chat, text,
                               extra={"reply_markup": menu_btn_json()})
            print(f"  Action bang (via {key}): {'OK' if ok else 'FAIL'} "
                  f"({len(names)} mã)")
        else:
            ok = send_telegram(
                otoken, chat,
                "🎯 Chưa có mã mặc định hay mã theo dõi nào.\n"
                "→ 🔎 chi tiết mã (BOT2) → ⭐ Gửi mặc định, hoặc\n"
                "   chạm một mã trong menu để ✅ theo dõi.",
                extra={"reply_markup": menu_btn_json()})
            print(f"  Action bang (via {key}): guidance (no default/watch)")
    elif act == "news":
        text, items = news_pipeline(mark_seen=False)
        if not items:
            text = "⏳ Chưa có tin mới — thử lại sau vài phút."
        ok = send_telegram(otoken, chat, text, parse_mode=None,
                           extra={"reply_markup": menu_btn_json()})
        print(f"  Action news (via {key}): {'OK' if ok else 'FAIL'}")
    else:
        return
    # remember this chat for the tapped bot too (routing/menu discovery)
    chats = state.setdefault("bot_chats", {}).setdefault(key, [])
    if str(chat) not in chats:
        chats.append(str(chat))
        save_state()


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


# Real EN -> VI machine translation cache (key: source text prefix)
_GT_CACHE = {}


def gtranslate_vi(text: str):
    """Machine-translate text to Vietnamese via the free Google translate
    endpoint (client=gtx, no API key). Returns the Vietnamese string, or
    None on failure so callers can fall back to the term dictionary."""
    if not text or len(text) > 500:
        return None
    key = text[:100]
    if key in _GT_CACHE:
        return _GT_CACHE[key]
    try:
        resp = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": "vi", "dt": "t", "q": text},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        translated = "".join(seg[0] for seg in (data[0] or []) if seg and seg[0])
        if translated and translated.strip():
            if len(_GT_CACHE) > 500:
                _GT_CACHE.clear()
            _GT_CACHE[key] = translated
            return translated
    except Exception as e:
        print(f"  gtranslate error: {e}")
    return None


def _parse_feed_ts(s):
    """RFC822 (RSS pubDate) or ISO-8601 (Atom) -> unix epoch (UTC) or None."""
    if not s:
        return None
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(s.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


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
                pub_el = item.find("pubDate")
                if title_el is not None and title_el.text:
                    title = title_el.text.strip()
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        items.append({
                            "title": title,
                            "url": link_el.text.strip() if link_el is not None and link_el.text else "",
                            "desc": (desc_el.text[:200] if desc_el is not None and desc_el.text else ""),
                            "source": feed_source,
                            "ts": _parse_feed_ts(
                                pub_el.text if pub_el is not None and pub_el.text else None),
                        })

            # Atom
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                title_el = entry.find("{http://www.w3.org/2005/Atom}title")
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
                pub_el = entry.find("{http://www.w3.org/2005/Atom}published")
                if pub_el is None:
                    pub_el = entry.find("{http://www.w3.org/2005/Atom}updated")
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
                            "ts": _parse_feed_ts(
                                pub_el.text if pub_el is not None and pub_el.text else None),
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

        # Yahoo 1H first (2mo for a warm EMA50 + ~84 H4 bars after resample);
        # CoinGecko only as fallback — its candle granularity varies by range,
        # which would distort resampled H4/D1 lines.
        if yahoo_sym:
            data = fetch_yahoo_chart(yahoo_sym, "1h", "2mo")
        if not data and coingecko_id:
            data = fetch_coingecko_ohlc(coingecko_id, "usd", 7)

        # D1 series for the 🧭 MTF block (all reports must show every khung)
        data1d = fetch_yahoo_chart(yahoo_sym, "1d", "6mo") if yahoo_sym else None

        if data:
            analysis = analyze_symbol(name, tv_sym, data, data1d=data1d)
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

    # Send to BOT1 (analysis) — chart photo for each standout signal first,
    # then the full text (menu button stays on the final message).
    if CONFIG["bot1_token"] and CONFIG["bot1_chat"]:
        charts = 0
        for name, _analysis in best_signals[:3]:
            item = next((a for a in all_analysis if a["name"] == name), None)
            if not item:
                continue
            details = None
            try:
                d = compute_analysis(name, item["symbol"], item["ohlcv"])
                if d and "r1" in d and "s1" in d:
                    details = d
            except Exception:
                details = None
            png = render_chart_png(name, item["symbol"], item["ohlcv"], details)
            if png and send_telegram_photo(
                    CONFIG["bot1_token"], CONFIG["bot1_chat"], png,
                    caption=f"🔥 {name} · 1H — tín hiệu nổi bật"):
                charts += 1
        ok1 = send_telegram(CONFIG["bot1_token"], CONFIG["bot1_chat"], text,
                            extra={"reply_markup": menu_btn_json()})
        print(f"BOT1: {'OK' if ok1 else 'FAIL'} ({charts} chart(s))")

    # Send summary to BOT2 (price feed - shorter)
    if CONFIG["bot2_token"] and CONFIG["bot2_chat"]:
        summary_text = build_banggia(all_analysis, top=8)
        # Menu button: tap to pick symbols to follow
        ok2 = send_telegram(CONFIG["bot2_token"], CONFIG["bot2_chat"], summary_text,
                            extra={"reply_markup": menu_btn_json()})
        print(f"BOT2: {'OK' if ok2 else 'FAIL'}")

    state["last_analysis"] = time.time()
    save_state()


def dashboard_price_strip() -> str:
    """Compact 'code price' strip from the dashboard (fresh from run_analysis)."""
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "cloud_data", "dashboard.json")
        with open(path, encoding="utf-8") as f:
            dd = json.load(f)
        parts = []
        for s in dd.get("symbols", []):
            closes = (s.get("ohlcv") or {}).get("close") or []
            if not closes:
                continue
            code = str(s.get("symbol", "")).split(":")[-1]
            parts.append(f"{code} {closes[-1]:,.2f}")
        if not parts:
            return None
        return "💰 GIÁ: " + " · ".join(parts)
    except Exception:
        return None


# News categories for the digest ("sơ đồ tư duy"): first match wins.
NEWS_CATS = [
    ("🇺🇸 Fed · Lãi suất · Kinh tế",
     ["FED", "FOMC", "ECB", "BOJ", "BOE", "POWELL", "CPI", "PPI", "NFP", "JOBS",
      "UNEMPLOYMENT", "RATE", "RATES", "INFLATION", "GDP", "PCE", "RECESSION",
      "ECONOMY", "ECONOMIC", "GROWTH", "DEBT", "STIMULUS"]),
    ("🌍 Địa chính trị · Chính sách",
     ["TARIFF", "TRADE", "SANCTION", "WAR", "GEOPOLIT", "CHINA", "CHINESE",
      "RUSSIA", "UKRAINE", "ISRAEL", "IRAN", "TAIWAN", "BRICS"]),
    ("🛢️ Dầu · Năng lượng · Hàng hóa",
     ["OIL", "WTI", "BRENT", "ENERGY", "GAS", "GOLD", "XAU", "SILVER",
      "COMMODITY", "OPEC", "COPPER"]),
    ("💰 Crypto",
     ["BTC", "BITCOIN", "ETH", "ETHEREUM", "CRYPTO", "SOLANA", "XRP", "ETF"]),
    ("📈 Chứng khoán · Cổ phiếu",
     ["STOCK", "STOCKS", "NASDAQ", "S&P", "DOW", "RALLY", "CRASH",
      "EARNINGS", "BANK", "FUTURES", "MARKET"]),
    ("💵 Forex · Dollar · Trái phiếu",
     ["USD", "DXY", "DOLLAR", "EURO", "POUND", "YEN", "JPY", "FOREX",
      "CURRENCY", "YIELD", "TREASURY", "BOND"]),
]


def classify_news_item(item) -> str:
    """Map one item to a digest category label (first keyword hit wins)."""
    title = (item.get("title") or "").upper()
    matched = " ".join(item.get("matched") or []).upper()
    hay = title + " " + matched
    for label, kws in NEWS_CATS:
        for kw in kws:
            if kw in hay:
                return label
    return "🌐 Khác"


def build_news_digest(new_items) -> str:
    """Compact bullet list: one line per item (translated headline, source),
    newest first — no links, no group walls."""
    now = datetime.now(timezone.utc).strftime("%H:%M %d/%m/%Y")
    lines = [f"📰 TIN MỚI · {now} UTC ({len(new_items)} tin)", "━" * 26]
    items = sorted(new_items, key=lambda it: it.get("ts") or 0, reverse=True)
    for it in items:
        title = (it.get("title_vi") or it.get("title") or "").replace("\n", " ")[:160]
        src = str(it.get("source") or "").split(":")[0][:18]
        lines.append(f"• {title}" + (f" ({src})" if src else ""))
    price_line = dashboard_price_strip()
    if price_line:
        lines.append("")
        lines.append(price_line)
    return "\n".join(lines)


def news_pipeline(mark_seen: bool = True):
    """Fetch, dedupe, translate and build the news message.

    Returns (text, selected_items). mark_seen=False is the on-demand path
    (menu 📰 button) - it does NOT consume titles, so the automatic push
    still delivers them later.
    """
    items = fetch_rss_news()
    tagged = filter_news(items, CONFIG["news_keywords"])

    # Dedup against seen_news FIRST, then cap — otherwise the cap would only
    # consider the first 6 pool items and miss fresh news deeper in the pool.
    # Round-robin across sources so one feed can't hog all slots (important now
    # that the pool spans EN + VN feeds). Only SELECTED items are marked seen.
    groups = {}
    for item in tagged:
        key = item["title"][:80]
        if mark_seen and key in state["seen_news"]:
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
            if mark_seen:
                state["seen_news"].append(it["title"][:80])
            new_items.append(it)
            if len(new_items) >= 6:
                break

    # Keep only last 300 seen (newest last)
    if mark_seen and len(state["seen_news"]) > 300:
        state["seen_news"] = state["seen_news"][-300:]

    if not new_items:
        return None, []

    # Machine-translate only the selected titles (fast, cached); fall back to
    # the financial term dictionary when the translator is unreachable.
    for item in new_items:
        vi = gtranslate_vi(item["title"])
        item["title_vi"] = vi if vi else translate_to_vietnamese(item["title"])

    return build_news_digest(new_items), new_items


def run_news():
    """Fetch and send news with Vietnamese translation."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Running news...")

    text, new_items = news_pipeline(mark_seen=True)
    if not new_items:
        print("  No new news items")
        state["last_news"] = time.time()
        save_state()
        return

    print(f"  News message: {len(text)} chars, {len(new_items)} items, sources: "
          f"{[i['source'] for i in new_items]}")

    # Send to BOT3 (news) as plain text so bare URLs remain clickable
    if CONFIG["bot3_token"] and CONFIG["bot3_chat"]:
        ok = send_telegram(CONFIG["bot3_token"], CONFIG["bot3_chat"], text,
                           parse_mode=None, extra={"reply_markup": menu_btn_json()})
        print(f"  News -> BOT3: {'OK' if ok else 'FAIL'}")
    # Fallback to BOT1 if BOT3 not configured
    elif CONFIG["bot1_token"] and CONFIG["bot1_chat"]:
        ok = send_telegram(CONFIG["bot1_token"], CONFIG["bot1_chat"], text, parse_mode=None)
        print(f"  News -> BOT1: {'OK' if ok else 'FAIL'}")

    state["last_news"] = time.time()
    save_state()


def _news_summary(item) -> str:
    """Clean RSS description -> short Vietnamese summary (no URLs/HTML).

    Strips HTML tags + http(s) links, collapses whitespace, translates the
    text, caps at ~240 chars, and escapes Telegram-Markdown specials so the
    stats report never carries a link wall or broken formatting.
    """
    desc = item.get("desc") or item.get("description") or ""
    if not desc:
        return ""
    desc = re.sub(r"<[^>]+>", " ", desc)
    desc = re.sub(r"https?://\S+", "", desc)
    desc = re.sub(r"&[a-z]+;", " ", desc)
    desc = re.sub(r"\s+", " ", desc).strip()
    if len(desc) < 25:  # too short / boilerplate — skip
        return ""
    vi = gtranslate_vi(desc)
    if not vi:
        vi = translate_to_vietnamese(desc)
    vi = re.sub(r"\s+", " ", vi or "").strip()
    if len(vi) > 240:
        vi = vi[:237] + "…"
    return re.sub(r"([_*`\[\]])", r"\\\1", vi)


def report_price_strip(max_symbols=8) -> str:
    """`CODE price (24h chg)` strip from the dashboard cache — with ticker codes."""
    parts = []
    for s in load_dashboard_symbols()[:max_symbols]:
        c = (s.get("ohlcv") or {}).get("close") or []
        if len(c) < 2:
            continue
        code = str(s.get("symbol") or "").split(":")[-1]
        if not code:
            continue
        price = c[-1]
        prev = c[-25] if len(c) >= 25 else c[0]
        chg = ((price - prev) / prev * 100) if prev else 0.0
        icon = "🟢" if chg >= 0 else "🔴"
        parts.append(f"`{code}` `{price:,.2f}` {icon}{chg:+.1f}%")
    return " · ".join(parts)


def build_news_report(items, now=None):
    """📊 3-hourly stats report — window = fresh (≤3h) + backlog (3h→7d).

    Totals, theme counts with a fresh delta, top sources, hot headlines with
    FULL content summaries, and a price strip with ticker codes. No links
    (the live digest already delivers links as news breaks).
    """
    now = now or time.time()
    cut_fresh = now - 3 * 3600
    cut_7d = now - 7 * 86400
    fresh, backlog = [], []
    undated = 0
    for it in items:
        ts = it.get("ts")
        if ts is None:
            undated += 1
            continue
        if ts < cut_7d:
            continue
        (fresh if ts >= cut_fresh else backlog).append(it)

    # Theme counts: whole 7-day window, plus fresh subset per theme
    cats = {}
    for it in fresh + backlog:
        lab = classify_news_item(it)
        cats.setdefault(lab, [0, 0])
        cats[lab][0] += 1
    for it in fresh:
        cats[classify_news_item(it)][1] += 1

    srcs = {}
    for it in fresh + backlog:
        s = (it.get("source") or "?").replace("feeds.", "").replace("www.", "")
        srcs[s] = srcs.get(s, 0) + 1
    top_srcs = sorted(srcs.items(), key=lambda x: -x[1])[:3]

    hot = sorted(fresh, key=lambda x: x.get("ts") or 0, reverse=True)[:5]
    for it in hot:
        vi = gtranslate_vi(it["title"])
        it["title_vi"] = vi if vi else translate_to_vietnamese(it["title"])

    now_s = datetime.now(timezone.utc).strftime("%H:%M %d/%m/%Y")
    total = len(fresh) + len(backlog)
    lines = [
        "📊 *BÁO CÁO TIN 3 GIỜ*",
        "━" * 26,
        f"⏰ {now_s} UTC · cửa sổ: 3h qua → 7 ngày",
        f"📰 Tổng (7 ngày): *{total}* · 3h qua: *{len(fresh)}* · "
        f"3h→7 ngày: *{len(backlog)}*",
    ]
    if undated:
        lines.append(f"   (không rõ thời gian: {undated} — không tính)")
    lines += ["", "📊 *Chủ đề (7 ngày):*"]
    cat_items = sorted(cats.items(), key=lambda x: -x[1][0])
    for lab, (tot, fr) in cat_items[:7]:
        suffix = f" · 🔥{fr} mới" if fr else ""
        lines.append(f"  {lab}: {tot}{suffix}")
    rest = sum(v[0] for _, v in cat_items[7:])
    if rest:
        lines.append(f"  • Khác: {rest}")
    if top_srcs:
        lines.append("")
        lines.append("🏆 *Nguồn nhiều nhất:* "
                     + " · ".join(f"{s} ({n})" for s, n in top_srcs))
    if hot:
        lines += ["", "🔥 *NỔI BẬT 3H QUA:*"]
        for i, it in enumerate(hot, 1):
            t = it.get("title_vi") or it["title"]
            if len(t) > 130:
                t = t[:127] + "…"
            lines.append(f"{i}. {t}")
            s = _news_summary(it)
            if s:
                lines.append(f"   ↳ {s}")
    strip = report_price_strip()
    if strip:
        lines += ["", "💹 *GIÁ (mã · giá · 24h):*", strip]
    lines += ["",
              "(↳ tin mới nhất đã gửi trực tiếp khi xuất hiện — "
              "bấm 📰 menu để xem chi tiết)"]
    return "\n".join(lines)


def run_news_report():
    """Every 3h: send the news statistics report (window 3h → 7d) to BOT3."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Running news report (3h stats)...")
    try:
        items = fetch_rss_news()
        text = build_news_report(items)
    except Exception as e:
        print(f"  News report error: {e}")
        state["last_news_report"] = time.time()
        save_state()
        return
    sent = False
    if CONFIG["bot3_token"] and CONFIG["bot3_chat"]:
        sent = send_telegram(CONFIG["bot3_token"], CONFIG["bot3_chat"], text,
                             extra={"reply_markup": menu_btn_json()})
        print(f"  News report -> BOT3: {'OK' if sent else 'FAIL'} ({len(text)} chars)")
    elif CONFIG["bot1_token"] and CONFIG["bot1_chat"]:
        sent = send_telegram(CONFIG["bot1_token"], CONFIG["bot1_chat"], text,
                             extra={"reply_markup": menu_btn_json()})
        print(f"  News report -> BOT1: {'OK' if sent else 'FAIL'} ({len(text)} chars)")
    state["last_news_report"] = time.time()
    save_state()


# ─── SIGNAL ENGINE (BOT2: breakout / trap / test đỉnh-đáy / sideways) ─────────

SIGNAL_COOLDOWN = 1800        # per (symbol, pattern) — 30 min
SIGNAL_TOUCH_WINDOW = 21600   # double-top/bottom retest window — 6 h


def detect_signals(name: str, data: dict) -> list:
    """Detect chart patterns on a series. Returns list of dicts:
    {key, icon, label, detail}. Pure stateless detection except the
    range-transition memory (state['sig_range']) and touch timestamps."""
    out = []
    if not data or len(data.get("close", [])) < 30:
        return out
    c, h, l = data["close"], data["high"], data["low"]
    n = len(c)
    price = c[-1]

    # ATR(14)
    trs = [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
           for i in range(max(1, n - 14), n)]
    atr = sum(trs) / len(trs) if trs else 0
    if atr <= 0:
        return out

    def f(p):
        return f"{p:,.4f}" if p < 100 else f"{p:,.2f}"

    # Range = 20 bars BEFORE the current bar
    hh, ll = max(h[-21:-1]), min(l[-21:-1])
    rng = hh - ll
    if rng <= 0:
        return out
    hh2, ll2 = max(h[-21:-2]), min(l[-21:-2])   # excludes last 2 bars
    in_range = (hh - price) > 0.25 * rng and (price - ll) > 0.25 * rng
    was_in = state.get("sig_range", {}).get(name)

    def add(key, icon, label, detail):
        out.append({"key": key, "icon": icon, "label": label, "detail": detail})

    brk_up = price > hh + 0.3 * atr
    brk_dn = price < ll - 0.3 * atr

    if brk_up:
        detail = (f"đóng {f(price)} > đỉnh 20 nến {f(hh)} "
                  f"(+{(price - hh) / atr:.1f} ATR)")
        if was_in:
            detail += " · phá SIDEWAYS"
        add("up", "🔺", "BREAKOUT LÊN — THOÁT VÙNG", detail)
    elif brk_dn:
        detail = (f"đóng {f(price)} < đáy 20 nến {f(ll)} "
                  f"(-{(ll - price) / atr:.1f} ATR)")
        if was_in:
            detail += " · phá SIDEWAYS"
        add("dn", "🔻", "BREAKOUT XUỐNG — THOÁT VÙNG", detail)
    elif c[-2] > hh2 + 0.3 * atr and price <= hh:
        add("trap_up", "🪤", "BULL TRAP (phá giả lên)",
            f"nến trước đóng {f(c[-2])} vượt {f(hh2)} nhưng nay quay vào "
            f"{f(price)} — mua đỉnh giả")
    elif c[-2] < ll2 - 0.3 * atr and price >= ll:
        add("trap_dn", "🪤", "BEAR TRAP (phá giả xuống)",
            f"nến trước đóng {f(c[-2])} dưới {f(ll2)} nhưng nay bật lại "
            f"{f(price)} — bán đáy giả")
    else:
        # Test of the range high/low (rejected touch)
        if h[-1] >= hh - 0.15 * atr and price < hh - 0.25 * atr:
            touch = state.setdefault("sig_touch", {})
            prev = float(touch.get(f"{name}:top", 0) or 0)
            if prev and now_ts() - prev < SIGNAL_TOUCH_WINDOW:
                add("dtop", "🏔️", "TEST ĐỈNH LẦN 2 — nguy cơ DOUBLE TOP",
                    f"chạm {f(hh)} lần 2 trong 6h, đóng lại {f(price)}")
            else:
                add("ttop", "⛰️", "TEST ĐỈNH bị từ chối",
                    f"râu chạm {f(hh)} nhưng đóng {f(price)} — phe mua chưa phá được")
            touch[f"{name}:top"] = now_ts()
        elif l[-1] <= ll + 0.15 * atr and price > ll + 0.25 * atr:
            touch = state.setdefault("sig_touch", {})
            prev = float(touch.get(f"{name}:bot", 0) or 0)
            if prev and now_ts() - prev < SIGNAL_TOUCH_WINDOW:
                add("dbot", "🏔️", "TEST ĐÁY LẦN 2 — nguy cơ DOUBLE BOTTOM",
                    f"chạm {f(ll)} lần 2 trong 6h, đóng lại {f(price)}")
            else:
                add("tbot", "⛏️", "TEST ĐÁY được giữ",
                    f"râu chạm {f(ll)} nhưng đóng {f(price)} — phe bán chưa phá được")
            touch[f"{name}:bot"] = now_ts()
        elif was_in is False and in_range:
            add("range_in", "📏", "VÀO VÙNG SIDEWAYS",
                f"giá bị gói trong {f(ll)} – {f(hh)} ({rng / atr:.1f} ATR) — "
                f"chờ phá, trade biên trên/dưới")

    # Momentum bursts ("going to the moon" / crash sprint)
    if len(c) >= 7:
        ups = all(c[i] > c[i - 1] for i in range(n - 4, n))
        dns = all(c[i] < c[i - 1] for i in range(n - 4, n))
        move = c[-1] - c[-6]
        if ups and move > 3 * atr:
            add("momo_up", "🚀", "MOMENTUM MẠNH — 5 nến xanh liên tiếp",
                f"+{f(move)} trong 5 nến ({move / atr:.1f} ATR) — "
                f"đừng FOMO đuổi, chờ retest")
        elif dns and move < -3 * atr:
            add("momo_dn", "☄️", "MOMENTUM GIẢM MẠNH — 5 nến đỏ liên tiếp",
                f"{f(move)} trong 5 nến ({abs(move) / atr:.1f} ATR) — "
                f"cẩn thận bắt đáy rơi")

    # Range-transition memory for the next scan
    state.setdefault("sig_range", {})[name] = bool(in_range and not (brk_up or brk_dn))
    return out[:3]


def now_ts() -> float:
    return time.time()


def signal_chats():
    """Chat ids BOT2 alerts go to: BOT2_CHAT env + /start discovery."""
    chats = []
    if CONFIG["bot2_chat"]:
        chats.append(str(CONFIG["bot2_chat"]))
    chats += [str(c) for c in (state.get("bot_chats") or {}).get("bot2", [])]
    out, seen = [], set()
    for c in chats:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def run_signals():
    """Periodic scan: pattern alerts (breakout/trap/test/sideways) via BOT2."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Running signal scan...")
    token = CONFIG["bot2_token"]
    if not token:
        print("  BOT2_TOKEN not configured - skip")
        return
    now = time.time()
    chats = signal_chats()
    if not chats:
        print("  Signals: no chat yet - send /start to BOT2 first")
        state["last_signals"] = now
        save_state()
        return

    # Targets: every user's watched symbols first, then priority symbols.
    watched_union = []
    for c in chats:
        for n in watch_for(c):
            if n not in watched_union and find_menu_entry(n):
                watched_union.append(n)
    targets = []
    for n in watched_union + [e[0] for e in CONFIG["symbols"]]:
        if n not in targets and find_menu_entry(n):
            targets.append(n)
        if len(targets) >= 10:
            break

    # Multi-timeframe scan: 1H raw + 4H resampled from the same fetch;
    # 1D from a separate daily fetch (24x resample of 1H would be too short
    # for the >=30-bar detector). CoinGecko fallback covers D1 only.
    TF_COOLDOWN = {"1H": SIGNAL_COOLDOWN,
                   "4H": SIGNAL_COOLDOWN * 2,
                   "1D": SIGNAL_COOLDOWN * 12}
    alerts = []  # (tf, name, sig) candidates — cooldown applied per chat at send
    for name in targets:
        e = find_menu_entry(name)
        if not e:
            continue
        _, cg, yahoo, tv = e
        data1h = fetch_yahoo_chart(yahoo, "1h", "1mo") if yahoo else None
        data1d = fetch_yahoo_chart(yahoo, "1d", "6mo") if yahoo else None
        if not data1h and not data1d and cg:
            data1d = fetch_coingecko_ohlc(cg, "usd", 90)
        series = []
        if data1h:
            series.append(("1H", data1h))
            series.append(("4H", resample_bars(data1h, 4)))
        if data1d:
            series.append(("1D", data1d))
        for tf, sdata in series:
            # Per-TF detector memory (range/touch) via a prefixed name.
            for sig in detect_signals(f"{name}|{tf}", sdata):
                alerts.append((tf, name, sig))
                if len(alerts) >= 24:
                    break
            if len(alerts) >= 24:
                break
        if len(alerts) >= 24:
            break

    if not alerts:
        state["signal_ts"] = {k: v for k, v in state.get("signal_ts", {}).items()
                              if now - v < 7 * 86400}
        state["last_signals"] = now
        save_state()
        print("  Signals: no new signals")
        return

    # ONE message per timeframe PER USER; each chat only sees alerts for
    # THEIR watched symbols (per-chat cooldown keys prevent repeats).
    sigts = state.setdefault("signal_ts", {})
    by_tf = {}
    for tf, name, sig in alerts:
        by_tf.setdefault(tf, []).append((name, sig))
    sent = 0
    chats_served = 0
    for chat in chats:
        wset = set(watch_for(chat))
        if not wset:
            continue  # user hasn't picked symbols yet — nothing personalized
        chat_alerts = 0
        for tf in ("1H", "4H", "1D"):
            group = []
            for name, sig in by_tf.get(tf, []):
                if name not in wset:
                    continue
                ck = f"{chat}|{name}|{tf}|{sig['key']}"
                last = float(sigts.get(ck, 0) or 0)
                if now - last < TF_COOLDOWN.get(tf, SIGNAL_COOLDOWN):
                    continue
                sigts[ck] = now
                group.append((name, sig))
                chat_alerts += 1
                if chat_alerts >= 8:
                    break
            if not group:
                continue
            cd = TF_COOLDOWN.get(tf, SIGNAL_COOLDOWN)
            cd_txt = "30 phút" if cd < 3600 else f"{cd // 3600} giờ"
            lines = [f"⚡ CẢNH BÁO · KHUNG {tf}", "━" * 26]
            for name, sig in group:
                e2 = find_menu_entry(name)
                code = str(e2[3]).split(":")[-1] if e2 else name
                lines.append(f"{sig['icon']} `{code}` *{name}* · {sig['label']}")
                lines.append(f"   {sig['detail']}")
            lines.append("")
            lines.append(f"⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC %d/%m')} · "
                         f"cooldown {cd_txt}/mẫu")
            text = "\n".join(lines)
            if send_telegram(token, chat, text, extra={"reply_markup": menu_btn_json()}):
                sent += 1
            if chat_alerts >= 8:
                break
        if chat_alerts:
            chats_served += 1

    # Prune old cooldown keys (keep state.json small)
    state["signal_ts"] = {k: v for k, v in state.get("signal_ts", {}).items()
                          if now - v < 7 * 86400}
    state["last_signals"] = now
    save_state()
    print(f"  Signals: {len(alerts)} cand / {sent} tin / {chats_served} chat(s)")


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
    print(f"News report every: {CONFIG['news_report_interval']}s")
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

        # 3-hourly news statistics report (window 3h → 7 days) via BOT3
        age_nrpt = now - float(state.get("last_news_report", 0) or 0)
        if age_nrpt >= CONFIG["news_report_interval"]:
            try:
                run_news_report()
            except Exception as e:
                print(f"News report error: {e}")
        else:
            print(f"Skip news report: last run {int(age_nrpt)}s ago "
                  f"(< {CONFIG['news_report_interval']}s)")

        # BOT4: chart + detailed plan for watched symbols
        age_bot4 = now - float(state.get("last_bot4", 0) or 0)
        if age_bot4 >= CONFIG["bot4_interval"]:
            try:
                run_bot4()
            except Exception as e:
                print(f"Bot4 error: {e}")
        else:
            print(f"Skip bot4: last run {int(age_bot4)}s ago (< {CONFIG['bot4_interval']}s)")

        # Signal engine: breakout / trap / test / sideways alerts (BOT2)
        age_sig = now - float(state.get("last_signals", 0) or 0)
        if age_sig >= CONFIG["analysis_interval"]:
            try:
                run_signals()
            except Exception as e:
                print(f"Signals error: {e}")
        else:
            print(f"Skip signals: last run {int(age_sig)}s ago (< {CONFIG['analysis_interval']}s)")

        # Menu poll: answer /menu + inline taps until close to the 300s
        # workflow timeout (analysis+news+bot4 typically eat the first ~90s)
        if not no_poll:
            deadline = min(start_ts + CONFIG["menu_poll_sec"], start_ts + 285)
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

        if now - float(state.get("last_news_report", 0) or 0) >= CONFIG["news_report_interval"]:
            try:
                run_news_report()
            except Exception as e:
                print(f"News report error: {e}")

        if now - float(state.get("last_bot4", 0) or 0) >= CONFIG["bot4_interval"]:
            try:
                run_bot4()
            except Exception as e:
                print(f"Bot4 error: {e}")

        if now - float(state.get("last_signals", 0) or 0) >= CONFIG["analysis_interval"]:
            try:
                run_signals()
            except Exception as e:
                print(f"Signals error: {e}")

        # Serve menu taps briefly each loop iteration
        try:
            poll_menu(time.time() + 30)
        except Exception as e:
            print(f"Menu poll error: {e}")

        time.sleep(10)


if __name__ == "__main__":
    main()
