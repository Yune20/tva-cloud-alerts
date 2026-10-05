"""TradingView Analyzer Configuration"""
import os

# ─── TradingView Credentials ───────────────────────────────────
TV_USERNAME = os.getenv("TV_USERNAME", "")
TV_PASSWORD = os.getenv("TV_PASSWORD", "")
TV_AUTH_TOKEN = os.getenv("TV_AUTH_TOKEN", "")
TV_SESSION_ID = os.getenv("TV_SESSION_ID", "")
TV_SESSION_SIGN = os.getenv("TV_SESSION_SIGN", "")

# ─── Default Market Settings ───────────────────────────────────
DEFAULT_SYMBOLS = [
    # ── Metals ──
    "OANDA:XAUUSD", "OANDA:XAGUSD", "COMEX:GC1!",
    "COMEX:SI1!", "OANDA:XAUEUR",
    # ── Crypto ──
    "BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT",
    "BINANCE:BNBUSDT", "BINANCE:XRPUSDT", "BINANCE:ADAUSDT",
    "BINANCE:DOGEUSDT", "BINANCE:DOTUSDT", "BINANCE:AVAXUSDT",
    "BINANCE:MATICUSDT", "BINANCE:LINKUSDT", "BINANCE:ATOMUSDT",
    "BINANCE:UNIUSDT", "BINANCE:LTCUSDT", "BINANCE:NEARUSDT",
    # ── Forex ──
    "FX:EURUSD", "FX:GBPUSD", "FX:USDJPY", "FX:USDCHF",
    "FX:AUDUSD", "FX:USDCAD", "FX:NZDUSD", "FX:EURGBP",
    "FX:EURJPY", "FX:GBPJPY", "FX:EURAUD", "FX:USDTRY",
    "FX:USDZAR", "FX:USDMXN",
    # ── Indices ──
    "TVC:NDX", "TVC:DJI", "TVC:SPX", "TVC:IXIC",
    "TVC:NKY", "TVC:HSI", "TVC:FTSE", "TVC:GDAXI",
    "TVC:CAC40", "TVC:STOXX50E", "BSE:SENSEX", "NSE:NIFTY",
    "TVC:ASX200", "TVC:KOSPI",
    # ── Energy ──
    "NYMEX:CL1!", "NYMEX:NG1!", "NYMEX:HO1!", "NYMEX:RB1!",
    "ICE:BZ1!", "ICE:GAS1!",
    # ── US Stocks ──
    "NASDAQ:AAPL", "NASDAQ:MSFT", "NASDAQ:GOOGL", "NASDAQ:AMZN",
    "NASDAQ:META", "NASDAQ:TSLA", "NASDAQ:NVDA", "NASDAQ:AMD",
    "NASDAQ:NFLX", "NASDAQ:COIN", "NASDAQ:INTC", "NASDAQ:CRM",
    "NASDAQ:ADBE", "NASDAQ:PYPL", "NYSE:XYZ", "NASDAQ:UBER",
    "NASDAQ:ABNB", "NASDAQ:SNOW", "NASDAQ:PLTR", "NASDAQ:RIVN",
    "NASDAQ:LCID", "NASDAQ:MARA", "NASDAQ:RIOT", "NASDAQ:HOOD",
    "NYSE:JPM", "NYSE:GS", "NYSE:BAC", "NYSE:V",
    "NYSE:MA", "NYSE:JNJ", "NYSE:UNH", "NYSE:WMT",
    "NYSE:DIS", "NYSE:BA", "NYSE:CAT", "NYSE:DE",
    "NYSE:CVX", "NYSE:XOM", "NYSE:COP", "NYSE:SLB",
    "NYSE:OXY", "NYSE:MO", "NYSE:PM", "NYSE:PEP",
    "NYSE:KO", "NYSE:MCD", "NYSE:NKE", "NYSE:TGT",
    "NYSE:HD", "NYSE:LOW", "NYSE:COST", "NYSE:WBA",
    "NYSE:T", "NYSE:VZ", "NYSE:CMCSA", "NYSE:IBM", "NYSE:AXP",
    "NYSE:SNAP", "NYSE:PINS", "NYSE:RBLX",
    # ── CFD ──
    "FOREXCOM:XAUUSD", "FOREXCOM:XAGUSD",
    "TVC:DXY", "TVC:US10Y", "TVC:US02Y", "TVC:US30Y",
    "TVC:DAX", "TVC:VIX",
    # ── Vietnam Stocks ──
    "HOSE:VNM", "HOSE:VIC", "HOSE:VHM", "HOSE:VRE", "HOSE:VCB", "HOSE:BID",
    "HOSE:CTG", "HOSE:TCB", "HOSE:MBB", "HOSE:ACB", "HOSE:VPB", "HOSE:STB",
    "HOSE:HDB", "HOSE:TPB", "HOSE:LPB", "HOSE:MSB", "HOSE:VIB", "HOSE:OCB",
    "HOSE:FPT", "HOSE:MWG", "HOSE:VJC", "HOSE:HPG", "HOSE:GAS", "HOSE:PLX",
    "HOSE:POW", "HOSE:NT2", "HOSE:SAB", "HOSE:MSN", "HOSE:PNJ", "HOSE:DGW",
    "HOSE:SSI", "HOSE:HCM", "HOSE:VND", "HOSE:CTD", "HOSE:CII", "HOSE:DXG",
    "HOSE:GEX", "HOSE:REE", "HOSE:KBC", "HOSE:KDH", "HOSE:NLG", "HOSE:SCR",
    "HOSE:AAA", "HOSE:BWE", "HOSE:DBD", "HOSE:FLC", "HOSE:GVR", "HOSE:HT1",
    "HOSE:ITC", "HOSE:LDG", "HOSE:MBG", "HOSE:OIL", "HOSE:PGC", "HOSE:PHR",
    "HOSE:PPC", "HOSE:QNS", "HOSE:SBS", "HOSE:SLV", "HOSE:SVI", "HOSE:SZC",
    "HOSE:TAG", "HOSE:TCH", "HOSE:TRA", "HOSE:TTF", "HOSE:VGT", "HOSE:VMD",
    "HNX:SHB", "HNX:PVS", "HNX:PVD", "HNX:PVB", "HNX:BVS", "HNX:CEO",
    "HNX:IDC", "HNX:SHS", "HNX:LAS", "HNX:DPM", "HNX:HEV", "HNX:KLS",
    "HNX:NCT", "HNX:NTC", "HNX:PAC", "HNX:PET", "HNX:PLC", "HNX:S99",
    "HNX:SCS", "HNX:VNR", "HNX:WSS", "HNX:XMC",
]

