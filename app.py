# -*- coding: utf-8 -*-
"""
TradingView Analyzer Pro — Professional Trading Terminal
Complete rewrite: rich charts, visual gauges, professional layout.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

from config import (
    DASHBOARD_TITLE, DASHBOARD_ICON, DEFAULT_SYMBOLS,
    DEFAULT_INTERVAL, DEFAULT_BARS_COUNT, INTERVALS,
    REFRESH_PRESETS, WATCHLIST,
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BB_PERIOD, BB_STD, EMA_SHORT, EMA_LONG,
    ADX_PERIOD, ATR_PERIOD, INITIAL_CAPITAL, COMMISSION_PCT,
    MTF_TIMEFRAMES,
)
from tv_scraper_pro import TVScraperPro
from core.indicators import TechnicalAnalyzer
from core.statistical import StatisticalAnalyzer
from core.predictor import MLPredictor
from core.backtester import BacktestEngine
from core.consensus import ConsensusEngine
from core.multi_timeframe import MTFAnalyzer
from core.trade_setup import compute_setup
from core.analysis_plans import build_action_plan, build_per_tf_plans
from core.watchlist import fetch_watchlist, compute_market_breadth
from core.free_apis import fetch_all_market_data
from core.database import TradeDatabase
from core.capital import DailyCapital
from core.pattern_matcher import PatternMatcher

# ═══════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════
st.set_page_config(page_title=DASHBOARD_TITLE, page_icon=DASHBOARD_ICON, layout="wide", initial_sidebar_state="expanded")

# ═══════════════════════════════════════════════════════════════
#  PROFESSIONAL CSS
# ═══════════════════════════════════════════════════════════════
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
:root{--bg:#0a0e17;--panel:#111827;--panel2:#1a2035;--border:#1f2a40;--border2:#2a3650;--text:#e2e8f0;--muted:#64748b;--dim:#475569;--accent:#3b82f6;--up:#10b981;--down:#ef4444;--amber:#f59e0b;--purple:#a855f7;--teal:#14b8a6;--cyan:#06b6d4}
html,body,[data-testid="stAppViewContainer"],[data-testid="stApp"]{background:var(--bg)!important;color:var(--text);font-family:'Inter','Segoe UI',system-ui,sans-serif}
.block-container{padding:0!important;max-width:100%!important}
h1,h2,h3,h4,h5{color:var(--text)!important;font-weight:600;margin:0!important}
p,li,.stMarkdown{color:var(--text);font-size:14px;margin:0!important}
code,pre{font-family:'JetBrains Mono','Cascadia Code',monospace}

/* Sidebar */
section[data-testid="stSidebar"]{background:var(--panel)!important;border-right:1px solid var(--border)!important;min-width:280px}
section[data-testid="stSidebar"]>div{padding:0.5rem 0.8rem}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding-top:0.3rem}
section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] span,section[data-testid="stSidebar"] small{color:var(--text)}
section[data-testid="stSidebar"] hr{margin:0.5rem 0;border-color:var(--border)}
.sb-title{font-size:10px;font-weight:700;letter-spacing:1.5px;color:var(--muted);text-transform:uppercase;margin:4px 0 6px 0}

/* Compress */
.stColumn>div{gap:0!important}
div[data-baseweb="tab-panel"]{padding-top:0.3rem!important}
.stTabs [data-baseweb="tab-list"]{gap:0!important;margin-bottom:0!important}
.stTabs [data-baseweb="tab"]{padding:0.25rem 0.5rem!important;font-size:12px}
.stSelectbox,.stMultiSelect,.stTextInput,.stNumberInput,.stToggle,.stSlider,.stCheckbox,.stRadio,.stPills{margin-bottom:0!important}
div[data-testid="stExpander"]{margin-bottom:0!important}
div[data-testid="stExpander"] summary{padding:0.3rem 0!important}
.stAlert{margin-bottom:0!important;border-radius:6px!important}
hr{margin:0.2rem 0!important}

/* Widgets */
.stButton>button{border-radius:6px;border:1px solid var(--border2);background:var(--panel2);color:var(--text);font-weight:500;transition:all 0.15s}
.stButton>button:hover{border-color:var(--accent);color:#fff}
.stButton>button[kind="primary"]{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
.stButton>button[kind="primary"]:hover{background:#2563eb;border-color:#2563eb}
.stNumberInput input,.stTextInput input,.stSelectbox [data-baseweb="select"]{font-size:13px}
div[data-testid="stExpander"]{background:var(--panel);border:1px solid var(--border);border-radius:8px}
div[data-testid="stExpander"] summary{font-size:13px;color:var(--text)}
.stTabs [aria-selected="true"]{color:var(--accent);font-weight:600}
div[data-testid="stMetric"]{background:var(--panel)!important;border:1px solid var(--border)!important;border-radius:8px!important;padding:0.4rem 0.6rem!important}
div[data-testid="stMetric"] [data-testid="stMetricValue"]{font-family:'JetBrains Mono',monospace;font-size:1rem}
div[data-testid="stMetric"] [data-testid="stMetricLabel"]{font-size:0.72rem;color:var(--muted)}
div[data-testid="stDataFrame"]{border:1px solid var(--border)!important;border-radius:8px!important;overflow:hidden}
div[data-testid="stCaptionContainer"] p,.stCaption{color:var(--muted)}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--panel)}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
</style>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  COLORS
# ═══════════════════════════════════════════════════════════════
BG = "#0a0e17"; PANEL = "#111827"; PANEL2 = "#1a2035"; BORDER = "#1f2a40"
TEXT = "#e2e8f0"; MUTED = "#64748b"; DIM = "#475569"
ACCENT = "#3b82f6"; GREEN = "#10b981"; RED = "#ef4444"; AMBER = "#f59e0b"
PURPLE = "#a855f7"; TEAL = "#14b8a6"; CYAN = "#06b6d4"

# ═══════════════════════════════════════════════════════════════
#  SECTION TITLE (module header)
# ═══════════════════════════════════════════════════════════════
def sec_title(text: str, color: str = ACCENT) -> str:
    """Readable module header that sits clearly above its table/card."""
    return (f'<div style="font-size:13px;color:{color};font-weight:700;letter-spacing:1.2px;'
            f'margin:12px 0 6px;padding:5px 10px;background:{PANEL};'
            f'border-left:3px solid {color};border-radius:0 4px 4px 0">{text}</div>')

# ═══════════════════════════════════════════════════════════════
#  SESSION STATE
# ═══════════════════════════════════════════════════════════════
DEFAULTS = {
    "data": None, "signals": {}, "stats": {}, "prediction": {},
    "backtest": {}, "consensus": {}, "mtf": None, "setup": None,
    "tv_indicators": {}, "feature_importance": {},
    "activity_log": [], "last_refresh": None, "last_refresh_ts": None,
    "refresh_sec": 30, "watchlist_data": None, "alerts": [],
    "active_cat": "all", "market_data": None,
    "db": None, "daily_capital": None, "pattern_matcher": None,
    "trade_history": [], "similar_patterns": [], "pattern_stats": {},
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.db is None:
    st.session_state.db = TradeDatabase()
if st.session_state.daily_capital is None:
    st.session_state.daily_capital = DailyCapital()
if st.session_state.pattern_matcher is None:
    st.session_state.pattern_matcher = PatternMatcher(st.session_state.db)

dc = st.session_state.daily_capital
if dc.check_reset():
    st.toast("New day — capital reset")

def log(msg, icon="✅"):
    ts = time.strftime("%H:%M:%S")
    st.session_state.activity_log.insert(0, (ts, msg, icon))
    st.session_state.activity_log = st.session_state.activity_log[:50]

# ═══════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid {BORDER};margin-bottom:8px">
      <div style="width:32px;height:32px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;color:#fff">TV</div>
      <div><div style="font-size:14px;font-weight:700;color:{TEXT}">Analyzer Pro</div><div style="font-size:10px;color:{MUTED};letter-spacing:1px">TRADING TERMINAL</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sb-title">Symbol & Timeframe</div>', unsafe_allow_html=True)
    custom = st.text_input("Tìm mã", placeholder="VD: OANDA:XAUUSD", label_visibility="collapsed")
    symbol = custom if custom else st.selectbox("Mã", DEFAULT_SYMBOLS, index=1, label_visibility="collapsed")
    g1 = st.columns([3, 1])
    tv_intervals = list(INTERVALS.keys())
    if "cur_tf" not in st.session_state:
        st.session_state.cur_tf = "15m"
    if "khung_keygen" not in st.session_state:
        st.session_state.khung_keygen = 0
    next_tf = st.session_state.pop("khung_next", None)
    if next_tf:
        st.session_state.khung_keygen += 1
        st.session_state.cur_tf = next_tf
    interval = g1[0].selectbox("Khung", tv_intervals,
                               index=tv_intervals.index(st.session_state.cur_tf),
                               key=f"khung_sb_{st.session_state.khung_keygen}",
                               label_visibility="collapsed")
    st.session_state.cur_tf = interval
    bars_count = g1[1].number_input("Nến", 50, 500, DEFAULT_BARS_COUNT, 50)
    data_source = st.selectbox("Nguồn", ["TradingView + yfinance", "yfinance"])

    st.divider()
    st.markdown('<div class="sb-title">Watchlist</div>', unsafe_allow_html=True)
    CATS = [("all", "All"), ("crypto", "Crypto"), ("forex", "FX"), ("index", "Index"), ("commodity", "Comm"), ("stock", "Stock")]
    cat = st.pills("Danh mục", [v for _, v in CATS], default="All", key="cat_pills")
    st.session_state.active_cat = next((k for k, v in CATS if v == cat), "all")
    if st.session_state.watchlist_data is None or time.time() - getattr(st, '_wl_ts', 0) > 30:
        try:
            st.session_state.watchlist_data = fetch_watchlist()
            st._wl_ts = time.time()
        except:
            st.session_state.watchlist_data = []

    wl = [d for d in (st.session_state.watchlist_data or []) if st.session_state.active_cat == "all" or d.get("cat") == st.session_state.active_cat]
    if wl:
        st.markdown(f"""
        <div style="display:grid;grid-template-columns:1fr auto auto auto;gap:2px 8px;font-size:11px;font-family:'JetBrains Mono',monospace">
          <div style="color:{DIM};font-weight:600">SYMBOL</div><div style="color:{DIM};font-weight:600;text-align:right">PRICE</div><div style="color:{DIM};font-weight:600;text-align:right">CHG</div><div style="color:{DIM}">…</div>
        </div>
        """, unsafe_allow_html=True)
        for d in wl[:12]:
            price = f"{d['price']:,.2f}" if d.get("price") else "—"
            chg = d.get("change_pct", 0)
            chg_c = GREEN if chg >= 0 else RED
            arrow = "▲" if chg >= 0 else "▼"
            st.markdown(f"""
            <div style="display:grid;grid-template-columns:1fr auto auto auto;gap:2px 8px;font-size:12px;font-family:'JetBrains Mono',monospace;padding:1px 0">
              <span style="color:{TEXT}">{d.get('icon','')}{d.get('symbol','')}</span>
              <span style="color:{TEXT};text-align:right">{price}</span>
              <span style="color:{chg_c};text-align:right">{"+" if chg>=0 else ""}{chg:.2f}%</span>
              <span style="color:{chg_c}">{arrow}</span>
            </div>
            """, unsafe_allow_html=True)

    st.divider()
    st.markdown('<div class="sb-title">Indicators</div>', unsafe_allow_html=True)
    ic1, ic2 = st.columns(2)
    show_rsi = ic1.toggle("RSI", True); show_macd = ic2.toggle("MACD", True)
    show_bb = ic1.toggle("Bollinger", True); show_ma = ic2.toggle("SMA", True)
    show_volume = ic1.toggle("Volume", True); show_stoch = ic2.toggle("Stochastic", False)
    show_adx = ic1.toggle("ADX", False); show_ema = ic2.toggle("EMA", False)
    show_vwap = ic1.toggle("VWAP", False); show_ichi = ic2.toggle("Ichimoku", False)
    show_st = ic1.toggle("Supertrend", True); show_psar = ic2.toggle("PSAR", False)
    show_kc = ic1.toggle("Keltner", False); show_dc = ic2.toggle("Donchian", False)
    show_ema200 = ic1.toggle("EMA 200", False)

    st.divider()
    st.markdown('<div class="sb-title">Analysis</div>', unsafe_allow_html=True)
    mtf_timeframes = MTF_TIMEFRAMES
    st.caption(f"MTF phân tích toàn bộ {len(MTF_TIMEFRAMES)} khung: {', '.join(MTF_TIMEFRAMES)}")
    show_setup = st.toggle("Trade Plan", True)

    with st.expander("Advanced"):
        r1, r2 = st.columns(2)
        rsi_period = r1.number_input("RSI Period", 5, 50, RSI_PERIOD)
        macd_fast = r1.number_input("MACD Fast", 5, 30, MACD_FAST)
        macd_slow = r2.number_input("MACD Slow", 10, 50, MACD_SLOW)
        macd_signal = r2.number_input("MACD Signal", 5, 20, MACD_SIGNAL)
        bb_period = r1.number_input("BB Period", 5, 50, BB_PERIOD)
        bb_std = r2.number_input("BB Std", 0.5, 4.0, BB_STD, 0.1)
        ema_short = r1.number_input("EMA Short", 5, 50, EMA_SHORT)
        ema_long = r2.number_input("EMA Long", 20, 200, EMA_LONG)
        adx_period = r1.number_input("ADX Period", 5, 50, ADX_PERIOD)
        atr_period = r2.number_input("ATR Period", 5, 50, ATR_PERIOD)

    st.divider()
    analyze_btn = st.button("▶  PHÂN TÍCH", type="primary", use_container_width=True)
    rc1, rc2 = st.columns([3, 1])
    realtime_mode = rc1.toggle("Auto Refresh", False)
    rc2.caption(f"**{st.session_state.refresh_sec}s**")
    preset_cols = st.columns(5)
    for i, sec in enumerate(REFRESH_PRESETS):
        if preset_cols[i].button(f"{sec}s", key=f"pre_{sec}", use_container_width=True):
            st.session_state.refresh_sec = sec
    refresh_sec = int(st.session_state.refresh_sec)

# ═══════════════════════════════════════════════════════════════
#  ANALYSIS PIPELINE
# ═══════════════════════════════════════════════════════════════
def run_analysis():
    global symbol
    symbol = str(symbol).strip().upper()
    log(f"Loading {symbol} {interval}...", "🔄")
    with st.spinner("Fetching data..."):
        scraper = TVScraperPro()
        if "yfinance" in data_source.lower() and "TradingView" not in data_source:
            df = scraper.scrape_yfinance(symbol, interval=interval)
            scanner_data = {}
        else:
            full_data = scraper.get_full_data(symbol, interval=interval)
            df = full_data["ohlcv"]
            scanner_data = full_data["scanner"]
        if df.empty:
            st.error(f"Không lấy được dữ liệu cho **{symbol}** ({interval}). "
                     f"Kiểm tra lại mã — phải đúng định dạng TradingView (VD: `OANDA:XAUUSD`, `NASDAQ:AAPL`, `BINANCE:BTCUSDT`) hoặc ticker yfinance.")
            return None, None, None, None, None, None, {}
        df = df.tail(bars_count).copy()
        tv_indicators = scanner_data
        log(f"Loaded {len(df)} candles {interval}", "✅")

    with st.spinner("Computing indicators..."):
        analyzer = TechnicalAnalyzer(df)
        df = analyzer.compute_all(rsi_period=rsi_period, macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal, bb_period=bb_period, bb_std=bb_std, ema_short=ema_short, ema_long=ema_long, adx_period=adx_period, atr_period=atr_period)
        signals = analyzer.get_latest_signals()
        log("Indicators done", "✅")

    with st.spinner("Statistics..."):
        stat_analyzer = StatisticalAnalyzer(df)
        stats = stat_analyzer.run_all()
        log("Stats done", "✅")

    with st.spinner("ML Prediction..."):
        predictor = MLPredictor(df)
        try: predictor.train()
        except: pass
        prediction = predictor.predict()
        log("ML done", "✅")

    with st.spinner("Backtest..."):
        bt_engine = BacktestEngine(df)
        backtest = bt_engine.run_all_strategies()
        log("Backtest done", "✅")

    with st.spinner("Consensus..."):
        cons_engine = ConsensusEngine(df)
        consensus = cons_engine.compute_all(indicators=signals, stats=stats, ml_prediction=prediction)
        log("Consensus done", "✅")

    mtf = None
    if len(mtf_timeframes) > 0:
        with st.spinner("Multi-timeframe..."):
            try:
                mtf = MTFAnalyzer(symbol, mtf_timeframes).run(scraper)
                if mtf and mtf.get("results"):
                    c = mtf["consensus"]
                    log(f"MTF: {c['direction']} ({c['aligned']}/{c['total']}, {c['strength']*100:.0f}%)", "🕐")
            except Exception as e:
                log(f"MTF error: {e}", "⚠️")

    setup = None
    try:
        cdir = consensus.get("consensus", {}).get("direction", "NEUTRAL") if consensus else "NEUTRAL"
        mtf_dir = mtf["consensus"]["direction"] if mtf else None
        mtf_str = mtf["consensus"]["strength"] if mtf else 0.0
        direction = mtf_dir if cdir == "NEUTRAL" and mtf_dir and mtf_dir != "NEUTRAL" else cdir
        daily_cap = st.session_state.daily_capital.daily_capital
        setup = compute_setup(df, direction, signals, mtf_dir=mtf_dir, mtf_strength=mtf_str, daily_capital=daily_cap)
        if setup:
            log(f"Plan: {setup['direction']} R:R {setup['rr_ratios']['avg']}R Conf {setup['reliability']}", "🎯")
            try:
                pm = st.session_state.pattern_matcher
                current_signals = {
                    "rsi": signals.get("RSI", {}).get("value"),
                    "macd_hist": signals.get("MACD", {}).get("histogram"),
                    "bb_position": signals.get("Bollinger", {}).get("position"),
                    "adx": signals.get("ADX", {}).get("value"),
                    "stoch_k": signals.get("Stochastic", {}).get("K"),
                    "fib_nearest": setup.get("fib_nearest", {}).get("distance_pct"),
                    "sr_distance_pct": None,
                    "trendline_type": setup.get("trendlines", [{}])[0].get("type") if setup.get("trendlines") else None,
                    "pattern_name": setup.get("pattern"),
                }
                similar = pm.find_similar(current_signals, symbol)
                pattern_stats = pm.get_pattern_stats(similar) if similar else {}
                st.session_state["similar_patterns"] = similar
                st.session_state["pattern_stats"] = pattern_stats
            except: pass
    except Exception as e:
        log(f"Setup error: {e}", "⚠️")

    st.session_state.mtf = mtf
    st.session_state.setup = setup
    st.session_state.last_refresh = time.strftime("%H:%M:%S")
    st.session_state.last_refresh_ts = time.time()
    return df, signals, stats, prediction, backtest, consensus, tv_indicators

def store_result(result):
    (st.session_state.data, st.session_state.signals, st.session_state.stats,
     st.session_state.prediction, st.session_state.backtest,
     st.session_state.consensus, st.session_state.tv_indicators) = result
    try:
        sym = symbol.split(":")[-1] if ":" in symbol else symbol
        st.session_state.market_data = fetch_all_market_data(sym)
    except: pass

# ═══════════════════════════════════════════════════════════════
#  EXECUTION
# ═══════════════════════════════════════════════════════════════
refresh_count = 0
if realtime_mode:
    refresh_count = st_autorefresh(interval=refresh_sec * 1000, key="realtime_auto")

if analyze_btn or st.session_state.pop("want_analyze", False):
    result = run_analysis()
    if result[0] is not None:
        store_result(result)
        st.success("Analysis complete!")
elif realtime_mode and refresh_count > 0 and st.session_state.data is not None:
    with st.spinner("Updating..."):
        result = run_analysis()
        if result[0] is not None:
            store_result(result)

if st.session_state.market_data is None:
    try:
        sym = symbol.split(":")[-1] if ":" in symbol else symbol
        st.session_state.market_data = fetch_all_market_data(sym)
    except: pass

# ═══════════════════════════════════════════════════════════════
#  GENERATE ALERTS
# ═══════════════════════════════════════════════════════════════
def generate_alerts():
    alerts = []
    now_str = time.strftime("%H:%M")
    setup = st.session_state.setup
    mtf = st.session_state.mtf
    tv_sym = symbol.split(":")[-1] if ":" in symbol else symbol
    if setup and setup.get("direction") in ("LONG", "SHORT"):
        d = setup["direction"]
        tps = setup.get("take_profits") or []
        tp_price = tps[0].get("price") if tps else None
        alerts.append({"type": "entry", "direction": d, "title": f"Entry Signal ({d})", "symbol": tv_sym, "time": now_str, "description": f"Price: {setup['price']:,.2f} · SL: {setup['stop_loss']:,.2f} · TP: {tp_price:,.2f}", "confidence": setup.get("reliability", 0), "color": GREEN if d == "LONG" else RED, "icon": "🟢" if d == "LONG" else "🔴"})
    if mtf and mtf.get("consensus"):
        c = mtf["consensus"]
        md = c.get("direction", "NEUTRAL")
        strength = int(c.get("strength", 0) * 100)
        if md != "NEUTRAL":
            alerts.append({"type": "info", "direction": md, "title": "Trend " + ("Bullish" if md == "LONG" else "Bearish"), "symbol": tv_sym, "time": now_str, "description": f"ADX: {st.session_state.signals.get('ADX', {}).get('value', 'N/A')} · MTF {strength}%", "confidence": strength, "color": GREEN if md == "LONG" else RED, "icon": "📈" if md == "LONG" else "📉"})
        if mtf.get("results"):
            for tf in ["1H", "4H", "1D"]:
                res = mtf["results"].get(tf)
                if res and res["trend"]["direction"] != "NEUTRAL":
                    tdir = res["trend"]["direction"]
                    alerts.append({"type": "info", "direction": tdir, "title": f"{tf}: {tdir}", "symbol": tv_sym, "time": now_str, "description": f"{tf}: {res['trend']['bull']} bull / {res['trend']['bear']} bear", "confidence": int(res["trend"]["confidence"] * 100), "color": GREEN if tdir == "LONG" else RED, "icon": "🟢" if tdir == "LONG" else "🔴"})
                bk = res.get("breakout", {}) if res else {}
                if bk.get("type") and bk["type"] != "none":
                    bk_color = GREEN if bk["type"] == "BREAKOUT" else RED
                    alerts.append({"type": "warning", "direction": "LONG" if bk["type"] == "BREAKOUT" else "SHORT", "title": f"{bk['type']} {tf}", "symbol": tv_sym, "time": now_str, "description": f"{bk['detail']} @ {bk['level']:,.2f} ({int(bk['confidence']*100)}%)", "confidence": int(bk["confidence"] * 100), "color": bk_color, "icon": "⚡"})
    return alerts

st.session_state.alerts = generate_alerts()

# ═══════════════════════════════════════════════════════════════
#  NO DATA
# ═══════════════════════════════════════════════════════════════
if st.session_state.data is None:
    st.markdown(f"""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:80vh;color:{MUTED}">
      <div style="width:80px;height:80px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);border-radius:20px;display:flex;align-items:center;justify-content:center;font-size:36px;font-weight:700;color:#fff;margin-bottom:24px">TV</div>
      <div style="font-size:20px;font-weight:600;color:{TEXT};margin-bottom:8px">TradingView Analyzer Pro</div>
      <div style="font-size:14px;color:{MUTED};margin-bottom:24px">Professional Trading Terminal</div>
      <div style="font-size:13px;color:{DIM};border:1px solid {BORDER};padding:12px 20px;border-radius:8px">👈 Select symbol + timeframe in sidebar, then click <b style="color:{ACCENT}">▶ PHÂN TÍCH</b></div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ═══════════════════════════════════════════════════════════════
