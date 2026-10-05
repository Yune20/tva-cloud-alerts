"""
TradingView Browser Scraper
Uses Playwright to scrape OHLCV data directly from TradingView chart page.
"""
import asyncio
import json
import re
import pandas as pd
from typing import Optional


async def scrape_tradingview(symbol: str = "OANDA:XAUUSD", timeframe: str = "D", bars: int = 200) -> pd.DataFrame:
    """Scrape OHLCV data from TradingView chart using Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        # Capture WebSocket data
        captured_data = []

        async def handle_ws(ws):
            async def on_message(msg):
                try:
                    data = json.loads(msg)
                    if isinstance(data, list) and len(data) > 1:
                        msg_type = data[0] if isinstance(data[0], str) else ""
                        if "timescale_update" in msg_type or "series_update" in msg_type:
                            captured_data.append(data)
                except (json.JSONDecodeError, IndexError):
                    pass
            ws.on("framereceived", on_message)

        page.on("websocket", handle_ws)

        # Navigate to TradingView chart
        tv_url = f"https://www.tradingview.com/chart/?symbol={symbol}"
        print(f"[*] Navigating to {tv_url}")
        await page.goto(tv_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)  # Wait for chart to load

        # Try to extract data from page's JavaScript
        try:
            ohlcv_data = await page.evaluate("""() => {
                // Try to access TradingView's internal data
                const result = [];

                // Method 1: Check for chart widget data
                if (window.tvWidget && window.tvWidget.activeChart) {
                    const chart = window.tvWidget.activeChart();
                    if (chart && chart.getSeries) {
                        const series = chart.getSeries();
                        const data = series.data();
                        for (let i = 0; i < data.length; i++) {
                            result.push({
                                time: data[i].time,
                                open: data[i].open,
                                high: data[i].high,
                                low: data[i].low,
                                close: data[i].close,
                                volume: data[i].volume || 0,
                            });
                        }
                    }
                }

                // Method 2: Try __NEXT_DATA__
                if (result.length === 0 && window.__NEXT_DATA__) {
                    try {
                        const chartData = window.__NEXT_DATA__.props?.pageProps?.chart?.data;
                        if (chartData) {
                            for (const [key, val] of Object.entries(chartData)) {
                                if (val && val.o) {
                                    result.push({
                                        time: val.t || parseInt(key),
                                        open: val.o,
                                        high: val.h,
                                        low: val.l,
                                        close: val.c,
                                        volume: val.v || 0,
                                    });
                                }
                            }
                        }
                    } catch(e) {}
                }

                return result;
            }""")
            if ohlcv_data:
                print(f"[*] Got {len(ohlcv_data)} bars from JS")
                df = pd.DataFrame(ohlcv_data)
                if not df.empty and "close" in df.columns:
                    if "time" in df.columns:
                        df["date"] = pd.to_datetime(df["time"], unit="s")
                        df.set_index("date", inplace=True)
                    await browser.close()
                    return df
        except Exception as e:
            print(f"[!] JS extraction failed: {e}")

        # Method 3: Intercept network requests
        print("[*] Falling back to network interception...")

        # Try to capture from the page's data table or export
        try:
            # Look for the chart data in the DOM
            chart_data = await page.evaluate("""() => {
                const result = [];
                // Try to find candle data in global scope
                const keys = Object.keys(window);
                for (const key of keys) {
                    try {
                        const val = window[key];
                        if (val && typeof val === 'object' && val.bars) {
                            for (const bar of val.bars) {
                                result.push({
                                    time: bar.time || bar.t,
                                    open: bar.open || bar.o,
                                    high: bar.high || bar.h,
                                    low: bar.low || bar.l,
                                    close: bar.close || bar.c,
                                    volume: bar.volume || bar.v || 0,
                                });
                            }
                            if (result.length > 0) break;
                        }
                    } catch(e) {}
                }
                return result;
            }""")
            if chart_data:
                print(f"[*] Got {len(chart_data)} bars from DOM")
                df = pd.DataFrame(chart_data)
                if not df.empty and "close" in df.columns:
                    if "time" in df.columns:
                        df["date"] = pd.to_datetime(df["time"], unit="s")
                        df.set_index("date", inplace=True)
                    await browser.close()
                    return df
        except Exception as e:
            print(f"[!] DOM extraction failed: {e}")

        await browser.close()
        return pd.DataFrame()


async def scrape_tradingview_snapshot(symbol: str = "OANDA:XAUUSD", timeframe: str = "D") -> dict:
    """Get a snapshot of current price data from TradingView."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        page = await context.new_page()

        tv_url = f"https://www.tradingview.com/chart/?symbol={symbol}"
        await page.goto(tv_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(8)

        # Extract visible data
        snapshot = await page.evaluate("""() => {
            const result = {price: null, symbol: null, indicators: {}};

            // Get symbol info
            const symbolEl = document.querySelector('[class*="symbolTitle"], [data-name="legend-source-item"]');
            if (symbolEl) result.symbol = symbolEl.textContent.trim();

            // Get current price
            const priceEl = document.querySelector('[class*="lastPrice"], [class*="valueValue"], .tv-symbol-price-quote__value');
            if (priceEl) result.price = parseFloat(priceEl.textContent.replace(/,/g, ''));

            // Get all visible text that looks like OHLCV
            const els = document.querySelectorAll('[class*="highlight"], [class*="value"]');
            const texts = [];
            els.forEach(el => {
                const text = el.textContent.trim();
                if (/^\\d+\\.\\d+$/.test(text)) {
                    texts.push(parseFloat(text));
                }
            });
            result.raw_values = texts.slice(0, 20);

            return result;
        }""")

        await browser.close()
        return snapshot


def scrape_sync(symbol: str = "OANDA:XAUUSD", timeframe: str = "D", bars: int = 200) -> pd.DataFrame:
    """Synchronous wrapper for scraping."""
    return asyncio.run(scrape_tradingview(symbol, timeframe, bars))


if __name__ == "__main__":
    print("=" * 60)
    print("TradingView Browser Scraper")
    print("=" * 60)

    symbol = "OANDA:XAUUSD"
    print(f"\n[*] Scraping {symbol}...")

    df = scrape_sync(symbol)

    if not df.empty:
        print(f"[+] Got {len(df)} bars")
        print(f"\nLatest 5 candles:")
        print(df.tail())
    else:
        print("[-] No data scraped. Using yfinance fallback...")

        import sys
        sys.path.insert(0, '.')
        from core.tv_fetcher import TVFetcher
        f = TVFetcher()
        df = f.fetch_ohlcv(symbol, "1D", 200)
        if not df.empty:
            print(f"[+] yfinance: {len(df)} rows")
            print(df.tail())
