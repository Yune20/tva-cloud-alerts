"""
Chart Tab - Interactive OHLCV candlestick chart with indicators.
"""
import streamlit as st
import pandas as pd
from dashboard.components import (
    render_candlestick_chart, render_metric_card, render_signal_badge,
)


def render(df: pd.DataFrame, symbol: str, interval: str, indicators: dict = None):
    """Render the chart tab."""
    st.subheader(f"📈 {symbol} — {interval}")

    if df.empty:
        st.warning("No data available. Check your TradingView connection.")
        return

    # Price metrics
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    change = latest["close"] - prev["close"]
    change_pct = (change / prev["close"]) * 100

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        render_metric_card("Close", f"{latest['close']:.4f}", f"{change_pct:+.2f}%")
    with col2:
        render_metric_card("Open", f"{latest['open']:.4f}")
    with col3:
        render_metric_card("High", f"{latest['high']:.4f}")
    with col4:
        render_metric_card("Low", f"{latest['low']:.4f}")
    with col5:
        vol = latest.get("volume", 0)
        render_metric_card("Volume", f"{vol:,.0f}" if vol else "N/A")

    st.divider()

    # Indicator selector
    available_indicators = []
    indicator_map = {
        "SMA_20": "SMA 20", "SMA_50": "SMA 50", "SMA_200": "SMA 200",
    }
    ema_cols = sorted([c for c in df.columns if c.startswith("EMA_")])
    for c in ema_cols:
        indicator_map[c] = c

    for col, name in indicator_map.items():
        if col in df.columns:
            available_indicators.append((name, col))

    selected = st.multiselect(
        "Overlay Indicators",
        [s[0] for s in available_indicators],
        default=[s[0] for s in available_indicators[:2]],
    )

    selected_cols = [s[1] for s in available_indicators if s[0] in selected]

    # Chart
    fig = render_candlestick_chart(
        df,
        title=f"{symbol} {interval}",
        indicators=selected_cols,
        height=550,
    )
    st.plotly_chart(fig, use_container_width=True)

    # TradingView recommendation
    if indicators:
        rec = indicators.get("Recommend.All", 0)
        if rec is not None:
            if rec >= 0.5:
                signal = "STRONG BUY"
            elif rec >= 0.2:
                signal = "BUY"
            elif rec <= -0.5:
                signal = "STRONG SELL"
            elif rec <= -0.2:
                signal = "SELL"
            else:
                signal = "NEUTRAL"

            st.info(f"**TradingView Recommendation:** {render_signal_badge(signal, abs(rec))}", unsafe_allow_html=True)

    # Data table
    with st.expander("📋 Raw Data (Last 20 candles)"):
        display_cols = ["open", "high", "low", "close", "volume"]
        display_cols += [c for c in ["RSI", "MACD.macd", "ADX", "ATR"] if c in df.columns]
        st.dataframe(
            df[display_cols].tail(20).round(4),
            use_container_width=True,
        )
