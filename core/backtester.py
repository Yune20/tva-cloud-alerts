"""
Backtesting Module
Uses kernc/backtesting.py for strategy simulation.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
from backtesting import Backtest, Strategy

from config import INITIAL_CAPITAL, COMMISSION_PCT


class RsiEmaStrategy(Strategy):
    """RSI + EMA cross strategy."""
    rsi_oversold = 30
    rsi_overbought = 70

    def init(self):
        self.rsi = self.I(lambda x: x, self.data.df["RSI"].values) if "RSI" in self.data.df.columns else None
        ema_cols = sorted([c for c in self.data.df.columns if c.startswith("EMA_")])
        self.ema_s = self.I(lambda x: x, self.data.df[ema_cols[0]].values) if len(ema_cols) > 0 else None
        self.ema_l = self.I(lambda x: x, self.data.df[ema_cols[1]].values) if len(ema_cols) > 1 else None

    def next(self):
        if self.rsi is None or self.ema_s is None or self.ema_l is None:
            return
        if len(self.rsi) < 2 or len(self.ema_s) < 2:
            return

        rsi_val = self.rsi[-1]
        ema_s = self.ema_s[-1]
        ema_l = self.ema_l[-1]
        prev_ema_s = self.ema_s[-2]
        prev_ema_l = self.ema_l[-2]

        golden_cross = prev_ema_s <= prev_ema_l and ema_s > ema_l
        death_cross = prev_ema_s >= prev_ema_l and ema_s < ema_l

        if not self.position:
            if golden_cross and rsi_val < self.rsi_overbought:
                self.buy()
            elif death_cross and rsi_val > self.rsi_oversold:
                self.sell()
        else:
            if self.position.is_long and (death_cross or rsi_val > self.rsi_overbought):
                self.position.close()
            elif not self.position.is_long and (golden_cross or rsi_val < self.rsi_oversold):
                self.position.close()


class MomentumStrategy(Strategy):
    """Simple momentum strategy using returns."""
    lookback = 10
    threshold = 0.02

    def init(self):
        self.returns = self.I(lambda x: x, self.data.df["returns"].values) if "returns" in self.data.df.columns else None

    def next(self):
        if self.returns is None or len(self.returns) < self.lookback:
            return
        cum_return = sum(self.returns[-self.lookback:])
        if not self.position:
            if cum_return > self.threshold:
                self.buy()
            elif cum_return < -self.threshold:
                self.sell()
        else:
            if abs(cum_return) < self.threshold / 2:
                self.position.close()


class BbRsiStrategy(Strategy):
    """Bollinger Band + RSI mean reversion strategy."""
    rsi_period = 14

    def init(self):
        self.rsi = self.I(lambda x: x, self.data.df["RSI"].values) if "RSI" in self.data.df.columns else None
        bbu = [c for c in self.data.df.columns if c.startswith("BBU")]
        bbl = [c for c in self.data.df.columns if c.startswith("BBL")]
        self.bbu = self.I(lambda x: x, self.data.df[bbu[0]].values) if bbu else None
        self.bbl = self.I(lambda x: x, self.data.df[bbl[0]].values) if bbl else None

    def next(self):
        if self.rsi is None or self.bbu is None or self.bbl is None:
            return
        close = self.data.Close[-1]
        rsi_val = self.rsi[-1]
        upper = self.bbu[-1]
        lower = self.bbl[-1]

        if not self.position:
            if close <= lower and rsi_val < 30:
                self.buy()
            elif close >= upper and rsi_val > 70:
                self.sell()
        else:
            if self.position.is_long and (close >= (upper + lower) / 2 or rsi_val > 60):
                self.position.close()
            elif not self.position.is_long and (close <= (upper + lower) / 2 or rsi_val < 40):
                self.position.close()


STRATEGIES = {
    "RSI + EMA Cross": RsiEmaStrategy,
    "Momentum": MomentumStrategy,
    "BB + RSI": BbRsiStrategy,
}


class BacktestEngine:
    """Run backtests on OHLCV data with different strategies."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.results: Dict = {}

    def run_backtest(
        self,
        strategy_name: str = "RSI + EMA Cross",
        capital: float = INITIAL_CAPITAL,
        commission: float = COMMISSION_PCT,
    ) -> Dict:
        """Run a single backtest."""
        strategy_cls = STRATEGIES.get(strategy_name)
        if not strategy_cls:
            return {"error": f"Unknown strategy: {strategy_name}"}

        df = self._prepare_backtest_data()
        if df.empty or len(df) < 20:
            return {"error": "No valid data for backtest", "strategy": strategy_name}

        try:
            bt = Backtest(
                df,
                strategy_cls,
                cash=capital,
                commission=commission,
                exclusive_orders=True,
                finalize_trades=True,
            )

            stats = bt.run()

            result = {
                "strategy": strategy_name,
                "start": str(stats.get("Start", "")),
                "end": str(stats.get("End", "")),
                "duration": str(stats.get("Duration", "")),
                "exposure_time": round(float(stats.get("Exposure Time [%]", 0) or 0), 2),
                "equity_final": round(float(stats.get("Equity Final [$]", 0) or 0), 2),
                "equity_peak": round(float(stats.get("Equity Peak [$]", 0) or 0), 2),
                "return_pct": round(float(stats.get("Return [%]", 0) or 0), 2),
                "buy_hold_return": round(float(stats.get("Buy & Hold Return [%]", 0) or 0), 2),
                "ann_return": round(float(stats.get("Return (Ann.) [%]", 0) or 0), 2),
                "volatility_ann": round(float(stats.get("Volatility (Ann.) [%]", 0) or 0), 2),
                "sharpe_ratio": round(float(stats.get("Sharpe Ratio", 0) or 0), 4),
                "sortino_ratio": round(float(stats.get("Sortino Ratio", 0) or 0), 4),
                "calmar_ratio": round(float(stats.get("Calmar Ratio", 0) or 0), 4),
                "max_drawdown": round(float(stats.get("Max. Drawdown [%]", 0) or 0), 2),
                "avg_drawdown": round(float(stats.get("Avg. Drawdown [%]", 0) or 0), 2),
                "trades": int(stats.get("# Trades", 0) or 0),
                "win_rate": round(float(stats.get("Win Rate [%]", 0) or 0), 2),
                "best_trade": round(float(stats.get("Best Trade [%]", 0) or 0), 2),
                "worst_trade": round(float(stats.get("Worst Trade [%]", 0) or 0), 2),
                "avg_trade": round(float(stats.get("Avg. Trade [%]", 0) or 0), 2),
                "profit_factor": round(float(stats.get("Profit Factor", 0) or 0), 4),
                "expectancy": round(float(stats.get("Expectancy [%]", 0) or 0), 4),
                "sqn": round(float(stats.get("SQN", 0) or 0), 4),
            }

            # Equity curve
            eq_curve = stats.get("_equity_curve", pd.DataFrame())
            if eq_curve is not None and not eq_curve.empty and "Equity" in eq_curve.columns:
                result["equity_curve"] = {
                    "dates": [str(d) for d in eq_curve.index],
                    "equity": eq_curve["Equity"].tolist(),
                }

            self.results[strategy_name] = result
            return result

        except Exception as e:
            return {"error": str(e), "strategy": strategy_name}

    def run_all_strategies(self) -> Dict:
        """Run all available strategies and compare."""
        results = {}
        for name in STRATEGIES:
            results[name] = self.run_backtest(name)

        # Find best strategy
        valid = {k: v for k, v in results.items() if "error" not in v}
        if valid:
            best = max(valid.keys(), key=lambda k: valid[k].get("sharpe_ratio", 0))
            results["_best_strategy"] = best

        return results

    def _prepare_backtest_data(self) -> pd.DataFrame:
        """Prepare OHLCV data in the format required by backtesting.py."""
        df = self.df.copy()

        # backtesting.py needs: Open, High, Low, Close, Volume (capitalized)
        rename_map = {}
        for lower, upper in [("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close"), ("volume", "Volume")]:
            if lower in df.columns:
                rename_map[lower] = upper

        df = df.rename(columns=rename_map)

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col not in df.columns:
                df[col] = 0

        # Keep only OHLCV + needed indicators
        keep = ["Open", "High", "Low", "Close", "Volume"]
        keep += [c for c in ["RSI", "MACD.macd", "MACD.signal", "MACD.hist",
                              "BBU", "BBL", "BBM", "ADX", "ATR",
                              "STOCH_K", "STOCH_D", "returns", "ml_signal", "ml_confidence"]
                 if c in df.columns]
        keep = [c for c in keep if c in df.columns]

        result = df[keep].copy()
        result = result.dropna(subset=["Open", "High", "Low", "Close"])
        return result
