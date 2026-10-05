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

    # Intervals (seconds)
    "analysis_interval": int(os.getenv("ANALYSIS_INTERVAL", "900")),  # 15 min
    "news_interval": int(os.getenv("NEWS_INTERVAL", "900")),  # 15 min

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

    # News keywords
    "news_keywords": ["XAUUSD", "GOLD", "DXY", "USD", "WTI", "OIL", "FED", "FOMC", "CPI", "NFP", "BTC", "ETH"],
    "news_feeds": [
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        "https://finance.yahoo.com/news/rssindex",
        "https://oilprice.com/rss/main",
    ],
}

# ─── STATE ────────────────────────────────────────────────────────────────────
state = {
    "last_analysis": 0,
    "last_news": 0,
    "seen_news": set(),
}

# ─── DATA FETCHERS ────────────────────────────────────────────────────────────

def fetch_coingecko_ohlc(coin_id: str, vs_currency: str = "usd", days: int = 5):
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

def analyze_symbol(name: str, tv_symbol: str, data: dict):
    """Analyze a symbol and return formatted analysis."""
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
        elif price < ema21 < ema50:
            trend = "🔴 GIẢM"
        else:
            trend = "🟡 ĐI NGANG"
    else:
        trend = "🟡 ĐI NGANG"

    # MACD (simplified using EMA difference)
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    macd_sig = "CHUYỂN"
    if ema12 and ema26:
        if ema12 > ema26:
            macd_sig = "BULL"
        else:
            macd_sig = "BEAR"

    # ADX strength
    adx_sig = "MẠNH" if adx and adx > 25 else "YẾU"

    # S/R (pivot from last 20 candles)
    recent_high = max(highs[-20:]) if len(highs) >= 20 else max(highs)
    recent_low = min(lows[-20:]) if len(lows) >= 20 else min(lows)
    pivot = (recent_high + recent_low + price) / 3
    r1 = 2 * pivot - recent_low
    s1 = 2 * pivot - recent_high

    # Psychology based on RSI
    if rsi:
        if rsi < 30:
            psyc = "QUÁ BÁN"
        elif rsi < 40:
            psyc = "SỢ HẠI"
        elif rsi < 60:
            psyc = "TRUNG TÍNH"
        elif rsi < 70:
            psyc = "THAM LAM"
        else:
            psyc = "QUÁ MUA"
    else:
        psyc = "N/A"

    # Format
    fmt_price = f"{price:,.4f}" if price < 100 else f"{price:,.2f}"
    fmt_r1 = f"{r1:,.4f}" if r1 < 100 else f"{r1:,.2f}"
    fmt_s1 = f"{s1:,.4f}" if s1 < 100 else f"{s1:,.2f}"

    lines = [
        f"*{name}* ({tv_symbol})",
        f"  Giá: `{fmt_price}` {icon} {chg:+.2f}%",
        f"  RSI: `{rsi:.1f}` | MACD: {macd_sig} | ADX: `{adx:.0f}` ({adx_sig})" if rsi and adx else f"  RSI: N/A | MACD: {macd_sig}",
        f"  Xu hướng: {trend}",
        f"  Kháng cự: `{fmt_r1}` | Hỗ trợ: `{fmt_s1}`",
        f"  Tâm lý: {psyc}",
        "",
    ]
    return "\n".join(lines)


# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def send_telegram(token: str, chat_id: str, text: str, parse_mode: str = "Markdown"):
    """Send message via Telegram Bot API."""
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        return data.get("ok", False)
    except Exception as e:
        print(f"Telegram send error: {e}")
        return False


# ─── NEWS ─────────────────────────────────────────────────────────────────────