#  DATA
# ═══════════════════════════════════════════════════════════════
df = st.session_state.data
signals = st.session_state.signals
stats = st.session_state.stats
prediction = st.session_state.prediction
backtest = st.session_state.backtest
consensus = st.session_state.consensus
mtf = st.session_state.mtf
setup = st.session_state.setup
tv_sym = symbol.split(":")[-1] if ":" in symbol else symbol

# ═══════════════════════════════════════════════════════════════
#  HEADER BAR
# ═══════════════════════════════════════════════════════════════
elapsed = time.time() - st.session_state.last_refresh_ts if st.session_state.last_refresh_ts else 0
remaining = max(0, int(refresh_sec - elapsed))

st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 16px;background:{PANEL};border-bottom:1px solid {BORDER};font-family:'JetBrains Mono',monospace;font-size:12px">
  <div style="display:flex;align-items:center;gap:12px">
    <span style="color:{ACCENT};font-weight:700;font-size:13px">TV</span>
    <span style="color:{MUTED}">ANALYZER</span>
    <span style="color:{BORDER}">│</span>
    <span style="font-weight:600;color:{TEXT}">{tv_sym}</span>
    <span style="background:{PANEL2};padding:2px 6px;border-radius:3px;color:{MUTED}">{interval}</span>
    <span style="color:{BORDER}">│</span>
    <span style="color:{MUTED}">O</span><span style="color:{TEXT}">{df['open'].iloc[-1]:,.2f}</span>
    <span style="color:{MUTED}">H</span><span style="color:{GREEN}">{df['high'].iloc[-1]:,.2f}</span>
    <span style="color:{MUTED}">L</span><span style="color:{RED}">{df['low'].iloc[-1]:,.2f}</span>
    <span style="color:{MUTED}">C</span><span style="font-weight:600;color:{TEXT}">{df['close'].iloc[-1]:,.2f}</span>
    <span style="color:{GREEN if df['close'].iloc[-1]>=df['open'].iloc[-1] else RED};font-weight:600">{((df['close'].iloc[-1]-df['open'].iloc[-1])/df['open'].iloc[-1]*100):+.2f}%</span>
  </div>
  <div style="display:flex;align-items:center;gap:8px">
    <span style="color:{GREEN if remaining>5 else RED}">●</span>
    <span style="color:{MUTED}">yfinance</span>
    <span style="color:{TEXT}">{remaining:02d}s</span>
    <span style="color:{MUTED}">{len(df)} bars</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  CHART