DEFAULT_INTERVAL = "1D"
DEFAULT_BARS_COUNT = 200

INTERVALS = {
    "1m": "1", "5m": "5", "15m": "15", "30m": "30",
    "1H": "60", "4H": "240", "1D": "1D", "1W": "1W", "1M": "1M",
}

# ─── Analysis Settings ─────────────────────────────────────────
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2.0
EMA_SHORT = 21
EMA_LONG = 50
ADX_PERIOD = 14
ATR_PERIOD = 14

# ─── ML Prediction Settings ────────────────────────────────────
PREDICTION_LOOKBACK = 60
PREDICTION_FORWARD = 1
TRAIN_TEST_SPLIT = 0.8
N_ESTIMATORS = 200
RANDOM_STATE = 42

# ─── Backtesting Settings ──────────────────────────────────────
INITIAL_CAPITAL = 10000.0
COMMISSION_PCT = 0.001
SLIPPAGE_PCT = 0.0005

# ─── Consensus Settings ────────────────────────────────────────
SCHOOLS = ["technical", "statistical", "ml_prediction", "momentum", "volume"]
CONFIDENCE_THRESHOLD = 0.6

# ─── Dashboard Settings ────────────────────────────────────────
DASHBOARD_TITLE = "TradingView Data Analyzer Pro"
DASHBOARD_ICON = "📊"
AUTO_REFRESH_INTERVAL = 300
CACHE_TTL = 300
REFRESH_PRESETS = [15, 30, 60, 120]

# ─── Multi-Timeframe Analysis ──────────────────────────────────
MTF_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1H", "4H", "1D"]
MTF_WEIGHTS = {"1m": 1, "5m": 1, "15m": 1, "30m": 1, "1H": 2, "4H": 3, "1D": 3}
YF_CACHE_TTL = 20.0

# ─── Trade Setup Engine ────────────────────────────────────────
SL_ATR_MULT = 1.5
RR_TARGET = 2.0
RR_TARGET_2 = 3.0
CHART_VIEW_BARS = 150

# ─── Partial Exit Strategy ──────────────────────────────────────
R_LEVELS = [1, 2, 3, 4, 5]
PARTIAL_TP = {1: 0.25, 2: 0.25, 3: 0.30, 4: 0.10, 5: 0.10}
PARTIAL_SL = {0.5: 0.30, 1.0: 0.40, 1.5: 0.30}
TRAILING_STOP_ACTIVATE = 1
TRAILING_STOP_OFFSET = 0.5

# ─── Daily Capital Management ──────────────────────────────────
DEFAULT_DAILY_CAPITAL = 1000.0
MAX_RISK_PER_TRADE_PCT = 2.0
MAX_DAILY_LOSS_PCT = 5.0
MAX_DAILY_TRADES = 10
POSITION_SIZE_METHOD = "fixed_risk"

# ─── Fibonacci / S/R / Trendline ───────────────────────────────
FIB_LOOKBACK = 100
FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
FIB_EXTENSIONS = [1.272, 1.618, 2.0]
SR_MIN_TOUCHES = 2
SR_TOLERANCE = 0.002
TRENDLINE_MIN_POINTS = 3
CONFLUENCE_TOLERANCE = 0.003

# ─── Pattern Matching ──────────────────────────────────────────
PATTERN_SIMILARITY_THRESHOLD = 0.75
PATTERN_MAX_RESULTS = 10
PATTERN_MIN_OCCURRENCES = 5
CHART_DATA_BARS = 50

# ─── Database ──────────────────────────────────────────────────
import pathlib as _pl
DB_PATH = str(_pl.Path(__file__).parent / "data" / "trades.db")
DAILY_ARCHIVE_DIR = str(_pl.Path(__file__).parent / "data" / "daily_archive")
OHLCV_CACHE_PATH = str(_pl.Path(__file__).parent / "data" / "cache" / "ohlcv.db")

