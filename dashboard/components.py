"""
Shared Dashboard Components — v2 Professional TradingView-style UI
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import time


# ═══════════════════════════════════════════════════════════════
#  COLORS
# ═══════════════════════════════════════════════════════════════
BG_DARK = "#0b0e14"
BG_SIDEBAR = "#131722"
BG_CARD = "#131722"
BORDER = "#1e222d"
TEXT_PRIMARY = "#d1d4dc"
TEXT_SECONDARY = "#787b86"
GREEN = "#089981"
RED = "#f23645"
TEAL = "#14b8a6"
BLUE = "#2962ff"
YELLOW = "#ffb02e"
ORANGE = "#f97316"


def _dir_color(d: str) -> str:
    return {
        "LONG": GREEN, "SHORT": RED, "NEUTRAL": TEXT_SECONDARY,
        "BULLISH": GREEN, "BEARISH": RED,
        "STRONG BUY": GREEN, "BUY": GREEN,
        "STRONG SELL": RED, "SELL": RED,
    }.get(d, TEXT_SECONDARY)


def _dir_icon(d: str) -> str:
    return {"LONG": "🟢", "SHORT": "🔴", "NEUTRAL": "🟡",
            "BULLISH": "🟢", "BEARISH": "🔴"}.get(d, "⚪")


def _trend_arrow(t: str) -> str:
    return {"up": "▲", "down": "▼", "flat": "—"}.get(t, "—")


def _trend_color(t: str) -> str:
    return {"up": GREEN, "down": RED, "flat": TEXT_SECONDARY}.get(t, TEXT_SECONDARY)


def _first_tp(setup) -> float:
    """First take-profit price from the new partial-TP list."""
    if not setup:
        return 0.0
    tps = setup.get("take_profits") or []
    if tps and tps[0].get("price") is not None:
        return float(tps[0]["price"])
    # fallback for legacy keys
    return float(setup.get("take_profit_2r") or 0.0)


# ═══════════════════════════════════════════════════════════════
#  HEADER BAR
# ═══════════════════════════════════════════════════════════════
def render_header_bar(active_tab: str = "Biểu đồ", refresh_sec: int = 15,
                      last_refresh_ts: float = None, data_source: str = "TradingView") -> None:
    elapsed = time.time() - last_refresh_ts if last_refresh_ts else 0
    remaining = max(0, int(refresh_sec - elapsed))

    tabs = ["OVERVIEW", "CHART", "AI", "ALERTS", "POSITIONS", "SETTINGS"]
    tabs_html = ""
    for t in tabs:
        if t.lower() == active_tab.lower() or (active_tab == "Biểu đồ" and t == "CHART"):
            tabs_html += f'<span style="color:#2962ff;border-bottom:2px solid #2962ff;padding:0 8px;font-size:12px;font-weight:600;letter-spacing:0.5px">{t}</span>'
        else:
            tabs_html += f'<span style="color:#565b66;padding:0 8px;font-size:12px;letter-spacing:0.5px;cursor:pointer">{t}</span>'

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 12px;background:#131722;border-bottom:1px solid #1e222d;margin:-0.25rem -0.5rem 0.2rem -0.5rem;font-family:JetBrains Mono,monospace;">
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="color:#2962ff;font-size:14px;font-weight:700;">TV</span>
        <span style="color:#565b66;font-size:11px;">ANALYZER</span>
      </div>
      <div style="display:flex;align-items:center;gap:0;">{tabs_html}</div>
      <div style="display:flex;align-items:center;gap:8px;font-size:11px;">
        <span style="color:{"#089981" if remaining > 5 else "#f23645"};">●</span>
        <span style="color:#787b86;">{data_source}</span>
        <span style="color:#d1d4dc;font-family:JetBrains Mono,monospace;">{remaining:02d}s</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  WATCHLIST (sidebar) — compact native widgets
# ═══════════════════════════════════════════════════════════════
def render_watchlist(watchlist_data: list, active_cat: str = "all") -> None:
    filtered = [d for d in watchlist_data if active_cat == "all" or d.get("cat") == active_cat]

    if not filtered:
        st.sidebar.caption("No data")
        return

    # Header
    hdr = st.sidebar.columns([1.5, 1.1, 0.8, 0.35])
    hdr[0].markdown("<div style='font-size:11px;color:#565b66;font-weight:600;font-family:JetBrains Mono,monospace'>SYMBOL</div>", unsafe_allow_html=True)
    hdr[1].markdown("<div style='font-size:11px;color:#565b66;font-weight:600;font-family:JetBrains Mono,monospace;text-align:right'>PRICE</div>", unsafe_allow_html=True)
    hdr[2].markdown("<div style='font-size:11px;color:#565b66;font-weight:600;font-family:JetBrains Mono,monospace;text-align:right'>CHG</div>", unsafe_allow_html=True)
    hdr[3].markdown("<div style='font-size:11px;color:#565b66;text-align:center'>··</div>", unsafe_allow_html=True)

    for d in filtered[:12]:
        price = f"{d['price']:,.2f}" if d.get("price") else "—"
        chg = d.get("change_pct", 0)
        chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
        arrow = _trend_arrow(d.get("trend"))
        icon = d.get("icon", "")
        sym = d.get("symbol", "")
        chg_color = "#089981" if chg >= 0 else "#f23645"

        row = st.sidebar.columns([1.5, 1.1, 0.8, 0.35])
        row[0].markdown(f"<div style='font-size:12px;color:#d1d4dc;font-family:JetBrains Mono,monospace'>{icon}{sym}</div>", unsafe_allow_html=True)
        row[1].markdown(f"<div style='font-size:12px;color:#e8eaed;font-family:JetBrains Mono,monospace;text-align:right'>{price}</div>", unsafe_allow_html=True)
        row[2].markdown(f"<div style='font-size:12px;color:{chg_color};font-family:JetBrains Mono,monospace;text-align:right'>{chg_str}</div>", unsafe_allow_html=True)
        row[3].markdown(f"<div style='font-size:12px;color:{chg_color};text-align:center'>{arrow}</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  CHART HEADER STRIP
# ═══════════════════════════════════════════════════════════════
def render_chart_header(symbol: str, interval: str, df: pd.DataFrame, signals: dict = None) -> None:
    latest = df.iloc[-1] if df is not None and not df.empty else None
    prev = df.iloc[-2] if df is not None and len(df) > 1 else latest
    if latest is None:
        return

    close = float(latest["close"])
    change = close - float(prev["close"]) if prev is not None else 0
    change_pct = (change / float(prev["close"]) * 100) if prev is not None and float(prev["close"]) else 0
    chg_color = "#089981" if change >= 0 else "#f23645"

    tv_symbol = symbol.split(":")[-1] if ":" in symbol else symbol

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;padding:3px 6px;background:#131722;border:1px solid #1e222d;border-radius:3px;margin-bottom:2px;font-family:JetBrains Mono,monospace;">
      <span style="font-size:13px;font-weight:700;color:#e8eaed;">{tv_symbol}</span>
      <span style="background:#1e222d;padding:1px 5px;border-radius:2px;color:#787b86;font-size:11px;">{interval}</span>
      <span style="color:#565b66;font-size:11px;">O <span style="color:#d1d4dc">{latest['open']:,.2f}</span></span>
      <span style="color:#565b66;font-size:11px;">H <span style="color:#089981">{latest['high']:,.2f}</span></span>
      <span style="color:#565b66;font-size:11px;">L <span style="color:#f23645">{latest['low']:,.2f}</span></span>
      <span style="color:#565b66;font-size:11px;">C <span style="color:#e8eaed">{close:,.2f}</span></span>
      <span style="color:{chg_color};font-size:11px;font-weight:600;">{change:+,.2f} ({change_pct:+.2f}%)</span>
      <span style="color:#565b66;font-size:11px;margin-left:auto;">{len(df)} bars</span>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  STACKED CHART (upgraded with BUY/SELL markers)
# ═══════════════════════════════════════════════════════════════
def render_stacked_chart(
    df: pd.DataFrame,
    title: str = "Price Chart",
    show_rsi: bool = True,
    show_macd: bool = True,
    show_volume: bool = True,
    show_bb: bool = True,
    show_sma: bool = True,
    show_ema: bool = False,
    show_stoch: bool = False,
    show_adx: bool = False,
    height: int = 600,
    setup: dict = None,
    view_bars: int = None,
    hovermode: str = "x unified",
) -> go.Figure:
    from plotly.subplots import make_subplots
    import config as cfg

    has_rsi = show_rsi and "RSI" in df.columns and df["RSI"].notna().sum() > 0
    has_macd = show_macd and "MACD.macd" in df.columns
    has_vol = show_volume and "volume" in df.columns
    has_stoch = show_stoch and "STOCH_K" in df.columns
    has_adx = show_adx and "ADX" in df.columns

    row_heights = [0.52]
    if has_vol:
        row_heights.append(0.10)
    if has_rsi:
        row_heights.append(0.12)
    if has_macd:
        row_heights.append(0.13)
    if has_stoch:
        row_heights.append(0.10)
    if has_adx:
        row_heights.append(0.10)
    total_rows = len(row_heights)
    row_sum = sum(row_heights)
    if row_sum > 0:
        row_heights = [h / row_sum for h in row_heights]

    fig = make_subplots(
        rows=total_rows, cols=1, shared_xaxes=True,
        vertical_spacing=0.015, row_heights=row_heights,
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="OHLC",
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    ), row=1, col=1)

    # Current price tag
    close_s = df["close"].dropna()
    if not close_s.empty:
        last_t = df.index[-1]
        last_p = float(close_s.iloc[-1])
        fig.add_hline(y=last_p, line_dash="dot", line_color="#FFD54F",
                      line_width=1, opacity=0.75, row=1, col=1)
        fig.add_trace(go.Scatter(
            x=[last_t], y=[last_p], mode="markers",
            marker=dict(color="#FFD54F", size=7, symbol="circle"),
            name="Giá hiện tại", showlegend=False,
        ), row=1, col=1)
        fig.add_annotation(
            x=last_t, y=last_p, text=f"  {last_p:,.2f}",
            showarrow=False, xanchor="left",
            font=dict(color="#FFD54F", size=11),
            bgcolor="#131722", row=1, col=1,
        )

    # BUY/SELL markers from setup
    if setup:
        price = float(close_s.iloc[-1]) if not close_s.empty else (setup.get("price") or 0)
        d = setup.get("direction", "NEUTRAL")
        entry = setup.get("entry")
        sl = setup.get("stop_loss")
        tps = setup.get("take_profits") or []

        if sl is not None:
            fig.add_hline(y=float(sl), line_dash="dash", line_color=RED,
                          line_width=1.2, opacity=0.85, row=1, col=1)
            fig.add_annotation(x=df.index[-1], y=float(sl),
                               text=f"  SL: {float(sl):,.2f}", showarrow=False,
                               xanchor="left", font=dict(color=RED, size=10),
                               bgcolor="#131722", row=1, col=1)
        tp_colors = [GREEN, TEAL, "#ffb02e", BLUE]
        for i, tp in enumerate(tps[:4]):
            tp_price = tp.get("price")
            if tp_price is None:
                continue
            fig.add_hline(y=float(tp_price), line_dash="dash",
                          line_color=tp_colors[i % len(tp_colors)],
                          line_width=1, opacity=0.8, row=1, col=1)
            fig.add_annotation(x=df.index[-1], y=float(tp_price),
                               text=f"  {tp.get('level', 'TP')}: {float(tp_price):,.2f}",
                               showarrow=False, xanchor="left",
                               font=dict(color=tp_colors[i % len(tp_colors)], size=10),
                               bgcolor="#131722", row=1, col=1)

        # BUY/SELL signal markers on last candle
        if d in ("LONG", "SHORT") and entry is not None:
            marker_color = GREEN if d == "LONG" else RED
            marker_symbol = "triangle-up" if d == "LONG" else "triangle-down"
            fig.add_trace(go.Scatter(
                x=[df.index[-1]], y=[float(entry)],
                mode="markers",
                marker=dict(color=marker_color, size=14, symbol=marker_symbol),
                name=f"{'BUY' if d=='LONG' else 'SELL'} Signal",
                showlegend=False,
            ), row=1, col=1)

    # SMA overlays
    if show_sma:
        colors = {"SMA_20": "#3b82f6", "SMA_50": "#f97316", "SMA_200": "#a855f7"}
        for col, color in colors.items():
            if col in df.columns and df[col].notna().sum() > 0:
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[col], name=col,
                    line=dict(color=color, width=1),
                ), row=1, col=1)

    # EMA overlays
    if show_ema:
        for col in sorted(c for c in df.columns if c.startswith("EMA_")):
            if df[col].notna().sum() > 0:
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[col], name=col,
                    line=dict(color="#4CAF50", width=1, dash="dot"),
                ), row=1, col=1)

    # Bollinger Bands
    if show_bb:
        bbu = [c for c in df.columns if c.startswith("BBU") or "BB.upper" in c]
        bbl = [c for c in df.columns if c.startswith("BBL") or "BB.lower" in c]
        if bbu and bbl:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[bbu[0]],
                line=dict(color="#64748b", width=0.5), name="BB Upper", showlegend=False,
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df.index, y=df[bbl[0]],
                line=dict(color="#64748b", width=0.5), name="BB Lower", showlegend=False,
                fill="tonexty", fillcolor="rgba(100,116,139,0.06)",
            ), row=1, col=1)

    next_row = 2

    # Volume
    if has_vol:
        v_colors = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(df["close"], df["open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["volume"], marker_color=v_colors,
            name="Volume", showlegend=False,
        ), row=next_row, col=1)
        next_row += 1

    # RSI
    if has_rsi:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["RSI"], name="RSI",
            line=dict(color="#E040FB", width=1.2),
        ), row=next_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color=RED, opacity=0.4, row=next_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color=GREEN, opacity=0.4, row=next_row, col=1)
        fig.update_yaxes(range=[0, 100], row=next_row, col=1)
        next_row += 1

    # MACD
    if has_macd:
        hist = df["MACD.hist"].fillna(0) if "MACD.hist" in df.columns else df["MACD.macd"] * 0
        m_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in hist]
        fig.add_trace(go.Bar(
            x=df.index, y=hist, marker_color=m_colors,
            name="Histogram", showlegend=False,
        ), row=next_row, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MACD.macd"], name="MACD",
            line=dict(color="#3b82f6", width=1.2),
        ), row=next_row, col=1)
        if "MACD.signal" in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["MACD.signal"], name="Signal",
                line=dict(color="#f97316", width=1.2),
            ), row=next_row, col=1)
        next_row += 1

    # Stochastic
    if has_stoch:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["STOCH_K"], name="Stoch %K",
            line=dict(color="#3b82f6", width=1),
        ), row=next_row, col=1)
        if "STOCH_D" in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["STOCH_D"], name="Stoch %D",
                line=dict(color="#f97316", width=1),
            ), row=next_row, col=1)
        fig.add_hline(y=80, line_dash="dash", line_color=RED, opacity=0.3, row=next_row, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color=GREEN, opacity=0.3, row=next_row, col=1)
        fig.update_yaxes(range=[0, 100], row=next_row, col=1)
        next_row += 1

    # ADX
    if has_adx:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["ADX"], name="ADX",
            line=dict(color="#eab308", width=1.2),
        ), row=next_row, col=1)
        fig.add_hline(y=25, line_dash="dash", line_color="#64748b", opacity=0.4, row=next_row, col=1)

    # Layout
    fig.update_layout(
        height=height, xaxis_rangeslider_visible=False,
        template="plotly_dark", paper_bgcolor="#0b0e14", plot_bgcolor="#131722",
        font=dict(color="white", family="Inter, sans-serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0.01,
                    font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=40, r=10, t=10, b=0),
        hovermode=hovermode,
    )
    for r in range(1, total_rows + 1):
        fig.update_xaxes(gridcolor="#1e222d", row=r, col=1)
        fig.update_yaxes(gridcolor="#1e222d", row=r, col=1)
    if total_rows > 1:
        for r in range(1, total_rows):
            fig.update_xaxes(showticklabels=False, row=r, col=1)

    if view_bars is None:
        view_bars = getattr(cfg, "CHART_VIEW_BARS", 150)
    if len(df.index) > view_bars:
        fig.update_xaxes(range=[df.index[-view_bars], df.index[-1]], row=total_rows, col=1)

    return fig


# ═══════════════════════════════════════════════════════════════
#  ALERT CARDS — horizontal strip across screen
# ═══════════════════════════════════════════════════════════════
def render_alert_cards(alerts: list, max_show: int = 4) -> None:
    if not alerts:
        return

    shown = alerts[:max_show]
    cols = st.columns(len(shown), gap="small")

    for col, a in zip(cols, shown):
        icon = a.get("icon", "")
        title = a.get("title", "")
        ts = a.get("time", "")
        desc = a.get("description", "")
        conf = a.get("confidence", 0)
        color = a.get("color", "#787b86")

        with col:
            st.markdown(f"""
            <div style="padding:8px 12px;background:#131722;border:1px solid #1e222d;border-left:3px solid {color};border-radius:6px;font-family:'Inter','Segoe UI',sans-serif;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">
                <span style="font-size:13px;font-weight:600;color:#e8eaed">{icon} {title}</span>
                <span style="font-size:11px;color:#787b86">{ts}</span>
              </div>
              <div style="font-size:12px;color:#787b86;margin-bottom:3px">{desc}</div>
              <div style="display:flex;align-items:center;gap:8px;">
                <div style="flex:1;height:4px;background:#1e222d;border-radius:2px;overflow:hidden">
                  <div style="width:{conf}%;height:100%;background:{color};border-radius:2px"></div>
                </div>
                <span style="font-size:11px;color:{color};font-weight:600;white-space:nowrap">{conf}%</span>
              </div>
            </div>
            """, unsafe_allow_html=True)


def render_market_status(mtf: dict, breadth: dict = None, watchlist_data: list = None) -> None:
    st.markdown("<div style=\"font-size:13px;color:#2962ff;font-weight:600;letter-spacing:0.5px;margin-bottom:2px\">MARKET STATUS</div>", unsafe_allow_html=True)
    mdir = "NEUTRAL"
    strength = 50
    if mtf and mtf.get("consensus"):
        mdir = mtf["consensus"].get("direction", "NEUTRAL")
        strength = int(mtf["consensus"].get("strength", 0.5) * 100)
    if breadth:
        strength = breadth.get("trend_strength", strength)
    dir_label = {"BULLISH": "BULLISH", "BEARISH": "BEARISH", "NEUTRAL": "NEUTRAL"}.get(mdir, "NEUTRAL")
    dir_color = "#089981" if mdir == "BULLISH" else "#f23645" if mdir == "BEARISH" else "#787b86"

    with st.container(border=True):
        st.markdown(f"<div style=\"font-family:JetBrains Mono,monospace;font-size:0.8rem;color:{dir_color};font-weight:700\">&#x25b2; {dir_label}</div>", unsafe_allow_html=True)
        if mtf and mtf.get("results"):
            tf_labels = {"1m": "1m", "5m": "5m", "15m": "15m", "1H": "1H", "4H": "4H", "1D": "1D"}
            for tf in mtf.get("timeframes", []):
                res = mtf["results"].get(tf)
                if not res:
                    continue
                tdir = res["trend"]["direction"]
                tc = "#089981" if tdir == "LONG" else "#f23645" if tdir == "SHORT" else "#565b66"
                st.markdown(f"<div style=\"font-size:13px;color:#787b86;font-family:JetBrains Mono,monospace\"> {tf_labels.get(tf, tf)} <span style=\"color:{tc}\">{tdir}</span></div>", unsafe_allow_html=True)
        st.progress(strength / 100)
        st.caption(f"Strength: {strength}%")


def render_ai_suggestion(setup: dict, symbol: str) -> None:
    st.markdown("<div style=\"font-size:13px;color:#2962ff;font-weight:600;letter-spacing:0.5px;margin-bottom:2px\">AI STRATEGY</div>", unsafe_allow_html=True)
    if not setup:
        st.caption("Click RUN to analyze")
        return
    d = setup.get("direction", "NEUTRAL")
    conf = setup.get("reliability", 0)
    reasons = setup.get("reasons", [])
    tv_sym = symbol.split(":")[-1] if ":" in symbol else symbol

    with st.container(border=True):
        dir_color = "#089981" if d == "LONG" else "#f23645" if d == "SHORT" else "#787b86"
        st.markdown(f"<div style=\"font-family:JetBrains Mono,monospace\"><span style=\"color:{dir_color};font-weight:700\">{d}</span> <span style=\"color:#565b66\">|</span> <span style=\"color:#787b86\">{tv_sym}</span></div>", unsafe_allow_html=True)
        for r in reasons[:3]:
            st.markdown(f"<div style=\"font-size:13px;color:#787b86\">&#x2713; {r}</div>", unsafe_allow_html=True)
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div style=\"font-size:12px;color:#565b66\">ENTRY</div><div style=\"font-family:JetBrains Mono,monospace;font-size:15px;color:#e8eaed\">{setup.get('entry',0):,.2f}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div style=\"font-size:12px;color:#565b66\">SL</div><div style=\"font-family:JetBrains Mono,monospace;font-size:15px;color:#f23645\">{setup.get('stop_loss',0):,.2f}</div>", unsafe_allow_html=True)
        c3.markdown(f"<div style=\"font-size:12px;color:#565b66\">TP</div><div style=\"font-family:JetBrains Mono,monospace;font-size:15px;color:#089981\">{_first_tp(setup):,.2f}</div>", unsafe_allow_html=True)
        st.progress(conf / 100)
        st.caption(f"Confidence: {conf}")


def render_realtime_feed(logs: list, max_show: int = 6) -> None:
    st.markdown("<div style=\"font-size:13px;color:#2962ff;font-weight:600;letter-spacing:0.5px;margin-bottom:2px\">LOG</div>", unsafe_allow_html=True)
    if not logs:
        st.caption("No entries")
        return
    with st.container(border=True):
        for ts, msg, icon in logs[:max_show]:
            c1, c2 = st.columns([1, 5])
            c1.caption(ts)
            c2.caption(f"{icon} {msg}")


def render_bottom_table(df: pd.DataFrame, setup: dict, mtf: dict,
                        stats: dict, backtest: dict, logs: list,
                        symbol: str, interval: str) -> None:
    if df is None or df.empty:
        return

    tv_sym = symbol.split(":")[-1] if ":" in symbol else symbol
    tp_first = _first_tp(setup)

    # ── Signal Summary Bar ──
    if setup and setup.get("direction") in ("LONG", "SHORT"):
        d = setup["direction"]
        dc = "#089981" if d == "LONG" else "#f23645"
        entry = setup.get("entry", 0)
        sl = setup.get("stop_loss", 0)
        rr_avg = setup.get("rr_ratios", {}).get("avg", 0)
        conf = setup.get("reliability", 0)
        now_price = setup.get("price", entry)
        pnl_pct = ((tp_first - entry) / entry * 100) if entry and tp_first else 0
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:14px;padding:7px 12px;background:#131722;border:1px solid #1e222d;border-radius:6px;margin-bottom:3px;font-family:'JetBrains Mono','Cascadia Code',Consolas,monospace;font-size:13px;">
          <span style="background:{dc};color:#0b0e14;font-weight:700;padding:3px 10px;border-radius:4px;font-size:12px">{d}</span>
          <span style="color:#787b86">Entry</span><span style="color:#e8eaed;font-weight:600">{entry:,.2f}</span>
          <span style="color:#787b86">Now</span><span style="color:{'#089981' if now_price >= entry else '#f23645'};font-weight:600">{now_price:,.2f}</span>
          <span style="color:#787b86">SL</span><span style="color:#f23645">{sl:,.2f}</span>
          <span style="color:#787b86">TP</span><span style="color:#089981">{tp_first:,.2f}</span>
          <span style="color:#787b86">R:R</span><span style="color:#ffb02e;font-weight:600">{rr_avg}R</span>
          <span style="color:#787b86">Conf</span><span style="color:{dc};font-weight:600">{conf}/100</span>
          <span style="color:#565b66">|</span>
          <span style="color:#787b86">Bars</span><span style="color:#e8eaed">{len(df)}</span>
          <span style="color:#787b86">TF</span><span style="color:#e8eaed">{interval}</span>
        </div>
        """, unsafe_allow_html=True)

    # ── Tabs ──
    t1, t2, t3 = st.tabs(["📊 Signals", "📈 Stats", "📋 Backtest"])

    with t1:
        rows = []
        if setup and setup.get("direction") in ("LONG", "SHORT"):
            rows.append({
                "Time": time.strftime("%d-%m %H:%M"),
                "Symbol": tv_sym,
                "Dir": d,
                "Entry": f"{entry:,.2f}",
                "Now": f"{now_price:,.2f}",
                "SL": f"{sl:,.2f}",
                "TP": f"{tp_first:,.2f}" if tp_first else "—",
                "R:R": f"1:{rr_avg}",
                "Conf": f"{conf}",
            })

        if mtf and mtf.get("results"):
            for tf in mtf.get("timeframes", [])[:3]:
                res = mtf["results"].get(tf)
                if not res:
                    continue
                tdir = res["trend"]["direction"]
                if tdir == "NEUTRAL":
                    continue
                rows.append({
                    "Time": time.strftime("%d-%m %H:%M"),
                    "Symbol": tv_sym,
                    "Dir": tdir,
                    "Entry": f"{res.get('last_close',0):,.2f}",
                    "Now": f"{res.get('last_close',0):,.2f}",
                    "SL": "—",
                    "TP": "—",
                    "R:R": "—",
                    "Conf": f"{res['trend'].get('confidence',0):.0%}",
                })

        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                         column_config={
                             "Time": st.column_config.TextColumn("Time", width="medium"),
                             "Symbol": st.column_config.TextColumn("Symbol", width="small"),
                             "Dir": st.column_config.TextColumn("Dir", width="small"),
                             "Entry": st.column_config.TextColumn("Entry", width="medium"),
                             "Now": st.column_config.TextColumn("Now", width="medium"),
                             "SL": st.column_config.TextColumn("SL", width="medium"),
                             "TP": st.column_config.TextColumn("TP", width="medium"),
                             "R:R": st.column_config.TextColumn("R:R", width="small"),
                             "Conf": st.column_config.TextColumn("Conf", width="small"),
                         })
        else:
            st.caption("No signals. Click ▶ Phân tích.")

    with t2:
        if stats:
            stat_rows = [{"Metric": k, "Value": f"{v:.4f}" if isinstance(v, float) else str(v)}
                         for k, v in list(stats.items())[:15]]
            st.dataframe(pd.DataFrame(stat_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No stats.")

    with t3:
        if backtest and not backtest.get("error"):
            best = backtest.get("best", {})
            if best and not best.get("error"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Strategy", best.get('strategy', ''))
                c2.metric("Return", f"{best.get('return_pct',0):.1f}%")
                c3.metric("Sharpe", f"{best.get('sharpe_ratio',0):.2f}")
            else:
                st.caption("No backtest results.")
        else:
            st.caption("No backtest run.")


def render_candlestick_chart(df, title="Price Chart", indicators=None, height=500):
    return render_stacked_chart(df, title=title, height=height, show_rsi=False, show_macd=False, show_volume=False)

def render_metric_card(label, value, delta="", color="white"):
    delta_color = "normal" if not delta else ("inverse" if delta.startswith("-") else "normal")
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)

def render_signal_badge(direction, confidence):
    icon = _dir_icon(direction)
    return f"{icon} **{direction}** ({confidence*100:.1f}%)"

def render_indicator_gauge(name, value, min_val=0, max_val=100):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        title={"text": name, "font": {"size": 14}},
        gauge={"axis": {"range": [min_val, max_val]}, "bar": {"color": "#2962ff"},
               "steps": [{"range": [min_val, min_val+(max_val-min_val)*0.3], "color": "#1a1f2b"},
                          {"range": [min_val+(max_val-min_val)*0.3, min_val+(max_val-min_val)*0.7], "color": "#1c2433"},
                          {"range": [min_val+(max_val-min_val)*0.7, max_val], "color": "#2d1b1b"}]},
    ))
    fig.update_layout(height=180, margin=dict(l=10,r=10,t=30,b=10), template="plotly_dark", paper_bgcolor="#131722")
    return fig

