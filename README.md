# TradingView Analyzer Pro

Professional trading analysis dashboard with multi-school consensus, ML prediction, and backtesting.

## Features

- **Interactive Charts** — Candlestick with 130+ technical indicators
- **Technical Analysis** — RSI, MACD, Bollinger Bands, ADX, Stochastic, EMA Cross
- **Statistical Analysis** — Distribution, stationarity, correlation, volatility regime
- **ML Prediction** — Ensemble of Random Forest + XGBoost + LightGBM
- **Backtesting** — Multiple strategies with performance metrics
- **Multi-School Consensus** — 5 schools vote: Technical, Statistical, ML, Momentum, Volume

## Quick Start

```powershell
cd D:\NOTEBOOK\TradingView-Analyzer
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## TradingView Data

The tool fetches data from TradingView via WebSocket. Supports:

- **Anonymous mode** — Daily data real-time, intraday delayed
- **Free account** — Login via cookies for better access
- **yfinance fallback** — Automatic fallback if TradingView is unavailable

### To use your TradingView account:

1. Open TradingView in browser and log in
2. Press F12 → Application → Cookies → tradingview.com
3. Copy `sessionid` and `sessionid_sign`
4. Set environment variables:
   ```powershell
   $env:TV_SESSION_ID = "your_session_id"
   $env:TV_SESSION_SIGN = "your_session_sign"
   ```

## Project Structure

```
TradingView-Analyzer/
├── app.py                    # Streamlit dashboard
├── config.py                 # Configuration
├── requirements.txt
├── core/
│   ├── tv_fetcher.py         # TradingView data fetcher
│   ├── indicators.py         # Technical indicators
│   ├── statistical.py        # Statistical analysis
│   ├── predictor.py          # ML prediction
│   ├── backtester.py         # Backtesting engine
│   └── consensus.py          # Multi-school consensus
├── dashboard/
│   ├── components.py         # Shared UI components
│   └── tabs/                 # Dashboard tabs
└── data/cache/               # Model cache
```

## Disclaimer

This is for **educational and research purposes only**. Not financial advice. Always do your own research before trading.
