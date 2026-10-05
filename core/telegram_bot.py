"""
Telegram bot with inline keyboard for symbol selection + rich analysis.
Commands: /start, /menu — inline keyboard toggles symbols on/off.
"""
import json
import os
import time
import threading
import httpx
from typing import Dict, List, Optional
import sys
sys.path.insert(0, r"D:\NOTEBOOK\news-lite")

_translate_cache: Dict[str, str] = {}

def translate_vi(text: str) -> str:
    """Translate English text to Vietnamese using MyMemory API (free, no key)."""
    if not text or not text.strip():
        return text
    cached = _translate_cache.get(text[:100])
    if cached:
        return cached
    try:
        r = httpx.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:500], "langpair": "en|vi"},
            timeout=10,
        )
        data = r.json()
        translated = data.get("responseData", {}).get("translatedText", "")
        if translated and len(translated) > 2:
            _translate_cache[text[:100]] = translated
            if len(_translate_cache) > 500:
                _translate_cache.clear()
            return translated
    except Exception:
        pass
    return text

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "telegram_config.json")
SUBS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "telegram_subs.json")

# ── All available symbols grouped by category ──────────────────
SYMBOL_GROUPS = {
    "crypto": {
        "icon": "₿",
        "name": "Crypto",
        "symbols": [
            ("BINANCE:BTCUSDT", "Bitcoin"),
            ("BINANCE:ETHUSDT", "Ethereum"),
            ("BINANCE:SOLUSDT", "Solana"),
            ("BINANCE:BNBUSDT", "BNB"),
            ("BINANCE:XRPUSDT", "XRP"),
            ("BINANCE:DOGEUSDT", "DOGE"),
            ("BINANCE:ADAUSDT", "Cardano"),
            ("BINANCE:AVAXUSDT", "Avalanche"),
        ],
    },
    "metals": {
        "icon": "🥇",
        "name": "Kim loại",
        "symbols": [
            ("OANDA:XAUUSD", "Vàng"),
            ("OANDA:XAGUSD", "Bạc"),
        ],
    },
    "energy": {
        "icon": "🛢",
        "name": "Năng lượng",
        "symbols": [
            ("NYMEX:CL1!", "Dầu WTI"),
            ("ICE:BZ1!", "Brent"),
            ("NYMEX:NG1!", "Khí tự nhiên"),
        ],
    },
    "forex": {
        "icon": "💱",
        "name": "Forex",
        "symbols": [
            ("FX:EURUSD", "EUR/USD"),
            ("FX:GBPUSD", "GBP/USD"),
            ("FX:USDJPY", "USD/JPY"),
            ("FX:AUDUSD", "AUD/USD"),
            ("FX:USDCAD", "USD/CAD"),
            ("FX:USDCHF", "USD/CHF"),
            ("FX:NZDUSD", "NZD/USD"),
        ],
    },
    "indices": {
        "icon": "📈",
        "name": "Chỉ số",
        "symbols": [
            ("TVC:SPX", "S&P 500"),
            ("TVC:NDX", "Nasdaq 100"),
            ("TVC:DJI", "Dow Jones"),
            ("TVC:DXY", "Dollar Index"),
            ("TVC:VIX", "VIX"),
        ],
    },
    "stocks": {
        "icon": "🇺🇸",
        "name": "CP Mỹ",
        "symbols": [
            ("NASDAQ:AAPL", "Apple"),
            ("NASDAQ:MSFT", "Microsoft"),
            ("NASDAQ:NVDA", "NVIDIA"),
            ("NASDAQ:GOOGL", "Google"),
            ("NASDAQ:AMZN", "Amazon"),
            ("NASDAQ:TSLA", "Tesla"),
            ("NASDAQ:META", "Meta"),
        ],
    },
}

# Flat lookup: tv_symbol -> display name
SYM_NAMES: Dict[str, str] = {}
for _g in SYMBOL_GROUPS.values():
    for _tv, _label in _g["symbols"]:
        SYM_NAMES[_tv] = _label

ALL_SYMBOLS = list(SYM_NAMES.keys())

# ── State ──────────────────────────────────────────────────────
_state = {
    # Bot 1: Tín hiệu giao dịch (signals, plans, charts)
    "signal_bot": {
        "enabled": True,
        "bot_token": "",
        "chat_id": "",
        "min_strength": 0.7,
        "send_interval": 300,
        "plan_enabled": True,
        "plan_interval": 900,
        "chart_enabled": True,
        "chart_interval": 600,
        "chart_symbols": [],
        "analysis_interval": 900,
    },
    # Bot 2: Cảnh báo giá + biểu đồ định kỳ
    "price_feed_bot": {
        "enabled": True,
        "bot_token": "",
        "chat_id": "",
        "symbols": ["OANDA:XAUUSD"],
        "timeframes": ["5m", "15m", "30m", "1H"],
        "interval": 300,
    },
    # Bot 3: Tin tức thị trường (gold, XAUUSD, DXY, USD, WTI...)
    "market_news_bot": {
        "enabled": True,
        "bot_token": "",
        "chat_id": "",
        "keywords": ["XAUUSD", "GOLD", "DXY", "USD", "WTI", "OIL", "USOIL", "FED", "FOMC", "CPI", "NFP", "POWELL", "INFLATION", "INTEREST RATE"],
        "interval": 600,
        "max_news": 5,
    },
    # Shared
    "last_sent": 0.0, "last_plan_sent": 0.0, "last_chart_sent": 0.0,
    "pending_alerts": [], "thread": None,
    "last_price_feed": 0.0,
    "last_news": 0.0,
    "seen_news": [],
    "last_analysis_alert": 0.0,
}

# Per-chat subscriptions: { "chat_id": ["BINANCE:BTCUSDT", ...] }
_subs: Dict[str, List[str]] = {}
# Per-chat menu state: { "chat_id": {"page": 0, "view": "main"} }
_menu_state: Dict[str, Dict] = {}


def _get_signal_bot() -> Dict:
    return _state.get("signal_bot", {})


def _get_price_feed_bot() -> Dict:
    return _state.get("price_feed_bot", {})


def _get_market_news_bot() -> Dict:
    return _state.get("market_news_bot", {})


def _load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)

            # New format: signal_bot + price_feed_bot + market_news_bot
            if "signal_bot" in cfg:
                _state["signal_bot"].update(cfg["signal_bot"])
            elif "bot_token" in cfg and cfg.get("bot_token"):
                # Migrate old single-bot format
                _state["signal_bot"] = {
                    "enabled": True,
                    "bot_token": cfg.get("bot_token", ""),
                    "chat_id": cfg.get("chat_id", ""),
                    "min_strength": cfg.get("min_strength", 0.7),
                    "send_interval": cfg.get("send_interval", 300),
                    "plan_enabled": cfg.get("plan_enabled", True),
                    "plan_interval": cfg.get("plan_interval", 900),
                    "chart_enabled": cfg.get("chart_enabled", True),
                    "chart_interval": cfg.get("chart_interval", 600),
                    "chart_symbols": cfg.get("chart_symbols", []),
                }

            if "price_feed_bot" in cfg:
                _state["price_feed_bot"].update(cfg["price_feed_bot"])
            elif "price_feed_symbol" in cfg:
                # Migrate old price_feed format
                _state["price_feed_bot"] = {
                    "enabled": cfg.get("price_feed_enabled", True),
                    "bot_token": cfg.get("bot_token", ""),
                    "chat_id": cfg.get("chat_id", ""),
                    "symbols": [cfg.get("price_feed_symbol", "OANDA:XAUUSD")],
                    "timeframes": cfg.get("price_feed_timeframes", ["5m", "15m", "30m", "1H"]),
                    "interval": cfg.get("price_feed_interval", 300),
                }

            if "market_news_bot" in cfg:
                _state["market_news_bot"].update(cfg["market_news_bot"])
    except Exception:
        pass


def _save_config():
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "signal_bot": _state["signal_bot"],
            "price_feed_bot": _state["price_feed_bot"],
            "market_news_bot": _state["market_news_bot"],
        }, f, indent=2)


def _load_subs():
    global _subs
    try:
        if os.path.exists(SUBS_FILE):
            with open(SUBS_FILE, "r") as f:
                _subs = json.load(f)
    except Exception:
        _subs = {}


def _save_subs():
    os.makedirs(os.path.dirname(SUBS_FILE), exist_ok=True)
    with open(SUBS_FILE, "w") as f:
        json.dump(_subs, f, indent=2)


def get_subscribed(chat_id: str = None) -> List[str]:
    """Get subscribed symbols for a chat. Falls back to signal_bot's chart_symbols config."""
    sb = _state["signal_bot"]
    if chat_id is None:
        chat_id = sb.get("chat_id", "")
    if chat_id in _subs and _subs[chat_id]:
        return _subs[chat_id]
    return sb.get("chart_symbols", [])


def set_subscribed(chat_id: str, symbols: List[str]):
    _subs[chat_id] = symbols
    _save_subs()


def get_config() -> Dict:
    _load_config()
    sb = _state["signal_bot"]
    pfb = _state["price_feed_bot"]
    nb = _state["market_news_bot"]

    def _mask(token):
        if not token or len(token) < 8:
            return ""
        return token[:4] + "..." + token[-4:]

    return {
        "signal_bot": {
            "enabled": sb["enabled"],
            "bot_token_masked": _mask(sb["bot_token"]),
            "chat_id": sb["chat_id"],
            "min_strength": sb["min_strength"],
            "send_interval": sb["send_interval"],
            "plan_enabled": sb["plan_enabled"],
            "plan_interval": sb["plan_interval"],
            "chart_enabled": sb["chart_enabled"],
            "chart_interval": sb["chart_interval"],
            "chart_symbols": sb.get("chart_symbols", []),
            "has_token": bool(sb["bot_token"]),
        },
        "price_feed_bot": {
            "enabled": pfb["enabled"],
            "bot_token_masked": _mask(pfb["bot_token"]),
            "chat_id": pfb["chat_id"],
            "symbols": pfb.get("symbols", []),
            "timeframes": pfb.get("timeframes", []),
            "interval": pfb.get("interval", 300),
            "has_token": bool(pfb["bot_token"]),
        },
        "market_news_bot": {
            "enabled": nb["enabled"],
            "bot_token_masked": _mask(nb["bot_token"]),
            "chat_id": nb["chat_id"],
            "keywords": nb.get("keywords", []),
            "interval": nb.get("interval", 600),
            "max_news": nb.get("max_news", 5),
            "has_token": bool(nb["bot_token"]),
        },
    }


def set_signal_bot(**kwargs) -> Dict:
    _load_config()
    for k in ["enabled", "bot_token", "chat_id", "min_strength", "send_interval",
              "plan_enabled", "plan_interval", "chart_enabled", "chart_interval",
              "chart_symbols"]:
        if k in kwargs and kwargs[k] is not None:
            _state["signal_bot"][k] = kwargs[k]
    _save_config()
    return get_config()


def set_price_feed_bot(**kwargs) -> Dict:
    _load_config()
    for k in ["enabled", "bot_token", "chat_id", "symbols", "timeframes", "interval"]:
        if k in kwargs and kwargs[k] is not None:
            _state["price_feed_bot"][k] = kwargs[k]
    _save_config()
    return get_config()