# ═══════════════════════════════════════════════════════════════
def build_price_chart(df, show_bb, show_sma, show_ema, setup, xb=None,
                      show_vwap=False, show_ichi=False, show_st=False, show_psar=False,
                      show_kc=False, show_dc=False, show_ema200=False):
    """Main price chart — candles + overlays, own panel."""
    has_vwap = show_vwap and "VWAP" in df.columns and df["VWAP"].notna().sum() > 0

    fig = make_subplots(rows=1, cols=1, shared_xaxes=True, vertical_spacing=0.01)

    # Candlestick
    fig.add_trace(go.Candlestick(x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
                                  increasing_line_color="#26a69a", decreasing_line_color="#ef5350", increasing_fillcolor="#26a69a", decreasing_fillcolor="#ef5350",
                                  name="OHLC"), 1, 1)

    # Current price line
    last_p = float(df["close"].iloc[-1])
    fig.add_hline(y=last_p, line_dash="dot", line_color="#FFD54F", line_width=1, opacity=0.7)
    fig.add_annotation(x=df.index[-1], y=last_p, text=f"  {last_p:,.2f}", showarrow=False, xanchor="left",
                       font=dict(color="#FFD54F", size=10, family="JetBrains Mono"), bgcolor=PANEL)

    # Setup overlays
    if setup:
        entry = setup.get("entry")
        sl = setup.get("stop_loss")
        tps = setup.get("take_profits") or []
        d = setup.get("direction", "NEUTRAL")
        mc = GREEN if d == "LONG" else RED

        if entry:
            fig.add_hline(y=float(entry), line_dash="solid", line_color=ACCENT, line_width=1.5, opacity=0.8)
            fig.add_annotation(x=df.index[-1], y=float(entry), text=f"  Entry: {float(entry):,.2f}", showarrow=False, xanchor="left",
                               font=dict(color=ACCENT, size=10, family="JetBrains Mono"), bgcolor=PANEL)
        if sl:
            fig.add_hline(y=float(sl), line_dash="dash", line_color=RED, line_width=1.2, opacity=0.8)
            fig.add_annotation(x=df.index[-1], y=float(sl), text=f"  SL: {float(sl):,.2f}", showarrow=False, xanchor="left",
                               font=dict(color=RED, size=10, family="JetBrains Mono"), bgcolor=PANEL)
        tp_colors = [GREEN, TEAL, AMBER, ACCENT, PURPLE]
        for i, tp in enumerate(tps[:5]):
            tp_p = tp.get("price")
            if tp_p is None: continue
            fig.add_hline(y=float(tp_p), line_dash="dash", line_color=tp_colors[i % len(tp_colors)], line_width=1, opacity=0.8)
            fig.add_annotation(x=df.index[-1], y=float(tp_p), text=f"  {tp.get('level', f'TP{i+1}')}: {float(tp_p):,.2f}", showarrow=False, xanchor="left",
                               font=dict(color=tp_colors[i % len(tp_colors)], size=10, family="JetBrains Mono"), bgcolor=PANEL)
        if d in ("LONG", "SHORT") and entry:
            fig.add_trace(go.Scatter(x=[df.index[-1]], y=[float(entry)], mode="markers",
                                      marker=dict(color=mc, size=16, symbol="triangle-up" if d=="LONG" else "triangle-down", line=dict(color="#fff", width=1)),
                                      name=f"{'BUY' if d=='LONG' else 'SELL'} Signal", showlegend=False), 1, 1)

    # SMA
    if show_sma:
        sma_colors = {"SMA_20": "#3b82f6", "SMA_50": "#f97316", "SMA_200": "#a855f7"}
        for col, color in sma_colors.items():
            if col in df.columns and df[col].notna().sum() > 0:
                fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col, line=dict(color=color, width=1)), 1, 1)

    # EMA
    if show_ema:
        for col in sorted(c for c in df.columns if c.startswith("EMA_")):
            if df[col].notna().sum() > 0:
                fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col, line=dict(color=CYAN, width=1, dash="dot")), 1, 1)

    # Bollinger
    if show_bb:
        bbu = [c for c in df.columns if c.startswith("BBU") or "BB.upper" in c]
        bbl = [c for c in df.columns if c.startswith("BBL") or "BB.lower" in c]
        if bbu and bbl:
            fig.add_trace(go.Scatter(x=df.index, y=df[bbu[0]], line=dict(color="#64748b", width=0.5), name="BB Upper", showlegend=False), 1, 1)
            fig.add_trace(go.Scatter(x=df.index, y=df[bbl[0]], line=dict(color="#64748b", width=0.5), name="BB Lower", showlegend=False, fill="tonexty", fillcolor="rgba(100,116,139,0.06)"), 1, 1)

    # VWAP
    if has_vwap:
        fig.add_trace(go.Scatter(x=df.index, y=df["VWAP"], name="VWAP", line=dict(color="#f59e0b", width=1.2)), 1, 1)

    # EMA 200
    if show_ema200 and len(df) > 60:
        ema200 = df["close"].ewm(span=200, adjust=False).mean()
        if ema200.notna().iloc[-1]:
            fig.add_trace(go.Scatter(x=df.index, y=ema200, name="EMA 200", line=dict(color="#fb923c", width=1.3)), 1, 1)

    # Ichimoku
    if show_ichi:
        isa = [c for c in df.columns if c.startswith("ISA") or c.startswith("ITS")]
        isb = [c for c in df.columns if c.startswith("ISB") or c.startswith("ICS")]
        if isa and isb:
            fig.add_trace(go.Scatter(x=df.index, y=df[isa[0]], name="Tenkan/KS", line=dict(color="#22d3ee", width=1), showlegend=False), 1, 1)
            fig.add_trace(go.Scatter(x=df.index, y=df[isb[0]], name="Kijun/KB", line=dict(color="#e879f9", width=1), showlegend=False,
                                      fill="tonexty", fillcolor="rgba(34,211,238,0.10)"), 1, 1)

    # Supertrend
    if show_st:
        su = [c for c in df.columns if c.startswith("SUPERT_")]
        su_idx = [c for c in df.columns if c.startswith("SUPERTd")]
        if su or su_idx:
            st_vals = df[su[0]] if su else df[su_idx[0]] * 0
            fig.add_trace(go.Scatter(x=df.index, y=st_vals, name="Supertrend",
                                      line=dict(color="#26a69a", width=1.4), showlegend=False), 1, 1)

    # PSAR
    if show_psar:
        psarl = [c for c in df.columns if c.startswith("PSARl")]
        psars = [c for c in df.columns if c.startswith("PSARs")]
        if psarl or psars:
            cols_ps = psarl if psarl else psars
            mc = ("#26a69a" if psarl else "#ef5350")
            fig.add_trace(go.Scatter(x=df.index, y=df[cols_ps[0]], mode="markers", name="PSAR",
                                      marker=dict(color=mc, size=3, symbol="circle"), showlegend=False), 1, 1)

    # Keltner Channels
    if show_kc:
        kcu = [c for c in df.columns if c.startswith("KCU") or c.startswith("KCUe")]
        kcl = [c for c in df.columns if c.startswith("KCL") or c.startswith("KCLe")]
        if kcu and kcl:
            fig.add_trace(go.Scatter(x=df.index, y=df[kcu[0]], name="Kelt U", line=dict(color="#64748b", width=0.6), showlegend=False), 1, 1)
            fig.add_trace(go.Scatter(x=df.index, y=df[kcl[0]], name="Kelt L", line=dict(color="#64748b", width=0.6), showlegend=False,
                                      fill="tonexty", fillcolor="rgba(148,163,184,0.05)"), 1, 1)

    # Donchian Channel
    if show_dc:
        dcu = [c for c in df.columns if c.startswith("DCU")]
        dcl = [c for c in df.columns if c.startswith("DCL")]
        if dcu and dcl:
            fig.add_trace(go.Scatter(x=df.index, y=df[dcu[0]], name="DC Upper", line=dict(color="#f472b6", width=0.8, dash="dash"), showlegend=False), 1, 1)
            fig.add_trace(go.Scatter(x=df.index, y=df[dcl[0]], name="DC Lower", line=dict(color="#f472b6", width=0.8, dash="dash"), showlegend=False), 1, 1)

    fig.update_layout(
        height=520, xaxis_rangeslider_visible=False,
        template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=PANEL,
        font=dict(color="white", family="Inter, sans-serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0.01, font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=45, r=10, t=8, b=0), hovermode="x unified",
        dragmode="pan",
    )
    fig.update_xaxes(gridcolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER)
    if xb:
        fig.update_xaxes(range=xb)

    fig.update_xaxes(
        rangeselector=dict(
            x=0.0, y=1.06, font=dict(size=10, color="white"),
            bgcolor="rgba(30,41,59,0.9)", activecolor="#1e3a5f",
            bordercolor="#334155", borderwidth=1,
            buttons=[
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=3, label="3M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="YTD", step="year", stepmode="todate"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(step="all", label="ALL"),
            ],
        ),
    )

    return fig


def _indicator_chart(title, height, xb):
    fig = make_subplots(rows=1, cols=1, shared_xaxes=True, vertical_spacing=0.01)
    fig.update_layout(
        height=height, xaxis_rangeslider_visible=False,
        template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=PANEL,
        font=dict(color="white", family="Inter, sans-serif"),
        margin=dict(l=45, r=10, t=6, b=0), hovermode="x unified",
        dragmode="pan",
    )
    fig.update_xaxes(gridcolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER)
    fig.add_annotation(x=0.01, y=1.04, xref="paper", yref="paper", text=title, showarrow=False,
                       font=dict(color="#94a3b8", size=11), xanchor="left")
    if xb:
        fig.update_xaxes(range=xb)
    return fig


def build_volume_chart(df, xb=None):
    fig = _indicator_chart("VOLUME", 140, xb)
    vc = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["volume"], marker_color=vc, name="Volume"))
    return fig


