"""
Prediction Tab - ML model prediction results and visualization.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from dashboard.components import render_bar_chart, render_signal_badge


def render(df: pd.DataFrame, prediction: dict, metrics: dict, feature_importance: dict):
    """Render the ML prediction tab."""
    st.subheader("🤖 ML Prediction")

    if not prediction or prediction.get("error"):
        st.warning("ML model not trained yet. Go to the Consensus tab to train.")
        return

    # Prediction result
    direction = prediction.get("prediction", prediction.get("direction", "NEUTRAL"))
    confidence = prediction.get("confidence", 0)
    signal = prediction.get("signal", "NEUTRAL")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        icon = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "🟡"
        st.metric("Prediction", f"{icon} {direction}")
    with col2:
        st.metric("Confidence", f"{confidence*100:.1f}%")
    with col3:
        st.metric("P(Up)", f"{prediction.get('probability_up', 0)*100:.1f}%")
    with col4:
        st.metric("P(Down)", f"{prediction.get('probability_down', 0)*100:.1f}%")

    st.divider()

    # Model metrics
    if metrics:
        st.markdown("### Model Performance")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Accuracy", f"{metrics.get('accuracy', 0)*100:.1f}%")
        with col2:
            st.metric("Train Size", f"{metrics.get('train_size', 0):,}")
        with col3:
            st.metric("Test Size", f"{metrics.get('test_size', 0):,}")
        with col4:
            cr = metrics.get("classification_report", {})
            if "1" in cr:
                st.metric("F1 (Up)", f"{cr['1'].get('f1-score', 0):.3f}")

        # Confusion matrix
        cm = metrics.get("confusion_matrix", [])
        if cm:
            st.markdown("**Confusion Matrix:**")
            cm_df = pd.DataFrame(cm, index=["Actual Down", "Actual Up"], columns=["Pred Down", "Pred Up"])
            st.dataframe(cm_df, use_container_width=True)

    st.divider()

    # Feature importance
    if feature_importance:
        st.markdown("### Feature Importance")
        sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:15]
        labels = [f[0] for f in sorted_features]
        values = [f[1] for f in sorted_features]
        fig = render_bar_chart(labels, values, "Top 15 Features", "#2196F3")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Prediction history chart
    if "ml_signal" in df.columns and not df["ml_signal"].isna().all():
        st.markdown("### Signal History")
        signal_df = df[["close", "ml_signal", "ml_confidence"]].dropna()
        if not signal_df.empty:
            fig = go.Figure()

            # Price
            fig.add_trace(go.Scatter(
                x=signal_df.index, y=signal_df["close"],
                name="Price", line=dict(color="#2196F3", width=2),
            ))

            # Signal markers
            long_signals = signal_df[signal_df["ml_signal"] == 1]
            short_signals = signal_df[signal_df["ml_signal"] == 0]

            if not long_signals.empty:
                fig.add_trace(go.Scatter(
                    x=long_signals.index, y=long_signals["close"],
                    mode="markers", name="LONG",
                    marker=dict(color="#26a69a", size=10, symbol="triangle-up"),
                ))
            if not short_signals.empty:
                fig.add_trace(go.Scatter(
                    x=short_signals.index, y=short_signals["close"],
                    mode="markers", name="SHORT",
                    marker=dict(color="#ef5350", size=10, symbol="triangle-down"),
                ))

            fig.update_layout(
                title="Price with ML Signals",
                template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
                font=dict(color="white"), height=400,
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Train the model first to see signal history.")
