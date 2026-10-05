"""
Indicators Tab - Technical indicators visualization.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dashboard.components import render_indicator_gauge, render_radar_chart


def render(df: pd.DataFrame, signals: dict):
    """Render the indicators tab."""
    st.subheader("🔧 Technical Indicators")

    if df.empty or not signals:
        st.warning("No indicator data available.")
        return

    # Indicator gauges
    st.markdown("### Key Indicators")

    gauge_indicators = []
    if "RSI" in signals:
        gauge_indicators.append(("RSI", signals["RSI"]["value"], 0, 100))
    if "ADX" in signals:
        gauge_indicators.append(("ADX", signals["ADX"]["value"], 0, 100))
    if "Stochastic" in signals:
        gauge_indicators.append(("Stoch %K", signals["Stochastic"]["K"], 0, 100))
    if "MFI" in df.columns:
        gauge_indicators.append(("MFI", float(df["MFI"].iloc[-1]), 0, 100))

    if gauge_indicators:
        cols = st.columns(min(len(gauge_indicators), 4))
        for i, (name, value, mn, mx) in enumerate(gauge_indicators):
            with cols[i % len(cols)]:
                fig = render_indicator_gauge(name, value, mn, mx)
                st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Indicator details
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### RSI (Relative Strength Index)")
        if "RSI" in signals:
            rsi = signals["RSI"]
            st.metric("RSI Value", f"{rsi['value']:.1f}")
            st.caption(f"Signal: **{rsi['signal']}**")

            # RSI chart
            if "RSI" in df.columns:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="#2196F3")))
                fig.add_hline(y=70, line_dash="dash", line_color="#F44336", annotation_text="Overbought")
                fig.add_hline(y=30, line_dash="dash", line_color="#4CAF50", annotation_text="Oversold")
                fig.update_layout(
                    title="RSI",
                    template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
                    font=dict(color="white"), height=250, margin=dict(l=0, r=0, t=40, b=0),
                )
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("### MACD")
        if "MACD" in signals:
            macd = signals["MACD"]
            c1, c2, c3 = st.columns(3)
            c1.metric("MACD", f"{macd['macd']:.4f}")
            c2.metric("Signal", f"{macd['signal']:.4f}")
            c3.metric("Histogram", f"{macd['histogram']:.4f}")

            # MACD chart
            macd_cols = [c for c in df.columns if "MACD" in c]
            if macd_cols:
                fig = go.Figure()
                hist_col = [c for c in df.columns if "MACD.hist" in c]
                if hist_col:
                    colors = ["#26a69a" if v >= 0 else "#ef5350" for v in df[hist_col[0]]]
                    fig.add_trace(go.Bar(x=df.index, y=df[hist_col[0]], name="Histogram", marker_color=colors))
                macd_line = [c for c in df.columns if "MACD.macd" in c]
                signal_line = [c for c in df.columns if "MACD.signal" in c]
                if macd_line:
                    fig.add_trace(go.Scatter(x=df.index, y=df[macd_line[0]], name="MACD", line=dict(color="#2196F3")))
                if signal_line:
                    fig.add_trace(go.Scatter(x=df.index, y=df[signal_line[0]], name="Signal", line=dict(color="#FF9800")))
                fig.update_layout(
                    title="MACD", template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
                    font=dict(color="white"), height=250, margin=dict(l=0, r=0, t=40, b=0),
                )
                st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Bollinger Bands")
        if "Bollinger" in signals:
            bb = signals["Bollinger"]
            c1, c2, c3 = st.columns(3)
            c1.metric("Upper", f"{bb['upper']:.4f}")
            c2.metric("Position", f"{bb['position']:.1f}%")
            c3.metric("Lower", f"{bb['lower']:.4f}")
            st.caption(f"Signal: **{bb['signal']}**")

        st.markdown("### Stochastic")
        if "Stochastic" in signals:
            stoch = signals["Stochastic"]
            c1, c2 = st.columns(2)
            c1.metric("%K", f"{stoch['K']:.1f}")
            c2.metric("%D", f"{stoch['D']:.1f}")
            st.caption(f"Signal: **{stoch['signal']}**")

        st.markdown("### EMA Cross")
        if "EMA_Cross" in signals:
            ema = signals["EMA_Cross"]
            c1, c2 = st.columns(2)
            c1.metric("Short EMA", f"{ema['short']:.4f}")
            c2.metric("Long EMA", f"{ema['long']:.4f}")
            st.caption(f"Signal: **{ema['signal']}**")

    st.divider()

    # Signal summary
    st.markdown("### Signal Summary")
    signal_data = []
    for name, sig in signals.items():
        signal_data.append({
            "Indicator": name,
            "Value": str(sig.get("value", sig.get("direction", sig.get("trend", "N/A")))),
            "Signal": sig.get("signal", sig.get("direction", sig.get("trend_strength", "N/A"))),
        })
    if signal_data:
        st.dataframe(pd.DataFrame(signal_data), use_container_width=True, hide_index=True)

    # Radar chart
    if len(signals) >= 3:
        st.markdown("### Indicator Radar")
        categories = []
        values = []
        for name, sig in signals.items():
            if "value" in sig and isinstance(sig["value"], (int, float)):
                categories.append(name)
                val = sig["value"]
                # Normalize to 0-1
                if name == "RSI" or name == "Stochastic":
                    values.append(val / 100)
                elif name == "ADX":
                    values.append(val / 100)
                else:
                    values.append(min(abs(val) / 100, 1))
        if len(categories) >= 3:
            fig = render_radar_chart(categories, values, "Indicator Overview")
            st.plotly_chart(fig, use_container_width=True)
