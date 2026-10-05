"""
Statistical Analysis Module
Provides distribution tests, stationarity, correlation, and volatility modeling.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from scipy import stats
import warnings
warnings.filterwarnings("ignore")

try:
    from statsmodels.tsa.stattools import adfuller, kpss, coint
    from statsmodels.tsa.seasonal import seasonal_decompose
    from statsmodels.stats.diagnostic import acorr_ljungbox
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


class StatisticalAnalyzer:
    """Comprehensive statistical analysis on price data."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.results: Dict = {}

    def run_all(self) -> Dict:
        """Run all statistical analyses."""
        results = {}
        results["distribution"] = self.distribution_analysis()
        results["stationarity"] = self.stationarity_tests()
        results["correlation"] = self.correlation_analysis()
        results["normality"] = self.normality_tests()
        results["volatility"] = self.volatility_analysis()
        results["autocorrelation"] = self.autocorrelation_analysis()
        results["descriptive"] = self.descriptive_stats()
        self.results = results
        return results

    def distribution_analysis(self) -> Dict:
        """Analyze return distribution."""
        if "returns" not in self.df.columns:
            self.df["returns"] = self.df["close"].pct_change()
        returns = self.df["returns"].dropna()

        return {
            "mean": float(returns.mean()),
            "std": float(returns.std()),
            "skewness": float(returns.skew()),
            "kurtosis": float(returns.kurtosis()),
            "min": float(returns.min()),
            "max": float(returns.max()),
            "median": float(returns.median()),
            "jarque_bera": {
                "statistic": float(stats.jarque_bera(returns)[0]),
                "p_value": float(stats.jarque_bera(returns)[1]),
                "is_normal": bool(stats.jarque_bera(returns)[1] > 0.05),
            },
        }

    def stationarity_tests(self) -> Dict:
        """ADF and KPSS tests for stationarity."""
        close = self.df["close"].dropna()
        results = {"close": {}, "returns": {}}

        # ADF test on close prices
        if HAS_STATSMODELS and len(close) > 20:
            adf_result = adfuller(close, autolag="AIC")
            results["close"]["adf"] = {
                "statistic": float(adf_result[0]),
                "p_value": float(adf_result[1]),
                "lags": int(adf_result[2]),
                "is_stationary": bool(adf_result[1] < 0.05),
            }

            # KPSS test
            try:
                kpss_result = kpss(close, regression="ct", nlags="auto")
                results["close"]["kpss"] = {
                    "statistic": float(kpss_result[0]),
                    "p_value": float(kpss_result[1]),
                    "is_stationary": bool(kpss_result[1] > 0.05),
                }
            except Exception:
                pass

        # ADF on returns
        returns = self.df["returns"].dropna() if "returns" in self.df.columns else close.pct_change().dropna()
        if HAS_STATSMODELS and len(returns) > 20:
            adf_ret = adfuller(returns, autolag="AIC")
            results["returns"]["adf"] = {
                "statistic": float(adf_ret[0]),
                "p_value": float(adf_ret[1]),
                "lags": int(adf_ret[2]),
                "is_stationary": bool(adf_ret[1] < 0.05),
            }

        return results

    def correlation_analysis(self) -> Dict:
        """Correlation matrix of key features."""
        cols = ["close", "volume"]
        if "returns" in self.df.columns:
            cols.append("returns")
        if "volatility_20" in self.df.columns:
            cols.append("volatility_20")
        if "momentum_10" in self.df.columns:
            cols.append("momentum_10")

        available_cols = [c for c in cols if c in self.df.columns]
        if len(available_cols) < 2:
            return {"matrix": {}, "pairs": []}

        corr_matrix = self.df[available_cols].corr()
        matrix_dict = corr_matrix.to_dict()

        # Find strong correlations
        pairs = []
        for i in range(len(available_cols)):
            for j in range(i + 1, len(available_cols)):
                c1, c2 = available_cols[i], available_cols[j]
                corr_val = corr_matrix.loc[c1, c2]
                if abs(corr_val) > 0.5:
                    pairs.append({
                        "col1": c1, "col2": c2,
                        "correlation": round(float(corr_val), 4),
                        "strength": "STRONG" if abs(corr_val) > 0.7 else "MODERATE",
                    })

        return {"matrix": matrix_dict, "strong_pairs": pairs}

    def normality_tests(self) -> Dict:
        """Shapiro-Wilk and D'Agostino tests."""
        returns = self.df["returns"].dropna() if "returns" in self.df.columns else pd.Series()
        if len(returns) < 8:
            return {"error": "Insufficient data"}

        results = {}

        # Shapiro-Wilk (max 5000 samples)
        sample = returns.sample(min(5000, len(returns)), random_state=42)
        sw_stat, sw_p = stats.shapiro(sample)
        results["shapiro_wilk"] = {
            "statistic": float(sw_stat),
            "p_value": float(sw_p),
            "is_normal": bool(sw_p > 0.05),
        }

        # D'Agostino
        if len(returns) >= 20:
            da_stat, da_p = stats.normaltest(returns)
            results["dagostino"] = {
                "statistic": float(da_stat),
                "p_value": float(da_p),
                "is_normal": bool(da_p > 0.05),
            }

        return results

    def volatility_analysis(self) -> Dict:
        """Volatility metrics and regime detection."""
        returns = self.df["returns"].dropna() if "returns" in self.df.columns else self.df["close"].pct_change().dropna()

        if len(returns) < 20:
            return {"error": "Insufficient data"}

        # Rolling volatility
        vol_20 = returns.rolling(20).std() * np.sqrt(252)
        vol_60 = returns.rolling(60).std() * np.sqrt(252)

        # Historical VaR
        var_95 = float(returns.quantile(0.05))
        var_99 = float(returns.quantile(0.01))

        # CVaR (Expected Shortfall)
        cvar_95 = float(returns[returns <= var_95].mean())

        # Volatility regime
        current_vol = float(vol_20.iloc[-1]) if not vol_20.empty else 0
        avg_vol = float(vol_20.mean()) if not vol_20.empty else 0
        vol_regime = "HIGH" if current_vol > avg_vol * 1.2 else "LOW" if current_vol < avg_vol * 0.8 else "NORMAL"

        return {
            "current_annualized_vol": round(current_vol, 4),
            "average_annualized_vol": round(avg_vol, 4),
            "vol_regime": vol_regime,
            "var_95": round(var_95, 6),
            "var_99": round(var_99, 6),
            "cvar_95": round(cvar_95, 6),
            "vol_series": vol_20.tolist()[-50:] if not vol_20.empty else [],
        }

    def autocorrelation_analysis(self) -> Dict:
        """ACF/PACF analysis."""
        returns = self.df["returns"].dropna() if "returns" in self.df.columns else self.df["close"].pct_change().dropna()

        if len(returns) < 20 or not HAS_STATSMODELS:
            return {"error": "Insufficient data or statsmodels not installed"}

        # Ljung-Box test
        lb_result = acorr_ljungbox(returns, lags=[10, 20], return_df=True)
        lb_dict = {}
        for lag, row in lb_result.iterrows():
            lb_dict[int(lag)] = {
                "lb_stat": float(row["lb_stat"]),
                "lb_pvalue": float(row["lb_pvalue"]),
            }

        # Simple ACF values
        acf_values = [returns.autocorr(lag=i) for i in range(1, 21)]

        return {
            "ljung_box": lb_dict,
            "acf_values": [round(v, 4) for v in acf_values],
            "has_autocorrelation": any(
                v["lb_pvalue"] < 0.05 for v in lb_dict.values()
            ),
        }

    def descriptive_stats(self) -> Dict:
        """Basic descriptive statistics."""
        df = self.df
        return {
            "data_points": len(df),
            "date_range": {
                "start": str(df.index[0]) if len(df) > 0 else "",
                "end": str(df.index[-1]) if len(df) > 0 else "",
            },
            "price": {
                "open": round(float(df["open"].iloc[-1]), 4) if len(df) > 0 else 0,
                "high": round(float(df["high"].max()), 4) if len(df) > 0 else 0,
                "low": round(float(df["low"].min()), 4) if len(df) > 0 else 0,
                "close": round(float(df["close"].iloc[-1]), 4) if len(df) > 0 else 0,
                "avg_volume": round(float(df["volume"].mean()), 0) if "volume" in df.columns else 0,
            },
        }