def render_bar_chart(labels, values, title, color="#2962ff"):
    fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker_color=color))
    fig.update_layout(title=title, template="plotly_dark", paper_bgcolor="#131722",
                      plot_bgcolor="#131722", font=dict(color="#d1d4dc"),
                      height=max(300, len(labels)*30), margin=dict(l=0,r=0,t=40,b=0))
    return fig

def render_equity_curve(dates, equity, benchmark=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=equity, name="Strategy", line=dict(color="#2962ff", width=2), fill="tozeroy", fillcolor="rgba(88,166,255,0.1)"))
    if benchmark:
        fig.add_trace(go.Scatter(x=dates, y=benchmark, name="Buy & Hold", line=dict(color="#ffb02e", width=1, dash="dash")))
    fig.update_layout(template="plotly_dark", paper_bgcolor="#131722", font=dict(color="#d1d4dc"), height=300, margin=dict(l=0,r=0,t=30,b=0))
    return fig

def render_distribution(data, title="Return Distribution"):
    fig = go.Figure(go.Histogram(x=data, nbinsx=50, marker_color="#2962ff", opacity=0.7))
    fig.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.5)
    fig.update_layout(title=title, template="plotly_dark", paper_bgcolor="#131722", font=dict(color="#d1d4dc"), height=250)
    return fig