def build_rsi_chart(df, xb=None):
    fig = _indicator_chart("RSI (14)", 140, xb)
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="#E040FB", width=1.2)))
    fig.add_hline(y=70, line_dash="dash", line_color=RED, opacity=0.4)
    fig.add_hline(y=30, line_dash="dash", line_color=GREEN, opacity=0.4)
    fig.update_yaxes(range=[0, 100])
    return fig


def build_macd_chart(df, xb=None):
    fig = _indicator_chart("MACD (12,26,9)", 160, xb)
    hist = df["MACD.hist"].fillna(0) if "MACD.hist" in df.columns else df["MACD.macd"] * 0
    mc = ["#26a69a" if v >= 0 else "#ef5350" for v in hist]
    fig.add_trace(go.Bar(x=df.index, y=hist, marker_color=mc, name="Histogram"))
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD.macd"], name="MACD", line=dict(color="#3b82f6", width=1.2)))
    if "MACD.signal" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD.signal"], name="Signal", line=dict(color="#f97316", width=1.2)))
    return fig


def build_stoch_chart(df, xb=None):
    fig = _indicator_chart("STOCHASTIC (14,3,3)", 140, xb)
    fig.add_trace(go.Scatter(x=df.index, y=df["STOCH_K"], name="Stoch %K", line=dict(color="#3b82f6", width=1)))
    if "STOCH_D" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["STOCH_D"], name="Stoch %D", line=dict(color="#f97316", width=1)))
    fig.add_hline(y=80, line_dash="dash", line_color=RED, opacity=0.3)
    fig.add_hline(y=20, line_dash="dash", line_color=GREEN, opacity=0.3)
    fig.update_yaxes(range=[0, 100])
    return fig


def build_adx_chart(df, xb=None):
    fig = _indicator_chart("ADX (14)", 140, xb)
    fig.add_trace(go.Scatter(x=df.index, y=df["ADX"], name="ADX", line=dict(color="#eab308", width=1.2)))
    fig.add_hline(y=25, line_dash="dash", line_color="#64748b", opacity=0.4)
    return fig


CHART_CONFIG = {"scrollZoom": True, "displaylogo": False,
                "modeBarButtonsToAdd": ["pan2d", "zoomIn2d", "zoomOut2d", "autoScale2d"],
                "modeBarButtonsToRemove": ["lasso2d", "select2d"]}

xb = None
if len(df.index) > 150:
    xb = [df.index[-150], df.index[-1]]

st.markdown(sec_title("BIỂU ĐỒ GIÁ", TEAL), unsafe_allow_html=True)
fig_price = build_price_chart(df, show_bb, show_ma, show_ema, setup if show_setup else None, xb=xb,
                              show_vwap=show_vwap, show_ichi=show_ichi, show_st=show_st, show_psar=show_psar,
                              show_kc=show_kc, show_dc=show_dc, show_ema200=show_ema200)
st.plotly_chart(fig_price, use_container_width=True, config=CHART_CONFIG)

st.markdown('<div class="sb-title">Khung thời gian (nhanh)</div>', unsafe_allow_html=True)
tf_quick = ["1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W"]
tf_cols = st.columns(len(tf_quick))
for i, tf in enumerate(tf_quick):
    active = (tf == interval)
    if tf_cols[i].button(tf, key=f"tfq_{tf}", use_container_width=True,
                         type="primary" if active else "secondary"):
        st.session_state.khung_next = tf
        st.session_state.want_analyze = True
        st.rerun()

