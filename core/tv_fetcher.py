"""
TradingView Data Fetcher
Fetches OHLCV data, search symbols, and technical analysis from TradingView.
Supports: Anonymous, Auth Token, Username/Password, Session Cookies.
"""
import json
import time
import logging
import re
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

import pandas as pd
import numpy as np
import requests
import websocket

logger = logging.getLogger(__name__)


class TVFetcher:
    """Fetch data from TradingView via WebSocket and REST API."""

    SIGN_IN_URL = "https://www.tradingview.com/accounts/signin/"
    SEARCH_URL = "https://symbol-search.tradingview.com/symbol_search/?text={}&hl=1&exchange={}&lang=en&type=&domain=production"
    SCANNER_URL = "https://scanner.tradingview.com/forex/scan"
    WS_URL = "wss://data.tradingview.com/socket.io/websocket"
    WS_HEADERS = {"Origin": "https://data.tradingview.com"}

    def __init__(
        self,
        username: str = "",
        password: str = "",
        auth_token: str = "",
        session_id: str = "",
        session_sign: str = "",
    ):
        self.username = username
        self.password = password
        self.auth_token = auth_token or self._auth(username, password)
        self.session_id = session_id
        self.session_sign = session_sign
        self.ws = None
        self.session = self._generate_session()
        self.chart_session = self._generate_chart_session()

    def _auth(self, username: str, password: str) -> str:
        if not username or not password:
            return "unauthorized_user_token"
        try:
            resp = requests.post(
                self.SIGN_IN_URL,
                data={"username": username, "password": password, "remember": "on"},
                headers={"Referer": "https://www.tradingview.com"},
                timeout=10,
            )
            return resp.json()["user"]["auth_token"]
        except Exception as e:
            logger.warning(f"TradingView auth failed: {e}")
            return "unauthorized_user_token"

    @staticmethod
    def _generate_session() -> str:
        return "qs_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))

    @staticmethod
    def _generate_chart_session() -> str:
        return "cs_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))

    @staticmethod
    def _generate_msg_id() -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=10))

    def _create_ws_connection(self) -> websocket.WebSocket:
        ws = websocket.create_connection(
            self.WS_URL,
            headers=self.WS_HEADERS,
            timeout=10,
        )
        self._send_packet(ws, {"m": "set_auth_token", "p": [self.auth_token]})
        return ws

    @staticmethod
    def _send_packet(ws: websocket.WebSocket, data: dict) -> None:
        msg = f"~m~{len(json.dumps(data))}~m~{json.dumps(data)}"
        ws.send(msg)

    @staticmethod
    def _filter_raw_message(text: str) -> Optional[str]:
        try:
            return re.search(r'"m":"(.+?)",', text).group(1)
        except (AttributeError, IndexError):
            return None

    def _parse_message(self, raw: str) -> dict:
        try:
            parts = raw.split("~m~")
            payload = parts[2] if len(parts) > 2 else parts[-1]
            return json.loads(payload)
        except (json.JSONDecodeError, IndexError):
            return {}

    def _fetch_via_ws(self, symbol: str, interval: str, bars_count: int) -> pd.DataFrame:
        """Fetch OHLCV via WebSocket chart session."""
        try:
            ws = self._create_ws_connection()
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            return pd.DataFrame()

        self._send_packet(ws, {
            "m": "chart_create_session",
            "p": [self.chart_session, ""]
        })

        self._send_packet(ws, {
            "m": "resolve_symbol",
            "p": [
                self.chart_session,
                "sds_sym_1",
                f"={symbol}",
            ]
        })

        self._send_packet(ws, {
            "m": "series_create_session",
            "p": [self.session]
        })

        self._send_packet(ws, {
            "m": "series_create",
            "p": [
                self.session,
                self.chart_session,
                "sds_sym_1",
                interval,
                "",
                bars_count,
                "",
                "",
                True,
            ]
        })

        # Wait for data
        bars = []
        start_time = time.time()
        while time.time() - start_time < 10:
            try:
                raw = ws.recv()
                msg = self._parse_message(raw)

                if msg.get("m") == "series_loading":
                    continue
                if msg.get("m") == "series_completed":
                    break
                if msg.get("m") == "timescale_update" or msg.get("m") == "series_update":
                    data = msg.get("p", [None, None, []])
                    if len(data) >= 3:
                        candle_data = data[2]
                        if isinstance(candle_data, list) and len(candle_data) >= 6:
                            bars.append({
                                "timestamp": candle_data[0],
                                "open": candle_data[1],
                                "high": candle_data[2],
                                "low": candle_data[3],
                                "close": candle_data[4],
                                "volume": candle_data[5],
                            })
            except websocket.WebSocketTimeoutException:
                break
            except Exception as e:
                logger.debug(f"WS recv error: {e}")
                break

        ws.close()

        if not bars:
            return pd.DataFrame()

        df = pd.DataFrame(bars)
        df["date"] = pd.to_datetime(df["timestamp"], unit="s")
        df.set_index("date", inplace=True)
        df.sort_index(inplace=True)
        return df

    def _fetch_via_scanner(self, symbol: str, interval: str) -> Dict:
        """Fetch latest data via TradingView Scanner API (REST)."""
        try:
            exchange, ticker = symbol.split(":")
        except ValueError:
            exchange, ticker = "FX", symbol

        data = {
            "columns": [
                "close", "open", "high", "low", "volume",
                "change", "change_abs", "Recommend.All",
                "RSI", "RSI[1]", "Stoch.K", "Stoch.D",
                "CCI20", "CCI20[1]", "ADX", "ADX[1]",
                "AO", "AO[1]", "Mom", "Mom[1]",
                "MACD.macd", "MACD.signal",
                "Rec.BB", "BB.upper", "BB.lower",
                "Rec.Stoch.RSI", "Rec.WR", "Rec.UO",
                "Rec.ADX", "Rec.AO", "Rec.MACD",
                "Rec.Ichimoku", "Rec.VWMA", "Rec.EMA",
                "Rec.SMA",
            ],
            "symbols": {"tickers": [symbol]},
            "options": {"lang": "en"},
            "markets": ["forex", "crypto", "america", "europe", "asia"],
        }

        # Map interval to scanner range
        range_map = {
            "1m": "1d", "5m": "1d", "15m": "1d", "30m": "1d",
            "1H": "1d", "4H": "5d", "1D": "1M", "1W": "3M", "1M": "12M",
        }
        range_val = range_map.get(interval, "1M")
        data["options"]["range"] = [range_val]

        try:
            resp = requests.post(
                self.SCANNER_URL.replace("forex", self._get_market_type(exchange)),
                json=data,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            result = resp.json()
            if result.get("data") and len(result["data"]) > 0:
                return result["data"][0].get("d", [])
        except Exception as e:
            logger.error(f"Scanner API failed: {e}")
        return []

    @staticmethod
    def _get_market_type(exchange: str) -> str:
        mapping = {
            "BINANCE": "crypto", "COINBASE": "crypto", "KRAKEN": "crypto",
            "NASDAQ": "america", "NYSE": "america", "AMEX": "america",
            "LSE": "europe", "XETRA": "europe",
            "TSE": "asia", "HKEX": "asia", "SSE": "asia",
            "OANDA": "forex", "FX": "forex",
        }
        return mapping.get(exchange.upper(), "forex")

    def fetch_ohlcv(
        self,
        symbol: str = "OANDA:XAUUSD",
        interval: str = "1D",
        bars_count: int = 200,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV data. Tries WS first, falls back to yfinance."""
        # Try WebSocket first
        df = self._fetch_via_ws(symbol, interval, bars_count)
        if not df.empty:
            return df

        # Fallback: yfinance
        logger.info(f"WS failed, falling back to yfinance for {symbol}")
        return self._fetch_via_yfinance(symbol, interval, bars_count, start_date, end_date)

    def _fetch_via_yfinance(
        self, symbol: str, interval: str, bars_count: int,
        start_date: Optional[str] = None, end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fallback: fetch via yfinance."""
        try:
            import yfinance as yf

            # Convert TradingView symbol to yfinance ticker
            yf_symbol = self._tv_to_yf_symbol(symbol)

            # Map interval
            yf_interval = {
                "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                "1H": "1h", "4H": "1h", "1D": "1d", "1W": "1wk", "1M": "1mo",
            }.get(interval, "1d")

            ticker = yf.Ticker(yf_symbol)

            if start_date and end_date:
                df = ticker.history(start=start_date, end=end_date, interval=yf_interval)
            elif yf_interval in ("1m", "5m", "15m", "30m"):
                # yfinance limits intraday to 7 days
                df = ticker.history(period="5d", interval=yf_interval)
            else:
                days_back = min(bars_count * 2, 730)
                df = ticker.history(period=f"{days_back}d", interval=yf_interval)

            if df.empty:
                return df

            df.columns = [c.lower().replace(" ", "_") for c in df.columns]
            if "adj close" in df.columns:
                df.drop(columns=["adj close"], inplace=True, errors="ignore")
            for drop_col in ["stock splits", "capital gains"]:
                if drop_col in df.columns:
                    df.drop(columns=[drop_col], inplace=True, errors="ignore")
            if "dividends" in df.columns:
                df.drop(columns=["dividends"], inplace=True, errors="ignore")

            return df.tail(bars_count)

        except Exception as e:
            logger.error(f"yfinance fallback failed: {e}")
            return pd.DataFrame()

    @staticmethod
    def _tv_to_yf_symbol(tv_symbol: str) -> str:
        """Convert TradingView symbol to yfinance format."""
        parts = tv_symbol.split(":")
        if len(parts) == 2:
            exchange, ticker = parts
            exchange_upper = exchange.upper()

            # Gold/Silver/Commodities
            commodity_map = {
                "XAUUSD": "GC=F",    # Gold futures
                "XAGUSD": "SI=F",    # Silver futures
                "XAU": "GC=F",
                "XAG": "SI=F",
            }
            if ticker.upper() in commodity_map:
                return commodity_map[ticker.upper()]

            # Forex pairs
            if exchange_upper in ("OANDA", "FX"):
                return f"{ticker}=X"

            # Crypto
            if exchange_upper in ("BINANCE", "COINBASE", "KRAKEN"):
                if ticker.endswith("USDT"):
                    base = ticker[:-4]
                    return f"{base}-USD"
                elif ticker.endswith("USD"):
                    base = ticker[:-3]
                    return f"{base}-USD"
                return f"{ticker}-USD"

            # Index
            if exchange_upper in ("TVC", "TVC"):
                index_map = {
                    "DJI": "^DJI", "SPX": "^GSPC", "IXIC": "^IXIC",
                    "VIX": "^VIX", "DXY": "DX-Y.NYB",
                }
                return index_map.get(ticker, f"^{ticker}")
            if exchange_upper == "CRYPTOCAP":
                return f"^{ticker}"

            # Default: use ticker directly
            return ticker

        return tv_symbol

    def search_symbol(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search TradingView symbols."""
        try:
            resp = requests.get(
                self.SEARCH_URL.format(query, ""),
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            results = resp.json().get("symbols", [])
            return [
                {
                    "symbol": r.get("symbol", ""),
                    "description": r.get("description", ""),
                    "exchange": r.get("exchange", ""),
                    "type": r.get("type", ""),
                    "full_symbol": r.get("full_name", ""),
                }
                for r in results[:max_results]
            ]
        except Exception as e:
            logger.error(f"Symbol search failed: {e}")
            return []

    def get_scanner_indicators(self, symbol: str, interval: str = "1D") -> Dict:
        """Get technical indicators from TradingView Scanner."""
        raw = self._fetch_via_scanner(symbol, interval)
        if not raw:
            return {}

        keys = [
            "close", "open", "high", "low", "volume",
            "change", "change_abs", "Recommend.All",
            "RSI", "RSI[1]", "Stoch.K", "Stoch.D",
            "CCI20", "CCI20[1]", "ADX", "ADX[1]",
            "AO", "AO[1]", "Mom", "Mom[1]",
            "MACD.macd", "MACD.signal",
            "Rec.BB", "BB.upper", "BB.lower",
            "Rec.Stoch.RSI", "Rec.WR", "Rec.UO",
            "Rec.ADX", "Rec.AO", "Rec.MACD",
            "Rec.Ichimoku", "Rec.VWMA", "Rec.EMA", "Rec.SMA",
        ]
        return dict(zip(keys, raw))

    def get_tv_recommendation(self, symbol: str, interval: str = "1D") -> str:
        """Get TradingView overall recommendation."""
        indicators = self.get_scanner_indicators(symbol, interval)
        rec = indicators.get("Recommend.All", 0)
        if rec >= 0.5:
            return "STRONG BUY"
        elif rec >= 0.2:
            return "BUY"
        elif rec <= -0.5:
            return "STRONG SELL"
        elif rec <= -0.2:
            return "SELL"
        return "NEUTRAL"


# Convenience singleton
_fetcher: Optional[TVFetcher] = None


def get_fetcher(**kwargs) -> TVFetcher:
    global _fetcher
    if _fetcher is None:
        from config import TV_USERNAME, TV_PASSWORD, TV_AUTH_TOKEN, TV_SESSION_ID, TV_SESSION_SIGN
        _fetcher = TVFetcher(
            username=kwargs.get("username", TV_USERNAME),
            password=kwargs.get("password", TV_PASSWORD),
            auth_token=kwargs.get("auth_token", TV_AUTH_TOKEN),
            session_id=kwargs.get("session_id", TV_SESSION_ID),
            session_sign=kwargs.get("session_sign", TV_SESSION_SIGN),
        )
    return _fetcher