def render_radar_chart(categories, values, title):
    fig = go.Figure(go.Scatterpolar(r=values+[values[0]], theta=categories+[categories[0]], fill="toself",
                                     fillcolor="rgba(88,166,255,0.2)", line=dict(color="#2962ff")))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0,1]), bgcolor="#131722"),
                      template="plotly_dark", paper_bgcolor="#131722", font=dict(color="#d1d4dc"), height=300, title=title, showlegend=False)
    return fig

def render_school_comparison(schools):
    names = list(schools.keys())
    conf = [schools[n]["confidence"] for n in names]
    dirs = [schools[n]["direction"] for n in names]
    colors = ["#089981" if d == "BULLISH" else "#f23645" if d == "BEARISH" else "#787b86" for d in dirs]
    fig = go.Figure(go.Bar(x=names, y=conf, marker_color=colors,
                           text=[f"{d}\n{c*100:.0f}%" for d,c in zip(dirs,conf)], textposition="outside"))
    fig.update_layout(template="plotly_dark", paper_bgcolor="#131722", font=dict(color="#d1d4dc"), height=300, yaxis=dict(range=[0,1]))
    return fig

def render_heatmap(data, title="Correlation Matrix"):
    fig = px.imshow(data, text_auto=".2f", aspect="auto", color_continuous_scale="RdYlGn", title=title)
    fig.update_layout(template="plotly_dark", paper_bgcolor="#131722", font=dict(color="#d1d4dc"), height=350)
    return fig