def fetch_rss_news():
    """Fetch news from RSS feeds."""
    import xml.etree.ElementTree as ET

    items = []
    for feed_url in CONFIG["news_feeds"]:
        try:
            resp = requests.get(feed_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            for item in root.iter("item"):
                title = item.find("title")
                link = item.find("link")
                if title is not None and title.text:
                    items.append({
                        "title": title.text.strip(),
                        "url": link.text.strip() if link is not None and link.text else "",
                        "source": urllib.parse.urlparse(feed_url).netloc,
                    })
        except Exception as e:
            print(f"RSS error {feed_url}: {e}")

    return items


def filter_news(items: list, keywords: list, max_items: int = 5):
    """Filter news by keywords."""
    filtered = []
    for item in items:
        title_upper = item["title"].upper()
        matched = [kw for kw in keywords if kw.upper() in title_upper]
        if matched:
            item["matched"] = matched[:3]
            filtered.append(item)
            if len(filtered) >= max_items:
                break
    return filtered


# ─── MAIN FUNCTIONS ───────────────────────────────────────────────────────────

def run_analysis():
    """Run analysis on all symbols and send to bots."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Running analysis...")

    lines = [
        "⚡ *CẢNH BÁO PHÂN TÍCH*",
        "━" * 30,
        "",
    ]

    sent_count = 0
    for name, coingecko_id, yahoo_sym, tv_sym in CONFIG["symbols"]:
        data = None

        # Try CoinGecko for crypto/gold
        if coingecko_id:
            data = fetch_coingecko_ohlc(coingecko_id, "usd", 5)

        # Fallback to Yahoo
        if not data and yahoo_sym:
            data = fetch_yahoo_chart(yahoo_sym, "1h", "5d")

        if data:
            analysis = analyze_symbol(name, tv_sym, data)
            if analysis:
                lines.append(analysis)
                sent_count += 1
                print(f"  OK: {name}")
            else:
                print(f"  Analyze failed: {name}")
        else:
            print(f"  No data: {name}")

    if sent_count == 0:
        print("No data fetched, skipping...")
        return

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S %d/%m/%Y')} UTC | {sent_count} mã")

    text = "\n".join(lines)
    print(f"Message length: {len(text)} chars")

    # Send to BOT1
    if CONFIG["bot1_token"] and CONFIG["bot1_chat"]:
        ok1 = send_telegram(CONFIG["bot1_token"], CONFIG["bot1_chat"], text)
        print(f"BOT1: {'OK' if ok1 else 'FAIL'}")

    # Send to BOT2
    if CONFIG["bot2_token"] and CONFIG["bot2_chat"]:
        ok2 = send_telegram(CONFIG["bot2_token"], CONFIG["bot2_chat"], text)
        print(f"BOT2: {'OK' if ok2 else 'FAIL'}")

    state["last_analysis"] = time.time()


def run_news():
    """Fetch and send news."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Running news...")

    items = fetch_rss_news()
    filtered = filter_news(items, CONFIG["news_keywords"], max_items=5)

    # Filter out seen news
    new_items = []
    for item in filtered:
        key = item["title"][:80]
        if key not in state["seen_news"]:
            new_items.append(item)
            state["seen_news"].add(key)

    # Keep only last 200 seen
    if len(state["seen_news"]) > 200:
        state["seen_news"] = set(list(state["seen_news"])[-200:])

    if not new_items:
        state["last_news"] = time.time()
        return

    lines = [
        "📰 *TIN TỨC THỊ TRƯỜNG*",
        "━" * 28,
        "",
    ]

    for i, item in enumerate(new_items, 1):
        keywords_str = ", ".join(item["matched"][:3])
        title = item["title"][:100]
        lines.append(f"*{i}. {title}*")
        lines.append(f"   🏷️ {keywords_str} | 📡 {item['source']}")
        if item.get("url"):
            lines.append(f"   🔗 [Đọc thêm]({item['url']})")
        lines.append("")

    lines.append(f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S %d/%m/%Y')} UTC")

    text = "\n".join(lines)

    # Send to BOT3 (news) - or BOT1 if you prefer
    if CONFIG["bot1_token"] and CONFIG["bot1_chat"]:
        ok = send_telegram(CONFIG["bot1_token"], CONFIG["bot1_chat"], text)
        print(f"News -> BOT1: {'OK' if ok else 'FAIL'}")

    state["last_news"] = time.time()


def main():
    """Main loop. Supports --once flag for GitHub Actions."""
    once = "--once" in sys.argv

    print("=" * 50)
    print("Cloud Alerts V2 - Starting...")
    print(f"Mode: {'Once (GitHub Actions)' if once else 'Continuous (VPS)'}")
    print(f"Analysis interval: {CONFIG['analysis_interval']}s")
    print(f"News interval: {CONFIG['news_interval']}s")
    print(f"Symbols: {len(CONFIG['symbols'])}")
    print("=" * 50)

    if once:
        # GitHub Actions mode: run analysis + news once, then exit
        try:
            run_analysis()
        except Exception as e:
            print(f"Analysis error: {e}")
        try:
            run_news()
        except Exception as e:
            print(f"News error: {e}")
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

        time.sleep(10)


if __name__ == "__main__":
    main()