# Separate indicator panels — clean, per standard technical-analysis charts
if show_volume and "volume" in df.columns:
    st.markdown(sec_title("KHỐI LƯỢNG (VOLUME)", "#64748b"), unsafe_allow_html=True)
    st.plotly_chart(build_volume_chart(df, xb), use_container_width=True, config=CHART_CONFIG)

if show_rsi and "RSI" in df.columns and df["RSI"].notna().sum() > 0:
    st.markdown(sec_title("RSI (14)", "#E040FB"), unsafe_allow_html=True)
    st.plotly_chart(build_rsi_chart(df, xb), use_container_width=True, config=CHART_CONFIG)

if show_macd and "MACD.macd" in df.columns:
    st.markdown(sec_title("MACD (12,26,9)", "#3b82f6"), unsafe_allow_html=True)
    st.plotly_chart(build_macd_chart(df, xb), use_container_width=True, config=CHART_CONFIG)

if show_stoch and "STOCH_K" in df.columns:
    st.markdown(sec_title("STOCHASTIC (14,3,3)", "#14b8a6"), unsafe_allow_html=True)
    st.plotly_chart(build_stoch_chart(df, xb), use_container_width=True, config=CHART_CONFIG)

if show_adx and "ADX" in df.columns:
    st.markdown(sec_title("ADX (14)", "#eab308"), unsafe_allow_html=True)
    st.plotly_chart(build_adx_chart(df, xb), use_container_width=True, config=CHART_CONFIG)

# ═══════════════════════════════════════════════════════════════
#  BUY / SELL STRENGTH DASHBOARD
# ═══════════════════════════════════════════════════════════════
def compute_strength_score(signals):
    """Compute composite buy/sell strength from multiple indicators."""
    buy_score = 0
    sell_score = 0
    total_weight = 0
    details = []

    # RSI (weight: 15)
    rsi = signals.get("RSI", {})
    if rsi:
        val = rsi.get("value", 50)
        w = 15
        total_weight += w
        if val < 30:
            buy_score += w
            details.append(("RSI", f"{val:.1f}", "OVERSOLD", GREEN, w))
        elif val < 40:
            buy_score += w * 0.6
            details.append(("RSI", f"{val:.1f}", "Weak", GREEN, int(w*0.6)))
        elif val > 70:
            sell_score += w
            details.append(("RSI", f"{val:.1f}", "OVERBOUGHT", RED, w))
        elif val > 60:
            sell_score += w * 0.6
            details.append(("RSI", f"{val:.1f}", "Strong", RED, int(w*0.6)))
        else:
            details.append(("RSI", f"{val:.1f}", "NEUTRAL", MUTED, 0))

    # MACD (weight: 15)
    macd = signals.get("MACD", {})
    if macd:
        hist = macd.get("histogram", 0)
        w = 15
        total_weight += w
        if hist > 0:
            s = min(abs(hist) / 0.5, 1.0)
            buy_score += w * s
            details.append(("MACD", f"+{hist:.4f}", "BULL", GREEN, int(w*s)))
        elif hist < 0:
            s = min(abs(hist) / 0.5, 1.0)
            sell_score += w * s
            details.append(("MACD", f"{hist:.4f}", "BEAR", RED, int(w*s)))
        else:
            details.append(("MACD", "0", "FLAT", MUTED, 0))

    # Stochastic (weight: 10)
    stoch = signals.get("Stochastic", {})
    if stoch:
        k = stoch.get("K", 50)
        w = 10
        total_weight += w
        if k < 20:
            buy_score += w
            details.append(("STOCH", f"{k:.1f}", "OVERSOLD", GREEN, w))
        elif k > 80:
            sell_score += w
            details.append(("STOCH", f"{k:.1f}", "OVERBOUGHT", RED, w))
        else:
            details.append(("STOCH", f"{k:.1f}", "NEUTRAL", MUTED, 0))

    # MFI (weight: 12)
    mfi = signals.get("MFI", {})
    if mfi:
        val = mfi.get("value", 50)
        w = 12
        total_weight += w
        if val < 20:
            buy_score += w
            details.append(("MFI", f"{val:.1f}", "OVERSOLD", GREEN, w))
        elif val > 80:
            sell_score += w
            details.append(("MFI", f"{val:.1f}", "OVERBOUGHT", RED, w))
        else:
            pct = (val - 50) / 50
            if pct < 0:
                buy_score += w * abs(pct)
                details.append(("MFI", f"{val:.1f}", "Weak Buy", GREEN, int(w*abs(pct))))
            else:
                sell_score += w * pct
                details.append(("MFI", f"{val:.1f}", "Weak Sell", RED, int(w*pct)))

    # CCI (weight: 10)
    cci = signals.get("CCI", {})
    if cci:
        val = cci.get("value", 0)
        w = 10
        total_weight += w
        if val < -100:
            buy_score += w
            details.append(("CCI", f"{val:.1f}", "OVERSOLD", GREEN, w))
        elif val > 100:
            sell_score += w
            details.append(("CCI", f"{val:.1f}", "OVERBOUGHT", RED, w))
        else:
            details.append(("CCI", f"{val:.1f}", "NEUTRAL", MUTED, 0))

    # Williams %R (weight: 8)
    wr = signals.get("WilliamsR", {})
    if wr:
        val = wr.get("value", -50)
        w = 8
        total_weight += w
        if val < -80:
            buy_score += w
            details.append(("W%R", f"{val:.1f}", "OVERSOLD", GREEN, w))
        elif val > -20:
            sell_score += w
            details.append(("W%R", f"{val:.1f}", "OVERBOUGHT", RED, w))
        else:
            details.append(("W%R", f"{val:.1f}", "NEUTRAL", MUTED, 0))

    # OBV (weight: 10)
    obv = signals.get("OBV", {})
    if obv:
        trend = obv.get("trend", "")
        w = 10
        total_weight += w
        if trend == "RISING":
            buy_score += w
            details.append(("OBV", "Rising", "BULL", GREEN, w))
        elif trend == "FALLING":
            sell_score += w
            details.append(("OBV", "Falling", "BEAR", RED, w))
        else:
            details.append(("OBV", "Flat", "NEUTRAL", MUTED, 0))

    # VWAP (weight: 10)
    vwap = signals.get("VWAP", {})
    if vwap:
        dist = vwap.get("distance_pct", 0)
        w = 10
        total_weight += w
        if dist > 0.5:
            buy_score += min(w, w * abs(dist) / 2)
            details.append(("VWAP", f"+{dist:.2f}%", "ABOVE", GREEN, min(w, int(w * abs(dist) / 2))))
        elif dist < -0.5:
            sell_score += min(w, w * abs(dist) / 2)
            details.append(("VWAP", f"{dist:.2f}%", "BELOW", RED, min(w, int(w * abs(dist) / 2))))
        else:
            details.append(("VWAP", f"{dist:.2f}%", "NEAR", MUTED, 0))

    # A/D Line (weight: 10)
    ad = signals.get("AD", {})
    if ad:
        trend = ad.get("trend_20", "")
        w = 10
        total_weight += w
        if trend == "ACCUMULATION":
            buy_score += w
            details.append(("A/D", "Accum", "BULL", GREEN, w))
        elif trend == "DISTRIBUTION":
            sell_score += w
            details.append(("A/D", "Distrib", "BEAR", RED, w))
        else:
            details.append(("A/D", "Flat", "NEUTRAL", MUTED, 0))

    # Relative Volume (weight: 5)
    rv = signals.get("RelativeVolume", {})
    if rv:
        val = rv.get("value", 1.0)
        w = 5
        total_weight += w
        if val > 1.5:
            details.append(("RVOL", f"{val:.1f}x", "HIGH", AMBER, w))
        elif val < 0.5:
            details.append(("RVOL", f"{val:.1f}x", "LOW", DIM, w))
        else:
            details.append(("RVOL", f"{val:.1f}x", "NORMAL", MUTED, 0))

    # RSI Divergence
    div = signals.get("RSI_Divergence", {})
    if div:
        dtype = div.get("type", "")
        w = 15
        total_weight += w
        if dtype == "BULLISH":
            buy_score += w
            details.append(("DIV", div.get("detail", ""), "BULLISH", GREEN, w))
        elif dtype == "BEARISH":
            sell_score += w
            details.append(("DIV", div.get("detail", ""), "BEARISH", RED, w))

    # MACD Momentum
    mm = signals.get("MACD_Momentum", {})
    if mm:
        d = mm.get("direction", "")
        w = 10
        total_weight += w
        if "BULL" in d:
            buy_score += w
            details.append(("MOM", mm.get("detail", ""), "ACCEL↑", GREEN, w))
        elif "BEAR" in d:
            sell_score += w
            details.append(("MOM", mm.get("detail", ""), "ACCEL↓", RED, w))

    # Ichimoku (weight: 15)
    ichi = signals.get("Ichimoku", {})
    if ichi:
        sig = ichi.get("signal", "")
        w = 15
        total_weight += w
        if sig == "BULLISH":
            buy_score += w
            details.append(("ICHI", "Above Cloud", "BULL", GREEN, w))
        elif sig == "BEARISH":
            sell_score += w
            details.append(("ICHI", "Below Cloud", "BEAR", RED, w))
        else:
            tk = ichi.get("tk_cross", "")
            if tk == "BULL":
                buy_score += w * 0.3
                details.append(("ICHI", "In Cloud", "TK↑", GREEN, int(w*0.3)))
            else:
                sell_score += w * 0.3
                details.append(("ICHI", "In Cloud", "TK↓", RED, int(w*0.3)))

    # Supertrend (weight: 12)
    st = signals.get("Supertrend", {})
    if st:
        d = st.get("direction", "")
        w = 12
        total_weight += w
        if d == "BULL":
            buy_score += w
            details.append(("STRND", f"{st.get('value',0):,.2f}", "BULL", GREEN, w))
        elif d == "BEAR":
            sell_score += w
            details.append(("STRND", f"{st.get('value',0):,.2f}", "BEAR", RED, w))

    # CMF (weight: 10)
    cmf = signals.get("CMF", {})
    if cmf:
        val = cmf.get("value", 0)
        w = 10
        total_weight += w
        if val > 0.05:
            s = min(abs(val) * 10, 1.0)
            buy_score += w * s
            details.append(("CMF", f"{val:.3f}", "BUYING", GREEN, int(w*s)))
        elif val < -0.05:
            s = min(abs(val) * 10, 1.0)
            sell_score += w * s
            details.append(("CMF", f"{val:.3f}", "SELLING", RED, int(w*s)))
        else:
            details.append(("CMF", f"{val:.3f}", "NEUTRAL", MUTED, 0))

    # Elder Ray (weight: 8)
    er = signals.get("ElderRay", {})
    if er:
        sig = er.get("signal", "")
        w = 8
        total_weight += w
        if "BULL" in sig:
            buy_score += w * (1.0 if "STRONG" in sig else 0.5)
            details.append(("ELDR", f"B:{er.get('bull',0):.2f}", sig, GREEN, int(w*(1.0 if "STRONG" in sig else 0.5))))
        elif "BEAR" in sig:
            sell_score += w * (1.0 if "STRONG" in sig else 0.5)
            details.append(("ELDR", f"B:{er.get('bear',0):.2f}", sig, RED, int(w*(1.0 if "STRONG" in sig else 0.5))))

    # TRIX (weight: 8)
    trix = signals.get("TRIX", {})
    if trix:
        val = trix.get("value", 0)
        w = 8
        total_weight += w
        if val > 0.01:
            buy_score += min(w, w * abs(val) * 10)
            details.append(("TRIX", f"{val:.4f}", "BULL", GREEN, min(w, int(w * abs(val) * 10))))
        elif val < -0.01:
            sell_score += min(w, w * abs(val) * 10)
            details.append(("TRIX", f"{val:.4f}", "BEAR", RED, min(w, int(w * abs(val) * 10))))
        else:
            details.append(("TRIX", f"{val:.4f}", "FLAT", MUTED, 0))

    # Fisher (weight: 8)
    fish = signals.get("Fisher", {})
    if fish:
        sig = fish.get("signal", "")
        cross = fish.get("cross", "")
        w = 8
        total_weight += w
        if sig == "BULL" and cross == "BULL":
            buy_score += w
            details.append(("FISH", f"{fish.get('value',0):.2f}", "BULL↑", GREEN, w))
        elif sig == "BEAR" and cross == "BEAR":
            sell_score += w
            details.append(("FISH", f"{fish.get('value',0):.2f}", "BEAR↓", RED, w))
        else:
            details.append(("FISH", f"{fish.get('value',0):.2f}", sig, MUTED, 0))

    # PSAR (weight: 10)
    psar = signals.get("PSAR", {})
    if psar:
        d = psar.get("direction", "")
        w = 10
        total_weight += w
        if d == "BULL":
            buy_score += w
            details.append(("PSAR", "Long", "BULL", GREEN, w))
        else:
            sell_score += w
            details.append(("PSAR", "Short", "BEAR", RED, w))

    # Aroon (weight: 8)
    aroon = signals.get("Aroon", {})
    if aroon:
        sig = aroon.get("signal", "")
        w = 8
        total_weight += w
        if sig == "STRONG_BULL":
            buy_score += w
            details.append(("ARON", f"U:{aroon.get('up',50):.0f} D:{aroon.get('down',50):.0f}", "BULL", GREEN, w))
        elif sig == "STRONG_BEAR":
            sell_score += w
            details.append(("ARON", f"U:{aroon.get('up',50):.0f} D:{aroon.get('down',50):.0f}", "BEAR", RED, w))
        else:
            details.append(("ARON", f"U:{aroon.get('up',50):.0f} D:{aroon.get('down',50):.0f}", "NEUTRAL", MUTED, 0))

    # BOP (weight: 6)
    bop = signals.get("BOP", {})
    if bop:
        val = bop.get("value", 0)
        w = 6
        total_weight += w
        if val > 0.1:
            buy_score += w * min(abs(val) * 5, 1.0)
            details.append(("BOP", f"{val:.3f}", "BUYERS", GREEN, int(w * min(abs(val) * 5, 1.0))))
        elif val < -0.1:
            sell_score += w * min(abs(val) * 5, 1.0)
            details.append(("BOP", f"{val:.3f}", "SELLERS", RED, int(w * min(abs(val) * 5, 1.0))))
        else:
            details.append(("BOP", f"{val:.3f}", "BALANCED", MUTED, 0))

    # Awesome Oscillator (weight: 8)
    ao = signals.get("AwesomeOsc", {})
    if ao:
        val = ao.get("value", 0)
        mom = ao.get("momentum", "")
        w = 8
        total_weight += w
        if val > 0 and mom == "INCREASING":
            buy_score += w
            details.append(("AO", f"{val:.2f}", "BULL↑", GREEN, w))
        elif val < 0 and mom == "DECREASING":
            sell_score += w
            details.append(("AO", f"{val:.2f}", "BEAR↓", RED, w))
        elif val > 0:
            buy_score += w * 0.5
            details.append(("AO", f"{val:.2f}", "BULL", GREEN, int(w*0.5)))
        elif val < 0:
            sell_score += w * 0.5
            details.append(("AO", f"{val:.2f}", "BEAR", RED, int(w*0.5)))
        else:
            details.append(("AO", f"{val:.2f}", "FLAT", MUTED, 0))

    # Vortex (weight: 6)
    vortex = signals.get("Vortex", {})
    if vortex:
        vp = vortex.get("plus", 1)
        vm = vortex.get("minus", 1)
        w = 6
        total_weight += w
        if vp > vm * 1.2:
            buy_score += w
            details.append(("VRTX", f"+{vp:.2f} -{vm:.2f}", "BULL", GREEN, w))
        elif vm > vp * 1.2:
            sell_score += w
            details.append(("VRTX", f"+{vp:.2f} -{vm:.2f}", "BEAR", RED, w))
        else:
            details.append(("VRTX", f"+{vp:.2f} -{vm:.2f}", "NEUTRAL", MUTED, 0))

    # Compute final score
    if total_weight > 0:
        net_score = (buy_score - sell_score) / total_weight * 100
        buy_pct = buy_score / total_weight * 100
        sell_pct = sell_score / total_weight * 100
    else:
        net_score = 0
        buy_pct = 0
        sell_pct = 0

    return {
        "net_score": round(net_score, 1),
        "buy_pct": round(buy_pct, 1),
        "sell_pct": round(sell_pct, 1),
        "details": details,
    }