# ─── Watchlist — 100 Popular Symbols ───────────────────────────
WATCHLIST = [
    # ═══ PRIORITY — User's core symbols (default for bots) ═══
    {"tv": "OANDA:XAUUSD",    "yf": "GC=F",      "name": "Gold",          "icon": "🥇", "cat": "priority"},
    {"tv": "NYMEX:CL1!",      "yf": "CL=F",      "name": "USOIL",         "icon": "🛢", "cat": "priority"},
    {"tv": "BINANCE:BTCUSDT", "yf": "BTC-USD",   "name": "Bitcoin",       "icon": "₿", "cat": "priority"},
    {"tv": "BINANCE:ETHUSDT", "yf": "ETH-USD",   "name": "Ethereum",      "icon": "Ξ", "cat": "priority"},
    {"tv": "TVC:DJI",         "yf": "^DJI",      "name": "US30",          "icon": "D", "cat": "priority"},
    {"tv": "FX:GBPUSD",       "yf": "GBPUSD=X",  "name": "GBP/USD",       "icon": "£", "cat": "priority"},
    {"tv": "FX:EURUSD",       "yf": "EURUSD=X",  "name": "EUR/USD",       "icon": "€", "cat": "priority"},
    {"tv": "FX:USDJPY",       "yf": "USDJPY=X",  "name": "USD/JPY",       "icon": "¥", "cat": "priority"},
    {"tv": "TVC:DXY",         "yf": "DX-Y.NYB",  "name": "DXY",           "icon": "$", "cat": "priority"},
    {"tv": "TVC:JPY",         "yf": "JPY=X",     "name": "JPY Index",     "icon": "¥", "cat": "priority"},
    {"tv": "TVC:US10Y",       "yf": "^TNX",      "name": "Lãi suất US 10Y","icon": "📈", "cat": "priority"},

    # ═══ METALS (8) ═══
    {"tv": "OANDA:XAUUSD",    "yf": "GC=F",      "name": "Gold",          "icon": "🥇", "cat": "metal"},
    {"tv": "OANDA:XAGUSD",    "yf": "SI=F",      "name": "Silver",        "icon": "🥈", "cat": "metal"},
    {"tv": "OANDA:XAUUSDT",   "yf": "GC=F",      "name": "Gold (Spot)",   "icon": "Au", "cat": "metal"},
    {"tv": "COMEX:GC1!",      "yf": "GC=F",      "name": "Gold Futures",  "icon": "Au", "cat": "metal"},
    {"tv": "COMEX:SI1!",      "yf": "SI=F",      "name": "Silver Futures","icon": "Ag", "cat": "metal"},
    {"tv": "OANDA:XPTUSD",    "yf": "PL=F",      "name": "Platinum",      "icon": "Pt", "cat": "metal"},
    {"tv": "OANDA:XPDUSD",    "yf": "PA=F",      "name": "Palladium",     "icon": "Pd", "cat": "metal"},
    {"tv": "OANDA:XCUUSD",    "yf": "HG=F",      "name": "Copper",        "icon": "Cu", "cat": "metal"},

    # ═══ CRYPTO (20) ═══
    {"tv": "BINANCE:BTCUSDT",  "yf": "BTC-USD",   "name": "Bitcoin",       "icon": "₿", "cat": "crypto"},
    {"tv": "BINANCE:ETHUSDT",  "yf": "ETH-USD",   "name": "Ethereum",      "icon": "Ξ", "cat": "crypto"},
    {"tv": "BINANCE:SOLUSDT",  "yf": "SOL-USD",   "name": "Solana",        "icon": "S", "cat": "crypto"},
    {"tv": "BINANCE:BNBUSDT",  "yf": "BNB-USD",   "name": "BNB",           "icon": "B", "cat": "crypto"},
    {"tv": "BINANCE:XRPUSDT",  "yf": "XRP-USD",   "name": "XRP",           "icon": "X", "cat": "crypto"},
    {"tv": "BINANCE:ADAUSDT",  "yf": "ADA-USD",   "name": "Cardano",       "icon": "A", "cat": "crypto"},
    {"tv": "BINANCE:DOGEUSDT", "yf": "DOGE-USD",  "name": "Dogecoin",      "icon": "D", "cat": "crypto"},
    {"tv": "BINANCE:DOTUSDT",  "yf": "DOT-USD",   "name": "Polkadot",      "icon": "P", "cat": "crypto"},
    {"tv": "BINANCE:AVAXUSDT", "yf": "AVAX-USD",  "name": "Avalanche",     "icon": "A", "cat": "crypto"},
    {"tv": "BINANCE:LINKUSDT", "yf": "LINK-USD",  "name": "Chainlink",     "icon": "L", "cat": "crypto"},
    {"tv": "BINANCE:MATICUSDT","yf": "MATIC-USD", "name": "Polygon",       "icon": "M", "cat": "crypto"},
    {"tv": "BINANCE:ATOMUSDT", "yf": "ATOM-USD",  "name": "Cosmos",        "icon": "C", "cat": "crypto"},
    {"tv": "BINANCE:UNIUSDT",  "yf": "UNI-USD",   "name": "Uniswap",       "icon": "U", "cat": "crypto"},
    {"tv": "BINANCE:LTCUSDT",  "yf": "LTC-USD",   "name": "Litecoin",      "icon": "L", "cat": "crypto"},
    {"tv": "BINANCE:NEARUSDT", "yf": "NEAR-USD",  "name": "NEAR",          "icon": "N", "cat": "crypto"},
    {"tv": "BINANCE:APTUSDT",  "yf": "APT-USD",   "name": "Aptos",         "icon": "A", "cat": "crypto"},
    {"tv": "BINANCE:OPUSDT",   "yf": "OP-USD",    "name": "Optimism",      "icon": "O", "cat": "crypto"},
    {"tv": "BINANCE:ARBUSDT",  "yf": "ARB-USD",   "name": "Arbitrum",      "icon": "A", "cat": "crypto"},
    {"tv": "BINANCE:FILUSDT",  "yf": "FIL-USD",   "name": "Filecoin",      "icon": "F", "cat": "crypto"},
    {"tv": "BINANCE:INJUSDT",  "yf": "INJ-USD",   "name": "Injective",     "icon": "I", "cat": "crypto"},

    # ═══ FOREX (14) ═══
    {"tv": "FX:EURUSD",   "yf": "EURUSD=X",  "name": "EUR/USD",    "icon": "€", "cat": "forex"},
    {"tv": "FX:GBPUSD",   "yf": "GBPUSD=X",  "name": "GBP/USD",    "icon": "£", "cat": "forex"},
    {"tv": "FX:USDJPY",   "yf": "USDJPY=X",  "name": "USD/JPY",    "icon": "¥", "cat": "forex"},
    {"tv": "FX:USDCHF",   "yf": "USDCHF=X",  "name": "USD/CHF",    "icon": "Fr", "cat": "forex"},
    {"tv": "FX:AUDUSD",   "yf": "AUDUSD=X",  "name": "AUD/USD",    "icon": "A$", "cat": "forex"},
    {"tv": "FX:USDCAD",   "yf": "USDCAD=X",  "name": "USD/CAD",    "icon": "C$", "cat": "forex"},
    {"tv": "FX:NZDUSD",   "yf": "NZDUSD=X",  "name": "NZD/USD",    "icon": "N$", "cat": "forex"},
    {"tv": "FX:EURGBP",   "yf": "EURGBP=X",  "name": "EUR/GBP",    "icon": "€£", "cat": "forex"},
    {"tv": "FX:EURJPY",   "yf": "EURJPY=X",  "name": "EUR/JPY",    "icon": "€¥", "cat": "forex"},
    {"tv": "FX:GBPJPY",   "yf": "GBPJPY=X",  "name": "GBP/JPY",    "icon": "£¥", "cat": "forex"},
    {"tv": "FX:EURAUD",   "yf": "EURAUD=X",  "name": "EUR/AUD",    "icon": "€A", "cat": "forex"},
    {"tv": "FX:USDTRY",   "yf": "USDTRY=X",  "name": "USD/TRY",    "icon": "₺", "cat": "forex"},
    {"tv": "FX:USDZAR",   "yf": "USDZAR=X",  "name": "USD/ZAR",    "icon": "R", "cat": "forex"},
    {"tv": "FX:USDMXN",   "yf": "USDMXN=X",  "name": "USD/MXN",    "icon": "M$", "cat": "forex"},

    # ═══ ENERGY (6) ═══
    {"tv": "NYMEX:CL1!",   "yf": "CL=F",      "name": "Crude Oil",    "icon": "🛢", "cat": "energy"},
    {"tv": "NYMEX:NG1!",   "yf": "NG=F",      "name": "Natural Gas",  "icon": "🔥", "cat": "energy"},
    {"tv": "NYMEX:HO1!",   "yf": "HO=F",      "name": "Heating Oil",  "icon": "⛽", "cat": "energy"},
    {"tv": "NYMEX:RB1!",   "yf": "RB=F",      "name": "RBOB Gas",     "icon": "⛽", "cat": "energy"},
    {"tv": "ICE:BZ1!",     "yf": "BZ=F",      "name": "Brent Crude",  "icon": "🛢", "cat": "energy"},
    {"tv": "ICE:GAS1!",    "yf": "NG=F",      "name": "Gas Futures",  "icon": "🔥", "cat": "energy"},

    # ═══ INDICES (14) ═══
    {"tv": "TVC:NDX",      "yf": "^NDX",      "name": "Nasdaq 100",   "icon": "N", "cat": "index"},
    {"tv": "TVC:DJI",      "yf": "^DJI",      "name": "Dow Jones",    "icon": "D", "cat": "index"},
    {"tv": "TVC:SPX",      "yf": "^GSPC",     "name": "S&P 500",      "icon": "S", "cat": "index"},
    {"tv": "TVC:IXIC",     "yf": "^IXIC",     "name": "Nasdaq Comp",  "icon": "N", "cat": "index"},
    {"tv": "TVC:NKY",      "yf": "^N225",     "name": "Nikkei 225",   "icon": "J", "cat": "index"},
    {"tv": "TVC:HSI",      "yf": "^HSI",      "name": "Hang Seng",    "icon": "H", "cat": "index"},
    {"tv": "TVC:FTSE",     "yf": "^FTSE",     "name": "FTSE 100",     "icon": "F", "cat": "index"},
    {"tv": "TVC:GDAXI",    "yf": "^GDAXI",    "name": "DAX 40",       "icon": "D", "cat": "index"},
    {"tv": "TVC:CAC40",    "yf": "^FCHI",     "name": "CAC 40",       "icon": "C", "cat": "index"},
    {"tv": "TVC:STOXX50E", "yf": "^STOXX50E", "name": "Euro Stoxx",   "icon": "E", "cat": "index"},
    {"tv": "BSE:SENSEX",   "yf": "^BSESN",    "name": "BSE Sensex",   "icon": "I", "cat": "index"},
    {"tv": "NSE:NIFTY",    "yf": "^NSEI",     "name": "Nifty 50",     "icon": "I", "cat": "index"},
    {"tv": "TVC:ASX200",   "yf": "^AXJO",     "name": "ASX 200",      "icon": "A", "cat": "index"},
    {"tv": "TVC:KOSPI",    "yf": "^KS11",     "name": "KOSPI",        "icon": "K", "cat": "index"},

    # ═══ US STOCKS (50) ═══
    {"tv": "NASDAQ:AAPL",  "yf": "AAPL",   "name": "Apple",       "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:MSFT",  "yf": "MSFT",   "name": "Microsoft",   "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:GOOGL", "yf": "GOOGL",  "name": "Alphabet",    "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:AMZN",  "yf": "AMZN",   "name": "Amazon",      "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:META",  "yf": "META",   "name": "Meta",        "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:TSLA",  "yf": "TSLA",   "name": "Tesla",       "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:NVDA",  "yf": "NVDA",   "name": "NVIDIA",      "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:AMD",   "yf": "AMD",    "name": "AMD",         "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:INTC",  "yf": "INTC",   "name": "Intel",       "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:NFLX",  "yf": "NFLX",   "name": "Netflix",     "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:COIN",  "yf": "COIN",   "name": "Coinbase",    "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:CRM",   "yf": "CRM",    "name": "Salesforce",  "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:ADBE",  "yf": "ADBE",   "name": "Adobe",       "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:PYPL",  "yf": "PYPL",   "name": "PayPal",      "icon": "", "cat": "stock"},
    {"tv": "NYSE:XYZ",    "yf": "XYZ",    "name": "Block",       "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:UBER",  "yf": "UBER",   "name": "Uber",        "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:ABNB",  "yf": "ABNB",   "name": "Airbnb",      "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:SNOW",  "yf": "SNOW",   "name": "Snowflake",   "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:PLTR",  "yf": "PLTR",   "name": "Palantir",    "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:RIVN",  "yf": "RIVN",   "name": "Rivian",      "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:LCID",  "yf": "LCID",   "name": "Lucid",       "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:MARA",  "yf": "MARA",   "name": "Marathon",    "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:RIOT",  "yf": "RIOT",   "name": "Riot",        "icon": "", "cat": "stock"},
    {"tv": "NASDAQ:HOOD",  "yf": "HOOD",   "name": "Robinhood",   "icon": "", "cat": "stock"},
    {"tv": "NYSE:JPM",     "yf": "JPM",    "name": "JPMorgan",    "icon": "", "cat": "stock"},
    {"tv": "NYSE:GS",      "yf": "GS",     "name": "Goldman",     "icon": "", "cat": "stock"},
    {"tv": "NYSE:BAC",     "yf": "BAC",    "name": "BofA",        "icon": "", "cat": "stock"},
    {"tv": "NYSE:V",       "yf": "V",      "name": "Visa",        "icon": "", "cat": "stock"},
    {"tv": "NYSE:MA",      "yf": "MA",     "name": "Mastercard",  "icon": "", "cat": "stock"},
    {"tv": "NYSE:JNJ",     "yf": "JNJ",    "name": "J&J",         "icon": "", "cat": "stock"},
    {"tv": "NYSE:UNH",     "yf": "UNH",    "name": "UnitedHealth","icon": "", "cat": "stock"},
    {"tv": "NYSE:WMT",     "yf": "WMT",    "name": "Walmart",     "icon": "", "cat": "stock"},
    {"tv": "NYSE:DIS",     "yf": "DIS",    "name": "Disney",      "icon": "", "cat": "stock"},
    {"tv": "NYSE:BA",      "yf": "BA",     "name": "Boeing",      "icon": "", "cat": "stock"},
    {"tv": "NYSE:CAT",     "yf": "CAT",    "name": "Caterpillar", "icon": "", "cat": "stock"},
    {"tv": "NYSE:CVX",     "yf": "CVX",    "name": "Chevron",     "icon": "", "cat": "stock"},
    {"tv": "NYSE:XOM",     "yf": "XOM",    "name": "ExxonMobil",  "icon": "", "cat": "stock"},
    {"tv": "NYSE:COP",     "yf": "COP",    "name": "ConocoPhillips","icon": "", "cat": "stock"},
    {"tv": "NYSE:KO",      "yf": "KO",     "name": "Coca-Cola",   "icon": "", "cat": "stock"},
    {"tv": "NYSE:MCD",     "yf": "MCD",    "name": "McDonald's",  "icon": "", "cat": "stock"},
    {"tv": "NYSE:NKE",     "yf": "NKE",    "name": "Nike",        "icon": "", "cat": "stock"},
    {"tv": "NYSE:HD",      "yf": "HD",     "name": "Home Depot",  "icon": "", "cat": "stock"},
    {"tv": "NYSE:TGT",     "yf": "TGT",    "name": "Target",      "icon": "", "cat": "stock"},
    {"tv": "NYSE:COST",    "yf": "COST",   "name": "Costco",      "icon": "", "cat": "stock"},
    {"tv": "NYSE:T",       "yf": "T",      "name": "AT&T",        "icon": "", "cat": "stock"},
    {"tv": "NYSE:VZ",      "yf": "VZ",     "name": "Verizon",     "icon": "", "cat": "stock"},
    {"tv": "NYSE:CMCSA",   "yf": "CMCSA",  "name": "Comcast",     "icon": "", "cat": "stock"},
    {"tv": "NYSE:SNAP",    "yf": "SNAP",   "name": "Snap",        "icon": "", "cat": "stock"},
    {"tv": "NYSE:PINS",    "yf": "PINS",   "name": "Pinterest",   "icon": "", "cat": "stock"},
    {"tv": "NYSE:RBLX",    "yf": "RBLX",   "name": "Roblox",      "icon": "", "cat": "stock"},

    # ═══ VN30 — Top 30 HOSE ═══
    {"tv": "HOSE:VNM",    "yf": "VNM.VN",    "name": "Vinamilk",        "icon": "🇻🇳", "cat": "vnstock"},
    {"tv": "HOSE:VIC",    "yf": "VIC.VN",    "name": "Vingroup",        "icon": "🇻🇳", "cat": "vnstock"},
    {"tv": "HOSE:VHM",    "yf": "VHM.VN",    "name": "Vinhomes",        "icon": "🇻🇳", "cat": "vnstock"},
    {"tv": "HOSE:VRE",    "yf": "VRE.VN",    "name": "Vincom Retail",   "icon": "🇻🇳", "cat": "vnstock"},
    {"tv": "HOSE:VCB",    "yf": "VCB.VN",    "name": "Vietcombank",     "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:BID",    "yf": "BID.VN",    "name": "BIDV",            "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:CTG",    "yf": "CTG.VN",    "name": "VietinBank",      "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:TCB",    "yf": "TCB.VN",    "name": "Techcombank",     "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:MBB",    "yf": "MBB.VN",    "name": "MB Bank",         "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:ACB",    "yf": "ACB.VN",    "name": "ACB",             "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:VPB",    "yf": "VPB.VN",    "name": "VPBank",          "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:STB",    "yf": "STB.VN",    "name": "Sacombank",       "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:HDB",    "yf": "HDB.VN",    "name": "HDBank",          "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:TPB",    "yf": "TPB.VN",    "name": "TPBank",          "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:LPB",    "yf": "LPB.VN",    "name": "LienVietPostBank","icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:MSB",    "yf": "MSB.VN",    "name": "MSB",             "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:VIB",    "yf": "VIB.VN",    "name": "VIB",             "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:OCB",    "yf": "OCB.VN",    "name": "OCB",             "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:SHB",    "yf": "SHB.VN",    "name": "SHB",             "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:EIB",    "yf": "EIB.VN",    "name": "Eximbank",        "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:SEB",    "yf": "SEB.VN",    "name": "SeABank",         "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:PVB",    "yf": "PVB.VN",    "name": "PVcomBank",       "icon": "🏦", "cat": "vnstock"},
    {"tv": "HOSE:BAB",    "yf": "BAB.VN",    "name": "BacABank",        "icon": "🏦", "cat": "vnstock"},

    # ═══ VN30 — Large Cap non-bank ═══
    {"tv": "HOSE:FPT",    "yf": "FPT.VN",    "name": "FPT Corp",        "icon": "💻", "cat": "vnstock"},
    {"tv": "HOSE:MWG",    "yf": "MWG.VN",    "name": "Thế Giới Di Động","icon": "📱", "cat": "vnstock"},
    {"tv": "HOSE:VJC",    "yf": "VJC.VN",    "name": "VietJet Air",     "icon": "✈️", "cat": "vnstock"},
    {"tv": "HOSE:HPG",    "yf": "HPG.VN",    "name": "Hòa Phát",        "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:VGC",    "yf": "VGC.VN",    "name": "Viglacera",       "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:GAS",    "yf": "GAS.VN",    "name": "PV Gas",          "icon": "⛽", "cat": "vnstock"},
    {"tv": "HOSE:PLX",    "yf": "PLX.VN",    "name": "Petrolimex",      "icon": "⛽", "cat": "vnstock"},
    {"tv": "HOSE:POW",    "yf": "POW.VN",    "name": "PV Power",        "icon": "⚡", "cat": "vnstock"},
    {"tv": "HOSE:NT2",    "yf": "NT2.VN",    "name": "Nhơn Trạch 2",    "icon": "⚡", "cat": "vnstock"},
    {"tv": "HOSE:VSH",    "yf": "VSH.VN",    "name": "VinhSon",         "icon": "💧", "cat": "vnstock"},
    {"tv": "HOSE:SAB",    "yf": "SAB.VN",    "name": "Sabeco",          "icon": "🍺", "cat": "vnstock"},
    {"tv": "HOSE:MSN",    "yf": "MSN.VN",    "name": "Masan Group",     "icon": "🛒", "cat": "vnstock"},
    {"tv": "HOSE:PNJ",    "yf": "PNJ.VN",    "name": "PNJ",             "icon": "💎", "cat": "vnstock"},
    {"tv": "HOSE:DGW",    "yf": "DGW.VN",    "name": "Digiworld",       "icon": "📱", "cat": "vnstock"},
    {"tv": "HOSE:SSI",    "yf": "SSI.VN",    "name": "SSI Securities",  "icon": "📈", "cat": "vnstock"},
    {"tv": "HOSE:HCM",    "yf": "HCM.VN",    "name": "HSC",             "icon": "📈", "cat": "vnstock"},
    {"tv": "HOSE:VND",    "yf": "VND.VN",    "name": "VNDirect",        "icon": "📈", "cat": "vnstock"},
    {"tv": "HOSE:MIG",    "yf": "MIG.VN",    "name": "MIC",             "icon": "🛡", "cat": "vnstock"},
    {"tv": "HOSE:BMI",    "yf": "BMI.VN",    "name": "BaoMinh",         "icon": "🛡", "cat": "vnstock"},
    {"tv": "HOSE:PVI",    "yf": "PVI.VN",    "name": "PVI",             "icon": "🛡", "cat": "vnstock"},
    {"tv": "HOSE:DBD",    "yf": "DBD.VN",    "name": "Dabaco",          "icon": "🌾", "cat": "vnstock"},
    {"tv": "HOSE:VSA",    "yf": "VSA.VN",    "name": "VietStarcap",     "icon": "🇻🇳", "cat": "vnstock"},

    # ═══ VN — Mid/Small Cap popular ═══
    {"tv": "HOSE:SCR",    "yf": "SCR.VN",    "name": "SCIC",            "icon": "🇻🇳", "cat": "vnstock"},
    {"tv": "HOSE:VOS",    "yf": "VOS.VN",    "name": "VOSCO",           "icon": "🚢", "cat": "vnstock"},
    {"tv": "HOSE:GMD",    "yf": "GMD.VN",    "name": "Geleximco",       "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:KBC",    "yf": "KBC.VN",    "name": "Kinh Doanh",      "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:KDH",    "yf": "KDH.VN",    "name": "Kent Hospital",   "icon": "🏥", "cat": "vnstock"},
    {"tv": "HOSE:NLG",    "yf": "NLG.VN",    "name": "Nam Long",        "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:QCG",    "yf": "QCG.VN",    "name": "Quoc Cuong",      "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:TDH",    "yf": "TDH.VN",    "name": "Thuan Duc",       "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:NTL",    "yf": "NTL.VN",    "name": " Viet Urban",     "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:PTB",    "yf": "PTB.VN",    "name": "Phu Thai",        "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:PNVD",   "yf": "PNVD.VN",   "name": "Phu Nhuan",       "icon": "💎", "cat": "vnstock"},
    {"tv": "HOSE:AAA",    "yf": "AAA.VN",    "name": "An Phat",         "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:ANV",    "yf": "ANV.VN",    "name": "AnViet",          "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:BWE",    "yf": "BWE.VN",    "name": "BinhWasser",      "icon": "💧", "cat": "vnstock"},
    {"tv": "HOSE:CTD",    "yf": "CTD.VN",    "name": "Coteccons",       "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:CII",    "yf": "CII.VN",    "name": "CII",             "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:DXG",    "yf": "DXG.VN",    "name": "Dat Xanh",        "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:EVF",    "yf": "EVF.VN",    "name": "EVN Finance",     "icon": "📈", "cat": "vnstock"},
    {"tv": "HOSE:FCN",    "yf": "FCN.VN",    "name": "Fecon",           "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:FLC",    "yf": "FLC.VN",    "name": "FLC Group",       "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:GEX",    "yf": "GEX.VN",    "name": "Gelex",           "icon": "⚡", "cat": "vnstock"},
    {"tv": "HOSE:GVR",    "yf": "GVR.VN",    "name": "Casumina",        "icon": "🛞", "cat": "vnstock"},
    {"tv": "HOSE:HAV",    "yf": "HAV.VN",    "name": "Hai Vuong",       "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:HT1",    "yf": "HT1.VN",    "name": "Hoa Cat",         "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:HTG",    "yf": "HTG.VN",    "name": "Ha Thang",        "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:ITC",    "yf": "ITC.VN",    "name": "Intresco",        "icon": "📈", "cat": "vnstock"},
    {"tv": "HOSE:KSC",    "yf": "KSC.VN",    "name": "Khai Sang",       "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:LDG",    "yf": "LDG.VN",    "name": "Ladeco",          "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:LM8",    "yf": "LM8.VN",    "name": "Lam Thao",        "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:LSS",    "yf": "LSS.VN",    "name": "Luc Lam",         "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:MBG",    "yf": "MBG.VN",    "name": "MB Grand",        "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:OIL",    "yf": "OIL.VN",    "name": "Petrolimex Gas",  "icon": "⛽", "cat": "vnstock"},
    {"tv": "HOSE:PGC",    "yf": "PGC.VN",    "name": "Petrolimex Gas",  "icon": "⛽", "cat": "vnstock"},
    {"tv": "HOSE:PHR",    "yf": "PHR.VN",    "name": "Phuoc Hoa",       "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:PPC",    "yf": "PPC.VN",    "name": "Phu My 2",        "icon": "⚡", "cat": "vnstock"},
    {"tv": "HOSE:PSH",    "yf": "PSH.VN",    "name": "Phu Son",         "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:PTG",    "yf": "PTG.VN",    "name": "Phuong Thao",     "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:QNS",    "yf": "QNS.VN",    "name": "Quang Ngai",      "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:REE",    "yf": "REE.VN",    "name": "Ree Corp",        "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:SBS",    "yf": "SBS.VN",    "name": "Sacombank Sec",   "icon": "📈", "cat": "vnstock"},
    {"tv": "HOSE:SJC",    "yf": "SJC.VN",    "name": "SJC Gold",        "icon": "🥇", "cat": "vnstock"},
    {"tv": "HOSE:SLV",    "yf": "SLV.VN",    "name": "Sao Vang",        "icon": "🥇", "cat": "vnstock"},
    {"tv": "HOSE:SON",    "yf": "SON.VN",    "name": "Sonadezi",        "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:SVI",    "yf": "SVI.VN",    "name": "Savico",          "icon": "🚗", "cat": "vnstock"},
    {"tv": "HOSE:SZC",    "yf": "SZC.VN",    "name": "SZC Holdings",    "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:TAG",    "yf": "TAG.VN",    "name": "Tasco",           "icon": "🚗", "cat": "vnstock"},
    {"tv": "HOSE:TCH",    "yf": "TCH.VN",    "name": "Hung Thinh",      "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:TLG",    "yf": "TLG.VN",    "name": "TienLenh",        "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:TRA",    "yf": "TRA.VN",    "name": "Traphaco",        "icon": "💊", "cat": "vnstock"},
    {"tv": "HOSE:TS4",    "yf": "TS4.VN",    "name": "Tasco 4",         "icon": "🚗", "cat": "vnstock"},
    {"tv": "HOSE:TTF",    "yf": "TTF.VN",    "name": "Thien Thuat",     "icon": "🏭", "cat": "vnstock"},
    {"tv": "HOSE:VGT",    "yf": "VGT.VN",    "name": "Viet Garment",    "icon": "🧵", "cat": "vnstock"},
    {"tv": "HOSE:VMD",    "yf": "VMD.VN",    "name": "Vimedimex",       "icon": "💊", "cat": "vnstock"},
    {"tv": "HOSE:VOS",    "yf": "VOS.VN",    "name": "VOSCO",           "icon": "🚢", "cat": "vnstock"},
    {"tv": "HOSE:VTC",    "yf": "VTC.VN",    "name": "VTC Digital",     "icon": "📺", "cat": "vnstock"},
    {"tv": "HOSE:YEG",    "yf": "YEG.VN",    "name": "YellowBlue",      "icon": "🏗", "cat": "vnstock"},
    {"tv": "HOSE:ZCM",    "yf": "ZCM.VN",    "name": "ZCM Corp",        "icon": "🏭", "cat": "vnstock"},

    # ═══ HNX — Top HNX ═══
    {"tv": "HNX:SHB",    "yf": "SHB.HM",    "name": "SHB (HNX)",       "icon": "🏦", "cat": "vnstock"},
    {"tv": "HNX:PVS",    "yf": "PVS.HM",    "name": "PV Drilling",     "icon": "🛢", "cat": "vnstock"},
    {"tv": "HNX:PVD",    "yf": "PVD.HM",    "name": "PV Drilling",     "icon": "🛢", "cat": "vnstock"},
    {"tv": "HNX:PVB",    "yf": "PVB.HM",    "name": "PV Coating",      "icon": "🛢", "cat": "vnstock"},
    {"tv": "HNX:BVS",    "yf": "BVS.HM",    "name": "BaoViet Sec",     "icon": "📈", "cat": "vnstock"},
    {"tv": "HNX:CEO",    "yf": "CEO.HM",    "name": "CEO Group",       "icon": "🏗", "cat": "vnstock"},
    {"tv": "HNX:IDC",    "yf": "IDC.HM",    "name": "IDICO",           "icon": "🏗", "cat": "vnstock"},
    {"tv": "HNX:SHS",    "yf": "SHS.HM",    "name": "SHS",             "icon": "📈", "cat": "vnstock"},
    {"tv": "HNX:LAS",    "yf": "LAS.HM",    "name": "La San",          "icon": "💊", "cat": "vnstock"},
    {"tv": "HNX:NAF",    "yf": "NAF.HM",    "name": "Nafa",            "icon": "🏭", "cat": "vnstock"},
    {"tv": "HNX:ARM",    "yf": "ARM.HM",    "name": "ARM",             "icon": "🏭", "cat": "vnstock"},
    {"tv": "HNX:DDG",    "yf": "DDG.HM",    "name": "DDG",             "icon": "🏭", "cat": "vnstock"},
    {"tv": "HNX:DPM",    "yf": "DPM.HM",    "name": "Duc Phu My",      "icon": "🏭", "cat": "vnstock"},
    {"tv": "HNX:HEV",    "yf": "HEV.HM",    "name": "Hung Vuong",      "icon": "🏭", "cat": "vnstock"},
    {"tv": "HNX:KLS",    "yf": "KLS.HM",    "name": "KLF",             "icon": "📈", "cat": "vnstock"},
    {"tv": "HNX:NCT",    "yf": "NCT.HM",    "name": "Nha Trang",       "icon": "🏖", "cat": "vnstock"},
    {"tv": "HNX:NTC",    "yf": "NTC.HM",    "name": "Nam Tan Uyen",    "icon": "🏭", "cat": "vnstock"},
    {"tv": "HNX:PAC",    "yf": "PAC.HM",    "name": "Phuoc An",        "icon": "🏭", "cat": "vnstock"},
    {"tv": "HNX:PET",    "yf": "PET.HM",    "name": "Petroland",       "icon": "🏗", "cat": "vnstock"},
    {"tv": "HNX:PLC",    "yf": "PLC.HM",    "name": "Phu Le",          "icon": "🏭", "cat": "vnstock"},
    {"tv": "HNX:S99",    "yf": "S99.HM",    "name": "S99 Corp",        "icon": "🏭", "cat": "vnstock"},
    {"tv": "HNX:SCS",    "yf": "SCS.HM",    "name": "SCS",             "icon": "🏭", "cat": "vnstock"},
    {"tv": "HNX:SD2",    "yf": "SD2.HM",    "name": "SD2",             "icon": "🏭", "cat": "vnstock"},
    {"tv": "HNX:SEC",    "yf": "SEC.HM",    "name": "SEC Corp",        "icon": "📈", "cat": "vnstock"},
    {"tv": "HNX:VNR",    "yf": "VNR.HM",    "name": "VNR",             "icon": "🛡", "cat": "vnstock"},
    {"tv": "HNX:WSS",    "yf": "WSS.HM",    "name": "WSS",             "icon": "📈", "cat": "vnstock"},
    {"tv": "HNX:XMC",    "yf": "XMC.HM",    "name": "Xuan Mai",        "icon": "🏗", "cat": "vnstock"},

    # ═══ UPCOM — Popular UPCOM ═══
    {"tv": "UPCOM:SAB",   "yf": "SAB.VN",    "name": "Sabeco (UPCOM)",  "icon": "🍺", "cat": "vnstock"},
]

# ─── File Paths ────────────────────────────────────────────────
import pathlib
BASE_DIR = pathlib.Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
