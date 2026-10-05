"""
TradingView Scraper Pro
Uses TradingView Scanner API for forex/stocks + yfinance fallback for commodities.
OHLCV cascade: TradingView WebSocket -> tradingview-sdk -> yfinance -> Binance.
"""
import threading
import requests
import pandas as pd
import numpy as np
import time as _time
from typing import Dict, List, Optional
from datetime import datetime

from core.ohlcv_cache import get_cache
from core.tv_ws import fetch_tv_ws


_YF_CACHE: Dict = {}

# Shared tradingview-sdk client (thread-safe: each get_bars drives its own
# asyncio event loop; the underlying httpx client is thread-safe).
_TV_SDK: Optional["TradingView"] = None
_TV_SDK_LOCK = threading.Lock()


def _get_tv_sdk():
    global _TV_SDK
    if _TV_SDK is None:
        with _TV_SDK_LOCK:
            if _TV_SDK is None:
                from tradingview_sdk import TradingView
                _TV_SDK = TradingView(timeout=12)
    return _TV_SDK


class TVScraperPro:
    """Scrape data from TradingView + fallback sources."""

    SCANNER_URLS = {
        "forex": "https://scanner.tradingview.com/forex/scan",
        "crypto": "https://scanner.tradingview.com/crypto/scan",
        "america": "https://scanner.tradingview.com/america/scan",
        "europe": "https://scanner.tradingview.com/europe/scan",
        "asia": "https://scanner.tradingview.com/asia/scan",
    }

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
    }

    # TradingView symbol -> yfinance ticker (used when TV scanner has no data
    # or the symbol needs an equivalent yfinance series, e.g. futures/indices).
    YFINANCE_SYMBOLS = {
        # Spot metals (OANDA / FX / FOREXCOM all price the same cash market)
        "OANDA:XAUUSD": "GC=F", "FX:XAUUSD": "GC=F", "FOREXCOM:XAUUSD": "GC=F",
        "TVC:XAUUSD": "GC=F", "TVC:XAGUSD": "SI=F",
        "OANDA:XAGUSD": "SI=F", "FX:XAGUSD": "SI=F", "FOREXCOM:XAGUSD": "SI=F",
        "OANDA:XAUUSDT": "GC=F", "FOREXCOM:XAUUSDT": "GC=F",
        "OANDA:XPTUSD": "PL=F", "OANDA:XPDUSD": "PA=F", "OANDA:XCUUSD": "HG=F",
        # Futures (with or without front-month suffix)
        "COMEX:GC1!": "GC=F", "COMEX:SI1!": "SI=F",
        "NYMEX:CL1!": "CL=F", "NYMEX:NG1!": "NG=F",
        "NYMEX:HO1!": "HO=F", "NYMEX:RB1!": "RB=F",
        "ICE:BZ1!": "BZ=F", "ICE:GAS1!": "NG=F",
        # TradingView aggregates / markets
        "TVC:GOLD": "GC=F", "TVC:SILVER": "SI=F", "TVC:DXY": "DX-Y.NYB",
        "TVC:USOIL": "CL=F", "TVC:BG100": "GC=F",
        "TVC:VIX": "^VIX", "TVC:US10Y": "^TNX", "TVC:US30Y": "^TYX",
        "TVC:US02Y": "^IRX",
        # Indices
        "TVC:NDX": "^NDX", "TVC:DJI": "^DJI", "TVC:SPX": "^GSPC",
        "TVC:IXIC": "^IXIC", "TVC:NKY": "^N225", "TVC:HSI": "^HSI",
        "TVC:FTSE": "^FTSE", "TVC:GDAXI": "^GDAXI", "TVC:DAX": "^GDAXI",
        "TVC:CAC40": "^FCHI", "TVC:STOXX50E": "^STOXX50E",
        "TVC:ASX200": "^AXJO", "TVC:KOSPI": "^KS11",
        "BSE:SENSEX": "^BSESN", "NSE:NIFTY": "^NSEI",
        "TVC:OMX": "^OMX", "TVC:IBEX": "^IBEX",
    }

    def _resolve_yf_symbol(self, tv_symbol: str) -> str:
        """Best-effort convert any TradingView symbol into a yfinance ticker."""
        s = str(tv_symbol).strip().upper()
        if s in self.YFINANCE_SYMBOLS:
            return self.YFINANCE_SYMBOLS[s]

        if ":" in s:
            exchange, tk = s.split(":", 1)
        else:
            exchange, tk = "", s

        # Futures front-month: "GC1!" -> "GC=F", "ES!" -> "ES=F"
        if tk.endswith("!"):
            base = tk.rstrip("!")
            if base.isdigit():
                base = tk
            return f"{base}=F"

        if exchange in ("OANDA", "FX", "FOREXCOM"):
            if tk.startswith("XAU"): return "GC=F"
            if tk.startswith("XAG"): return "SI=F"
            if tk.startswith("XPT"): return "PL=F"
            if tk.startswith("XPD"): return "PA=F"
            if tk.startswith("XCU"): return "HG=F"
            # Spot FX pair: EURUSD -> EURUSD=X
            return f"{tk}=X"

        if exchange in ("BINANCE", "COINBASE", "KRAKEN", "BITSTAMP", "BITMEX"):
            base = tk
            for suffix in ("USDT", "USDC", "USD", "PERP", "BUSD"):
                if base.endswith(suffix):
                    base = base[:-len(suffix)]
                    break
            if not base or base == tk:
                base = tk.rstrip("USDT")
            return f"{base}-USD"

        if exchange in ("TVC", "TSE", "HKEX"):
            # Unmapped aggregate/asia index: try direct (often a ^-prefixed yf code)
            return tk if tk.startswith("^") else f"^{tk}"

        # NASDAQ / NYSE / AMEX / TSE / NSE / BSE etc. -> plain ticker
        return tk

    # App interval -> (yfinance interval, period)
    YF_INTERVAL_MAP = {
        "1m": ("1m", "1d"),
        "5m": ("5m", "1mo"),
        "15m": ("15m", "1mo"),
        "30m": ("30m", "1mo"),
        "1H": ("1h", "3mo"),
        "4H": ("1h", "3mo"),   # resampled to 4h below
        "1D": ("1d", "6mo"),
        "1W": ("1wk", "1y"),
        "1M": ("1mo", "2y"),
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def get_market_type(self, symbol: str) -> str:
        s = symbol.upper()
        if any(x in s for x in ["BINANCE", "COINBASE", "KRAKEN"]):
            return "crypto"
        if any(x in s for x in ["NASDAQ", "NYSE", "AMEX"]):
            return "america"
        if any(x in s for x in ["LSE", "XETR"]):
            return "europe"
        if any(x in s for x in ["TSE", "HKEX"]):
            return "asia"
        return "forex"

    def scrape_scanner(self, symbol: str) -> Dict:
        """Get real-time data from TradingView Scanner API."""
        columns = [
            "close", "open", "high", "low", "volume",
            "change", "change_abs", "Recommend.All",
            "RSI", "RSI[1]",
            "Stoch.K", "Stoch.D",
            "CCI20", "ADX", "ADX+DI", "ADX-DI",
            "MACD.macd", "MACD.signal", "MACD.hist",
            "BB.upper", "BB.lower",
            "EMA20", "EMA50", "SMA20", "SMA50", "SMA200",
            "VWMA",
            "Rec.BB", "Rec.MACD", "Rec.EMA", "Rec.SMA",
        ]

        market = self.get_market_type(symbol)
        url = self.SCANNER_URLS.get(market, self.SCANNER_URLS["forex"])

        # Persistent SQL cache: TradingView scanner is the slowest endpoint.
        from core.ohlcv_cache import SCANNER_TTL
        cached = get_cache().get_scanner(symbol, max_age=SCANNER_TTL)
        if cached is not None:
            return cached

        payload = {
            "columns": columns,
            "symbols": {"tickers": [symbol]},
            "options": {"lang": "en", "range": ["1M"]},
            "markets": list(self.SCANNER_URLS.keys()),
        }

        try:
            resp = self.session.post(url, json=payload, timeout=15)
            data = resp.json()

            if data.get("totalCount", 0) > 0:
                row = data["data"][0].get("d", [])
                result = {}
                for i, col in enumerate(columns):
                    if i < len(row):
                        result[col] = row[i]
                result = {"source": "tradingview", "data": result}
                get_cache().put_scanner(symbol, result)
                return result
        except Exception as e:
            pass

        return {"source": "none", "data": {}}

    def _yf_interval(self, interval: str) -> tuple:
        """Return (yf_interval, period) for an app interval key."""
        key = str(interval).upper()
        return self.YF_INTERVAL_MAP.get(key, self.YF_INTERVAL_MAP["1D"])

    # App interval -> Binance kline interval (fallback when yfinance has no
    # data, e.g. coins delisted on yahoo but still live on Binance)
    BINANCE_INTERVAL_MAP = {
        "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1H": "1h", "4H": "4h", "1D": "1d", "1W": "1w", "1M": "1M",
    }

    def _fetch_binance_ohlcv(self, tv_symbol: str, interval: str) -> pd.DataFrame:
        """Get OHLCV from Binance public klines API (no key needed)."""
        s = str(tv_symbol).strip().upper()
        if not s.startswith("BINANCE:"):
            return pd.DataFrame()
        pair = s.split(":", 1)[1]  # e.g. BTCUSDT
        raw = str(interval)
        iv = self.BINANCE_INTERVAL_MAP.get(raw) or self.BINANCE_INTERVAL_MAP.get(raw.upper())
        if not iv:
            return pd.DataFrame()
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": pair, "interval": iv, "limit": 300}
        try:
            resp = requests.get(url, params=params, timeout=10)
            rows = resp.json()
            if isinstance(rows, dict) or not rows:
                return pd.DataFrame()
            df = pd.DataFrame([{
                "open": float(x[1]), "high": float(x[2]), "low": float(x[3]),
                "close": float(x[4]), "volume": float(x[5]),
                "timestamp": pd.to_datetime(x[0], unit="ms"),
            } for x in rows])
            df.set_index("timestamp", inplace=True)
            return df.tail(200)
        except Exception:
            return pd.DataFrame()

    def scrape_yfinance(self, tv_symbol: str, interval: str = "1D", use_cache: bool = True, bars: int = 200) -> pd.DataFrame:
        """Get OHLCV from TradingView first, yfinance/binance as fallbacks.

        Cascade (kept name for backward compatibility):
          1. TradingView WebSocket (native 1m-1M resolutions, ~0.4s)
          2. tradingview-sdk (same TV chart protocol via a maintained client)
          3. yfinance
          4. Binance public API (coins delisted on yahoo)

        Every frame is normalized to tz-aware UTC before caching so bar epochs
        are exact. 4H comes natively from TV ("240"); the yfinance resample only
        applies on the yfinance fallback path.
        """
        raw_iv = str(interval)
        iv = raw_iv.upper()
        cache_key = (str(tv_symbol).strip().upper(), iv)

        # Persistent SQL cache: re-analysis instant, refetch only past TTL.
        if use_cache:
            cached_df = get_cache().get_frame(cache_key[0], iv)
            if cached_df is not None:
                return cached_df

        def _finish(df: pd.DataFrame, source: str, n: int = bars) -> pd.DataFrame:
            df = self._normalize_ohlcv(df)
            if df.empty:
                return pd.DataFrame()
            tail = df.tail(n).copy()
            if use_cache:
                get_cache().put_frame(cache_key[0], iv, tail, source)
            return tail

        # 1. TradingView WebSocket (primary; fastest, no API key)
        try:
            df_ws = fetch_tv_ws(cache_key[0], raw_iv, bars=max(bars, 300))
            if not df_ws.empty:
                return _finish(df_ws, "tradingview_ws")
        except Exception:
            pass

        # 2. tradingview-sdk (same protocol via a maintained async client)
        try:
            import config as _cfg
            sdk_iv = _cfg.INTERVALS.get(raw_iv, raw_iv)
            bs = _get_tv_sdk().get_bars(cache_key[0], sdk_iv, bars=max(bars, 300), timeout=6.0)
            if bs is not None and len(bs) > 0:
                df_sdk = bs.to_dataframe()
                if not df_sdk.empty:
                    return _finish(df_sdk, "tradingview_sdk")
        except Exception:
            pass

        # 3-4. yfinance → Binance fallback
        df_fb = self._fetch_yfinance_fallback(tv_symbol, interval, use_cache)
        return df_fb

    @staticmethod
    def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure OHLCV columns + a tz-aware UTC DatetimeIndex on any source frame."""
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        if df.index.name is None or not str(df.index.name).startswith(("date", "time")):
            df.index.name = "time"
        cols = {c: str(c).strip().lower() for c in df.columns}
        df = df.rename(columns=cols)
        for c in ("open", "high", "low", "close", "volume"):
            if c not in df.columns:
                df[c] = np.nan
        df = df[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
        idx = pd.to_datetime(df.index)
        if getattr(idx, "tz", None) is None:
            idx = idx.tz_localize("UTC")
        else:
            idx = idx.tz_convert("UTC")
        df.index = idx
        df.index.name = "time"
        df = df.dropna(subset=["open", "close"])
        return df.sort_index()

    def _fetch_yfinance_fallback(self, tv_symbol: str, interval: str, use_cache: bool) -> pd.DataFrame:
        """Original yfinance→binance path, kept as the dirty-ticket fallback."""
        import yfinance as yf
        import config as cfg

        yf_symbol = self.YFINANCE_SYMBOLS.get(str(tv_symbol).strip().upper())
        if not yf_symbol:
            yf_symbol = self._resolve_yf_symbol(tv_symbol)

        yf_interval, period = self._yf_interval(interval)

        # Short-TTL cache keyed by (symbol, interval) so MTF + realtime don't
        # hit the yfinance endpoint 6 times on every refresh.
        cache_key = (yf_symbol, yf_interval, str(interval).upper())
        ttl = getattr(cfg, "YF_CACHE_TTL", 20.0)
        now = _time.time()
        if use_cache:
            hit = _YF_CACHE.get(cache_key)
            if hit and (now - hit[0]) < ttl:
                return hit[1].copy()

        try:
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period=period, interval=yf_interval)

            if df.empty:
                df = ticker.history(period="6mo", interval="1d")

            if df.empty:
                df = ticker.history(period="1y", interval="1d")

            if not df.empty:
                df.columns = [c.lower().replace(" ", "_") for c in df.columns]
                for drop in ["stock_splits", "capital_gains", "dividends"]:
                    if drop in df.columns:
                        df.drop(columns=[drop], inplace=True, errors="ignore")

                # Resample hourly data into 4H candles (TV path needs no this).
                if str(interval).upper() == "4H":
                    freq = df.index.freq
                    if freq is not None and "h" in freq.name.lower() and len(df) >= 4:
                        agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
                        df = df.resample("4h").agg(agg)
                        df.dropna(subset=["open", "close"], inplace=True)

                tail = self._normalize_ohlcv(df).tail(200).copy()
                if not tail.empty:
                    if use_cache:
                        _YF_CACHE[cache_key] = (now, tail)
                    get_cache().put_frame(str(tv_symbol).strip().upper(), str(interval).upper(), tail, "yfinance")
                    return tail
        except Exception:
            pass

        # yfinance has nothing — fall back to Binance public API so coins
        # delisted on yahoo still render a chart (e.g. BINANCE:APTUSDT).
        dfb = self._fetch_binance_ohlcv(tv_symbol, interval)
        if not dfb.empty:
            dfb = self._normalize_ohlcv(dfb).tail(200)
            if not dfb.empty:
                if use_cache:
                    _YF_CACHE[cache_key] = (now, dfb.copy())
                get_cache().put_frame(str(tv_symbol).strip().upper(), str(interval).upper(), dfb, "binance")
                return dfb.copy()

        return pd.DataFrame()

    def get_full_data(self, symbol: str, interval: str = "1D") -> Dict:
        """Get comprehensive data - scanner + yfinance combined."""
        result = {
            "symbol": symbol,
            "scanner": {},
            "ohlcv": pd.DataFrame(),
            "source": "none",
        }

        # Try scanner first
        scanner = self.scrape_scanner(symbol)
        if scanner["data"]:
            result["scanner"] = scanner["data"]
            result["source"] = "tradingview"

        # Get OHLCV via the TradingView-first cascade
        df = self.scrape_yfinance(symbol, interval=interval)
        if not df.empty:
            result["ohlcv"] = df
            src_row = get_cache().conn.execute(
                "SELECT source FROM ohlcv_cache WHERE symbol=? AND interval=?",
                (str(symbol).strip().upper(), str(interval).upper()),
            ).fetchone()
            ohlcv_source = src_row["source"] if src_row else "ohlcv"
            if result["source"] == "none":
                result["source"] = ohlcv_source
            else:
                result["ohlcv_source"] = ohlcv_source

        return result

    def get_recommendation(self, data: Dict) -> str:
        """Get trading recommendation from scanner data."""
        rec = data.get("Recommend.All")
        if rec is None:
            return "N/A"
        if rec >= 0.5:
            return "STRONG BUY"
        elif rec >= 0.2:
            return "BUY"
        elif rec <= -0.5:
            return "STRONG SELL"
        elif rec <= -0.2:
            return "SELL"
        return "NEUTRAL"

    def get_indicators(self, data: Dict) -> Dict:
        """Extract indicator values from scanner data."""
        return {
            "RSI": data.get("RSI"),
            "Stoch_K": data.get("Stoch.K"),
            "Stoch_D": data.get("Stoch.D"),
            "CCI20": data.get("CCI20"),
            "ADX": data.get("ADX"),
            "ADX_DI_plus": data.get("ADX+DI"),
            "ADX_DI_minus": data.get("ADX-DI"),
            "MACD": data.get("MACD.macd"),
            "MACD_signal": data.get("MACD.signal"),
            "MACD_hist": data.get("MACD.hist"),
            "BB_upper": data.get("BB.upper"),
            "BB_lower": data.get("BB.lower"),
            "EMA20": data.get("EMA20"),
            "EMA50": data.get("EMA50"),
            "SMA20": data.get("SMA20"),
            "SMA50": data.get("SMA50"),
            "SMA200": data.get("SMA200"),
            "VWMA": data.get("VWMA"),
        }

    def search(self, query: str) -> List[Dict]:
        """Search TradingView symbols."""
        url = f"https://symbol-search.tradingview.com/symbol_search/v3/?text={query}&hl=1&lang=en"
        try:
            resp = self.session.get(url, timeout=10)
            data = resp.json()
            return [
                {
                    "symbol": r.get("symbol", ""),
                    "description": r.get("description", ""),
                    "exchange": r.get("exchange", ""),
                    "full_symbol": r.get("full_name", ""),
                }
                for r in data.get("symbols", [])[:10]
            ]
        except Exception:
            return []


# Convenience functions
def scrape(symbol: str = "OANDA:XAUUSD") -> Dict:
    """Scrape data from TradingView + yfinance."""
    scraper = TVScraperPro()
    return scraper.get_full_data(symbol)


def scrape_ohlcv(symbol: str = "OANDA:XAUUSD", bars: int = 200, interval: str = "1D") -> pd.DataFrame:
    """Get OHLCV DataFrame."""
    scraper = TVScraperPro()
    result = scraper.get_full_data(symbol, interval=interval)
    df = result["ohlcv"]
    if not df.empty:
        return df.tail(bars)
    return df


if __name__ == "__main__":
    print("=" * 60)
    print("TradingView Scraper Pro")
    print("=" * 60)

    symbols = ["OANDA:XAUUSD", "FX:EURUSD", "NASDAQ:AAPL", "BINANCE:BTCUSDT"]

    scraper = TVScraperPro()

    for symbol in symbols:
        print(f"\n[*] {symbol}")
        result = scraper.get_full_data(symbol)
        print(f"    Source: {result['source']}")

        if result["scanner"]:
            rec = scraper.get_recommendation(result["scanner"])
            print(f"    Recommendation: {rec}")
            indicators = scraper.get_indicators(result["scanner"])
            rsi = indicators.get("RSI")
            macd = indicators.get("MACD")
            if rsi:
                print(f"    RSI: {rsi:.1f}")
            if macd:
                print(f"    MACD: {macd:.4f}")

        if not result["ohlcv"].empty:
            df = result["ohlcv"]
            print(f"    OHLCV: {len(df)} bars")
            latest = df.iloc[-1]
            print(f"    Latest: O={latest['open']:.4f} H={latest['high']:.4f} L={latest['low']:.4f} C={latest['close']:.4f}")

    print("\n" + "=" * 60)