# ═══════════════════════════════════════════════════════════════
#  MTF ACTION PLAN (phương án xử lý toàn khung)
# ═══════════════════════════════════════════════════════════════
# (build_action_plan / build_tf_action / build_per_tf_plans moved to
#  core/analysis_plans.py — shared with the FastAPI/React dashboard.)


# ═══════════════════════════════════════════════════════════════
#  PER-TIMEFRAME PLANS (plan riêng cho từng khung)
# ═══════════════════════════════════════════════════════════════
def render_tf_plans(mtf):
    """Render grid các plan từng khung — rõ ràng từng thẻ card."""
    plans = build_per_tf_plans(mtf)
    if not plans:
        return
    st.markdown(sec_title("PLAN THEO TỪNG KHUNG — CHI TIẾT", ACCENT), unsafe_allow_html=True)
    _DIR_COLOR = {"LONG": GREEN, "SHORT": RED, "NEUTRAL": MUTED}
    _DIR_ICON = {"LONG": "▲", "SHORT": "▼", "NEUTRAL": "–"}
    order = ["1m", "5m", "15m", "30m", "1H", "4H", "1D"]
    ordered = sorted(plans, key=lambda p: order.index(p["tf"]) if p["tf"] in order else 99)
    for start in range(0, len(ordered), 4):
        chunk = ordered[start:start + 4]
        cols = st.columns(len(chunk))
        for col, p in zip(cols, chunk):
            dc = _DIR_COLOR.get(p["direction"], MUTED)
            icon = _DIR_ICON.get(p["direction"], "–")
            reasons = p["reasons"][:3]
            sup = f"{p['support']:,.2f}" if p["support"] else "—"
            r = f"{p['resistance']:,.2f}" if p["resistance"] else "—"
            bk = f"<div style='color:{AMBER};font-size:10px;margin-top:3px'>⚡ {p['breakout_type']}: {p['breakout_detail']}</div>" if p["breakout_type"] else ""
            reason_html = " · ".join(reasons) if reasons else "—"
            col.markdown(f"""
            <div style="background:{PANEL};border:1px solid {BORDER};border-top:2px solid {dc};border-radius:6px;padding:8px 10px;margin-bottom:8px;height:100%">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                <span style="font-size:13px;font-weight:700;color:{TEXT}">{p['tf']}</span>
                <span style="font-size:11px;font-weight:700;color:{dc};font-family:'JetBrains Mono',monospace">{icon} {p['direction']} {p['confidence']*100:.0f}%</span>
              </div>
              <div style="font-size:10px;color:{MUTED};margin-bottom:3px">Score {p['score']:+d} · {p['bars']} nến · Close {p['last_close']:,.2f}</div>
              <div style="font-size:10px;color:{DIM};margin-bottom:3px">Tín hiệu: {reason_html}</div>
              <div style="font-size:10px;color:{MUTED};font-family:'JetBrains Mono',monospace">S {sup} │ R {r}</div>
              {bk}
              <div style="font-size:11px;color:{TEXT};margin-top:4px;line-height:1.4">🎯 {p['action']}</div>
            </div>
            """, unsafe_allow_html=True)

strength = compute_strength_score(signals)
net = strength["net_score"]
buy_pct = strength["buy_pct"]
sell_pct = strength["sell_pct"]

# Color based on net score
if net > 20:
    main_color = GREEN; main_label = "STRONG BUY"; main_icon = "🟢🟢"
elif net > 5:
    main_color = GREEN; main_label = "BUY"; main_icon = "🟢"
