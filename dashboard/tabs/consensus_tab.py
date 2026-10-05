"""
Consensus Tab - Multi-school consensus signal and training.
"""
import streamlit as st
import pandas as pd
from dashboard.components import render_signal_badge, render_school_comparison


def render(
    consensus: dict,
    df: pd.DataFrame,
    indicators: dict,
    stats: dict,
    prediction: dict,
    on_train_click=None,
):
    """Render the consensus tab."""
    st.subheader("🎯 Multi-School Consensus")

    if not consensus:
        st.warning("No consensus data available.")
        return

    # Consensus result
    cons = consensus.get("consensus", {})
    direction = cons.get("direction", "NEUTRAL")
    confidence = cons.get("confidence", 0)
    verdict = cons.get("verdict", "No signal")

    # Big signal display
    st.markdown(f"# {render_signal_badge(direction, confidence)}", unsafe_allow_html=True)
    st.markdown(f"### {verdict}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Agreeing Schools", f"{cons.get('agreeing_schools', 0)} / {cons.get('total_schools', 5)}")
    with col2:
        st.metric("Long Schools", cons.get("long_schools", 0))
    with col3:
        st.metric("Short Schools", cons.get("short_schools", 0))

    st.divider()

    # School comparison chart
    schools = consensus.get("schools", {})
    if schools:
        fig = render_school_comparison(schools)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Individual school details
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📐 Technical Analysis")
        tech = schools.get("technical", {})
        st.markdown(f"- Direction: **{tech.get('direction', 'N/A')}**")
        st.markdown(f"- Confidence: **{tech.get('confidence', 0)*100:.1f}%**")
        st.caption(tech.get("reason", ""))

        st.markdown("### 📊 Statistical Analysis")
        stat = schools.get("statistical", {})
        st.markdown(f"- Direction: **{stat.get('direction', 'N/A')}**")
        st.markdown(f"- Confidence: **{stat.get('confidence', 0)*100:.1f}%**")
        st.caption(stat.get("reason", ""))

    with col2:
        st.markdown("### 🤖 ML Prediction")
        ml = schools.get("ml_prediction", {})
        st.markdown(f"- Direction: **{ml.get('direction', 'N/A')}**")
        st.markdown(f"- Confidence: **{ml.get('confidence', 0)*100:.1f}%**")
        st.caption(ml.get("reason", ""))

        st.markdown("### 🚀 Momentum")
        mom = schools.get("momentum", {})
        st.markdown(f"- Direction: **{mom.get('direction', 'N/A')}**")
        st.markdown(f"- Confidence: **{mom.get('confidence', 0)*100:.1f}%**")
        st.caption(mom.get("reason", ""))

        st.markdown("### 📊 Volume Analysis")
        vol = schools.get("volume", {})
        st.markdown(f"- Direction: **{vol.get('direction', 'N/A')}**")
        st.markdown(f"- Confidence: **{vol.get('confidence', 0)*100:.1f}%**")
        st.caption(vol.get("reason", ""))

    st.divider()

    # Training section
    st.markdown("### 🧠 Model Training")
    st.caption("Train the ML model with current data to improve predictions.")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🚀 Train Model", type="primary", use_container_width=True):
            if on_train_click:
                on_train_click()

    if prediction and not prediction.get("error"):
        st.success(f"Model accuracy: **{prediction.get('accuracy', 0)*100:.1f}%**")
    else:
        st.info("No trained model found. Click Train to build one.")