def set_market_news_bot(**kwargs) -> Dict:
    _load_config()
    for k in ["enabled", "bot_token", "chat_id", "keywords", "interval", "max_news"]:
        if k in kwargs and kwargs[k] is not None:
            _state["market_news_bot"][k] = kwargs[k]
    _save_config()
    return get_config()


# Backward compat
def get_config_legacy() -> Dict:
    cfg = get_config()
    sb = cfg["signal_bot"]
    return {**sb, "chat_id": sb["chat_id"]}


def set_config(**kwargs) -> Dict:
    """Legacy set_config — routes to signal_bot."""
    return set_signal_bot(**kwargs)


# ── Telegram API helpers ───────────────────────────────────────
_BOT_MAP = {
    "signal": "signal_bot",
    "price_feed": "price_feed_bot",
    "news": "market_news_bot",
}

def _send_message(text: str, chat_id: str = None, reply_markup: dict = None,
                  target: str = "signal") -> Dict:
    """Gửi message. target='signal'|'price_feed'|'news'."""
    _load_config()
    bot_key = _BOT_MAP.get(target, "signal_bot")
    bot = _state.get(bot_key, {})
    if not bot.get("bot_token") or not bot.get("enabled"):
        return {"ok": False, "error": f"Bot {target} chưa được bật hoặc thiếu token"}
    if chat_id and str(bot.get("chat_id")) != str(chat_id):
        return {"ok": False, "error": "Chat ID không khớp"}
    try:
        payload = {
            "chat_id": bot["chat_id"], "text": text,
            "parse_mode": "Markdown", "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        r = httpx.post(f"https://api.telegram.org/bot{bot['bot_token']}/sendMessage",
                       json=payload, timeout=15)
        data = r.json()
        if data.get("ok"):
            return {"ok": True}
        return {"ok": False, "error": data.get("description", "")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _send_photo(photo_path: str, caption: str = "", chat_id: str = None,
                target: str = "signal") -> Dict:
    """Gửi ảnh. target='signal'|'price_feed'|'news'."""
    _load_config()
    bot_key = _BOT_MAP.get(target, "signal_bot")
    bot = _state.get(bot_key, {})
    if not bot.get("bot_token") or not bot.get("enabled"):
        return {"ok": False, "error": f"Bot {target} chưa được bật hoặc thiếu token"}
    if chat_id and str(bot.get("chat_id")) != str(chat_id):
        return {"ok": False, "error": "Chat ID không khớp"}
    try:
        with open(photo_path, "rb") as f:
            r = httpx.post(
                f"https://api.telegram.org/bot{bot['bot_token']}/sendPhoto",
                data={"chat_id": bot["chat_id"], "caption": caption, "parse_mode": "Markdown"},
                files={"photo": f}, timeout=30,
            )
            resp = r.json()
            return {"ok": resp.get("ok", False), "error": resp.get("description", "")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _answer_callback(callback_query_id: str, text: str = ""):
    """Answer callback query from all active bots."""
    _load_config()
    for key in ["signal_bot", "price_feed_bot"]:
        bot = _state.get(key, {})
        if bot.get("bot_token") and bot.get("enabled"):
            try:
                httpx.post(
                    f"https://api.telegram.org/bot{bot['bot_token']}/answerCallbackQuery",
                    json={"callback_query_id": callback_query_id, "text": text, "show_alert": False},
                    timeout=5,
                )
            except Exception:
                pass


def _edit_message(chat_id: str, message_id: int, text: str, reply_markup: dict = None):
    """Edit an existing message (for keyboard updates)."""
    _load_config()
    # Tìm bot có chat_id này (thử cả 2 bot)
    for key in ["signal_bot", "price_feed_bot"]:
        bot = _state.get(key, {})
        if bot.get("bot_token") and str(bot.get("chat_id")) == str(chat_id):
            payload = {
                "chat_id": chat_id, "message_id": message_id,
                "text": text, "parse_mode": "Markdown",
            }
            if reply_markup:
                payload["reply_markup"] = json.dumps(reply_markup)
            try:
                httpx.post(
                    f"https://api.telegram.org/bot{bot['bot_token']}/editMessageText",
                    json=payload, timeout=10,
                )
            except Exception:
                pass
            return


def test_connection(target: str = "signal") -> Dict:
    _load_config()
    bot_key = _BOT_MAP.get(target, "signal_bot")
    bot = _state.get(bot_key, {})
    if not bot.get("bot_token") or not bot.get("chat_id"):
        return {"ok": False, "error": "Chưa cấu hình bot_token hoặc chat_id"}
    label = {"signal": "Tín hiệu", "price_feed": "Cảnh báo giá", "news": "Tin tức"}.get(target, target)
    return _send_message(f"🔔 *Bot {label}*\n✅ Kết nối thành công!", target=target)


# ── Menu Navigation ───────────────────────────────────────────
def _get_menu(chat_id: str) -> Dict:
    return _menu_state.setdefault(chat_id, {"page": 0, "view": "main", "category": ""})


def _sym_label(tv: str) -> str:
    name = SYM_NAMES.get(tv, tv)
    short = tv.split(":")[-1]
    return f"{short}"


def _build_signal_bot_menu(chat_id: str) -> tuple:
    """Build Bot 1 menu — Tín hiệu giao dịch (phân tích, plan, chart)."""
    _load_subs()
    subscribed = get_subscribed(chat_id)
    n = len(subscribed)
    sb = _state["signal_bot"]

    alert_icon = "🟢" if sb["enabled"] else "🔴"
    plan_icon = "🟢" if sb.get("plan_enabled") else "⚪"
    chart_icon = "🟢" if sb.get("chart_enabled") else "⚪"

    text = (
        f"┌{'─' * 36}┐\n"
        f"│  📊  *BOT TÍN HIỆU GIAO DỊCH*  {'':2}│\n"
        f"└{'─' * 36}┘\n\n"
        f"  📌 Theo dõi: *{n} mã*\n"
        f"  {alert_icon} Tín hiệu | {plan_icon} Plan | {chart_icon} Biểu đồ\n\n"
        f"  ── *LỆNH NHANH* ──\n"
        f"  `/analyze <mã>` — Phân tích 1 mã\n"
        f"  `/price <mã>` — Giá hiện tại\n"
        f"  `/status` — Trạng thái bot\n"
        f"  `/menu` — Menu chính"
    )

    if subscribed:
        preview = "  " + " · ".join([_sym_label(s) for s in subscribed[:6]])
        if len(subscribed) > 6:
            preview += f" +{len(subscribed) - 6}"
        text += f"\n\n  📋 *Đang theo dõi:*\n{preview}"

    buttons = [
        [
            {"text": "📌 Danh sách theo dõi", "callback_data": "nav:watchlist"},
            {"text": "⚙️ Cài đặt", "callback_data": "nav:settings"},
        ],
        [
            {"text": "📊 Phân tích nhanh", "callback_data": "nav:quick"},
            {"text": "🔄 Gửi chart", "callback_data": "action:charts"},
        ],
        [
            {"text": "📋 Gửi plan", "callback_data": "action:plans"},
            {"text": "🔔 Test kết nối", "callback_data": "action:test"},
        ],
        [{"text": "━━ Chọn theo nhóm ━━", "callback_data": "noop"}],
    ]
    for cat_key, cat in SYMBOL_GROUPS.items():
        count = sum(1 for s, _ in cat["symbols"] if s in subscribed)
        total = len(cat["symbols"])
        mark = f"({count}/{total})" if count > 0 else "(0)"
        buttons.append([{"text": f"{cat['icon']} {cat['name']} {mark}", "callback_data": f"cat:{cat_key}"}])

    return text, {"inline_keyboard": buttons}


def _build_price_feed_bot_menu(chat_id: str) -> tuple:
    """Build Bot 2 menu — Cảnh báo giá + biểu đồ định kỳ."""
    _load_config()
    pfb = _state["price_feed_bot"]

    pf_icon = "🟢" if pfb["enabled"] else "🔴"
    syms = pfb.get("symbols", [])
    tfs = pfb.get("timeframes", [])
    interval = pfb.get("interval", 300)

    sym_list = ", ".join([SYM_NAMES.get(s, s.split(":")[-1]) for s in syms[:4]])
    if len(syms) > 4:
        sym_list += f" +{len(syms)-4}"

    tf_list = ", ".join(tfs)

    text = (
        f"┌{'─' * 36}┐\n"
        f"│  💰  *BOT CẢNH BÁO GIÁ*  {'':9}│\n"
        f"└{'─' * 36}┘\n\n"
        f"  {pf_icon} Trạng thái: {'BẬT' if pfb['enabled'] else 'TẮT'}\n"
        f"  ⏱️ Chu kỳ: {interval // 60} phút\n"
        f"  💰 Symbols: {sym_list}\n"
        f"  📊 Khung: {tf_list}\n\n"
        f"  ── *LỆNH NHANH* ──\n"
        f"  `/price <mã>` — Giá hiện tại\n"
        f"  `/status` — Trạng thái bot\n"
        f"  `/menu` — Menu chính\n\n"
        f"  Bot tự gửi giá + chart định kỳ cho các mã đã cấu hình."
    )

    buttons = [
        [{"text": "⚙️ Cài đặt", "callback_data": "nav:pfsettings"}],
        [{"text": "🔄 Gửi ngay", "callback_data": "action:pfnow"}],
        [{"text": "🔔 Test kết nối", "callback_data": "action:pftest"}],
    ]

    return text, {"inline_keyboard": buttons}


def _build_news_bot_menu(chat_id: str) -> tuple:
    """Build Bot 3 menu — Tin tức thị trường."""
    _load_config()
    nb = _state["market_news_bot"]

    news_icon = "🟢" if nb["enabled"] else "🔴"
    keywords = nb.get("keywords", [])
    interval = nb.get("interval", 600)
    max_news = nb.get("max_news", 5)

    kw_list = ", ".join(keywords[:8])
    if len(keywords) > 8:
        kw_list += f" +{len(keywords)-8}"

    text = (
        f"┌{'─' * 36}┐\n"
        f"│  📰  *BOT TIN TỨC THỊ TRƯỜNG*  │\n"
        f"└{'─' * 36}┘\n\n"
        f"  {news_icon} Trạng thái: {'BẬT' if nb['enabled'] else 'TẮT'}\n"
        f"  ⏱️ Chu kỳ: {interval // 60} phút\n"
        f"  📰 Số tin/tối đa: {max_news}\n"
        f"  🏷️ Keywords: {kw_list}\n\n"
        f"  ── *LỆNH NHANH* ──\n"
        f"  `/status` — Trạng thái bot\n"
        f"  `/menu` — Menu chính\n\n"
        f"  Bot tự lọc tin quốc tế ảnh hưởng đến:\n"
        f"  XAUUSD, GOLD, DXY, USD, WTI, OIL..."
    )

    buttons = [
        [{"text": "⚙️ Cài đặt", "callback_data": "nav:nsettings"}],
        [{"text": "📰 Gửi tin ngay", "callback_data": "action:newsnow"}],
        [{"text": "🔔 Test kết nối", "callback_data": "action:newstest"}],
    ]

    return text, {"inline_keyboard": buttons}


def _build_watchlist_menu(chat_id: str) -> tuple:
    """Build watchlist management menu."""
    _load_subs()
    subscribed = get_subscribed(chat_id)
    n = len(subscribed)

    text = (
        f"┌{'─' * 36}┐\n"
        f"│  📌  *DANH SÁCH THEO DÕI*  {'':8}│\n"
        f"└{'─' * 36}┘\n\n"
        f"  Đang theo dõi: *{n} mã*\n"
    )

    if subscribed:
        lines = []
        for tv in subscribed[:20]:
            name = SYM_NAMES.get(tv, tv)
            short = tv.split(":")[-1]
            lines.append(f"    ✅ {short} — {name}")
        if n > 20:
            lines.append(f"    … và {n - 20} mã khác")
        text += "\n".join(lines)
    else:
        text += "  _Chưa chọn mã nào — hãy chọn bên dưới._"

    # Group buttons
    buttons = []
    for cat_key, cat in SYMBOL_GROUPS.items():
        count = sum(1 for s, _ in cat["symbols"] if s in subscribed)
        total = len(cat["symbols"])
        mark = f"✓{count}/{total}" if count > 0 else f"0/{total}"
        buttons.append([{"text": f"{cat['icon']} {cat['name']}  [{mark}]", "callback_data": f"cat:{cat_key}"}])

    buttons.append([
        {"text": "✅ Chọn tất cả", "callback_data": "wl:all"},
        {"text": "⬜ Bỏ tất cả", "callback_data": "wl:none"},
    ])
    buttons.append([{"text": "⬅️ Quay lại", "callback_data": "nav:main"}])

    return text, {"inline_keyboard": buttons}


def _build_category_menu(chat_id: str, cat_key: str) -> tuple:
    """Build a category's symbol toggle menu."""
    cat = SYMBOL_GROUPS.get(cat_key)
    if not cat:
        return "❌ Nhóm không tồn tại.", {"inline_keyboard": [[{"text": "⬅️ Quay lại", "callback_data": "nav:watchlist"}]]}

    _load_subs()
    subscribed = set(get_subscribed(chat_id))
    symbols = cat["symbols"]
    count = sum(1 for s, _ in symbols if s in subscribed)

    text = (
        f"┌{'─' * 36}┐\n"
        f"│  {cat['icon']}  *{cat['name'].upper()}*  ({count}/{len(symbols)})  │\n"
        f"└{'─' * 36}┘\n\n"
        f"  Chọn mã muốn theo dõi:"
    )

    buttons = []
    row = []
    for tv, label in symbols:
        check = "✅" if tv in subscribed else "⬜"
        row.append({"text": f"{check} {label}", "callback_data": f"tg:{tv}"})
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Row actions
    buttons.append([
        {"text": "✅ Chọn nhóm", "callback_data": f"catall:{cat_key}"},
        {"text": "⬜ Bỏ nhóm", "callback_data": f"catnone:{cat_key}"},
    ])
    buttons.append([
        {"text": "⬅️ Quay lại", "callback_data": "nav:watchlist"},
        {"text": "🏠 Chính", "callback_data": "nav:main"},
    ])

    return text, {"inline_keyboard": buttons}


def _build_settings_menu(chat_id: str) -> tuple:
    """Build settings menu for Bot 1 (signal bot)."""
    sb = _state["signal_bot"]
    a = "🟢" if sb["enabled"] else "🔴"
    p = "🟢" if sb.get("plan_enabled") else "⚪"
    c = "🟢" if sb.get("chart_enabled") else "⚪"
    ms = sb.get("min_strength", 0.7)
    si = sb.get("send_interval", 300)
    pi = sb.get("plan_interval", 900)
    ci = sb.get("chart_interval", 600)

    text = (
        f"┌{'─' * 36}┐\n"
        f"│  ⚙️  *CÀI ĐẶT BOT TÍN HIỆU*  │\n"
        f"└{'─' * 36}┘\n\n"
        f"  *Trạng thái:*\n"
        f"    {a} Tín hiệu tự động\n"
        f"    {p} Plan giao dịch (cứ {pi // 60} phút)\n"
        f"    {c} Biểu đồ (cứ {ci // 60} phút)\n\n"
        f"  *Ngưỡng:*\n"
        f"    ⚡ Strength tối thiểu: {ms:.0%}\n"
        f"    ⏱️ Gửi tối đa mỗi {si // 60} phút"
    )

    buttons = [
        [{"text": f"⚡ Strength: {ms:.0%}", "callback_data": "set:strength"}],
        [{"text": f"⏱️ Interval: {si // 60} phút", "callback_data": "set:si"}],
        [{"text": f"📋 Plan interval: {pi // 60} phút", "callback_data": "set:pi"}],
        [{"text": f"📊 Chart interval: {ci // 60} phút", "callback_data": "set:ci"}],
        [{"text": "⬅️ Quay lại", "callback_data": "nav:main"}],
    ]
    return text, {"inline_keyboard": buttons}


def _build_pf_settings_menu(chat_id: str) -> tuple:
    """Build settings menu for Bot 2 (price feed bot)."""
    pfb = _state["price_feed_bot"]
    pf = "🟢" if pfb.get("enabled") else "⚪"
    pfi = pfb.get("interval", 300)
    syms = pfb.get("symbols", ["OANDA:XAUUSD"])
    tfs = pfb.get("timeframes", ["5m", "15m", "30m", "1H"])

    sym_list = ", ".join([SYM_NAMES.get(s, s.split(":")[-1]) for s in syms[:3]])
    if len(syms) > 3:
        sym_list += f" +{len(syms)-3}"

    text = (
        f"┌{'─' * 36}┐\n"
        f"│  ⚙️  *CÀI ĐẶT BOT GIÁ*  {'':13}│\n"
        f"└{'─' * 36}┘\n\n"
        f"  {pf} Price feed: {'BẬT' if pfb.get('enabled') else 'TẮT'}\n"
        f"  ⏱️ Chu kỳ: {pfi // 60} phút\n"
        f"  💰 Symbols: {sym_list}\n"
        f"  📊 Khung: {', '.join(tfs)}\n\n"
        f"  Bot tự gửi giá + chart định kỳ."
    )

    buttons = [
        [{"text": f"⏱️ Chu kỳ: {pfi // 60} phút", "callback_data": "set:pfi"}],
        [{"text": "⬅️ Quay lại", "callback_data": "nav:main"}],
    ]
    return text, {"inline_keyboard": buttons}


def _build_news_settings_menu(chat_id: str) -> tuple:
    """Build settings menu for Bot 3 (news bot)."""
    nb = _state["market_news_bot"]
    news = "🟢" if nb.get("enabled") else "⚪"
    interval = nb.get("interval", 600)
    max_news = nb.get("max_news", 5)
    keywords = nb.get("keywords", [])

    kw_list = ", ".join(keywords[:6])
    if len(keywords) > 6:
        kw_list += f" +{len(keywords)-6}"

    text = (
        f"┌{'─' * 36}┐\n"
        f"│  ⚙️  *CÀI ĐẶT BOT TIN TỨC*  │\n"
        f"└{'─' * 36}┘\n\n"
        f"  {news} News: {'BẬT' if nb.get('enabled') else 'TẮT'}\n"
        f"  ⏱️ Chu kỳ: {interval // 60} phút\n"
        f"  📰 Số tin tối đa: {max_news}\n"
        f"  🏷️ Keywords: {kw_list}\n\n"
        f"  Bot lọc tin quốc tế ảnh hưởng đến:\n"
        f"  XAUUSD, GOLD, DXY, USD, WTI, OIL..."
    )

    buttons = [
        [{"text": f"⏱️ Chu kỳ: {interval // 60} phút", "callback_data": "set:nfi"}],
        [{"text": f"📰 Số tin: {max_news}", "callback_data": "set:nmax"}],
        [{"text": "⬅️ Quay lại", "callback_data": "nav:main"}],
    ]
    return text, {"inline_keyboard": buttons}


def _build_quick_menu(chat_id: str) -> tuple:
    """Build quick analysis menu — pick a symbol."""
    _load_subs()
    subscribed = get_subscribed(chat_id)
    text = (
        f"┌{'─' * 36}┐\n"
        f"│  📊  *PHÂN TÍCH NHANH*  {'':8}│\n"
        f"└{'─' * 36}┘\n\n"
        f"  Chọn mã để phân tích:"
    )

    # Show subscribed first, then all symbols
    buttons = []
    if subscribed:
        buttons.append([{"text": "── Theo dõi ──", "callback_data": "noop"}])
        row = []
        for tv in subscribed[:12]:
            short = _sym_label(tv)
            row.append({"text": short, "callback_data": f"qa:{tv}"})
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

    buttons.append([{"text": "── Tất cả ──", "callback_data": "noop"}])
    row = []
    for tv in ALL_SYMBOLS[:18]:
        short = _sym_label(tv)
        row.append({"text": short, "callback_data": f"qa:{tv}"})
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([{"text": "⬅️ Quay lại", "callback_data": "nav:main"}])
    return text, {"inline_keyboard": buttons}


def _handle_settings_set(chat_id: str, key: str):
    """Handle settings key change cycles."""
    _load_config()
    sb = _state["signal_bot"]
    pfb = _state["price_feed_bot"]
    nb = _state["market_news_bot"]

    # Price feed toggle (on/off)
    if key == "pf":
        pfb["enabled"] = not pfb.get("enabled", True)
        _save_config()
        return

    # Settings keys
    if key == "strength":
        cycles = [0.5, 0.6, 0.7, 0.8, 0.9]
        cur = sb.get("min_strength", 0.7)
        try:
            idx = cycles.index(cur)
        except ValueError:
            idx = 0
        sb["min_strength"] = cycles[(idx + 1) % len(cycles)]
    elif key == "si":
        cycles = [120, 300, 600, 900]
        cur = sb.get("send_interval", 300)
        try:
            idx = cycles.index(cur)
        except ValueError:
            idx = 0
        sb["send_interval"] = cycles[(idx + 1) % len(cycles)]
    elif key == "pi":
        cycles = [300, 600, 900, 1800]
        cur = sb.get("plan_interval", 900)
        try:
            idx = cycles.index(cur)
        except ValueError:
            idx = 0
        sb["plan_interval"] = cycles[(idx + 1) % len(cycles)]
    elif key == "ci":
        cycles = [300, 600, 900, 1800]
        cur = sb.get("chart_interval", 600)
        try:
            idx = cycles.index(cur)
        except ValueError:
            idx = 0
        sb["chart_interval"] = cycles[(idx + 1) % len(cycles)]
    elif key == "pfi":
        cycles = [60, 120, 300, 600, 900]
        cur = pfb.get("interval", 300)
        try:
            idx = cycles.index(cur)
        except ValueError:
            idx = 0
        pfb["interval"] = cycles[(idx + 1) % len(cycles)]
    elif key == "nfi":
        cycles = [300, 600, 900, 1800]
        cur = nb.get("interval", 600)
        try:
            idx = cycles.index(cur)
        except ValueError:
            idx = 0
        nb["interval"] = cycles[(idx + 1) % len(cycles)]
    elif key == "nmax":
        cycles = [3, 5, 8, 10]
        cur = nb.get("max_news", 5)
        try:
            idx = cycles.index(cur)
        except ValueError:
            idx = 0
        nb["max_news"] = cycles[(idx + 1) % len(cycles)]
    else:
        return
    _save_config()


def handle_start(chat_id: str, bot_type: str = "signal"):
    """Handle /start command — show menu for the specific bot."""
    _load_subs()
    _load_config()
    if bot_type == "price_feed":
        text, kb = _build_price_feed_bot_menu(chat_id)
    elif bot_type == "news":
        text, kb = _build_news_bot_menu(chat_id)
    else:
        text, kb = _build_signal_bot_menu(chat_id)
    _send_message(text, chat_id=chat_id, reply_markup=kb, target=bot_type)


def handle_menu(chat_id: str, message_id: int = None, bot_type: str = "signal"):
    """Handle /menu — show main menu for the specific bot."""
    _load_subs()
    _load_config()
    if bot_type == "price_feed":
        text, kb = _build_price_feed_bot_menu(chat_id)
    elif bot_type == "news":
        text, kb = _build_news_bot_menu(chat_id)
    else:
        text, kb = _build_signal_bot_menu(chat_id)
    if message_id:
        _edit_message(chat_id, message_id, text, reply_markup=kb)
    else:
        _send_message(text, chat_id=chat_id, reply_markup=kb, target=bot_type)


def _handle_analyze(chat_id: str, symbol: str):
    """Handle /analyze <symbol> — send full analysis."""
    try:
        from core.alerts import _get_df
        df = _get_df(symbol, "1H")
        if df is None or len(df) < 20:
            _send_message(f"❌ Không đủ dữ liệu cho `{symbol}`", chat_id=chat_id)
            return
        try:
            from core.multi_timeframe import MTFAnalyzer
            from config import MTF_TIMEFRAMES
            scraper = None
            try:
                from core.alerts import _get_scraper
                scraper = _get_scraper()
            except Exception:
                pass
            mtf = MTFAnalyzer(symbol, MTF_TIMEFRAMES).run(scraper) if scraper else None
            mtf_consensus = mtf.get("consensus", {}) if mtf else {}
        except Exception:
            mtf_consensus = {}
        text = _build_full_analysis(symbol, df, "1H", mtf_consensus)
        _send_message(text, chat_id=chat_id)
    except Exception as e:
        _send_message(f"❌ Lỗi phân tích `{symbol}`: {str(e)[:100]}", chat_id=chat_id)


def _handle_price(chat_id: str, symbol: str):
    """Handle /price <symbol> — send quick price info."""
    try:
        from core.alerts import _get_df, _safe
        df = _get_df(symbol, "5m")
        if df is None or len(df) < 2:
            _send_message(f"❌ Không lấy được giá `{symbol}`", chat_id=chat_id)
            return
        price = _safe(df["close"].iloc[-1])
        prev = _safe(df["close"].iloc[-2])
        chg = ((price - prev) / prev * 100) if prev and prev > 0 else 0
        high = _safe(df["high"].tail(20).max())
        low = _safe(df["low"].tail(20).min())
        icon = "🟢" if chg >= 0 else "🔴"
        name = SYM_NAMES.get(symbol, symbol)
        text = (
            f"┌{'─' * 30}┐\n"
            f"│  💰  *{name}*  {'':12}│\n"
            f"└{'─' * 30}┘\n\n"
            f"  Giá: `{price:,.2f}` {icon} ({chg:+.2f}%)\n"
            f"  Cao: `{high:,.2f}` | Thấp: `{low:,.2f}`\n"
            f"  {symbol}"
        )
        _send_message(text, chat_id=chat_id)
    except Exception as e:
        _send_message(f"❌ Lỗi: {str(e)[:100]}", chat_id=chat_id)


def _handle_status(chat_id: str, bot_type: str = "signal"):
    """Handle /status — send bot status dashboard."""
    _load_config()
    _load_subs()
    subscribed = get_subscribed(chat_id)
    sb = _state["signal_bot"]
    pfb = _state["price_feed_bot"]
    nb = _state["market_news_bot"]

    a = "🟢" if sb["enabled"] else "🔴"
    p = "🟢" if sb.get("plan_enabled") else "⚪"
    c = "🟢" if sb.get("chart_enabled") else "⚪"
    pf = "🟢" if pfb.get("enabled") else "⚪"
    news = "🟢" if nb.get("enabled") else "⚪"

    text = (
        f"┌{'─' * 36}┐\n"
        f"│  📊  *TRẠNG THÁI HỆ THỐNG*  {'':7}│\n"
        f"└{'─' * 36}┘\n\n"
        f"  *Bot 1 — Tín hiệu giao dịch:*\n"
        f"    {a} Tín hiệu (tối thiểu {sb.get('min_strength', 0.7):.0%})\n"
        f"    {p} Plan mỗi {sb.get('plan_interval', 900) // 60} phút\n"
        f"    {c} Chart mỗi {sb.get('chart_interval', 600) // 60} phút\n"
        f"    Token: {'✅' if sb.get('bot_token') else '❌'}\n\n"
        f"  *Bot 2 — Cảnh báo giá:*\n"
        f"    {pf} Price feed (cứ {pfb.get('interval', 300) // 60} phút)\n"
        f"    💰 Symbol: {', '.join(pfb.get('symbols', ['OANDA:XAUUSD']))}\n"
        f"    📊 Khung: {', '.join(pfb.get('timeframes', ['5m', '15m', '30m', '1H']))}\n"
        f"    Token: {'✅' if pfb.get('bot_token') else '❌'}\n\n"
        f"  *Bot 3 — Tin tức thị trường:*\n"
        f"    {news} News (cứ {nb.get('interval', 600) // 60} phút)\n"
        f"    🏷️ Keywords: {', '.join(nb.get('keywords', [])[:5])}\n"
        f"    📰 Số tin tối đa: {nb.get('max_news', 5)}\n"
        f"    Token: {'✅' if nb.get('bot_token') else '❌'}\n\n"
        f"  *Danh sách:* {len(subscribed)} mã"
    )
    _send_message(text, chat_id=chat_id, target=bot_type)


def handle_callback(callback_query: dict, bot_type: str = "signal"):
    """Handle inline keyboard callback."""
    data = callback_query.get("data", "")
    chat_id = str(callback_query["message"]["chat"]["id"])
    message_id = callback_query["message"]["message_id"]
    cq_id = callback_query["id"]

    _load_subs()
    _load_config()
    menu = _get_menu(chat_id)

    # No-op (group header)
    if data == "noop":
        _answer_callback(cq_id, "")
        return

    # Navigation
    if data.startswith("nav:"):
        view = data.split(":", 1)[1]
        menu["view"] = view
        if view == "main":
            if bot_type == "price_feed":
                text, kb = _build_price_feed_bot_menu(chat_id)
            elif bot_type == "news":
                text, kb = _build_news_bot_menu(chat_id)
            else:
                text, kb = _build_signal_bot_menu(chat_id)
        elif view == "watchlist":
            text, kb = _build_watchlist_menu(chat_id)
        elif view == "settings":
            text, kb = _build_settings_menu(chat_id)
        elif view == "pfsettings":
            text, kb = _build_pf_settings_menu(chat_id)
        elif view == "nsettings":
            text, kb = _build_news_settings_menu(chat_id)
        elif view == "quick":
            text, kb = _build_quick_menu(chat_id)
        else:
            text, kb = _build_signal_bot_menu(chat_id)
        _answer_callback(cq_id, "")
        _edit_message(chat_id, message_id, text, reply_markup=kb)
        return

    # Category view
    if data.startswith("cat:"):
        cat_key = data.split(":", 1)[1]
        menu["category"] = cat_key
        menu["view"] = "category"
        text, kb = _build_category_menu(chat_id, cat_key)
        _answer_callback(cq_id, "")
        _edit_message(chat_id, message_id, text, reply_markup=kb)
        return

    # Toggle symbol
    if data.startswith("tg:"):
        sym = data.split(":", 1)[1]
        subs = get_subscribed(chat_id)
        if sym in subs:
            subs.remove(sym)
            _answer_callback(cq_id, f"⬜ Bỏ {SYM_NAMES.get(sym, sym)}")
        else:
            subs.append(sym)
            _answer_callback(cq_id, f"✅ Thêm {SYM_NAMES.get(sym, sym)}")
        set_subscribed(chat_id, subs)
        # Rebuild current category view
        cat_key = menu.get("category", "")
        if cat_key:
            text, kb = _build_category_menu(chat_id, cat_key)
        else:
            text, kb = _build_watchlist_menu(chat_id)
        _edit_message(chat_id, message_id, text, reply_markup=kb)
        return

    # Category select all / none
    if data.startswith("catall:"):
        cat_key = data.split(":", 1)[1]
        cat = SYMBOL_GROUPS.get(cat_key, {})
        new_syms = [s for s, _ in cat.get("symbols", [])]
        subs = get_subscribed(chat_id)
        # Add without duplicates
        for s in new_syms:
            if s not in subs:
                subs.append(s)
        set_subscribed(chat_id, subs)
        _answer_callback(cq_id, f"✅ Đã chọn {len(new_syms)} mã {cat.get('name', '')}")
        text, kb = _build_category_menu(chat_id, cat_key)
        _edit_message(chat_id, message_id, text, reply_markup=kb)
        return

    if data.startswith("catnone:"):
        cat_key = data.split(":", 1)[1]
        cat = SYMBOL_GROUPS.get(cat_key, {})
        cat_syms = set(s for s, _ in cat.get("symbols", []))
        subs = [s for s in get_subscribed(chat_id) if s not in cat_syms]
        set_subscribed(chat_id, subs)
        _answer_callback(cq_id, f"⬜ Đã bỏ nhóm {cat.get('name', '')}")
        text, kb = _build_category_menu(chat_id, cat_key)
        _edit_message(chat_id, message_id, text, reply_markup=kb)
        return

    # Watchlist actions
    if data == "wl:all":
        set_subscribed(chat_id, list(ALL_SYMBOLS))
        _answer_callback(cq_id, f"✅ Đã chọn tất cả {len(ALL_SYMBOLS)} mã")
        text, kb = _build_watchlist_menu(chat_id)
        _edit_message(chat_id, message_id, text, reply_markup=kb)
        return

    if data == "wl:none":
        set_subscribed(chat_id, [])
        _answer_callback(cq_id, "⬜ Đã bỏ tất cả")
        text, kb = _build_watchlist_menu(chat_id)
        _edit_message(chat_id, message_id, text, reply_markup=kb)
        return

    # Quick analysis
    if data.startswith("qa:"):
        sym = data.split(":", 1)[1]
        _answer_callback(cq_id, f"📊 {SYM_NAMES.get(sym, sym)}")
        _handle_analyze(chat_id, sym)
        return

    # Settings cycle
    if data.startswith("set:"):
        key = data.split(":", 1)[1]
        _handle_settings_set(chat_id, key)
        _answer_callback(cq_id, "⚙️ Đã cập nhật")
        if key in ("nfi", "nmax"):
            text, kb = _build_news_settings_menu(chat_id)
        elif key == "pfi":
            text, kb = _build_pf_settings_menu(chat_id)
        else:
            text, kb = _build_settings_menu(chat_id)
        _edit_message(chat_id, message_id, text, reply_markup=kb)
        return

    # Actions — Bot 1 (signal)
    if data == "action:charts":
        _answer_callback(cq_id, "📊 Đang gửi chart…")
        from core.telegram_bot import push_charts
        _state["last_chart_sent"] = 0  # Force
        push_charts(chat_id=chat_id)
        return

    if data == "action:plans":
        _answer_callback(cq_id, "📋 Đang gửi plan…")
        from core.telegram_bot import push_plans
        _state["last_plan_sent"] = 0  # Force
        from core.alerts import generate_plans_all
        subs = get_subscribed(chat_id)
        plans = generate_plans_all(symbols=subs or None, interval="1H", force=True, limit=10)
        push_plans(plans, chat_id=chat_id)
        return

    if data == "action:test":
        _answer_callback(cq_id, "🔔 Test kết nối…")
        result = _send_message("✅ *Kết nối OK!*\nBot Tín hiệu đang hoạt động.", chat_id=chat_id, target="signal")
        if not result.get("ok"):
            _answer_callback(cq_id, f"❌ {result.get('error', 'Lỗi')}")
        return

    # Actions — Bot 2 (price feed)
    if data == "action:pfnow":
        _answer_callback(cq_id, "💰 Đang gửi giá…")
        _state["last_price_feed"] = 0  # Force
        push_price_feed(chat_id=chat_id)
        return

    if data == "action:pftest":
        _answer_callback(cq_id, "🔔 Test kết nối…")
        result = _send_message("✅ *Kết nối OK!*\nBot Giá đang hoạt động.", chat_id=chat_id, target="price_feed")
        if not result.get("ok"):
            _answer_callback(cq_id, f"❌ {result.get('error', 'Lỗi')}")
        return

    # Actions — Bot 3 (news)
    if data == "action:newsnow":
        _answer_callback(cq_id, "📰 Đang gửi tin…")
        _state["last_news"] = 0  # Force
        push_news(chat_id=chat_id)
        return

    if data == "action:newstest":
        _answer_callback(cq_id, "🔔 Test kết nối…")
        result = _send_message("✅ *Kết nối OK!*\nBot Tin tức đang hoạt động.", chat_id=chat_id, target="news")
        if not result.get("ok"):
            _answer_callback(cq_id, f"❌ {result.get('error', 'Lỗi')}")
        return

    # Legacy callbacks (fallback)
    if data == "refresh_menu":
        _answer_callback(cq_id, "🔄 Đã làm mới")
        handle_menu(chat_id, message_id, bot_type=bot_type)
        return

    if data.startswith("toggle:"):
        sym = data.split(":", 1)[1]
        subs = get_subscribed(chat_id)
        if sym in subs:
            subs.remove(sym)
            _answer_callback(cq_id, f"⬜ Đã bỏ {sym}")
        else:
            subs.append(sym)
            _answer_callback(cq_id, f"✅ Đã thêm {sym}")
        set_subscribed(chat_id, subs)
        handle_menu(chat_id, message_id, bot_type=bot_type)
        return

    _answer_callback(cq_id, "")


def poll_updates():
    """Long-poll for bot updates from all 3 bots."""
    _load_config()
    offsets = {}

    while True:
        _load_config()
        sb = _state["signal_bot"]
        pfb = _state["price_feed_bot"]
        nb = _state["market_news_bot"]

        # Poll signal_bot
        if sb.get("bot_token") and sb.get("enabled"):
            try:
                r = httpx.get(
                    f"https://api.telegram.org/bot{sb['bot_token']}/getUpdates",
                    params={
                        "offset": offsets.get("signal", 0),
                        "timeout": 25,
                        "allowed_updates": json.dumps(["message", "callback_query"])
                    },
                    timeout=30,
                )
                data = r.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offsets["signal"] = update["update_id"] + 1
                        _process_update(update, "signal")
            except Exception:
                pass

        # Poll price_feed_bot
        if pfb.get("bot_token") and pfb.get("enabled"):
            try:
                r = httpx.get(
                    f"https://api.telegram.org/bot{pfb['bot_token']}/getUpdates",
                    params={
                        "offset": offsets.get("price_feed", 0),
                        "timeout": 25,
                        "allowed_updates": json.dumps(["message", "callback_query"])
                    },
                    timeout=30,
                )
                data = r.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offsets["price_feed"] = update["update_id"] + 1
                        _process_update(update, "price_feed")
            except Exception:
                pass

        # Poll market_news_bot
        if nb.get("bot_token") and nb.get("enabled"):
            try:
                r = httpx.get(
                    f"https://api.telegram.org/bot{nb['bot_token']}/getUpdates",
                    params={
                        "offset": offsets.get("news", 0),
                        "timeout": 25,
                        "allowed_updates": json.dumps(["message", "callback_query"])
                    },
                    timeout=30,
                )
                data = r.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offsets["news"] = update["update_id"] + 1
                        _process_update(update, "news")
            except Exception:
                pass

        time.sleep(1)


def _process_update(update: Dict, bot_type: str):
    """Process a single Telegram update (message or callback)."""
    msg = update.get("message")
    cb = update.get("callback_query")

    if msg and msg.get("text"):
        text = msg["text"].strip()
        cid = str(msg["chat"]["id"])
        if text.startswith("/start"):
            handle_start(cid, bot_type=bot_type)
        elif text.startswith("/menu"):
            handle_menu(cid, bot_type=bot_type)
        elif text.startswith("/status"):
            _handle_status(cid)
        elif text.startswith("/analyze"):
            if bot_type != "signal":
                _send_message("📌 Lệnh này chỉ có ở Bot Tín hiệu", chat_id=cid, target=bot_type)
            else:
                parts = text.split(None, 1)
                if len(parts) >= 2:
                    _handle_analyze(cid, parts[1].strip())
                else:
                    _send_message("📌 *Cách dùng:* `/analyze BINANCE:BTCUSDT`", chat_id=cid, target=bot_type)
        elif text.startswith("/price"):
            parts = text.split(None, 1)
            if len(parts) >= 2:
                _handle_price(cid, parts[1].strip())
            else:
                _send_message("📌 *Cách dùng:* `/price OANDA:XAUUSD`", chat_id=cid, target=bot_type)

    if cb:
        handle_callback(cb, bot_type=bot_type)


# ── Rich Analysis ──────────────────────────────────────────────
_dir_emoji = {"LONG": "🟢", "SHORT": "🔴", "NEUTRAL": "🟡"}
_tf_labels = {"1W": "Tuần", "1D": "Ngày", "4H": "4H", "1H": "1H", "30m": "30m", "15m": "15m", "5m": "5m"}


def _build_full_analysis(sym: str, df, interval: str, mtf_consensus: dict = None) -> str:
    """Build full analysis: PTKT + PTCB + trading strategy."""
    try:
        from ta.trend import EMAIndicator, MACD as taMACD, ADXIndicator
        from ta.momentum import RSIIndicator, StochRSIIndicator
        from ta.volatility import BollingerBands, AverageTrueRange
        from ta.volume import OnBalanceVolumeIndicator, MFIIndicator
        from core.alerts import _safe
    except ImportError:
        return f"📊 {sym} — {interval}"

    price = _safe(df["close"].iloc[-1])
    prev = _safe(df["close"].iloc[-2]) if len(df) >= 2 else price
    chg = ((price - prev) / prev * 100) if prev and prev > 0 else 0
    high_24h = _safe(df["high"].max())
    low_24h = _safe(df["low"].min())
    icon = "🟢" if chg >= 0 else "🔴"

    # ── Indicators ──
    ema21 = EMAIndicator(df["close"], window=21).ema_indicator().iloc[-1]
    ema50 = EMAIndicator(df["close"], window=50).ema_indicator().iloc[-1]
    ema200 = EMAIndicator(df["close"], window=200).ema_indicator().iloc[-1] if len(df) >= 200 else None

    rsi = RSIIndicator(df["close"], window=14).rsi().iloc[-1]
    macd = taMACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
    macd_line = macd.macd().iloc[-1]
    macd_signal = macd.macd_signal().iloc[-1]
    macd_hist = macd.macd_diff().iloc[-1]

    bb = BollingerBands(df["close"], window=20, window_dev=2)
    bb_upper = bb.bollinger_hband().iloc[-1]
    bb_lower = bb.bollinger_lband().iloc[-1]
    bb_mid = bb.bollinger_mavg().iloc[-1]

    atr = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range().iloc[-1]
    atr_pct = (atr / price * 100) if price > 0 else 0

    adx = ADXIndicator(df["high"], df["low"], df["close"], window=14)
    adx_val = adx.adx().iloc[-1]
    plus_di = adx.adx_pos().iloc[-1]
    minus_di = adx.adx_neg().iloc[-1]

    stoch_rsi = StochRSIIndicator(df["close"], window=14)
    stoch_k = stoch_rsi.stochrsi_k().iloc[-1] * 100
    stoch_d = stoch_rsi.stochrsi_d().iloc[-1] * 100

    obv = OnBalanceVolumeIndicator(df["close"], df["volume"]).on_balance_volume()
    obv_change = ((obv.iloc[-1] - obv.iloc[-5]) / abs(obv.iloc[-5]) * 100) if len(obv) >= 5 and obv.iloc[-5] != 0 else 0

    mfi = MFIIndicator(df["high"], df["low"], df["close"], df["volume"], window=14).money_flow_index().iloc[-1]

    # ── Trend analysis ──
    if price > ema21 > ema50:
        trend = "🟢 UPTREND"
        trend_detail = "Giá > EMA21 > EMA50 — xu hướng tăng"
    elif price < ema21 < ema50:
        trend = "🔴 DOWNTREND"
        trend_detail = "Giá < EMA21 < EMA50 — xu hướng giảm"
    elif ema21 > ema50:
        trend = "🟡 TĂNG YẾU"
        trend_detail = "EMA21 > EMA50 nhưng giá dưới EMA21 — có thể đảo chiều"
    else:
        trend = "🟡 SIDEWAYS"
        trend_detail = "EMA21 & EMA50 đan xen — thị trường đi ngang"

    # ── RSI analysis ──
    if rsi > 70:
        rsi_sig = "🔴 Overbought — có thể điều chỉnh"
    elif rsi > 60:
        rsi_sig = "🟢 Mạnh — momentum tăng"
    elif rsi < 30:
        rsi_sig = "🟢 Oversold — có thể hồi"
    elif rsi < 40:
        rsi_sig = "🔴 Yếu — momentum giảm"
    else:
        rsi_sig = "🟡 Trung tính"

    # ── MACD analysis ──
    if macd_line > macd_signal and macd_hist > 0:
        macd_sig = "🟢 Bullish — MACD trên signal"
    elif macd_line < macd_signal and macd_hist < 0:
        macd_sig = "🔴 Bearish — MACD dưới signal"
    else:
        macd_sig = "🟡 Chuyển tiếp"

    # ── ADX analysis ──
    if adx_val > 25:
        adx_sig = f"💪 Xu hướng mạnh (ADX {adx_val:.0f})"
        if plus_di > minus_di:
            adx_sig += " — bên mua chiếm ưu thế"
        else:
            adx_sig += " — bên bán chiếm ưu thế"
    else:
        adx_sig = f"😐 Xu hướng yếu (ADX {adx_val:.0f}) — đi ngang"

    # ── BB analysis ──
    bb_range = bb_upper - bb_lower
    bb_pos = (price - bb_lower) / bb_range * 100 if bb_range > 0 else 50
    if price >= bb_upper:
        bb_sig = "⚠️触及上轨 — có thể pullback"
    elif price <= bb_lower:
        bb_sig = "⚠️触及下轨 — có thể bounce"
    else:
        bb_sig = f"Vị trí {bb_pos:.0f}% trong band"

    # ── Volume analysis ──
    vol_signal = "Tăng" if obv_change > 5 else "Giảm" if obv_change < -5 else "Ổn định"

    # ── Support/Resistance ──
    recent_high = _safe(df["high"].tail(20).max())
    recent_low = _safe(df["low"].tail(20).min())
    pivot = (recent_high + recent_low + price) / 3
    r1 = 2 * pivot - recent_low
    s1 = 2 * pivot - recent_high

    # ── Trading strategy ──
    strategy_lines = []
    if trend.startswith("🟢") and rsi < 70 and macd_line > macd_signal:
        strategy_lines.append("📈 *Chiến lược: LONG*")
        strategy_lines.append(f"  Entry: `{price:,.2f}` hoặc pullback về `{s1:,.2f}`")
        strategy_lines.append(f"  SL: `{s1 * 0.99:,.2f}` (dưới S1)")
        strategy_lines.append(f"  TP1: `{r1:,.2f}` | TP2: `{bb_upper:,.2f}`")
        rr1 = (r1 - price) / (price - s1 * 0.99) if price > s1 * 0.99 else 0
        strategy_lines.append(f"  R:R: {rr1:.1f}:1")
    elif trend.startswith("🔴") and rsi > 30 and macd_line < macd_signal:
        strategy_lines.append("📉 *Chiến lược: SHORT*")
        strategy_lines.append(f"  Entry: `{price:,.2f}` hoặc rally về `{r1:,.2f}`")
        strategy_lines.append(f"  SL: `{r1 * 1.01:,.2f}` (trên R1)")
        strategy_lines.append(f"  TP1: `{s1:,.2f}` | TP2: `{bb_lower:,.2f}`")
        rr1 = (price - s1) / (r1 * 1.01 - price) if r1 * 1.01 > price else 0
        strategy_lines.append(f"  R:R: {rr1:.1f}:1")
    else:
        strategy_lines.append("⏸️ *Chiến lược: CHỜ*")
        strategy_lines.append(f"  Không vào lệnh — tín hiệu mâu thuẫn")
        strategy_lines.append(f"  Chờ breakout khỏi `{recent_low:,.2f}` — `{recent_high:,.2f}`")

    # ── Market assessment ──
    bull_score = 0
    bear_score = 0
    if price > ema21: bull_score += 1
    else: bear_score += 1
    if price > ema50: bull_score += 1
    else: bear_score += 1
    if rsi > 50: bull_score += 1
    else: bear_score += 1
    if macd_line > macd_signal: bull_score += 1
    else: bear_score += 1
    if plus_di > minus_di: bull_score += 1
    else: bear_score += 1

    total = bull_score + bear_score
    bull_pct = bull_score / total * 100 if total > 0 else 50
    if bull_pct >= 70:
        outlook = "🟢 TÍCH CỰC — Ưu tiên LONG"
    elif bull_pct <= 30:
        outlook = "🔴 TIÊU CỰC — Ưu tiên SHORT"
    else:
        outlook = "🟡 TRUNG TÍNH — Thận trọng"

    # ── MTF consensus ──
    mtf_line = ""
    if mtf_consensus:
        mtf_dir = mtf_consensus.get("direction", "?")
        mtf_str = mtf_consensus.get("strength", 0)
        mtf_aligned = mtf_consensus.get("aligned", 0)
        mtf_total = mtf_consensus.get("total", 0)
        mtf_e = _dir_emoji.get(mtf_dir, "⚪")
        mtf_line = f"\n📋 *MTF:* {mtf_e} {mtf_dir} — {mtf_aligned}/{mtf_total} khung ({mtf_str:.0%})"

    # ── Build message ──
    lines = [
        f"{'═' * 24}",
        f"📊 *PHÂN TÍCH {sym}* — {interval}",
        f"{'═' * 24}",
        f"{icon} *{price:,.2f}* ({chg:+.2f}%) | H: `{high_24h:,.2f}` L: `{low_24h:,.2f}`",
        "",
        f"📈 *XU HƯỚNG:* {trend}",
        f"  {trend_detail}",
        "",
        f"📊 *CHỈ BÁO KỸ THUẬT (PTKT):*",
        f"  RSI(14): `{rsi:.1f}` — {rsi_sig}",
        f"  MACD: {macd_sig}",
        f"  ADX: {adx_sig}",
        f"  Bollinger: {bb_sig} (BBU `{bb_upper:,.2f}` / BBL `{bb_lower:,.2f}`)",
        f"  Stoch RSI: K=`{stoch_k:.0f}` D=`{stoch_d:.0f}`",
        f"  ATR: `{atr:,.2f}` ({atr_pct:.1f}%) — Volatility {'Cao' if atr_pct > 2 else 'Thấp' if atr_pct < 0.5 else 'Trung bình'}",
        f"  MFI: `{mfi:.0f}` — {'Mua' if mfi > 80 else 'Bán' if mfi < 20 else 'Trung tính'}",
        f"  Volume: {vol_signal} (OBV {obv_change:+.1f}%)",
        "",
        f"📐 *HỖ TRỢ / KHÁNG CỰ:*",
        f"  R1: `{r1:,.2f}` | Pivot: `{pivot:,.2f}` | S1: `{s1:,.2f}`",
        f"  BB: `{bb_lower:,.2f}` — `{bb_upper:,.2f}`",
        "",
        f"🎯 *CHIẾN LƯỢC GIAO DỊCH:*",
    ]
    lines.extend(strategy_lines)
    lines.append("")
    lines.append(f"🔮 *NHẬN ĐỊNH:* {outlook}")
    lines.append(f"  Bull: {bull_score}/5 | Bear: {bear_score}/5 ({bull_pct:.0f}%)")
    if mtf_line:
        lines.append(mtf_line)
    lines.append("")
    lines.append(f"⏰ {time.strftime('%H:%M %d/%m/%Y')}")
    lines.append(f"{'═' * 24}")
    return "\n".join(lines)


def _analyze_caption(sym: str, df, interval: str) -> str:
    """Short analysis caption for chart image."""
    try:
        from ta.trend import EMAIndicator, MACD as taMACD
        from ta.momentum import RSIIndicator
        from ta.volatility import BollingerBands
        from core.alerts import _safe
    except ImportError:
        return f"📊 {sym} — {interval}"

    price = _safe(df["close"].iloc[-1])
    prev = _safe(df["close"].iloc[-2]) if len(df) >= 2 else price
    chg = ((price - prev) / prev * 100) if prev and prev > 0 else 0
    icon = "🟢" if chg >= 0 else "🔴"

    ema21 = EMAIndicator(df["close"], window=21).ema_indicator().iloc[-1]
    ema50 = EMAIndicator(df["close"], window=50).ema_indicator().iloc[-1]
    if price > ema21 > ema50:
        trend = "🟢 UPTREND"
    elif price < ema21 < ema50:
        trend = "🔴 DOWNTREND"
    else:
        trend = "🟡 SIDEWAYS"

    rsi_val = RSIIndicator(df["close"], window=14).rsi().iloc[-1]
    if rsi_val > 70:
        rsi_str = f"🔴 {rsi_val:.0f} (Overbought)"
    elif rsi_val < 30:
        rsi_str = f"🟢 {rsi_val:.0f} (Oversold)"
    else:
        rsi_str = f"🟡 {rsi_val:.0f}"

    macd = taMACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
    if macd.macd().iloc[-1] > macd.macd_signal().iloc[-1]:
        macd_str = "🟢 Bullish"
    else:
        macd_str = "🔴 Bearish"

    bb = BollingerBands(df["close"], window=20, window_dev=2)
    bb_upper = bb.bollinger_hband().iloc[-1]
    bb_lower = bb.bollinger_lband().iloc[-1]
    pct = (price - bb_lower) / (bb_upper - bb_lower) * 100 if bb_upper != bb_lower else 50

    return "\n".join([
        f"📊 *{sym}* — {interval}",
        f"{icon} *{price:,.2f}* ({chg:+.2f}%)",
        f"📈 Trend: {trend}",
        f"📊 RSI: {rsi_str} | MACD: {macd_str}",
        f"📏 BB: {pct:.0f}% trong band",
    ])


# ── Chart Generation ──────────────────────────────────────────
_CHART_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "charts")
os.makedirs(_CHART_DIR, exist_ok=True)
CHART_TIMEFRAMES = ["5m", "15m", "1H", "4H"]


def generate_chart(sym: str, interval: str = "5m", limit: int = 100) -> Optional[str]:
    """Generate candlestick chart image. Returns file path."""
    try:
        import plotly.graph_objects as go
        from core.alerts import _get_df, _safe
    except ImportError:
        return None
    df = _get_df(sym, interval)
    if df is None or len(df) < 10:
        return None
    df = df.tail(limit).copy()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#1b8a5a", decreasing_line_color="#d32f2f", name=sym,
    )])
    try:
        from ta.trend import EMAIndicator
        ema21 = EMAIndicator(df["close"], window=21).ema_indicator()
        ema50 = EMAIndicator(df["close"], window=50).ema_indicator()
        fig.add_trace(go.Scatter(x=df.index, y=ema21, name="EMA21", line=dict(color="#2196F3", width=1)))
        fig.add_trace(go.Scatter(x=df.index, y=ema50, name="EMA50", line=dict(color="#FF9800", width=1)))
    except Exception:
        pass
    try:
        from ta.volatility import BollingerBands
        bb = BollingerBands(df["close"], window=20, window_dev=2)
        fig.add_trace(go.Scatter(x=df.index, y=bb.bollinger_hband(), name="BBU", line=dict(color="#9C27B0", width=0.8, dash="dash")))
        fig.add_trace(go.Scatter(x=df.index, y=bb.bollinger_lband(), name="BBL", line=dict(color="#9C27B0", width=0.8, dash="dash")))
    except Exception:
        pass

    price = _safe(df["close"].iloc[-1])
    prev_price = _safe(df["close"].iloc[-2]) if len(df) >= 2 else price
    change_pct = ((price - prev_price) / prev_price * 100) if prev_price and prev_price > 0 else 0
    direction = "🟢" if change_pct >= 0 else "🔴"
    fig.update_layout(
        title=f"{sym} | {interval} | {direction} {price:,.2f} ({change_pct:+.2f}%)",
        template="plotly_white", width=900, height=500,
        xaxis_rangeslider_visible=False, margin=dict(l=40, r=20, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    filepath = os.path.join(_CHART_DIR, f"chart_{sym.replace(':', '_').replace('/', '_')}_{interval}.png")
    try:
        fig.write_image(filepath, scale=2)
        return filepath
    except Exception:
        return None


# ── Push functions ─────────────────────────────────────────────
def push_alerts(alerts: List[Dict], chat_id: str = None):
    """Push alerts to signal_bot. Filters by min_strength and subscriptions."""
    _load_config()
    sb = _state["signal_bot"]
    if not sb["enabled"] or not sb["bot_token"]:
        return
    now = time.time()
    if now - _state["last_sent"] < sb["send_interval"]:
        _state["pending_alerts"].extend(alerts)
        return

    subs = set(get_subscribed(chat_id))
    to_send = [a for a in alerts if a.get("strength", 0) >= sb["min_strength"]
               and (not subs or a.get("symbol") in subs)]
    if not to_send and _state["pending_alerts"]:
        to_send = [a for a in _state["pending_alerts"] if a.get("strength", 0) >= sb["min_strength"]
                   and (not subs or a.get("symbol") in subs)]
        _state["pending_alerts"] = []
    if not to_send:
        return

    batch = to_send[:10]
    header = f"🔔 *{len(batch)} tín hiệu*\n{'─' * 20}"
    lines = [header]
    for a in batch:
        e = _dir_emoji.get(a.get("direction", "NEUTRAL"), "⚪")
        lines.append(f"{e} *{a.get('pattern','?')}* — {a.get('symbol','?')}")
        lines.append(f"  {a.get('interval','1H')} | Strength: {a.get('strength',0):.0%}")
        if a.get("price"):
            lines.append(f"  💰 `{a['price']:,.2f}`")
        if a.get("desc"):
            lines.append(f"  📊 {a['desc']}")
        lines.append("─" * 15)

    result = _send_message("\n".join(lines), chat_id=chat_id, target="signal")
    if result.get("ok"):
        _state["last_sent"] = now
        _state["pending_alerts"] = []


def format_plan_message(plan: Dict) -> str:
    sym = plan.get("symbol", "?")
    price = plan.get("price", 0)
    consensus = plan.get("consensus", {})
    action_plan = plan.get("action_plan", {})
    tf_plans = plan.get("tf_plans", [])
    bias = consensus.get("direction", "NEUTRAL")
    strength = consensus.get("strength", 0)
    aligned = consensus.get("aligned", 0)
    total = consensus.get("total", 0)
    e = _dir_emoji.get(bias, "⚪")

    lines = [
        f"📋 *PLAN {sym}* — {e} {bias}",
        f"💰 Giá: `{price:,.2f}`" if price else "",
        f"📊 Đồng thuận: {aligned}/{total} khung ({strength:.0%})",
    ]
    steps = action_plan.get("steps", [])
    if steps:
        lines.append("")
        for s in steps[:3]:
            lines.append(f"  • {s}")
    if tf_plans:
        lines.append("")
        for tf_plan in tf_plans:
            tf = tf_plan.get("tf", "?")
            d = tf_plan.get("direction", "NEUTRAL")
            de = _dir_emoji.get(d, "⚪")
            entry = tf_plan.get("entry")
            sl = tf_plan.get("stop_loss")
            tp1 = tf_plan.get("take_profit_1")
            rr = tf_plan.get("risk_reward")
            parts = [f"{de} *{tf}* {d}"]
            if entry: parts.append(f"E `{entry:,.2f}`")
            if sl: parts.append(f"SL `{sl:,.2f}`")
            if tp1: parts.append(f"TP `{tp1:,.2f}`")
            if rr: parts.append(f"R:R {rr}")
            lines.append("  " + " | ".join(parts))
    return "\n".join(lines)


def push_plans(plans: List[Dict], chat_id: str = None):
    """Push MTF plans to signal_bot."""
    _load_config()
    sb = _state["signal_bot"]
    if not sb["enabled"] or not sb["plan_enabled"]:
        return
    if not sb["bot_token"]:
        return
    now = time.time()
    if now - _state["last_plan_sent"] < sb["plan_interval"]:
        return
    if not plans:
        return

    subs = set(get_subscribed(chat_id))
    if subs:
        plans = [p for p in plans if p.get("symbol") in subs]
    if not plans:
        return

    changed = [p for p in plans if p.get("changed")]
    if changed:
        to_send = changed[:5]
        header = f"🚨 *{len(changed)} THAY ĐỔI PLAN*\n{'═' * 22}"
    else:
        to_send = sorted(plans, key=lambda p: p.get("consensus", {}).get("strength", 0), reverse=True)[:5]
        header = f"📋 *PLAN GIAO DỊCH*\n{'═' * 22}"

    lines = [header]
    for p in to_send:
        if p.get("changed"):
            lines.append(f"🔄 *{p['symbol']}*: {p.get('prev_direction','?')} → {p['consensus'].get('direction','?')}")
        lines.append(format_plan_message(p))
        lines.append("═" * 18)

    result = _send_message("\n".join(lines), chat_id=chat_id, target="signal")
    if result.get("ok"):
        _state["last_plan_sent"] = now


def push_charts(symbols: List[str] = None, timeframes: List[str] = None, chat_id: str = None):
    """Generate and push chart images + full analysis to signal_bot."""
    _load_config()
    sb = _state["signal_bot"]
    if not sb["enabled"] or not sb["chart_enabled"]:
        return
    if not sb["bot_token"]:
        return
    now = time.time()
    if now - _state["last_chart_sent"] < sb["chart_interval"]:
        return
    if timeframes is None:
        timeframes = CHART_TIMEFRAMES

    # Get symbols from signal_bot's chart_symbols
    if symbols is None:
        symbols = sb.get("chart_symbols", [])
    if not symbols:
        symbols = get_subscribed(chat_id)
    if not symbols:
        import config as cfg
        symbols = [s["tv"] for s in cfg.WATCHLIST[:5]]

    sent = 0
    for sym in symbols:
        for tf in timeframes:
            try:
                chart_path = generate_chart(sym, interval=tf)
                if chart_path and os.path.exists(chart_path):
                    from core.alerts import _get_df
                    df = _get_df(sym, tf)
                    caption = _analyze_caption(sym, df, tf) if df is not None and len(df) >= 10 else f"📊 *{sym}* — {tf}"
                    result = _send_photo(chart_path, caption, chat_id=chat_id, target="signal")
                    if result.get("ok"):
                        sent += 1
                    try:
                        os.remove(chart_path)
                    except Exception:
                        pass

                    if df is not None and len(df) >= 20:
                        try:
                            from core.multi_timeframe import MTFAnalyzer
                            from config import MTF_TIMEFRAMES
                            scraper = None
                            try:
                                from core.alerts import _get_scraper
                                scraper = _get_scraper()
                            except Exception:
                                pass
                            mtf = MTFAnalyzer(sym, MTF_TIMEFRAMES).run(scraper) if scraper else None
                            mtf_consensus = mtf.get("consensus", {}) if mtf else {}
                        except Exception:
                            mtf_consensus = {}
                        full_analysis = _build_full_analysis(sym, df, tf, mtf_consensus)
                        _send_message(full_analysis, chat_id=chat_id, target="signal")
                if sent >= 20:
                    break
            except Exception:
                continue
        if sent >= 20:
            break

    if sent > 0:
        _state["last_chart_sent"] = now


def push_price_feed(chat_id: str = None):
    """Gửi giá + chart định kỳ cho price_feed_bot trên nhiều timeframe."""
    _load_config()
    pfb = _state["price_feed_bot"]
    if not pfb["enabled"] or not pfb["bot_token"]:
        return

    now = time.time()
    if now - _state["last_price_feed"] < pfb.get("interval", 300):
        return

    symbols = pfb.get("symbols", ["OANDA:XAUUSD"])
    timeframes = pfb.get("timeframes", ["5m", "15m", "30m", "1H"])
    if not symbols or not timeframes:
        return

    from core.alerts import _get_df, _safe

    sent = 0
    for sym in symbols:
        for tf in timeframes:
            try:
                df = _get_df(sym, tf)
                if df is None or len(df) < 10:
                    continue
                df = df.tail(100).copy()
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)

                price = _safe(df["close"].iloc[-1])
                prev_price = _safe(df["close"].iloc[-2]) if len(df) >= 2 else price
                high = _safe(df["high"].iloc[-1])
                low = _safe(df["low"].iloc[-1])

                change_pct = 0.0
                if prev_price and prev_price > 0:
                    change_pct = (price - prev_price) / prev_price * 100

                direction = "🟢" if change_pct >= 0 else "🔴"
                arrow = "↑" if change_pct >= 0 else "↓"

                sym_display = SYM_NAMES.get(sym, sym)
                tf_label = {"5m": "5 phút", "15m": "15 phút", "30m": "30 phút",
                            "1H": "1 giờ", "4H": "4 giờ"}.get(tf, tf)

                from ta.trend import EMAIndicator
                from ta.momentum import RSIIndicator
                ema21 = EMAIndicator(df["close"], window=21).ema_indicator()
                ema50 = EMAIndicator(df["close"], window=50).ema_indicator()
                rsi = RSIIndicator(df["close"], window=14).rsi()

                ema21_now = _safe(ema21.iloc[-1])
                ema50_now = _safe(ema50.iloc[-1])
                rsi_now = _safe(rsi.iloc[-1])

                if price > ema21_now and price > ema50_now and rsi_now > 50:
                    signal = "🟢 MUA"
                elif price < ema21_now and price < ema50_now and rsi_now < 50:
                    signal = "🔴 BÁN"
                else:
                    signal = "🟡 TRUNG LẬP"

                msg = (
                    f"{'━' * 28}\n"
                    f"💰 *{sym_display}* — Khung {tf_label}\n"
                    f"{'━' * 28}\n\n"
                    f"💲 Giá: `{price:,.2f}`\n"
                    f"{direction} Thay đổi: `{change_pct:+.3f}%` {arrow}\n"
                    f"📈 Cao: `{high:,.2f}`\n"
                    f"📉 Thấp: `{low:,.2f}`\n\n"
                    f"📊 EMA21: `{ema21_now:,.2f}` | EMA50: `{ema50_now:,.2f}`\n"
                    f"RSI(14): `{rsi_now:.1f}`\n\n"
                    f"📡 *Signal:* {signal}\n"
                    f"⏰ {time.strftime('%H:%M:%S')}"
                )

                chart_path = generate_chart(sym, interval=tf)
                if chart_path and os.path.exists(chart_path):
                    result = _send_photo(chart_path, msg, chat_id=chat_id, target="price_feed")
                    if result.get("ok"):
                        sent += 1
                    try:
                        os.remove(chart_path)
                    except Exception:
                        pass
                else:
                    result = _send_message(msg, chat_id=chat_id, target="price_feed")
                    if result.get("ok"):
                        sent += 1
            except Exception:
                continue

    if sent > 0:
        _state["last_price_feed"] = now


# ── Market News (Bot 3) ────────────────────────────────────────
def fetch_market_news() -> List[Dict]:
    """Fetch international market news affecting gold, XAUUSD, DXY, USD, WTI...
    
    Sources: TradingView RSS + Yahoo Finance RSS + Kitco RSS (free, no API key).
    Returns list of {title, source, url, time, matched_keywords}.
    """
    import xml.etree.ElementTree as ET
    from datetime import datetime, timezone

    keywords = [k.upper() for k in _state.get("market_news_bot", {}).get("keywords", [])]
    seen_titles = set()
    news_items = []

    # RSS feeds — Vietnamese financial + international sources
    rss_feeds = [
        # Vietnamese sources (user-requested)
        ("VNWallStreet", "https://vnwallstreet.com/rss/tin-tuc.rss"),
        ("Vietstock", "https://vietstock.vn/rss/tin-tuc-chung-khoan.rss"),
        ("TinNhanhCK", "https://www.tinnhanhchungkhoan.vn/rss/tin-tuc-chung-khoan.rss"),
        ("VietnamFinance", "https://vietnamfinance.vn/rss/tin-moi-nhat.rss"),
        ("Thoibaonganhang", "https://thoibaonganhang.vn/rss/tin-moi-nhat.rss"),
        ("CafeF", "https://cafef.vn/tim-kiem/rss.chn"),
        ("VNExpress KinhDoanh", "https://vnexpress.net/rss/kinh-doanh.rss"),
        ("TuoiTre KinhDoanh", "https://tuoitre.vn/rss/kinh-doanh.rss"),
        ("DanTri KinhDoanh", "https://dantri.com.vn/rss/kinh-doanh.rss"),
        ("VNExpress ThiTruong", "https://vnexpress.net/rss/thi-truong.rss"),
        ("BaoDauTu", "https://baodautu.vn/rss/tin-moi-nhat.rss"),
        # International sources
        ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
        ("MarketWatch Markets", "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines"),
        ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
        ("CNBC Commodities", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"),
        ("CNBC Finance", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147"),
        ("Yahoo Finance", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,CL=F,DX-Y.NYB&region=US&lang=en-US"),
        ("Yahoo Gold", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F&region=US&lang=en-US"),
        ("OilPrice", "https://oilprice.com/rss/main"),
        ("SeekingAlpha", "https://seekingalpha.com/feed.xml"),
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    for source_name, url in rss_feeds:
        try:
            r = httpx.get(url, headers=headers, timeout=8, follow_redirects=True)
            if r.status_code != 200:
                continue
            content = r.text
            if not content or len(content) < 100:
                continue

            # Parse RSS/Atom XML
            try:
                root = ET.fromstring(content)
            except ET.ParseError:
                continue

            # Handle RSS 2.0
            items = root.findall(".//item")
            if not items:
                # Handle Atom
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for item in items[:15]:  # Limit per source
                title = ""
                link = ""
                pub_date = ""

                # RSS 2.0
                title_el = item.find("title")
                if title_el is not None and title_el.text:
                    title = title_el.text.strip()
                link_el = item.find("link")
                if link_el is not None and link_el.text:
                    link = link_el.text.strip()
                date_el = item.find("pubDate")
                if date_el is not None and date_el.text:
                    pub_date = date_el.text.strip()

                # Atom
                if not title:
                    atom_title = item.find("{http://www.w3.org/2005/Atom}title")
                    if atom_title is not None and atom_title.text:
                        title = atom_title.text.strip()
                if not link:
                    atom_link = item.find("{http://www.w3.org/2005/Atom}link")
                    if atom_link is not None:
                        link = atom_link.get("href", "")
                if not pub_date:
                    atom_date = item.find("{http://www.w3.org/2005/Atom}updated")
                    if atom_date is None:
                        atom_date = item.find("{http://www.w3.org/2005/Atom}published")
                    if atom_date is not None and atom_date.text:
                        pub_date = atom_date.text.strip()

                if not title or len(title) < 10:
                    continue

                # Check for keyword matches
                title_upper = title.upper()
                matched = [k for k in keywords if k in title_upper]
                if not matched:
                    continue

                # Dedupe by title
                title_key = title.upper()[:80]
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                news_items.append({
                    "title": title,
                    "source": source_name,
                    "url": link,
                    "time": pub_date,
                    "matched_keywords": matched,
                })

                if len(news_items) >= 20:
                    break
        except Exception:
            continue
        if len(news_items) >= 20:
            break

    return news_items


def push_news(chat_id: str = None):
    """Gửi tin tức thị trường (gold, DXY, USD, WTI...) đến market_news_bot."""
    _load_config()
    nb = _state["market_news_bot"]
    if not nb["enabled"] or not nb["bot_token"]:
        return

    now = time.time()
    if now - _state["last_news"] < nb.get("interval", 600):
        return

    max_news = nb.get("max_news", 5)
    news_items = fetch_market_news()
    if not news_items:
        return

    # Filter out already-seen news
    seen = set(_state.get("seen_news", []))
    new_items = []
    for item in news_items:
        key = item["title"].upper()[:80]
        if key not in seen:
            new_items.append(item)
            seen.add(key)

    if not new_items:
        _state["last_news"] = now
        return

    # Keep only newest max_news
    new_items = new_items[:max_news]
    _state["seen_news"] = list(seen)[-200:]  # Keep last 200

    # Translate English titles to Vietnamese
    for item in new_items:
        title = item.get("title", "")
        # Skip if already Vietnamese (contains Vietnamese characters)
        has_vi = any(c in title for c in "ăâđêôơưáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")
        if not has_vi and title:
            item["title_vi"] = translate_vi(title)
        else:
            item["title_vi"] = title

    # Format message
    lines = [
        f"📰 *TIN TỨC THỊ TRƯỜNG*",
        f"{'━' * 28}",
        "",
    ]

    for i, item in enumerate(new_items, 1):
        keywords_str = ", ".join(item["matched_keywords"][:3])
        title_display = item.get("title_vi", item["title"])[:100]
        lines.append(
            f"*{i}. {title_display}*\n"
            f"   🏷️ {keywords_str} | 📡 {item['source']}"
        )
        if item.get("url"):
            lines.append(f"   🔗 [Đọc thêm]({item['url']})")
        lines.append("")

    lines.append(f"⏰ {time.strftime('%H:%M:%S %d/%m/%Y')}")

    text = "\n".join(lines)
    result = _send_message(text, chat_id=chat_id, target="news")
    if result.get("ok"):
        _state["last_news"] = now


def push_analysis_alerts(chat_id: str = None):
    """Gửi bảng phân tích cảnh báo cho BOT1 + BOT2 mỗi 15 phút."""
    _load_config()
    import config as cfg

    # Get priority symbols from config
    symbols = [item["tv"] for item in cfg.WATCHLIST if item.get("cat") == "priority"]

    from core.alerts import _get_df, _safe

    # Build analysis table
    lines = [
        f"⚡ *CẢNH BÁO PHÂN TÍCH*",
        f"{'━' * 30}",
        "",
    ]

    sent_count = 0
    for sym in symbols:
        try:
            df = _get_df(sym, "1H")
            if df is None or len(df) < 30:
                continue

            # Compute indicators
            from ta.trend import EMAIndicator, MACD as taMACD, ADXIndicator
            from ta.momentum import RSIIndicator
            from ta.volatility import BollingerBands

            price = _safe(df["close"].iloc[-1])
            prev = _safe(df["close"].iloc[-2]) if len(df) >= 2 else price
            chg = ((price - prev) / prev * 100) if prev and prev > 0 else 0
            icon = "🟢" if chg >= 0 else "🔴"

            ema21 = EMAIndicator(df["close"], window=21).ema_indicator().iloc[-1]
            ema50 = EMAIndicator(df["close"], window=50).ema_indicator().iloc[-1]

            rsi = RSIIndicator(df["close"], window=14).rsi().iloc[-1]
            macd = taMACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
            macd_line = macd.macd().iloc[-1]
            macd_signal = macd.macd_signal().iloc[-1]
            macd_hist = macd.macd_diff().iloc[-1]

            adx = ADXIndicator(df["high"], df["low"], df["close"], window=14)
            adx_val = adx.adx().iloc[-1]
            plus_di = adx.adx_pos().iloc[-1]
            minus_di = adx.adx_neg().iloc[-1]

            bb = BollingerBands(df["close"], window=20, window_dev=2)
            bb_upper = bb.bollinger_hband().iloc[-1]
            bb_lower = bb.bollinger_lband().iloc[-1]

            # Trend
            if price > ema21 > ema50:
                trend = "🟢 TĂNG"
            elif price < ema21 < ema50:
                trend = "🔴 GIẢM"
            else:
                trend = "🟡 ĐI NGANG"

            # MACD signal
            if macd_line > macd_signal and macd_hist > 0:
                macd_sig = "BULL"
            elif macd_line < macd_signal and macd_hist < 0:
                macd_sig = "BEAR"
            else:
                macd_sig = "CHUYỂN"

            # ADX strength
            adx_sig = "MẠNH" if adx_val > 25 else "YẾU"

            # S/R from recent 20 candles
            recent_high = _safe(df["high"].tail(20).max())
            recent_low = _safe(df["low"].tail(20).min())
            pivot = (recent_high + recent_low + price) / 3
            r1 = 2 * pivot - recent_low
            s1 = 2 * pivot - recent_high

            # Simple psychology based on RSI
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

            # Get friendly name
            name_map = {item["tv"]: item["name"] for item in cfg.WATCHLIST}
            friendly = name_map.get(sym, sym)

            # Format compact table
            lines.append(f"*{friendly}* ({sym})")
            lines.append(f"  Giá: `{price:,.4f}` {icon} {chg:+.2f}%")
            lines.append(f"  RSI: `{rsi:.1f}` | MACD: {macd_sig} | ADX: `{adx_val:.0f}` ({adx_sig})")
            lines.append(f"  Xu hướng: {trend}")
            lines.append(f"  Kháng cự: `{r1:,.4f}` | Hỗ trợ: `{s1:,.4f}`")
            lines.append(f"  Tâm lý: {psyc}")
            lines.append("")

            sent_count += 1
        except Exception:
            continue

    if sent_count == 0:
        return

    lines.append(f"━━━━━━━━━━━━━━━━━━")
    lines.append(f"⏰ {time.strftime('%H:%M:%S %d/%m/%Y')} | {sent_count} mã")

    text = "\n".join(lines)

    # Send to BOTH BOT1 (signal) and BOT2 (price_feed)
    now = time.time()
    sb = _state["signal_bot"]
    pfb = _state["price_feed_bot"]

    # BOT1
    if sb.get("enabled") and sb.get("bot_token"):
        chat1 = chat_id or sb.get("chat_id")
        if chat1:
            result = _send_message(text, chat_id=chat1, target="signal")
            if result.get("ok"):
                _state["last_analysis_alert"] = now

    # BOT2
    if pfb.get("enabled") and pfb.get("bot_token"):
        chat2 = pfb.get("chat_id")
        if chat2:
            _send_message(text, chat_id=chat2, target="price_feed")


def start_polling():
    """Start bot polling thread for commands + callbacks."""
    t = threading.Thread(target=poll_updates, daemon=True)
    t.start()
    return t


_load_config()
_load_subs()