def render_activity_log(logs, height=200):
    if not logs:
        return
    for ts, msg, icon in logs[:20]:
        st.caption(f"{icon} `{ts}` {msg}")

def find_support_resistance(df, n=30):
    if df is None or len(df) < 5:
        return None, None
    window = df.tail(n).reset_index(drop=True)
    close = window["close"].iloc[-1]
    highs = window["high"].values
    lows = window["low"].values
    piv_h, piv_l = [], []
    for i in range(1, len(window)-1):
        if highs[i] >= highs[i-1] and highs[i] >= highs[i+1]:
            piv_h.append(highs[i])
        if lows[i] <= lows[i-1] and lows[i] <= lows[i+1]:
            piv_l.append(lows[i])
    sup = [x for x in piv_l if x < close]
    res = [x for x in piv_h if x > close]
    support = max(sup) if sup else float(lows.min())
    resistance = min(res) if res else float(highs.max())
    return float(support), float(resistance)

def render_status_header(symbol, interval, bars, realtime_on, refresh_sec, last_refresh=""):
    pass

def render_trade_setup(setup):
    if not setup:
        return
    d = setup.get("direction", "NEUTRAL")
    conf = setup.get("reliability", 0)
    dir_color = "#089981" if d == "LONG" else "#f23645" if d == "SHORT" else "#787b86"

    with st.container(border=True):
        st.markdown(f"<span style='font-family:JetBrains Mono,monospace;font-size:15px;color:{dir_color};font-weight:700'>{d}</span> <span style='font-size:13px;color:#565b66'>|</span> <span style='font-size:13px;color:#787b86'>Conf: {conf}/100</span>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div style='font-size:12px;color:#565b66'>ENTRY</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#e8eaed'>{setup.get('entry',0):,.2f}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='font-size:12px;color:#565b66'>SL</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#f23645'>{setup.get('stop_loss',0):,.2f}</div>", unsafe_allow_html=True)
        c3.markdown(f"<div style='font-size:12px;color:#565b66'>TP</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#089981'>{_first_tp(setup):,.2f}</div>", unsafe_allow_html=True)
        c4.markdown(f"<div style='font-size:12px;color:#565b66'>R:R</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#ffb02e'>1:{setup.get('rr_ratios',{}).get('avg',0):.1f}</div>", unsafe_allow_html=True)