elif net < -20:
    main_color = RED; main_label = "STRONG SELL"; main_icon = "🔴🔴"
elif net < -5:
    main_color = RED; main_label = "SELL"; main_icon = "🔴"
else:
    main_color = AMBER; main_label = "NEUTRAL"; main_icon = "🟡"

st.markdown(sec_title("BUY / SELL STRENGTH", ACCENT), unsafe_allow_html=True)

# Main strength bar
st.markdown(f"""
<div style="padding:10px 14px;background:{PANEL};border:1px solid {BORDER};border-radius:8px;margin-bottom:4px">
  <div style="display:flex;align-items:center;gap:16px;margin-bottom:8px">
    <span style="font-size:20px">{main_icon}</span>
    <span style="font-size:18px;font-weight:700;color:{main_color};font-family:'JetBrains Mono',monospace">{main_label}</span>
    <span style="font-size:13px;color:{MUTED}">│</span>
    <span style="font-size:14px;color:{GREEN};font-weight:600">BUY {buy_pct:.0f}%</span>
    <span style="font-size:14px;color:{RED};font-weight:600">SELL {sell_pct:.0f}%</span>
    <span style="font-size:13px;color:{MUTED}">│</span>
    <span style="font-size:14px;color:{main_color};font-weight:700">NET: {net:+.1f}</span>
  </div>
  <div style="display:flex;height:8px;border-radius:4px;overflow:hidden;background:{BORDER}">
    <div style="width:{buy_pct}%;background:{GREEN};border-radius:4px 0 0 4px"></div>
    <div style="width:{sell_pct}%;background:{RED};border-radius:0 4px 4px 0"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:10px;color:{MUTED};margin-top:2px">
    <span>← BUY PRESSURE</span>
    <span>SELL PRESSURE →</span>
  </div>
</div>
""", unsafe_allow_html=True)

