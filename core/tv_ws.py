"""
TradingView WebSocket chart-session OHLCV fetcher (unofficial protocol).

Mirrors the exact wire protocol the ``tradingview-sdk`` package uses (same
``~m~<len>~m~<payload>`` framing with UTF-16 lengths, same ``create_series``
params, same ``timescale_update`` / ``du`` / ``series_completed`` handling) so
this repo has a first-party, dependency-light path to TradingView candles that
does not go through yfinance.

Verified live on this network: ``wss://data.tradingview.com/socket.io/websocket``
replies to the one-shot chart session below with real bars for OANDA:XAUUSD,
FX:EURUSD, NASDAQ:AAPL, BINANCE:BTCUSDT, TVC:SPX, NYMEX:CL1! and others.
"""
from __future__ import annotations

import json
import logging
import random
import re
import string
import time
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

try:
    import websocket as _websocket
    _HAS_WEBSOCKET = True
except ImportError:  # pragma: no cover
    _websocket = None
    _HAS_WEBSOCKET = False

WS_URL = "wss://data.tradingview.com/socket.io/websocket?from=chart%2F&type=chart"
WS_ORIGIN = "https://www.tradingview.com"

SYMBOL_ID = "sds_sym_1"
SERIES_ID = "sds_1"
SERIES_LABEL = "s1"

# App interval key -> TradingView resolution string (matches config.INTERVALS).
INTERVAL_MAP = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30", "45m": "45",
    "1H": "60", "2H": "120", "3H": "180", "4H": "240",
    "1D": "1D", "1W": "1W", "1M": "1M",
}

_FRAME_RE = re.compile(r"~m~(\d+)~m~")
_HEARTBEAT_RE = re.compile(r"^~h~\d+$")

_OHLCV_COLS = ("open", "high", "low", "close", "volume")


def map_interval(interval: str) -> str:
    """App interval key -> TradingView resolution. Unknown keys pass through."""
    return INTERVAL_MAP.get(str(interval), str(interval))


# ── wire framing (UTF-16 code-unit lengths, as JS String.length counts) ─────
def encode_message(method: str, params: List[Any]) -> str:
    payload = json.dumps({"m": method, "p": params}, separators=(",", ":"), ensure_ascii=True)
    return f"~m~{len(payload)}~m~{payload}"


def decode_frame(frame: str | bytes) -> List[str]:
    """Split one websocket message into its ``~m~``-framed payloads."""
    text = frame.decode("utf-8", "replace") if isinstance(frame, (bytes, bytearray)) else frame
    messages: List[str] = []
    pos = 0
    while pos < len(text):
        m = _FRAME_RE.match(text, pos)
        if not m:
            break
        end = m.end() + int(m.group(1))
        if end > len(text):
            break
        messages.append(text[m.end():end])
        pos = end
    return messages


def _bar_from_values(values: Any) -> Optional[dict]:
    """One ``{"v": [time, open, high, low, close, volume]}`` point -> bar dict."""
    if not isinstance(values, list) or len(values) < 5:
        return None
    try:
        return {
            "timestamp": int(values[0]),
            "open": float(values[1]),
            "high": float(values[2]),
            "low": float(values[3]),
            "close": float(values[4]),
            "volume": float(values[5]) if len(values) > 5 and values[5] is not None else 0.0,
        }
    except (TypeError, ValueError):
        return None


def _parse_series_bars(params: List[Any], series_id: str = SERIES_ID) -> List[dict]:
    """Bars from a ``timescale_update`` or ``du`` message's ``p`` list."""
    if len(params) < 2 or not isinstance(params[1], dict):
        return []
    series = params[1].get(series_id)
    if not isinstance(series, dict):
        return []
    bars: List[dict] = []
    for point in series.get("s") or []:
        if not isinstance(point, dict):
            continue
        bar = _bar_from_values(point.get("v"))
        if bar is not None:
            bars.append(bar)
    return bars


def fetch_tv_ws(symbol: str, interval: str = "1H", bars: int = 300,
                timeout: float = 8.0) -> pd.DataFrame:
    """One-shot anonymous chart-session fetch of OHLCV candles.

    Returns a DataFrame with columns open/high/low/close/volume and a UTC
    timezone-aware DatetimeIndex (named ``time``). Empty DataFrame on any
    failure (bad symbol, no network, protocol change).
    """
    if not _HAS_WEBSOCKET:
        logger.warning("websocket-client not installed; TradingView WS source disabled")
        return pd.DataFrame()

    resolution = map_interval(interval)
    # Ask the server for at least 300 bars so indicator lookbacks (EMA200, ...)
    # have history to chew on, but never more than the caller asked for beyond
    # that floor (the response is trimmed to `bars` rows below anyway).
    count = max(int(bars), 300)
    cs = "cs_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    spec = "=" + json.dumps({"adjustment": "splits", "symbol": symbol}, separators=(",", ":"))
    chart_session = cs

    try:
        ws = _websocket.create_connection(
            WS_URL,
            header=[f"Origin: {WS_ORIGIN}"],
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("TV WS connect failed for %s: %s", symbol, exc)
        return pd.DataFrame()

    bars_by_time: Dict[int, dict] = {}
    completed = False
    symbol_error = None

    def send(method: str, params: List[Any]) -> None:
        ws.send(encode_message(method, params))

    try:
        send("set_auth_token", ["unauthorized_user_token"])
        send("chart_create_session", [chart_session, ""])
        send("switch_timezone", [chart_session, "Etc/UTC"])
        send("resolve_symbol", [chart_session, SYMBOL_ID, spec])
        send("create_series", [chart_session, SERIES_ID, SERIES_LABEL, SYMBOL_ID, resolution, count, ""])

        start = time.time()
        while time.time() - start < timeout:
            try:
                raw = ws.recv()
            except _websocket.WebSocketTimeoutException:
                break
            except Exception as exc:  # noqa: BLE001
                logger.debug("TV WS recv failed for %s: %s", symbol, exc)
                break

            for message in decode_frame(raw):
                if _HEARTBEAT_RE.match(message):
                    # Server pings with "~h~<n>"; echo verbatim to stay connected.
                    try:
                        ws.send(message)
                    except Exception:  # noqa: BLE001
                        pass
                    continue
                if not message.startswith("{"):
                    continue
                try:
                    data = json.loads(message)
                except (ValueError, TypeError):
                    continue
                m = data.get("m")
                p = data.get("p") or []
                if m in ("timescale_update", "du"):
                    for bar in _parse_series_bars(p):
                        bars_by_time[bar["timestamp"]] = bar
                elif m == "series_completed":
                    completed = True
                elif m == "symbol_error":
                    symbol_error = str(p) if p else "unknown symbol"
                    break
            if completed or symbol_error is not None:
                break
    except Exception as exc:  # noqa: BLE001
        logger.debug("TV WS session failed for %s: %s", symbol, exc)
    finally:
        try:
            ws.close()
        except Exception:  # noqa: BLE001
            pass

    if symbol_error is not None:
        logger.debug("TradingView could not resolve %s: %s", symbol, symbol_error)
        return pd.DataFrame()
    if not bars_by_time:
        return pd.DataFrame()

    ordered = sorted(bars_by_time.values(), key=lambda b: b["timestamp"])
    if len(ordered) > int(bars):
        ordered = ordered[-int(bars):]

    df = pd.DataFrame(ordered)
    df.index = pd.DatetimeIndex(
        pd.to_datetime(df.pop("timestamp"), unit="s", utc=True), name="time"
    )
    return df[list(_OHLCV_COLS)]