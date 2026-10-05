"""
Statistical Tab - Distribution, stationarity, correlation analysis.
"""
import streamlit as st
import pandas as pd
import numpy as np
from dashboard.components import render_heatmap, render_distribution


def render(df: pd.DataFrame, stats: dict):
    """Render the statistical analysis tab."""
    st.subheader("📊 Statistical Analysis")

    if not stats:
        st.warning("No statistical data available.")
        return

    # Descriptive stats
    desc = stats.get("descriptive", {})
    if desc:
        st.markdown("### Descriptive Statistics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Data Points", desc.get("data_points", 0))
        with col2:
            price = desc.get("price", {})
            st.metric("Current Price", f"{price.get('close', 0):.4f}")
        with col3:
            st.metric("Period High", f"{price.get('high', 0):.4f}")
        with col4:
            st.metric("Period Low", f"{price.get('low', 0):.4f}")

        date_range = desc.get("date_range", {})
        if date_range:
            st.caption(f"Period: {date_range.get('start', '')} → {date_range.get('end', '')}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        # Distribution
        st.markdown("### Return Distribution")
        dist = stats.get("distribution", {})
        if dist and "skewness" in dist:
            c1, c2, c3 = st.columns(3)
            c1.metric("Mean", f"{dist['mean']*100:.3f}%")
            c2.metric("Std Dev", f"{dist['std']*100:.3f}%")
            c3.metric("Skewness", f"{dist['skewness']:.3f}")

            c1, c2, c3 = st.columns(3)
            c1.metric("Kurtosis", f"{dist['kurtosis']:.3f}")
            c2.metric("Min", f"{dist['min']*100:.3f}%")
            c3.metric("Max", f"{dist['max']*100:.3f}%")

            jb = dist.get("jarque_bera", {})
            st.caption(f"Jarque-Bera: stat={jb.get('statistic', 0):.2f}, p={jb.get('p_value', 0):.4f} — {'Normal' if jb.get('is_normal') else 'Non-normal'}")

            if "returns" in df.columns:
                fig = render_distribution(df["returns"].dropna(), "Return Distribution")
                st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Stationarity
        st.markdown("### Stationarity Tests")
        stationarity = stats.get("stationarity", {})
        if stationarity:
            for series_name, tests in stationarity.items():
                st.markdown(f"**{series_name.title()}**")
                if isinstance(tests, dict):
                    adf = tests.get("adf", {})
                    if adf:
                        st.markdown(f"- ADF: stat={adf.get('statistic', 0):.4f}, p={adf.get('p_value', 0):.4f} — {'Stationary' if adf.get('is_stationary') else 'Non-stationary'}")
                    kpss = tests.get("kpss", {})
                    if kpss:
                        st.markdown(f"- KPSS: stat={kpss.get('statistic', 0):.4f}, p={kpss.get('p_value', 0):.4f} — {'Stationary' if kpss.get('is_stationary') else 'Non-stationary'}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        # Volatility
        st.markdown("### Volatility Analysis")
        vol = stats.get("volatility", {})
        if vol and "current_annualized_vol" in vol:
            c1, c2 = st.columns(2)
            c1.metric("Current Vol (Ann.)", f"{vol['current_annualized_vol']*100:.1f}%")
            c2.metric("Average Vol (Ann.)", f"{vol['average_annualized_vol']*100:.1f}%")

            c1, c2 = st.columns(2)
            c1.metric("VaR 95%", f"{vol['var_95']*100:.3f}%")
            c2.metric("CVaR 95%", f"{vol['cvar_95']*100:.3f}%")

            st.caption(f"Volatility Regime: **{vol['vol_regime']}**")

    with col2:
        # Normality
        st.markdown("### Normality Tests")
        normality = stats.get("normality", {})
        if normality and "shapiro_wilk" in normality:
            sw = normality["shapiro_wilk"]
            st.markdown(f"- Shapiro-Wilk: stat={sw['statistic']:.4f}, p={sw['p_value']:.4f}")
            st.caption(f"Result: {'Normal distribution' if sw.get('is_normal') else 'Non-normal distribution'}")

            if "dagostino" in normality:
                da = normality["dagostino"]
                st.markdown(f"- D'Agostino: stat={da['statistic']:.4f}, p={da['p_value']:.4f}")

    st.divider()

    # Correlation
    st.markdown("### Correlation Analysis")
    corr = stats.get("correlation", {})
    matrix = corr.get("matrix", {})
    if matrix:
        corr_df = pd.DataFrame(matrix)
        fig = render_heatmap(corr_df, "Feature Correlation Matrix")
        st.plotly_chart(fig, use_container_width=True)

        strong_pairs = corr.get("strong_pairs", [])
        if strong_pairs:
            st.markdown("**Strong Correlations:**")
            for pair in strong_pairs:
                st.markdown(f"- {pair['col1']} ↔ {pair['col2']}: **{pair['correlation']:.4f}** ({pair['strength']})")

    # Autocorrelation
    auto = stats.get("autocorrelation", {})
    if auto and "acf_values" in auto:
        st.markdown("### Autocorrelation (ACF)")
        import plotly.graph_objects as go
        acf_values = auto["acf_values"]
        fig = go.Figure(go.Bar(
            x=list(range(1, len(acf_values) + 1)),
            y=acf_values,
        ))
        fig.update_layout(
            title="ACF",
            template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
            font=dict(color="white"), height=300,
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Autocorrelation detected: {'Yes' if auto.get('has_autocorrelation') else 'No'}")