def render_mtf_panel(mtf):
    if not mtf or not mtf.get("results"):
        return
    cons = mtf.get("consensus", {})
    mdir = cons.get("direction", "NEUTRAL")
    strength = cons.get("strength", 0)
    dir_color = "#089981" if mdir == "BULLISH" else "#f23645" if mdir == "BEARISH" else "#787b86"

    with st.container(border=True):
        st.markdown(f"<div style='font-size:13px;color:#2962ff;font-weight:600;letter-spacing:0.5px;margin-bottom:2px'>MTF</div><div style='font-family:JetBrains Mono,monospace'><span style='color:{dir_color};font-weight:700'>{mdir}</span> <span style='color:#565b66'>|</span> <span style='color:#787b86'>{strength*100:.0f}% · {cons.get('aligned',0)}/{cons.get('total',0)} tf</span></div>", unsafe_allow_html=True)

def render_analysis_panel(consensus, signals, prediction, stats, backtest, df):
    pass

def tf_label(tf):
    from core.multi_timeframe import tf_label as _label
    return _label(tf)


# ═══════════════════════════════════════════════════════════════
#  FREE API PANELS — CoinGecko, Mempool, Fear & Greed
# ═══════════════════════════════════════════════════════════════
def render_crypto_market(data: dict) -> None:
    if not data:
        return
    price = data.get("price", 0)
    change = data.get("change_24h", 0)
    mcap = data.get("market_cap", 0)
    vol = data.get("volume_24h", 0)
    chg_color = "#089981" if change >= 0 else "#f23645"

    with st.container(border=True):
        st.markdown("<div style=\"font-size:13px;color:#2962ff;font-weight:600;letter-spacing:0.5px;margin-bottom:2px\">CRYPTO</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.markdown(f"<div style='font-size:12px;color:#565b66'>PRICE</div><div style='font-family:JetBrains Mono,monospace;font-size:15px;color:#e8eaed'>${price:,.0f}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='font-size:12px;color:#565b66'>24h</div><div style='font-family:JetBrains Mono,monospace;font-size:15px;color:{chg_color}'>{change:+.2f}%</div>", unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        c3.markdown(f"<div style='font-size:12px;color:#565b66'>MCAP</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#d1d4dc'>${mcap/1e9:.1f}B</div>", unsafe_allow_html=True)
        c4.markdown(f"<div style='font-size:12px;color:#565b66'>VOL</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#d1d4dc'>${vol/1e9:.1f}B</div>", unsafe_allow_html=True)


def render_global_crypto(data: dict) -> None:
    if not data:
        return
    with st.container(border=True):
        st.markdown("<div style=\"font-size:13px;color:#2962ff;font-weight:600;letter-spacing:0.5px;margin-bottom:2px\">GLOBAL CRYPTO</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.markdown(f"<div style='font-size:12px;color:#565b66'>BTC DOM</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#ffb02e'>{data.get('btc_dominance', 0)}%</div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='font-size:12px;color:#565b66'>ETH DOM</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#787b86'>{data.get('eth_dominance', 0)}%</div>", unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        total = data.get("total_market_cap", 0)
        c3.markdown(f"<div style='font-size:12px;color:#565b66'>TOTAL</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#d1d4dc'>${total/1e12:.2f}T</div>", unsafe_allow_html=True)
        c4.markdown(f"<div style='font-size:12px;color:#565b66'>COINS</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#d1d4dc'>{data.get('active_cryptos', 0):,}</div>", unsafe_allow_html=True)


def render_mempool(data: dict) -> None:
    if not data:
        return
    tx = data.get("tx_count", 0)
    vsize = data.get("vsize_mb", 0)
    fast = data.get("fastest_fee", 0)
    mid = data.get("half_hour_fee", 0)
    slow = data.get("hour_fee", 0)

    with st.container(border=True):
        st.markdown("<div style=\"font-size:13px;color:#2962ff;font-weight:600;letter-spacing:0.5px;margin-bottom:2px\">MEMPOOL</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.markdown(f"<div style='font-size:12px;color:#565b66'>TXs</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#d1d4dc'>{tx:,}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='font-size:12px;color:#565b66'>SIZE</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#d1d4dc'>{vsize} MB</div>", unsafe_allow_html=True)
        c3, c4, c5 = st.columns(3)
        c3.markdown(f"<div style='font-size:12px;color:#565b66'>FAST</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#089981'>{fast} sat</div>", unsafe_allow_html=True)
        c4.markdown(f"<div style='font-size:12px;color:#565b66'>30MIN</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#ffb02e'>{mid} sat</div>", unsafe_allow_html=True)
        c5.markdown(f"<div style='font-size:12px;color:#565b66'>1HR</div><div style='font-family:JetBrains Mono,monospace;font-size:14px;color:#f23645'>{slow} sat</div>", unsafe_allow_html=True)


def render_fear_greed(data: dict) -> None:
    if not data:
        return
    val = data.get("value", 50)
    label = data.get("classification", "Neutral")

    if val <= 25:
        bar_color = "#f23645"
        label_text = "FEAR"
    elif val <= 45:
        bar_color = "#ffb02e"
        label_text = "FEAR"
    elif val <= 55:
        bar_color = "#787b86"
        label_text = "NEUTRAL"
    elif val <= 75:
        bar_color = "#089981"
        label_text = "GREED"
    else:
        bar_color = "#089981"
        label_text = "GREED"

    with st.container(border=True):
        st.markdown(f"<div style=\"font-size:13px;color:#2962ff;font-weight:600;letter-spacing:0.5px;margin-bottom:2px\">FEAR & GREED</div>", unsafe_allow_html=True)
        c1, c2 = st.columns([1, 2])
        c1.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:1.2rem;color:{bar_color};font-weight:700;text-align:center'>{val}</div><div style='font-size:12px;color:#787b86;text-align:center'>{label_text}</div>", unsafe_allow_html=True)
        c2.progress(val / 100)
        st.caption(f"{label}")


def render_market_overview(market_data: dict) -> None:
    if not market_data:
        return

    cg = market_data.get("coingecko", {})
    globe = market_data.get("global", {})
    pool = market_data.get("mempool", {})
    fg = market_data.get("fear_greed", {})

    is_crypto = bool(cg)

    if is_crypto:
        render_crypto_market(cg)
    render_fear_greed(fg)
    if is_crypto:
        render_global_crypto(globe)
    if pool:
        render_mempool(pool)


# ═══════════════════════════════════════════════════════════════
#  TRADE PLAN DETAILED — partial TP/SL, structural levels, scenarios
# ═══════════════════════════════════════════════════════════════
def render_trade_plan_detailed(setup: dict, symbol: str) -> None:
    if not setup:
        return

    d = setup["direction"]
    entry = setup["entry"]
    capital = setup["daily_capital"]
    dc = "#089981" if d == "LONG" else "#f23645" if d == "SHORT" else "#787b86"
    tv_sym = symbol.split(":")[-1] if ":" in symbol else symbol
    rr = setup.get("rr_ratios", {})
    rr_avg = rr.get("avg", 0)
    conf = setup.get("reliability", 0)
    quality = setup.get("quality", "")

    # ── PLAN HEADER — big badge + R:R ──
    st.markdown(f"""
    <div style="padding:10px 14px;background:#131722;border:1px solid #1e222d;border-left:4px solid {dc};border-radius:6px;margin-bottom:4px;font-family:'JetBrains Mono','Cascadia Code',Consolas,monospace">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
        <span style="background:{dc};color:#0b0e14;font-weight:700;padding:5px 14px;border-radius:4px;font-size:15px">{d}</span>
        <span style="color:#e8eaed;font-size:16px;font-weight:600">{tv_sym}</span>
      </div>
      <div style="display:flex;align-items:center;gap:16px;font-size:13px">
        <span style="background:#1e222d;padding:3px 8px;border-radius:3px;color:#2962ff;font-weight:700;font-size:14px">R:R {rr_avg}R</span>
        <span style="background:#1e222d;padding:3px 8px;border-radius:3px;color:{dc};font-weight:700;font-size:14px">Conf {conf}/100</span>
        <span style="background:#1e222d;padding:3px 8px;border-radius:3px;color:#ffb02e;font-size:13px">{quality}</span>
      </div>
      <div style="display:flex;gap:16px;font-size:13px;margin-top:4px">
        <span><span style="color:#787b86">Entry</span> <span style="color:#e8eaed;font-weight:600">{entry:,.2f}</span></span>
        <span><span style="color:#787b86">SL</span> <span style="color:#f23645;font-weight:600">{setup['stop_loss']:,.2f}</span></span>
        <span><span style="color:#787b86">Risk</span> <span style="color:#f23645">${setup['risk_amount']:.0f}</span></span>
        <span><span style="color:#787b86">Size</span> <span style="color:#e8eaed">{setup['position_size']:.2f}</span></span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── MASTER PLAN TABLE — all in one ──
    plan_rows = []
    # TP rows
    for tp in setup.get("take_profits", []):
        plan_rows.append({
            "Exit": tp["level"],
            "Type": "TP",
            "Price": f"{tp['price']:,.2f}",
            "R": f"+{tp['r_multiple']}R",
            "$": f"${tp['pnl_dollar']:+.0f}",
            "%": f"{tp['pnl_pct']:+.1f}%",
            "Pos": f"{tp['pct_of_position']}%",
        })
    # SL rows
    for sl in setup.get("partial_stops", []):
        plan_rows.append({
            "Exit": sl["level"],
            "Type": "SL",
            "Price": f"{sl['price']:,.2f}",
            "R": f"-{sl['r_from_entry']}R",
            "$": f"-${sl['loss_dollar']:.0f}",
            "%": f"{sl['loss_pct']:.1f}%",
            "Pos": f"{sl['pct_of_position']}%",
        })

    if plan_rows:
        df_plan = pd.DataFrame(plan_rows)
        n_tp = len(setup.get("take_profits", []))
        n_sl = len(setup.get("partial_stops", []))
        total_h = 30 + len(plan_rows) * 28
        st.dataframe(df_plan, use_container_width=True, hide_index=True, height=total_h)

    # ── Totals row ──
    st.markdown(f"""
    <div style="display:flex;gap:16px;font-size:12px;font-family:'JetBrains Mono',Consolas,monospace;padding:4px 8px;background:#131722;border:1px solid #1e222d;border-radius:3px;margin-top:2px">
      <span style="color:#089981">All TP: <b>${setup['total_tp_pnl']:+.0f}</b> ({setup['total_tp_pnl']/capital*100:+.1f}%)</span>
      <span style="color:#f23645">All SL: <b>-${setup['total_sl_loss']:.0f}</b> (-{setup['total_sl_loss']/capital*100:.1f}%)</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Structural Levels — compact table ──
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

    # ── Scenarios — compact ──
    sc = setup.get("scenarios", {})
    base_pnl = setup["total_tp_pnl"] * 0.5
    base_pct = base_pnl / capital * 100 if capital > 0 else 0
    sc_rows = [
        {"Case": "BEST", "$": f"${sc.get('best_case',{}).get('pnl',0):+.0f}", "%": f"{sc.get('best_case',{}).get('pct',0):+.1f}%", "Cap": f"${sc.get('best_case',{}).get('new_capital',capital):,.0f}"},
        {"Case": "BASE", "$": f"${base_pnl:+.0f}", "%": f"{base_pct:+.1f}%", "Cap": f"${capital + base_pnl:,.0f}"},
        {"Case": "WORST", "$": f"${sc.get('worst_case',{}).get('pnl',0):+.0f}", "%": f"{sc.get('worst_case',{}).get('pct',0):+.1f}%", "Cap": f"${sc.get('worst_case',{}).get('new_capital',capital):,.0f}"},
    ]
    st.dataframe(pd.DataFrame(sc_rows), use_container_width=True, hide_index=True, height=114)


# ═══════════════════════════════════════════════════════════════
#  DAILY CAPITAL PANEL
# ═══════════════════════════════════════════════════════════════
def render_daily_capital(daily: dict) -> None:
    if not daily:
        return

    st.markdown("<div style='font-size:13px;color:#2962ff;font-weight:600;letter-spacing:0.5px;margin-bottom:2px'>DAILY CAPITAL</div>", unsafe_allow_html=True)
    with st.container(border=True):
        pnl = daily.get("daily_pnl", 0)
        pnl_color = "#089981" if pnl >= 0 else "#f23645"

        c1, c2 = st.columns(2)
        c1.markdown(f"<div style='font-size:12px;color:#565b66'>CAPITAL</div><div style='font-family:JetBrains Mono;font-size:16px;color:#e8eaed'>${daily.get('current_capital', 0):,.0f}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='font-size:12px;color:#565b66'>P/L TODAY</div><div style='font-family:JetBrains Mono;font-size:16px;color:{pnl_color}'>${pnl:+,.0f} ({daily.get('daily_pnl_pct', 0):+.1f}%)</div>", unsafe_allow_html=True)

        c3, c4 = st.columns(2)
        c3.markdown(f"<div style='font-size:12px;color:#565b66'>TRADES</div><div style='font-family:JetBrains Mono;font-size:14px;color:#d1d4dc'>{daily.get('wins', 0)}W / {daily.get('losses', 0)}L ({daily.get('win_rate', 0)}%)</div>", unsafe_allow_html=True)
        can_trade = daily.get("can_trade", True)
        can_color = "#089981" if can_trade else "#f23645"
        c4.markdown(f"<div style='font-size:12px;color:#565b66'>STATUS</div><div style='font-size:14px;color:{can_color}'>{'CAN TRADE' if can_trade else 'STOPPED'}</div>", unsafe_allow_html=True)

        if daily.get("risk_budget_remaining") is not None:
            st.caption(f"Risk budget: ${daily['risk_budget_remaining']:.0f} remaining")


# ═══════════════════════════════════════════════════════════════
#  TRADE HISTORY TABLE
# ═══════════════════════════════════════════════════════════════
def render_trade_history(trades: list) -> None:
    if not trades:
        st.caption("No trades today")
        return

    rows = []
    for t in trades:
        pnl = t.get("total_pnl", 0)
        rows.append({
            "#": t.get("id", ""),
            "Dir": t.get("direction", ""),
            "Symbol": t.get("symbol", "").split(":")[-1] if ":" in t.get("symbol", "") else t.get("symbol", ""),
            "Entry": f"{t.get('entry_price', 0):,.2f}",
            "Exit": f"{t.get('exit_price', 0):,.2f}" if t.get("exit_price") else "—",
            "P/L $": f"${pnl:+.2f}",
            "P/L %": f"{t.get('total_pnl_pct', 0):+.1f}%",
            "R": f"{t.get('r_multiple', 0):.1f}R",
            "Status": t.get("status", ""),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
#  PATTERN MATCH ALERT
# ═══════════════════════════════════════════════════════════════
def render_pattern_alert(results: list, stats: dict) -> None:
    if not results:
        return

    st.markdown(f"<div style='font-size:13px;color:#ffb02e;font-weight:600;letter-spacing:0.5px;margin-bottom:2px'>PATTERN MATCH ({len(results)} similar)</div>", unsafe_allow_html=True)
    with st.container(border=True):
        rows = []
        for r in results[:5]:
            pnl = r.get("total_pnl", 0)
            rows.append({
                "Date": r.get("entry_time", "")[:10],
                "Dir": r.get("direction", ""),
                "P/L": f"${pnl:+.0f}",
                "R": f"{r.get('r_multiple', 0):.1f}R",
                "Match": f"{r.get('similarity', 0):.0f}%",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if stats:
            st.caption(f"Historical: {stats['win_rate']}% win rate | Avg P/L: {stats['avg_pnl']:+.2f}% | Avg R: {stats['avg_r']:.1f}R ({stats['count']} trades)")


# ═══════════════════════════════════════════════════════════════
#  MTF TABLE — per-TF analysis
# ═══════════════════════════════════════════════════════════════
def render_mtf_table(mtf: dict) -> None:
    if not mtf or not mtf.get("results"):
        return

    st.markdown("<div style='font-size:12px;color:#2962ff;font-weight:700;margin:2px 0 1px'>MULTI-TIMEFRAME ANALYSIS</div>", unsafe_allow_html=True)

    # Per-TF rows
    rows = []
    for tf in mtf.get("timeframes", []):
        res = mtf["results"].get(tf)
        if not res:
            continue
        trend = res.get("trend", {})
        direction = trend.get("direction", "NEUTRAL")
        bk = res.get("breakout", {})
        bk_type = bk.get("type", "") if bk else ""
        bk_info = f"{bk['detail']}" if bk_type and bk_type != "none" else "—"

        rows.append({
            "TF": tf,
            "Dir": direction,
            "Conf": f"{trend.get('confidence', 0):.0%}",
            "Breakout": bk_info,
            "Bars": res.get("bars", 0),
            "Close": f"{res.get('last_close', 0):,.2f}" if res.get("last_close") else "—",
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=30 + len(rows) * 28)

    # Consensus
    cons = mtf.get("consensus", {})
    mdir = cons.get("direction", "NEUTRAL")
    mc = "#089981" if mdir == "LONG" else "#f23645" if mdir == "SHORT" else "#787b86"
    align = cons.get("aligned", 0)
    total = cons.get("total", 0)
    strength = cons.get("strength", 0)
    active = cons.get("active_breakouts", [])

    consensus_text = f"Consensus: **{mdir}** | Strength: {strength:.0%} | Aligned: {align}/{total}"
    if active:
        bk_str = ", ".join([f"**{b['tf']}** {b['type']}" for b in active])
        consensus_text += f" | Breakouts: {bk_str}"

    st.markdown(f"<div style='font-size:12px;color:#787b86;padding:4px 8px;background:#131722;border:1px solid #1e222d;border-radius:3px'>{consensus_text}</div>", unsafe_allow_html=True)