# Detail grid
detail_cols = st.columns(6)
for i, (name, val, sig, color, weight) in enumerate(strength["details"][:18]):
    col_idx = i % 6
    with detail_cols[col_idx]:
        st.markdown(f"""
        <div style="padding:4px 6px;background:{PANEL};border:1px solid {BORDER};border-radius:4px;text-align:center;margin-bottom:2px">
          <div style="font-size:9px;color:{MUTED};letter-spacing:0.5px;font-weight:600">{name}</div>
          <div style="font-size:12px;color:{TEXT};font-family:'JetBrains Mono',monospace;font-weight:600">{val}</div>
          <div style="font-size:9px;color:{color};font-weight:600">{sig}</div>
        </div>
        """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  ALERTS STRIP
# ═══════════════════════════════════════════════════════════════
alerts = st.session_state.alerts
if alerts:
    shown = alerts[:5]
    cols = st.columns(len(shown))
    for col, a in zip(cols, shown):
        conf = a.get("confidence", 0)
        color = a.get("color", MUTED)
        with col:
            st.markdown(f"""
            <div style="padding:8px 10px;background:{PANEL};border:1px solid {BORDER};border-left:3px solid {color};border-radius:6px;font-family:'Inter',sans-serif">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">
                <span style="font-size:12px;font-weight:600;color:{TEXT}">{a.get('icon','')} {a.get('title','')}</span>
                <span style="font-size:10px;color:{MUTED}">{a.get('time','')}</span>
              </div>
              <div style="font-size:11px;color:{MUTED};margin-bottom:3px">{a.get('description','')}</div>
              <div style="display:flex;align-items:center;gap:6px">
                <div style="flex:1;height:3px;background:{BORDER};border-radius:2px;overflow:hidden">
                  <div style="width:{conf}%;height:100%;background:{color};border-radius:2px"></div>
                </div>
                <span style="font-size:10px;color:{color};font-weight:600">{conf}%</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  SIGNAL BAR + TRADE PLAN
# ═══════════════════════════════════════════════════════════════
if setup and setup.get("direction") in ("LONG", "SHORT"):
    d = setup["direction"]
    entry = setup["entry"]
    sl = setup["stop_loss"]
    rr_avg = setup.get("rr_ratios", {}).get("avg", 0)
    conf = setup.get("reliability", 0)
    quality = setup.get("quality", "")
    dc = GREEN if d == "LONG" else RED

    # Signal bar
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:16px;padding:10px 16px;background:{PANEL};border:1px solid {BORDER};border-radius:8px;margin:4px 0;font-family:'JetBrains Mono',monospace">
      <span style="background:{dc};color:#fff;font-weight:700;padding:6px 16px;border-radius:6px;font-size:14px;letter-spacing:1px">{d}</span>
      <span style="font-size:18px;font-weight:700;color:{TEXT}">{tv_sym}</span>
      <span style="color:{BORDER}">│</span>
      <span style="background:{PANEL2};padding:4px 10px;border-radius:4px;color:{ACCENT};font-weight:700;font-size:15px">R:R {rr_avg}R</span>
      <span style="background:{PANEL2};padding:4px 10px;border-radius:4px;color:{dc};font-weight:700;font-size:15px">Conf {conf}/100</span>
      <span style="background:{PANEL2};padding:4px 10px;border-radius:4px;color:{AMBER};font-size:13px">{quality}</span>
      <span style="color:{BORDER}">│</span>
      <span style="color:{MUTED}">Entry</span><span style="color:{TEXT};font-weight:600">{entry:,.2f}</span>
      <span style="color:{MUTED}">Now</span><span style="color:{GREEN if df['close'].iloc[-1]>=entry else RED};font-weight:600">{df['close'].iloc[-1]:,.2f}</span>
      <span style="color:{MUTED}">SL</span><span style="color:{RED}">{sl:,.2f}</span>
      <span style="color:{MUTED}">Risk</span><span style="color:{RED}">${setup['risk_amount']:.0f}</span>
    </div>
    """, unsafe_allow_html=True)

    # Two columns: Trade Plan + Scenarios / Structural
    plan_col, struct_col = st.columns([3, 2], gap="small")

    with plan_col:
        st.markdown(sec_title("TRADE PLAN", ACCENT), unsafe_allow_html=True)

        # Master plan table
        plan_rows = []
        for tp in setup.get("take_profits", []):
            plan_rows.append({"Exit": tp["level"], "Type": "TP", "Price": f"{tp['price']:,.2f}", "R": f"+{tp['r_multiple']}R", "$": f"${tp['pnl_dollar']:+.0f}", "%": f"{tp['pnl_pct']:+.1f}%", "Pos": f"{tp['pct_of_position']}%"})
        for sl in setup.get("partial_stops", []):
            plan_rows.append({"Exit": sl["level"], "Type": "SL", "Price": f"{sl['price']:,.2f}", "R": f"-{sl['r_from_entry']}R", "$": f"-${sl['loss_dollar']:.0f}", "%": f"{sl['loss_pct']:.1f}%", "Pos": f"{sl['pct_of_position']}%"})

        if plan_rows:
            st.dataframe(pd.DataFrame(plan_rows), use_container_width=True, hide_index=True, height=30 + len(plan_rows) * 28)

        # Totals
        capital = setup["daily_capital"]
        st.markdown(f"""
        <div style="display:flex;gap:16px;font-size:12px;font-family:'JetBrains Mono',monospace;padding:4px 8px;background:{PANEL};border:1px solid {BORDER};border-radius:4px">
          <span style="color:{GREEN}">All TP: <b>${setup['total_tp_pnl']:+.0f}</b> ({setup['total_tp_pnl']/capital*100:+.1f}%)</span>
          <span style="color:{RED}">All SL: <b>-${setup['total_sl_loss']:.0f}</b> (-{setup['total_sl_loss']/capital*100:.1f}%)</span>
        </div>
        """, unsafe_allow_html=True)

        # Scenarios
        sc = setup.get("scenarios", {})
        base_pnl = setup["total_tp_pnl"] * 0.5
        base_pct = base_pnl / capital * 100 if capital > 0 else 0
        sc_rows = [
            {"Case": "BEST", "$": f"${sc.get('best_case',{}).get('pnl',0):+.0f}", "%": f"{sc.get('best_case',{}).get('pct',0):+.1f}%", "Cap": f"${sc.get('best_case',{}).get('new_capital',capital):,.0f}"},
            {"Case": "BASE", "$": f"${base_pnl:+.0f}", "%": f"{base_pct:+.1f}%", "Cap": f"${capital + base_pnl:,.0f}"},
            {"Case": "WORST", "$": f"${sc.get('worst_case',{}).get('pnl',0):+.0f}", "%": f"{sc.get('worst_case',{}).get('pct',0):+.1f}%", "Cap": f"${sc.get('worst_case',{}).get('new_capital',capital):,.0f}"},
        ]
        st.markdown(sec_title("SCENARIOS", AMBER), unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(sc_rows), use_container_width=True, hide_index=True, height=114)

    with struct_col:
        # Structural Levels
        st.markdown(sec_title("STRUCTURAL LEVELS", ACCENT), unsafe_allow_html=True)
        sr_rows = []
        fib_info = setup.get("fib_nearest", {})
        if fib_info.get("nearest"):
            sr_rows.append({"Type": "Fib", "Price": f"{fib_info['nearest']:,.2f}", "Dist": f"{fib_info['distance_pct']:.2f}%", "Info": fib_info.get("level", "")})
        for s in setup.get("support_resistance", [])[:3]:
            sr_rows.append({"Type": s["type"][:3].upper(), "Price": f"{s['price']:,.2f}", "Dist": "", "Info": f"{s['touches']}x str:{s['strength']}"})
        for t in setup.get("trendlines", [])[:2]:
            p = t.get("support_price") or t.get("resistance_price") or 0
            sr_rows.append({"Type": "TL", "Price": f"{p:,.2f}", "Dist": "", "Info": f"{t['type']} conf:{t['confidence']:.0%}"})
        for z in setup.get("confluence_zones", [])[:2]:
            sr_rows.append({"Type": "Confl", "Price": f"{z['price']:,.2f}", "Dist": "", "Info": f"str:{z['strength']} {', '.join(z['levels'][:2])}"})
        if sr_rows:
            st.dataframe(pd.DataFrame(sr_rows), use_container_width=True, hide_index=True, height=30 + len(sr_rows) * 28)

        # Similar Patterns
        similar = st.session_state.get("similar_patterns", [])
        pstats = st.session_state.get("pattern_stats", {})
        if similar:
            st.markdown(sec_title(f"PATTERN MATCH ({len(similar)} similar)", AMBER), unsafe_allow_html=True)
            rows = []
            for r in similar[:5]:
                pnl = r.get("total_pnl", 0)
                rows.append({"Date": r.get("entry_time", "")[:10], "Dir": r.get("direction", ""), "P/L": f"${pnl:+.0f}", "R": f"{r.get('r_multiple', 0):.1f}R", "Match": f"{r.get('similarity', 0):.0f}%"})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            if pstats:
                st.caption(f"Historical: {pstats['win_rate']}% win | Avg P/L: {pstats['avg_pnl']:+.2f}% | Avg R: {pstats['avg_r']:.1f}R ({pstats['count']} trades)")

# ═══════════════════════════════════════════════════════════════
#  MTF TABLE
# ═══════════════════════════════════════════════════════════════
if mtf and mtf.get("results"):
    st.markdown(sec_title("MULTI-TIMEFRAME ANALYSIS", ACCENT), unsafe_allow_html=True)
    rows = []
    for tf in mtf.get("timeframes", []):
        res = mtf["results"].get(tf)
        if not res: continue
        trend = res.get("trend", {})
        direction = trend.get("direction", "NEUTRAL")
        bk = res.get("breakout", {})
        bk_type = bk.get("type", "") if bk else ""
        bk_info = f"{bk['detail']}" if bk_type and bk_type != "none" else "—"
        rows.append({"TF": tf, "Dir": direction, "Conf": f"{trend.get('confidence', 0):.0%}", "Breakout": bk_info, "Bars": res.get("bars", 0), "Close": f"{res.get('last_close', 0):,.2f}" if res.get("last_close") else "—"})
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=30 + len(rows) * 28)

    cons = mtf.get("consensus", {})
    mdir = cons.get("direction", "NEUTRAL")
    mc = GREEN if mdir == "LONG" else RED if mdir == "SHORT" else MUTED
    align = cons.get("aligned", 0)
    total = cons.get("total", 0)
    strength = cons.get("strength", 0)
    active = cons.get("active_breakouts", [])

    consensus_html = f'<div style="font-size:12px;color:{MUTED};padding:6px 10px;background:{PANEL};border:1px solid {BORDER};border-radius:4px;font-family:\'JetBrains Mono\',monospace">'
    consensus_html += f'<span style="color:{mc};font-weight:700">{mdir}</span> '
    consensus_html += f'<span style="color:{MUTED}">│</span> Strength: {strength:.0%} '
    consensus_html += f'<span style="color:{MUTED}">│</span> Aligned: {align}/{total}'
    if active:
        for b in active:
            consensus_html += f' <span style="color:{AMBER}">│ ⚡ {b["tf"]} {b["type"]}</span>'
    consensus_html += '</div>'
    st.markdown(consensus_html, unsafe_allow_html=True)

    # ── PLAN THEO TỪNG KHUNG (card riêng cho mỗi timeframe) ──
    render_tf_plans(mtf)

    # ── ACTION PLAN (phương án xử lý toàn khung) ──
    plan = build_action_plan(mtf, setup)
    pb = plan["bias"]
    pc = GREEN if pb == "LONG" else RED if pb == "SHORT" else MUTED
    ser = plan.get("series", {})

    def _sd(x):
        c = GREEN if x == "LONG" else RED if x == "SHORT" else MUTED
        return f'<span style="color:{c};font-weight:600">{x}</span>'

    plan_html = sec_title("ACTION PLAN — PHƯƠNG ÁN XỬ LÝ", AMBER) + '</div>'[0:0]
    plan_html += f'<div style="background:{PANEL};border:1px solid {BORDER};border-radius:6px;padding:10px 12px;font-size:12px;line-height:1.75;font-family:\'JetBrains Mono\',monospace">'
    plan_html += f'<div style="margin-bottom:4px">Bias <span style="color:{pc};font-weight:700">{pb}</span>'
    if ser:
        plan_html += f' <span style="color:{BORDER}">│</span> HTF {_sd(ser.get("HTF", "NEUTRAL"))} · MID {_sd(ser.get("MID", "NEUTRAL"))} · STF {_sd(ser.get("STF", "NEUTRAL"))}'
    plan_html += '</div>'
    for s in plan.get("steps", []):
        plan_html += f'<div style="color:{TEXT}">▸ {s}</div>'
    for c in plan.get("confluence", []):
        plan_html += f'<div style="color:{GREEN}">● {c}</div>'
    for c in plan.get("conflicts", []):
        plan_html += f'<div style="color:{RED}">⚠ {c}</div>'
    plan_html += '</div>'
    st.markdown(plan_html, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  DAILY CAPITAL + TRADE HISTORY
# ═══════════════════════════════════════════════════════════════
dc_info = st.session_state.daily_capital
if dc_info:
    daily = dc_info.get_summary()
    if daily:
        pnl = daily.get("daily_pnl", 0)
        pnl_color = GREEN if pnl >= 0 else RED
        can_trade = daily.get("can_trade", True)
        can_color = GREEN if can_trade else RED

        st.markdown(sec_title("DAILY CAPITAL", ACCENT), unsafe_allow_html=True)
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:20px;padding:8px 12px;background:{PANEL};border:1px solid {BORDER};border-radius:6px;font-family:'JetBrains Mono',monospace;font-size:12px">
          <span><span style="color:{MUTED}">Capital</span> <span style="color:{TEXT};font-weight:600;font-size:14px">${daily.get('current_capital',0):,.0f}</span></span>
          <span><span style="color:{MUTED}">P/L</span> <span style="color:{pnl_color};font-weight:600">${pnl:+,.0f} ({daily.get('daily_pnl_pct',0):+.1f}%)</span></span>
          <span><span style="color:{MUTED}">Trades</span> <span style="color:{TEXT}">{daily.get('wins',0)}W / {daily.get('losses',0)}L</span></span>
          <span><span style="color:{MUTED}">Win%</span> <span style="color:{TEXT}">{daily.get('win_rate',0)}%</span></span>
          <span><span style="color:{MUTED}">Status</span> <span style="color:{can_color};font-weight:600">{'CAN TRADE' if can_trade else 'STOPPED'}</span></span>
        </div>
        """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  TABS: Signals, Stats, Backtest, Log
# ═══════════════════════════════════════════════════════════════
t1, t2, t3, t4 = st.tabs(["📊 Signals", "📈 Statistics", "🔬 Backtest", "📋 Log"])

with t1:
    sig_rows = []
    if setup and setup.get("direction") in ("LONG", "SHORT"):
        d = setup["direction"]
        entry = setup["entry"]
        now_price = df["close"].iloc[-1]
        sig_rows.append({"Time": time.strftime("%d-%m %H:%M"), "Symbol": tv_sym, "Dir": d, "Entry": f"{entry:,.2f}", "Now": f"{now_price:,.2f}", "SL": f"{setup['stop_loss']:,.2f}", "TP": f"{setup.get('take_profits', [{}])[0].get('price', 0):,.2f}" if setup.get('take_profits') else "—", "R:R": f"1:{setup.get('rr_ratios',{}).get('avg',0)}", "Conf": f"{setup.get('reliability',0)}"})
    if mtf and mtf.get("results"):
        for tf in mtf.get("timeframes", [])[:3]:
            res = mtf["results"].get(tf)
            if not res: continue
            tdir = res["trend"]["direction"]
            if tdir == "NEUTRAL": continue
            sig_rows.append({"Time": time.strftime("%d-%m %H:%M"), "Symbol": tv_sym, "Dir": tdir, "Entry": f"{res.get('last_close',0):,.2f}", "Now": f"{res.get('last_close',0):,.2f}", "SL": "—", "TP": "—", "R:R": "—", "Conf": f"{res['trend'].get('confidence',0):.0%}"})
    if sig_rows:
        st.dataframe(pd.DataFrame(sig_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No signals. Click ▶ PHÂN TÍCH to analyze.")

with t2:
    if stats:
        stat_rows = [{"Metric": k, "Value": f"{v:.4f}" if isinstance(v, float) else str(v)} for k, v in list(stats.items())[:20]]
        st.dataframe(pd.DataFrame(stat_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Run analysis to see statistics.")

with t3:
    if backtest and not backtest.get("error"):
        best = backtest.get("best", {})
        if best and not best.get("error"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Strategy", best.get('strategy', ''))
            c2.metric("Return", f"{best.get('return_pct',0):.1f}%")
            c3.metric("Win Rate", f"{best.get('win_rate',0):.1f}%")
            c4.metric("Sharpe", f"{best.get('sharpe_ratio',0):.2f}")

            # Equity curve
            eq = best.get("equity_curve", [])
            if eq:
                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(y=eq, name="Strategy", line=dict(color=ACCENT, width=2), fill="tozeroy", fillcolor="rgba(59,130,246,0.1)"))
                fig_eq.update_layout(template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=PANEL, font=dict(color=TEXT), height=250, margin=dict(l=0,r=0,t=30,b=0), title="Equity Curve")
                st.plotly_chart(fig_eq, use_container_width=True, config={"scrollZoom": True, "displaylogo": False})
        else:
            st.info("No backtest results.")
    else:
        st.info("Run backtest to see results.")

with t4:
    logs = st.session_state.activity_log
    if logs:
        for ts, msg, icon in logs[:15]:
            st.markdown(f"""<div style="display:flex;gap:8px;font-size:12px;font-family:'JetBrains Mono',monospace;padding:2px 0;border-bottom:1px solid {BORDER}"><span style="color:{MUTED}">{ts}</span><span>{icon}</span><span style="color:{TEXT}">{msg}</span></div>""", unsafe_allow_html=True)
    else:
        st.info("No activity yet.")
