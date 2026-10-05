"""
Backtest Tab - Strategy backtesting results.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from dashboard.components import render_equity_curve


def render(backtest_results: dict):
    """Render the backtest tab."""
    st.subheader("📉 Backtesting")

    if not backtest_results:
        st.warning("No backtest results. Run backtest from the sidebar.")
        return

    # Strategy selector
    strategies = {k: v for k, v in backtest_results.items() if not k.startswith("_") and "error" not in v}
    best = backtest_results.get("_best_strategy", "")

    if not strategies:
        errors = {k: v for k, v in backtest_results.items() if "error" in v}
        for name, err in errors.items():
            st.error(f"**{name}**: {err.get('error', 'Unknown error')}")
        return

    selected = st.selectbox(
        "Select Strategy",
        list(strategies.keys()),
        index=list(strategies.keys()).index(best) if best in strategies else 0,
    )

    result = strategies[selected]

    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Return", f"{result['return_pct']:.1f}%")
    with col2:
        st.metric("Sharpe Ratio", f"{result['sharpe_ratio']:.2f}")
    with col3:
        st.metric("Max Drawdown", f"{result['max_drawdown']:.1f}%")
    with col4:
        st.metric("Win Rate", f"{result['win_rate']:.1f}%")
    with col5:
        st.metric("Trades", f"{result['trades']}")

    st.divider()

    # Equity curve
    equity = result.get("equity_curve", {})
    if equity and "dates" in equity:
        dates = equity["dates"]
        equity_vals = equity["equity"]

        # Compute buy & hold benchmark
        initial = equity_vals[0] if equity_vals else 10000
        # Use buy_hold_return to estimate benchmark
        bh_return = result.get("buy_hold_return", 0) / 100
        bh_equity = [initial * (1 + bh_return * i / len(equity_vals)) for i in range(len(equity_vals))]

        fig = render_equity_curve(dates, equity_vals, bh_equity)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Detailed metrics
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Performance Metrics")
        metrics_data = {
            "Metric": [
                "Start", "End", "Duration", "Exposure Time",
                "Equity Final", "Equity Peak", "Return %",
                "Ann. Return", "Ann. Volatility", "Buy & Hold Return",
            ],
            "Value": [
                result.get("start", "N/A"), result.get("end", "N/A"),
                result.get("duration", "N/A"), f"{result.get('exposure_time', 0):.1f}%",
                f"${result.get('equity_final', 0):,.2f}", f"${result.get('equity_peak', 0):,.2f}",
                f"{result.get('return_pct', 0):.2f}%", f"{result.get('ann_return', 0):.2f}%",
                f"{result.get('volatility_ann', 0):.2f}%", f"{result.get('buy_hold_return', 0):.2f}%",
            ],
        }
        st.dataframe(pd.DataFrame(metrics_data), use_container_width=True, hide_index=True)

    with col2:
        st.markdown("### Risk Metrics")
        risk_data = {
            "Metric": [
                "Sharpe Ratio", "Sortino Ratio", "Calmar Ratio",
                "Max Drawdown", "Avg Drawdown", "SQN",
                "Profit Factor", "Expectancy", "Win Rate",
            ],
            "Value": [
                f"{result.get('sharpe_ratio', 0):.4f}",
                f"{result.get('sortino_ratio', 0):.4f}",
                f"{result.get('calmar_ratio', 0):.4f}",
                f"{result.get('max_drawdown', 0):.2f}%",
                f"{result.get('avg_drawdown', 0):.2f}%",
                f"{result.get('sqn', 0):.4f}",
                f"{result.get('profit_factor', 0):.4f}",
                f"{result.get('expectancy', 0):.4f}%",
                f"{result.get('win_rate', 0):.2f}%",
            ],
        }
        st.dataframe(pd.DataFrame(risk_data), use_container_width=True, hide_index=True)

    # Trade stats
    st.divider()
    st.markdown("### Trade Statistics")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Trades", result.get("trades", 0))
    with col2:
        st.metric("Best Trade", f"{result.get('best_trade', 0):.2f}%")
    with col3:
        st.metric("Worst Trade", f"{result.get('worst_trade', 0):.2f}%")

    # Strategy comparison
    if len(strategies) > 1:
        st.divider()
        st.markdown("### Strategy Comparison")
        compare_data = []
        for name, res in strategies.items():
            compare_data.append({
                "Strategy": name,
                "Return %": res.get("return_pct", 0),
                "Sharpe": res.get("sharpe_ratio", 0),
                "Max DD %": res.get("max_drawdown", 0),
                "Win Rate %": res.get("win_rate", 0),
                "Trades": res.get("trades", 0),
            })
        st.dataframe(pd.DataFrame(compare_data).round(2), use_container_width=True, hide_index=True)
