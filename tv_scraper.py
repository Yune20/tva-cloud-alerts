"""
TradingView Direct Scraper
Uses TradingView's internal APIs (scanner + chart) with requests.
No browser needed - works with Free account.
"""
import requests
import json
import time
import random
import pandas as pd
from typing import Dict, List, Optional


class TVScraper:
    """Scrape data from TradingView's internal APIs."""

    SCANNER_URLS = {
        "forex": "https://scanner.tradingview.com/forex/scan",
        "crypto": "https://scanner.tradingview.com/crypto/scan",
        "america": "https://scanner.tradingview.com/america/scan",
        "europe": "https://scanner.tradingview.com/europe/scan",
        "asia": "https://scanner.tradingview.com/asia/scan",
    }

    CHART_URL = "https://symbol-search.tradingview.com/symbol_search/v3/"
    QUOTE_URL = "https://quote-feed.tradingview.com/"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
    }

    # All scanner columns available
    SCANNER_COLUMNS = [
        "close", "open", "high", "low", "volume",
        "change", "change_abs", "Recommend.All",
        "RSI", "RSI[1]", "RSI[2]", "RSI[3]",
        "Stoch.K", "Stoch.D", "Stoch.K[1]", "Stoch.D[1]",
        "CCI20", "CCI20[1]", "CCI20[2]",
        "ADX", "ADX[1]", "ADX[2]", "ADX+DI", "ADX-DI",
        "AO", "AO[1]", "AO[2]",
        "Mom", "Mom[1]", "Mom[2]",
        "MACD.macd", "MACD.signal", "MACD.hist",
        "Rec.BB", "BB.upper", "BB.lower", "BB.upper[1]", "BB.lower[1]",
        "Rec.Stoch.RSI", "Rec.WR", "Rec.UO",
        "Rec.ADX", "Rec.AO", "Rec.MACD",
        "Rec.Ichimoku", "Rec.VWMA", "Rec.EMA", "Rec.SMA",
        "VWMA", "EMA10", "EMA20", "EMA30", "EMA50", "EMA100", "EMA200",
        "SMA10", "SMA20", "SMA30", "SMA50", "SMA100", "SMA200",
        "highses", "lowses",
        "price_52_week_high", "price_52_week_low",
        "market_cap_basic", "earnings_per_share_basic_ttm",
        "number_of_employees", "country",
        "sector", "industry",
        "logoid", "type", "exchange",
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def get_market_type(self, symbol: str) -> str:
        """Determine market type from symbol."""
        symbol_upper = symbol.upper()
        if any(x in symbol_upper for x in ["BINANCE", "COINBASE", "KRAKEN", "CRYPTO"]):
            return "crypto"
        if any(x in symbol_upper for x in ["NASDAQ", "NYSE", "AMEX", "OTC"]):
            return "america"
        if any(x in symbol_upper for x in ["LSE", "XETR", "EURONEXT"]):
            return "europe"
        if any(x in symbol_upper for x in ["TSE", "HKEX", "SSE", "ASX"]):
            return "asia"
        return "forex"

    def get_scanner_data(
        self,
        symbol: str,
        columns: List[str] = None,
        range_period: str = "1M",
        limit: int = 100,
    ) -> Dict:
        """Get data from TradingView Scanner API."""
        if columns is None:
            columns = [
                "close", "open", "high", "low", "volume",
                "change", "change_abs", "Recommend.All",
                "RSI", "RSI[1]",
                "Stoch.K", "Stoch.D",
                "CCI20", "ADX", "ADX+DI", "ADX-DI",
                "AO", "Mom",
                "MACD.macd", "MACD.signal", "MACD.hist",
                "BB.upper", "BB.lower",
                "EMA20", "EMA50", "SMA20", "SMA50", "SMA200",
                "VWMA",
            ]

        market = self.get_market_type(symbol)
        url = self.SCANNER_URLS.get(market, self.SCANNER_URLS["forex"])

        payload = {
            "columns": columns,
            "symbols": {"tickers": [symbol]},
            "options": {
                "lang": "en",
                "range": [range_period],
            },
            "markets": list(self.SCANNER_URLS.keys()),
            "sort": {"sortBy": "close", "sortOrder": "desc"},
            "options": {"lang": "en"},
        }

        try:
            resp = self.session.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if "data" in data and len(data["data"]) > 0:
                row = data["data"][0]
                result = {}
                col_values = row.get("d", [])

                # Map values to column names
                for i, col in enumerate(columns):
                    if i < len(col_values):
                        result[col] = col_values[i]

                return result
        except Exception as e:
            print(f"[!] Scanner API error: {e}")

        return {}

    def get_ohlcv_from_scanner(
        self,
        symbol: str,
        timeframe: str = "1D",
        bars: int = 100,
    ) -> pd.DataFrame:
        """Get OHLCV data from scanner (limited - only latest values)."""
        market = self.get_market_type(symbol)
        url = self.SCANNER_URLS.get(market, self.SCANNER_URLS["forex"])

        payload = {
            "columns": [
                "open", "high", "low", "close", "volume",
            ],
            "symbols": {"tickers": [symbol]},
            "options": {
                "lang": "en",
                "range": ["1M"],
            },
            "markets": list(self.SCANNER_URLS.keys()),
        }

        try:
            resp = self.session.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if "data" in data and len(data["data"]) > 0:
                row = data["data"][0].get("d", [])
                if len(row) >= 5:
                    df = pd.DataFrame([{
                        "open": row[0],
                        "high": row[1],
                        "low": row[2],
                        "close": row[3],
                        "volume": row[4],
                    }])
                    df.index = pd.DatetimeIndex([pd.Timestamp.now().normalize()])
                    return df
        except Exception as e:
            print(f"[!] Scanner OHLCV error: {e}")

        return pd.DataFrame()

    def search_symbol(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search TradingView symbols."""
        url = f"https://symbol-search.tradingview.com/symbol_search/v3/?text={query}&hl=1&exchange=&lang=en&type=&domain=production"

        try:
            resp = self.session.get(url, timeout=10)
            data = resp.json()
            results = data.get("symbols", [])

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
            print(f"[!] Search error: {e}")
            return []

    def get_multiple_quotes(self, symbols: List[str]) -> Dict:
        """Get quotes for multiple symbols."""
        results = {}
        for symbol in symbols:
            data = self.get_scanner_data(symbol)
            if data:
                results[symbol] = data
            time.sleep(0.2)  # Rate limit
        return results

    def get_full_analysis(self, symbol: str) -> Dict:
        """Get comprehensive analysis data."""
        columns = [
            "close", "open", "high", "low", "volume",
            "change", "change_abs", "Recommend.All",
            "RSI", "RSI[1]", "RSI[2]",
            "Stoch.K", "Stoch.D",
            "CCI20", "ADX", "ADX+DI", "ADX-DI",
            "MACD.macd", "MACD.signal", "MACD.hist",
            "BB.upper", "BB.lower",
            "EMA20", "EMA50", "SMA20", "SMA50", "SMA200",
            "VWMA",
            "Rec.BB", "Rec.MACD", "Rec.Stoch.RSI",
            "Rec.ADX", "Rec.EMA", "Rec.SMA",
        ]

        data = self.get_scanner_data(symbol, columns)
        if not data:
            return {"error": "Failed to get data"}

        # Parse into structured format
        result = {
            "symbol": symbol,
            "price": {
                "close": data.get("close"),
                "open": data.get("open"),
                "high": data.get("high"),
                "low": data.get("low"),
                "volume": data.get("volume"),
                "change": data.get("change"),
                "change_abs": data.get("change_abs"),
            },
            "recommendation": data.get("Recommend.All"),
            "indicators": {
                "RSI": data.get("RSI"),
                "RSI_prev": data.get("RSI[1]"),
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
            },
            "moving_averages": {
                "EMA20": data.get("EMA20"),
                "EMA50": data.get("EMA50"),
                "SMA20": data.get("SMA20"),
                "SMA50": data.get("SMA50"),
                "SMA200": data.get("SMA200"),
                "VWMA": data.get("VWMA"),
            },
            "recommendations": {
                "BB": data.get("Rec.BB"),
                "MACD": data.get("Rec.MACD"),
                "Stoch_RSI": data.get("Rec.Stoch.RSI"),
                "ADX": data.get("Rec.ADX"),
                "EMA": data.get("Rec.EMA"),
                "SMA": data.get("Rec.SMA"),
            },
        }

        # Overall signal
        rec = result["recommendation"]
        if rec is not None:
            if rec >= 0.5:
                result["signal"] = "STRONG BUY"
            elif rec >= 0.2:
                result["signal"] = "BUY"
            elif rec <= -0.5:
                result["signal"] = "STRONG SELL"
            elif rec <= -0.2:
                result["signal"] = "SELL"
            else:
                result["signal"] = "NEUTRAL"

        return result


def scrape(symbol: str = "OANDA:XAUUSD") -> Dict:
    """Scrape data from TradingView."""
    scraper = TVScraper()
    return scraper.get_full_analysis(symbol)


def scrape_quotes(symbols: List[str]) -> Dict:
    """Scrape quotes for multiple symbols."""
    scraper = TVScraper()
    return scraper.get_multiple_quotes(symbols)


if __name__ == "__main__":
    print("=" * 60)
    print("TradingView Direct Scraper")
    print("=" * 60)

    symbols = ["OANDA:XAUUSD", "NASDAQ:AAPL", "BINANCE:BTCUSDT"]

    for symbol in symbols:
        print(f"\n[*] Scraping {symbol}...")
        result = scrape(symbol)

        if "error" not in result:
            price = result["price"]
            print(f"    Price: {price['close']}")
            print(f"    Change: {price['change']}")
            print(f"    Signal: {result.get('signal', 'N/A')}")
            print(f"    RSI: {result['indicators']['RSI']}")
            print(f"    MACD: {result['indicators']['MACD']}")
        else:
            print(f"    Error: {result['error']}")

    print("\n" + "=" * 60)
