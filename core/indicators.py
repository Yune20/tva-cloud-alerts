"""
Technical Indicators Module
Uses pandas-ta, tradingview-ta, and ta-lib for comprehensive analysis.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple

try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

try:
    from tradingview_ta import TA_Handler, Interval, Exchange
    HAS_TV_TA = True
except ImportError:
    HAS_TV_TA = False


class TechnicalAnalyzer:
    """Compute technical indicators on OHLCV data."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.results: Dict[str, pd.Series] = {}

    def compute_all(
        self,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        bb_std: float = 2.0,
        ema_short: int = 21,
        ema_long: int = 50,
        adx_period: int = 14,
        atr_period: int = 14,
    ) -> pd.DataFrame:
        """Compute all technical indicators."""
        df = self.df

        if HAS_PANDAS_TA:
            df.ta.rsi(length=rsi_period, append=True)
            df.ta.macd(fast=macd_fast, slow=macd_slow, signal=macd_signal, append=True)
            df.ta.bbands(length=bb_period, std=bb_std, append=True)
            df.ta.adx(length=adx_period, append=True)
            df.ta.atr(length=atr_period, append=True)
            df.ta.stoch(append=True)
            df.ta.cci(length=20, append=True)
            df.ta.willr(length=14, append=True)
            df.ta.obv(append=True)
            df.ta.vwap(append=True)
            df.ta.mfi(length=14, append=True)
            df.ta.ema(length=ema_short, append=True)
            df.ta.ema(length=ema_long, append=True)
            df.ta.sma(length=20, append=True)
            df.ta.sma(length=50, append=True)
            df.ta.sma(length=200, append=True)
            df.ta.ichimoku(append=True)
            df.ta.supertrend(append=True)
            df.ta.kc(length=20, scalar=2.0, append=True)
            df.ta.donchian(length=20, append=True)
            df.ta.squeeze(length=20, append=True)
            df.ta.ao(append=True)
            df.ta.vortex(length=14, append=True)
            df.ta.aroon(length=25, append=True)
            df.ta.bop(append=True)
            df.ta.uo(append=True)
            df.ta.rsx(length=14, append=True)
            df.ta.fisher(length=9, append=True)
            df.ta.psar(append=True)
            df.ta.hma(length=20, append=True)
            df.ta.vwma(length=20, append=True)
        else:
            # Fallback: manual computation
            df = self._compute_manual(df, rsi_period, macd_fast, macd_slow, macd_signal,
                                       bb_period, bb_std, ema_short, ema_long, adx_period, atr_period)

        df = self._compute_extra(df)

        self.df = df
        return df

    def _compute_manual(
        self, df: pd.DataFrame,
        rsi_period, macd_fast, macd_slow, macd_signal,
        bb_period, bb_std, ema_short, ema_long, adx_period, atr_period,
    ) -> pd.DataFrame:
        """Manual indicator computation as fallback."""
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # MACD
        ema_f = close.ewm(span=macd_fast).mean()
        ema_s = close.ewm(span=macd_slow).mean()
        df["MACD.macd"] = ema_f - ema_s
        df["MACD.signal"] = df["MACD.macd"].ewm(span=macd_signal).mean()
        df["MACD.hist"] = df["MACD.macd"] - df["MACD.signal"]

        # Bollinger Bands
        sma = close.rolling(bb_period).mean()
        std = close.rolling(bb_period).std()
        df["BBU"] = sma + bb_std * std
        df["BBM"] = sma
        df["BBL"] = sma - bb_std * std

        # EMA
        df[f"EMA_{ema_short}"] = close.ewm(span=ema_short).mean()
        df[f"EMA_{ema_long}"] = close.ewm(span=ema_long).mean()

        # SMA
        df["SMA_20"] = close.rolling(20).mean()
        df["SMA_50"] = close.rolling(50).mean()
        df["SMA_200"] = close.rolling(200).mean()

        # ATR
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(atr_period).mean()

        # ADX (simplified)
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        atr_s = tr.ewm(span=adx_period).mean()
        plus_di = 100 * (plus_dm.ewm(span=adx_period).mean() / atr_s)
        minus_di = 100 * (minus_dm.ewm(span=adx_period).mean() / atr_s)
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
        df["ADX"] = dx.ewm(span=adx_period).mean()

        # Stochastic
        low_14 = low.rolling(14).min()
        high_14 = high.rolling(14).max()
        df["STOCH_K"] = 100 * (close - low_14) / (high_14 - low_14)
        df["STOCH_D"] = df["STOCH_K"].rolling(3).mean()

        # CCI
        tp = (high + low + close) / 3
        sma_tp = tp.rolling(20).mean()
        mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        df["CCI"] = (tp - sma_tp) / (0.015 * mad)

        # Williams %R
        df["WILLR"] = -100 * (high_14 - close) / (high_14 - low_14)

        # OBV
        obv = (np.sign(close.diff()) * df["volume"]).fillna(0).cumsum()
        df["OBV"] = obv

        # MFI
        tp_mfi = (high + low + close) / 3
        mf = tp_mfi * df["volume"]
        pos_mf = mf.where(tp_mfi > tp_mfi.shift(), 0).rolling(14).sum()
        neg_mf = mf.where(tp_mfi < tp_mfi.shift(), 0).rolling(14).sum()
        mfi_ratio = pos_mf / neg_mf
        df["MFI"] = 100 - (100 / (1 + mfi_ratio))

        # Custom
        df["returns"] = close.pct_change()
        df["log_returns"] = np.log(close / close.shift(1))
        df["volatility_20"] = df["returns"].rolling(20).std() * np.sqrt(252)
        df["momentum_10"] = close / close.shift(10) - 1
        df["price_range"] = (high - low) / close

        return df

    def _compute_extra(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute extended indicator set in pure pandas/numpy (no pandas-ta needed)."""
        close = df["close"]
        high = df["high"]
        low = df["low"]
        vol = df["volume"]
        n = len(df)

        def wilder(s, p):
            return s.ewm(alpha=1.0 / p, adjust=False).mean()

        def wma(s, p):
            w = np.arange(1, p + 1)
            den = w.sum()
            return s.rolling(p).apply(lambda x: float((x * w).sum()) / den, raw=True)

        # True range
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)

        # VWAP
        if "VWAP" not in df.columns:
            typical = (high + low + close) / 3
            cum_vp = (typical * vol).cumsum()
            cum_v = vol.cumsum()
            df["VWAP"] = (cum_vp / cum_v).replace([np.inf, -np.inf], np.nan)

        # Ichimoku (10/26/52-ish, standard 9/26/52)
        if "ITS_9" not in df.columns:
            t9 = (high.rolling(9).max() + low.rolling(9).min()) / 2
            k26 = (high.rolling(26).max() + low.rolling(26).min()) / 2
            s52 = (high.rolling(52).max() + low.rolling(52).min()) / 2
            df["ITS_9"] = t9
            df["IKS_26"] = k26
            df["ISA_9"] = ((t9 + k26) / 2).shift(26)
            df["ISB_26"] = ((k26 + s52) / 2).shift(26)
            df["ICS_26"] = close.shift(-26)

        # Supertrend (10, 3)
        if "SUPERT_10_3.0" not in df.columns:
            atr_st = wilder(tr, 10)
            hl2 = (high + low) / 2
            up_base = hl2 + 3 * atr_st
            dn_base = hl2 - 3 * atr_st
            st = pd.Series(np.nan, index=df.index)
            dirn = pd.Series(1, index=df.index, dtype=float)
            upv = np.zeros(n)
            dnv = np.zeros(n)
            for i in range(1, n):
                upv[i] = up_base.iloc[i] if (up_base.iloc[i] < upv[i - 1] or close.iloc[i - 1] > upv[i - 1]) else upv[i - 1]
                dnv[i] = dn_base.iloc[i] if (dn_base.iloc[i] > dnv[i - 1] or close.iloc[i - 1] < dnv[i - 1]) else dnv[i - 1]
                if pd.isna(st.iloc[i - 1]):
                    dirn.iloc[i] = 1
                elif dirn.iloc[i - 1] == 1:
                    dirn.iloc[i] = 1 if close.iloc[i] > dnv[i] else -1
                else:
                    dirn.iloc[i] = -1 if close.iloc[i] < upv[i] else 1
                st.iloc[i] = dnv[i] if dirn.iloc[i] == 1 else upv[i]
            df["SUPERT_10_3.0"] = st
            df["SUPERTd_10_3.0"] = dirn

        # Keltner Channels (EMA20 +- 2*ATR20)
        if "KCUe_20_2.0" not in df.columns:
            ema20 = close.ewm(span=20).mean()
            atr20 = wilder(tr, 20)
            df["KCUe_20_2.0"] = ema20 + 2 * atr20
            df["KCBe_20_2.0"] = ema20
            df["KCLe_20_2.0"] = ema20 - 2 * atr20

        # Donchian Channel (20)
        if "DCU_20_0" not in df.columns:
            df["DCU_20_0"] = high.rolling(20).max()
            df["DCL_20_0"] = low.rolling(20).min()
            df["DCM_20_0"] = (df["DCU_20_0"] + df["DCL_20_0"]) / 2

        # Squeeze: Bollinger(20,2) width vs Keltner(20,2) width
        if not any(c.startswith("SQZ_") for c in df.columns):
            sd20 = close.rolling(20).std()
            bb_w = 4 * sd20
            kc_w = df["KCUe_20_2.0"] - df["KCLe_20_2.0"]
            sqz = pd.Series(np.nan, index=df.index)
            on = (bb_w < kc_w)
            sqz[on] = -1.0
            sqz[~on & kc_w.notna()] = 1.0
            df["SQZ_20_2.0_20_2.0"] = sqz

        # Awesome Oscillator
        if "AO" not in df.columns:
            mid = (high + low) / 2
            df["AO"] = mid.rolling(5).mean() - mid.rolling(34).mean()

        # Vortex (14)
        if not any(c.startswith("VTXP") for c in df.columns):
            trsum14 = tr.rolling(14).sum()
            df["VTXP_14"] = (high - low.shift()).abs().rolling(14).sum() / trsum14
            df["VTXM_14"] = (low - high.shift()).abs().rolling(14).sum() / trsum14

        # Aroon (25)
        if not any(c.startswith("AROON") for c in df.columns):
            per = 25
            df["AROONU_25"] = 100.0 * high.rolling(per + 1).apply(lambda x: np.argmax(x), raw=True) / per
            df["AROOND_25"] = 100.0 * low.rolling(per + 1).apply(lambda x: np.argmin(x), raw=True) / per
            df["AROONOSC_25"] = df["AROONU_25"] - df["AROOND_25"]

        # Balance of Power
        if "BOP" not in df.columns:
            rng = (high - low).replace(0, np.nan)
            df["BOP"] = ((close - df["open"]) / rng).replace([np.inf, -np.inf], np.nan).fillna(0)

        # Ultimate Oscillator (7, 14, 28)
        if "UO" not in df.columns:
            bp_uo = close - pd.concat([low.shift(), close.shift()], axis=1).min(axis=1)
            tr_uo = tr
            avg7 = bp_uo.rolling(7).sum() / tr_uo.rolling(7).sum()
            avg14 = bp_uo.rolling(14).sum() / tr_uo.rolling(14).sum()
            avg28 = bp_uo.rolling(28).sum() / tr_uo.rolling(28).sum()
            df["UO"] = 100.0 * (4 * avg7 + 2 * avg14 + 1 * avg28) / (4 + 2 + 1)

        # Fisher Transform (9)
        if not any("FISHER" in c and "FISHERs" not in c for c in df.columns):
            h9 = high.rolling(9).max()
            l9 = low.rolling(9).min()
            hl2 = (high + low) / 2
            rng9 = (h9 - l9).replace(0, np.nan)
            x_raw = 2 * ((hl2 - l9) / rng9 - 0.5)
            x_x = (0.33 * x_raw).ewm(alpha=0.67).mean()
            fish = 0.5 * np.log((1 + x_x).clip(lower=1e-9) / (2 - x_x).clip(lower=1e-9) - (1 if False else 0))
            df["FISHER"] = fish
            df["FISHERs"] = fish.shift(1)

        # PSAR (Wilder, 0.02 / 0.20)
        if not any(c.startswith("PSARl") or c.startswith("PSARs") for c in df.columns):
            af = 0.02
            af_max = 0.20
            sar = np.full(n, np.nan)
            trend = np.ones(n, dtype=float)
            ep = np.full(n, np.nan)
            afp = np.full(n, af)
            if n > 0:
                sar[0] = low.iloc[0]
                ep[0] = high.iloc[0]
                if n > 1:
                    trend[1] = 1.0 if close.iloc[1] >= close.iloc[0] else -1.0
            for i in range(1, n):
                prev_trend = trend[i - 1]
                prev_sar = sar[i - 1]
                if prev_trend == 1:
                    sar[i] = prev_sar + afp[i - 1] * (ep[i - 1] - prev_sar)
                    sar[i] = min(sar[i], low.iloc[i - 1], low.iloc[i - 2] if i >= 2 else low.iloc[i - 1])
                    if low.iloc[i] < sar[i]:
                        trend[i] = -1.0
                        sar[i] = ep[i - 1]
                        ep[i] = low.iloc[i]
                        afp[i] = af
                    else:
                        trend[i] = 1.0
                        if high.iloc[i] > ep[i - 1]:
                            ep[i] = high.iloc[i]
                            afp[i] = min(afp[i - 1] + af, af_max)
                        else:
                            ep[i] = ep[i - 1]
                            afp[i] = afp[i - 1]
                else:
                    sar[i] = prev_sar - afp[i - 1] * (prev_sar - ep[i - 1])
                    sar[i] = max(sar[i], high.iloc[i - 1], high.iloc[i - 2] if i >= 2 else high.iloc[i - 1])
                    if high.iloc[i] > sar[i]:
                        trend[i] = 1.0
                        sar[i] = ep[i - 1]
                        ep[i] = high.iloc[i]
                        afp[i] = af
                    else:
                        trend[i] = -1.0
                        if low.iloc[i] < ep[i - 1]:
                            ep[i] = low.iloc[i]
                            afp[i] = min(afp[i - 1] + af, af_max)
                        else:
                            ep[i] = ep[i - 1]
                            afp[i] = afp[i - 1]
            psar_s = pd.Series(sar, index=df.index, dtype=float)
            psar_l = psar_s.where(pd.Series(trend) == 1)
            psar_s_ = psar_s.where(pd.Series(trend) == -1)
            df["PSARl_0.02_0.2"] = psar_l
            df["PSARs_0.02_0.2"] = psar_s_

        # HMA (20)
        if "HMA_20" not in df.columns:
            half = wma(close, 10)
            full = wma(close, 20)
            df["HMA_20"] = wma(2 * half - full, 4)

        # VWMA (20)
        if "VWMA_20" not in df.columns:
            df["VWMA_20"] = (close * vol).rolling(20).sum() / vol.rolling(20).sum()

        # Elder Ray (Bull/Bear Power)
        if "BullPower" not in df.columns:
            ema13 = close.ewm(span=13).mean()
            df["BullPower"] = high - ema13
            df["BearPower"] = low - ema13

        # CMF (Chaikin Money Flow)
        if "CMF" not in df.columns:
            mfm = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
            mfm = mfm.replace([np.inf, -np.inf], 0).fillna(0)
            df["CMF"] = (mfm * vol).rolling(20).sum() / vol.rolling(20).sum()

        # TRIX
        if "TRIX" not in df.columns:
            ema1 = close.ewm(span=15).mean()
            ema2 = ema1.ewm(span=15).mean()
            ema3 = ema2.ewm(span=15).mean()
            df["TRIX"] = ema3.pct_change() * 100

        # Relative Volume
        if "RelVol" not in df.columns:
            df["RelVol"] = vol / vol.rolling(20).mean()

        return df

    def get_tradingview_recommendation(self, symbol: str = "", interval: str = "1D") -> Dict:
        """Get recommendation from TradingView's built-in analysis."""
        if not HAS_TV_TA:
            return {"error": "tradingview-ta not installed"}

        try:
            ta_handler = TA_Handler(
                symbol=symbol.split(":")[-1] if ":" in symbol else symbol,
                screener="forex" if "FX" in symbol.upper() or "OANDA" in symbol.upper() else "crypto",
                exchange=symbol.split(":")[0] if ":" in symbol else "",
                interval=interval,
            )
            analysis = ta_handler.get_analysis()
            return {
                "summary": analysis.summary,
                "indicators": analysis.indicators,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_latest_signals(self) -> Dict:
        """Get latest indicator values and signals."""
        df = self.df
        if df.empty:
            return {}

        latest = df.iloc[-1]
        signals = {}

        # RSI
        rsi_col = [c for c in df.columns if "RSI" in c and "STOCH" not in c]
        if rsi_col:
            rsi_val = latest[rsi_col[0]]
            signals["RSI"] = {
                "value": round(rsi_val, 2),
                "signal": "OVERBOUGHT" if rsi_val > 70 else "OVERSOLD" if rsi_val < 30 else "NEUTRAL",
            }

        # MACD
        macd_cols = [c for c in df.columns if "MACD.macd" in c]
        signal_cols = [c for c in df.columns if "MACD.signal" in c]
        hist_cols = [c for c in df.columns if "MACD.hist" in c]
        if macd_cols and signal_cols:
            macd_val = latest[macd_cols[0]]
            signal_val = latest[signal_cols[0]]
            hist_val = latest[hist_cols[0]] if hist_cols else macd_val - signal_val
            if pd.notna(macd_val) and pd.notna(signal_val):
                signals["MACD"] = {
                    "macd": round(float(macd_val), 4),
                    "signal": round(float(signal_val), 4),
                    "histogram": round(float(hist_val), 4) if pd.notna(hist_val) else 0,
                    "direction": "BULLISH" if pd.notna(hist_val) and hist_val > 0 else "BEARISH",
                }

        # Bollinger Bands
        bbu = [c for c in df.columns if c.startswith("BBU") or "BB.upper" in c]
        bbl = [c for c in df.columns if c.startswith("BBL") or "BB.lower" in c]
        if bbu and bbl:
            upper = latest[bbu[0]]
            lower = latest[bbl[0]]
            price = latest["close"]
            signals["Bollinger"] = {
                "upper": round(upper, 4),
                "lower": round(lower, 4),
                "position": round((price - lower) / (upper - lower) * 100, 1) if upper != lower else 50,
                "signal": "OVERBOUGHT" if price > upper else "OVERSOLD" if price < lower else "NEUTRAL",
            }

        # ADX
        adx_col = [c for c in df.columns if c == "ADX" or ("ADX" in c and "DI" not in c)]
        if adx_col:
            adx_val = latest[adx_col[0]]
            if pd.notna(adx_val):
                signals["ADX"] = {
                    "value": round(float(adx_val), 2),
                    "trend_strength": "STRONG" if adx_val > 25 else "WEAK",
                }

        # ATR
        atr_col = [c for c in df.columns if "ATR" in c]
        if atr_col:
            atr_val = latest[atr_col[0]]
            price = latest["close"]
            if pd.notna(atr_val) and pd.notna(price) and price != 0:
                signals["ATR"] = {
                    "value": round(float(atr_val), 4),
                    "percent": round(float(atr_val / price * 100), 2),
                }

        # Stochastic
        stoch_k = [c for c in df.columns if "STOCH_K" in c or c == "Stoch.K"]
        stoch_d = [c for c in df.columns if "STOCH_D" in c or c == "Stoch.D"]
        if stoch_k:
            k_val = latest[stoch_k[0]]
            d_val = latest[stoch_d[0]] if stoch_d else k_val
            signals["Stochastic"] = {
                "K": round(k_val, 2),
                "D": round(d_val, 2),
                "signal": "OVERBOUGHT" if k_val > 80 else "OVERSOLD" if k_val < 20 else "NEUTRAL",
            }

        # EMA Cross
        ema_cols = sorted([c for c in df.columns if c.startswith("EMA_")])
        if len(ema_cols) >= 2:
            ema_short_val = latest[ema_cols[0]]
            ema_long_val = latest[ema_cols[1]]
            signals["EMA_Cross"] = {
                "short": round(ema_short_val, 4),
                "long": round(ema_long_val, 4),
                "signal": "GOLDEN" if ema_short_val > ema_long_val else "DEATH",
            }

        # OBV trend
        obv_col = [c for c in df.columns if "OBV" in c]
        if obv_col and len(df) > 10:
            obv_series = df[obv_col[0]].dropna()
            if len(obv_series) > 10:
                obv_trend = "RISING" if obv_series.iloc[-1] > obv_series.iloc[-10] else "FALLING"
                obv_now = float(obv_series.iloc[-1])
                obv_prev = float(obv_series.iloc[-5]) if len(obv_series) > 5 else obv_now
                obv_chg = ((obv_now - obv_prev) / abs(obv_prev) * 100) if obv_prev != 0 else 0
                signals["OBV"] = {"trend": obv_trend, "value": round(obv_now, 0), "change_pct": round(obv_chg, 2)}

        # MFI (Money Flow Index)
        mfi_col = [c for c in df.columns if c == "MFI"]
        if mfi_col:
            mfi_val = latest[mfi_col[0]]
            if pd.notna(mfi_val):
                signals["MFI"] = {
                    "value": round(float(mfi_val), 2),
                    "signal": "OVERBOUGHT" if mfi_val > 80 else "OVERSOLD" if mfi_val < 20 else "NEUTRAL",
                    "buying_pressure": round(float(mfi_val), 1),
                }

        # CCI
        cci_col = [c for c in df.columns if c == "CCI"]
        if cci_col:
            cci_val = latest[cci_col[0]]
            if pd.notna(cci_val):
                signals["CCI"] = {
                    "value": round(float(cci_val), 2),
                    "signal": "OVERBOUGHT" if cci_val > 100 else "OVERSOLD" if cci_val < -100 else "NEUTRAL",
                }

        # Williams %R
        willr_col = [c for c in df.columns if c == "WILLR"]
        if willr_col:
            willr_val = latest[willr_col[0]]
            if pd.notna(willr_val):
                signals["WilliamsR"] = {
                    "value": round(float(willr_val), 2),
                    "signal": "OVERBOUGHT" if willr_val > -20 else "OVERSOLD" if willr_val < -80 else "NEUTRAL",
                    "buying_pressure": round(float(-willr_val), 1),  # Inverted: 0-100 scale
                }

        # VWAP
        vwap_col = [c for c in df.columns if "VWAP" in c]
        if vwap_col:
            vwap_val = latest[vwap_col[0]]
            price = latest["close"]
            if pd.notna(vwap_val) and pd.notna(price) and vwap_val != 0:
                vwap_dist = (price - vwap_val) / vwap_val * 100
                signals["VWAP"] = {
                    "value": round(float(vwap_val), 4),
                    "distance_pct": round(float(vwap_dist), 2),
                    "signal": "ABOVE" if price > vwap_val else "BELOW",
                }

        # Accumulation/Distribution
        ad = ((latest["close"] - latest["low"]) - (latest["high"] - latest["close"])) / (latest["high"] - latest["low"]) if (latest["high"] - latest["low"]) != 0 else 0
        ad_val = ad * latest["volume"]
        if len(df) > 20:
            ad_list = []
            for i in range(-20, 0):
                h, l, c, v = df["high"].iloc[i], df["low"].iloc[i], df["close"].iloc[i], df["volume"].iloc[i]
                ad_i = ((c - l) - (h - c)) / (h - l) * v if (h - l) != 0 else 0
                ad_list.append(ad_i)
            ad_sum = sum(ad_list)
            ad_trend = "ACCUMULATION" if ad_sum > 0 else "DISTRIBUTION"
            signals["AD"] = {
                "value": round(float(ad_val), 0),
                "trend_20": ad_trend,
                "sum_20": round(float(ad_sum), 0),
            }

        # Relative Volume (vs 20-bar average)
        if len(df) > 20:
            avg_vol = df["volume"].iloc[-20:].mean()
            cur_vol = latest["volume"]
            if avg_vol > 0:
                rel_vol = cur_vol / avg_vol
                signals["RelativeVolume"] = {
                    "value": round(float(rel_vol), 2),
                    "signal": "HIGH" if rel_vol > 1.5 else "LOW" if rel_vol < 0.5 else "NORMAL",
                }

        # RSI Divergence (look back 30 bars)
        rsi_col2 = [c for c in df.columns if "RSI" in c and "STOCH" not in c]
        if rsi_col2 and len(df) > 30:
            rsi_s = df[rsi_col2[0]].dropna()
            close_s = df["close"]
            if len(rsi_s) > 30:
                rsi_recent = rsi_s.iloc[-30:]
                close_recent = close_s.iloc[-30:]
                # Find swing lows in price
                price_lows = []
                rsi_lows = []
                for i in range(2, len(rsi_recent) - 2):
                    if close_recent.iloc[i] < close_recent.iloc[i-1] and close_recent.iloc[i] < close_recent.iloc[i+1]:
                        price_lows.append((i, close_recent.iloc[i]))
                        rsi_lows.append((i, rsi_recent.iloc[i]))
                if len(price_lows) >= 2:
                    if price_lows[-1][1] < price_lows[-2][1] and rsi_lows[-1][1] > rsi_lows[-2][1]:
                        signals["RSI_Divergence"] = {"type": "BULLISH", "detail": "Price ↓ but RSI ↑"}
                # Find swing highs
                price_highs = []
                rsi_highs = []
                for i in range(2, len(rsi_recent) - 2):
                    if close_recent.iloc[i] > close_recent.iloc[i-1] and close_recent.iloc[i] > close_recent.iloc[i+1]:
                        price_highs.append((i, close_recent.iloc[i]))
                        rsi_highs.append((i, rsi_recent.iloc[i]))
                if len(price_highs) >= 2:
                    if price_highs[-1][1] > price_highs[-2][1] and rsi_highs[-1][1] < rsi_highs[-2][1]:
                        signals["RSI_Divergence"] = {"type": "BEARISH", "detail": "Price ↑ but RSI ↓"}

        # Ichimoku
        ichi_cols = [c for c in df.columns if "ISA_" in c or "ISB_" in c or "ITS_" in c or "ICS_" in c]
        if len(ichi_cols) >= 4 and len(df) > 0:
            isa = [c for c in df.columns if c.startswith("ISA_")]
            isb = [c for c in df.columns if c.startswith("ISB_")]
            its = [c for c in df.columns if c.startswith("ITS_")]
            ics = [c for c in df.columns if c.startswith("ICS_")]
            if isa and isb and its and ics:
                cloud_top = max(float(latest[isa[0]]) if pd.notna(latest[isa[0]]) else 0, float(latest[isb[0]]) if pd.notna(latest[isb[0]]) else 0)
                cloud_bot = min(float(latest[isa[0]]) if pd.notna(latest[isa[0]]) else 0, float(latest[isb[0]]) if pd.notna(latest[isb[0]]) else 0)
                price = latest["close"]
                tenkan = latest[its[0]] if pd.notna(latest[its[0]]) else price
                kijun = latest[ics[0]] if pd.notna(latest[ics[0]]) else price
                if price > cloud_top:
                    ichi_signal = "BULLISH"
                elif price < cloud_bot:
                    ichi_signal = "BEARISH"
                else:
                    ichi_signal = "IN_CLOUD"
                tk_cross = "BULL" if float(tenkan) > float(kijun) else "BEAR"
                signals["Ichimoku"] = {
                    "signal": ichi_signal,
                    "tenkan": round(float(tenkan), 4),
                    "kijun": round(float(kijun), 4),
                    "tk_cross": tk_cross,
                    "cloud_top": round(cloud_top, 4),
                    "cloud_bot": round(cloud_bot, 4),
                }

        # Supertrend
        st_cols = [c for c in df.columns if "SUPERT" in c and "SUPERTd" not in c]
        std_cols = [c for c in df.columns if "SUPERTd" in c]
        if st_cols and std_cols:
            st_val = latest[st_cols[0]]
            st_dir = latest[std_cols[0]]
            if pd.notna(st_val) and pd.notna(st_dir):
                signals["Supertrend"] = {
                    "value": round(float(st_val), 4),
                    "direction": "BULL" if float(st_dir) > 0 else "BEAR",
                }

        # Keltner Channels
        kc_upper = [c for c in df.columns if "KCUe" in c or "KC_upper" in c]
        kc_lower = [c for c in df.columns if "KCLe" in c or "KC_lower" in c]
        if kc_upper and kc_lower:
            ku = float(latest[kc_upper[0]]) if pd.notna(latest[kc_upper[0]]) else 0
            kl = float(latest[kc_lower[0]]) if pd.notna(latest[kc_lower[0]]) else 0
            price = latest["close"]
            if ku > kl:
                kc_pos = (price - kl) / (ku - kl) * 100
                signals["Keltner"] = {
                    "upper": round(ku, 4),
                    "lower": round(kl, 4),
                    "position": round(float(kc_pos), 1),
                    "signal": "ABOVE" if price > ku else "BELOW" if price < kl else "INSIDE",
                }

        # Donchian
        dc_upper = [c for c in df.columns if "DCU_" in c or "DONCHIAN_upper" in c]
        dc_lower = [c for c in df.columns if "DCL_" in c or "DONCHIAN_lower" in c]
        if dc_upper and dc_lower:
            du = float(latest[dc_upper[0]]) if pd.notna(latest[dc_upper[0]]) else 0
            dl = float(latest[dc_lower[0]]) if pd.notna(latest[dc_lower[0]]) else 0
            price = latest["close"]
            if du > dl:
                dc_pos = (price - dl) / (du - dl) * 100
                signals["Donchian"] = {
                    "upper": round(du, 4),
                    "lower": round(dl, 4),
                    "position": round(float(dc_pos), 1),
                    "signal": "BREAKOUT_UP" if price >= du else "BREAKOUT_DOWN" if price <= dl else "INSIDE",
                }

        # Squeeze Momentum
        sq_cols = [c for c in df.columns if "SQZ_" in c or "squeeze" in c.lower()]
        if sq_cols:
            sq_val = latest[sq_cols[0]] if pd.notna(latest[sq_cols[0]]) else 0
            signals["Squeeze"] = {"value": round(float(sq_val), 4), "signal": "FIRED" if sq_val > 0 else "WAITING"}

        # Awesome Oscillator
        ao_cols = [c for c in df.columns if c == "AO" or "awesome" in c.lower()]
        if ao_cols:
            ao_val = latest[ao_cols[0]] if pd.notna(latest[ao_cols[0]]) else 0
            ao_prev = df[ao_cols[0]].iloc[-2] if len(df) > 1 and pd.notna(df[ao_cols[0]].iloc[-2]) else 0
            signals["AwesomeOsc"] = {
                "value": round(float(ao_val), 4),
                "signal": "BULL" if ao_val > 0 else "BEAR",
                "momentum": "INCREASING" if ao_val > ao_prev else "DECREASING",
            }

        # Aroon
        aroon_up_cols = [c for c in df.columns if "AROONU" in c.upper() or "AROON_UP" in c.upper()]
        aroon_dn_cols = [c for c in df.columns if "AROOND" in c.upper() or "AROON_DOWN" in c.upper()]
        if aroon_up_cols and aroon_dn_cols:
            au = float(latest[aroon_up_cols[0]]) if pd.notna(latest[aroon_up_cols[0]]) else 50
            ad_val = float(latest[aroon_dn_cols[0]]) if pd.notna(latest[aroon_dn_cols[0]]) else 50
            if au > 70 and ad_val < 30:
                ar_sig = "STRONG_BULL"
            elif au < 30 and ad_val > 70:
                ar_sig = "STRONG_BEAR"
            else:
                ar_sig = "NEUTRAL"
            signals["Aroon"] = {"up": round(au, 1), "down": round(ad_val, 1), "signal": ar_sig}

        # Vortex
        vp_cols = [c for c in df.columns if "VTXP" in c or "VIP" in c]
        vm_cols = [c for c in df.columns if "VTXM" in c or "VIN" in c]
        if vp_cols and vm_cols:
            vp = float(latest[vp_cols[0]]) if pd.notna(latest[vp_cols[0]]) else 1
            vm = float(latest[vm_cols[0]]) if pd.notna(latest[vm_cols[0]]) else 1
            signals["Vortex"] = {"plus": round(vp, 4), "minus": round(vm, 4), "signal": "BULL" if vp > vm else "BEAR"}

        # Balance of Power
        bop_cols = [c for c in df.columns if c == "BOP"]
        if bop_cols:
            bop_val = float(latest[bop_cols[0]]) if pd.notna(latest[bop_cols[0]]) else 0
            signals["BOP"] = {"value": round(bop_val, 4), "signal": "BUYERS" if bop_val > 0 else "SELLERS"}

        # Elder Ray
        bp_cols = [c for c in df.columns if c == "BullPower"]
        br_cols = [c for c in df.columns if c == "BearPower"]
        if bp_cols and br_cols:
            bp = float(latest[bp_cols[0]]) if pd.notna(latest[bp_cols[0]]) else 0
            br = float(latest[br_cols[0]]) if pd.notna(latest[br_cols[0]]) else 0
            if bp > 0 and br > 0:
                er_sig = "STRONG_BULL"
            elif bp < 0 and br < 0:
                er_sig = "STRONG_BEAR"
            elif bp > 0 and br < 0:
                er_sig = "MIXED_BULL"
            else:
                er_sig = "MIXED_BEAR"
            signals["ElderRay"] = {"bull": round(bp, 4), "bear": round(br, 4), "signal": er_sig}

        # CMF
        cmf_cols = [c for c in df.columns if c == "CMF"]
        if cmf_cols:
            cmf_val = float(latest[cmf_cols[0]]) if pd.notna(latest[cmf_cols[0]]) else 0
            signals["CMF"] = {"value": round(cmf_val, 4), "signal": "BUYING" if cmf_val > 0.05 else "SELLING" if cmf_val < -0.05 else "NEUTRAL"}

        # TRIX
        trix_cols = [c for c in df.columns if c == "TRIX"]
        if trix_cols:
            trix_val = float(latest[trix_cols[0]]) if pd.notna(latest[trix_cols[0]]) else 0
            signals["TRIX"] = {"value": round(trix_val, 4), "signal": "BULL" if trix_val > 0 else "BEAR"}

        # Fisher
        fisher_cols = [c for c in df.columns if "FISHER" in c and "FISHERs" not in c]
        fisher_s_cols = [c for c in df.columns if "FISHERs" in c]
        if fisher_cols:
            fv = float(latest[fisher_cols[0]]) if pd.notna(latest[fisher_cols[0]]) else 0
            fs = float(latest[fisher_s_cols[0]]) if fisher_s_cols and pd.notna(latest[fisher_s_cols[0]]) else 0
            signals["Fisher"] = {"value": round(fv, 4), "signal": "BULL" if fv > 0 else "BEAR", "cross": "BULL" if fv > fs else "BEAR"}

        # PSAR
        psar_cols = [c for c in df.columns if "PSAR" in c and "PSARl" not in c and "PSARs" not in c]
        psarl_cols = [c for c in df.columns if c.startswith("PSARl")]
        psars_cols = [c for c in df.columns if c.startswith("PSARs")]
        if psarl_cols or psars_cols:
            psar_long = True if psarl_cols and pd.notna(latest.get(psarl_cols[0])) else False
            signals["PSAR"] = {"direction": "BULL" if psar_long else "BEAR"}

        # MACD Histogram momentum (consecutive bars)
        hist_cols = [c for c in df.columns if "MACD.hist" in c]
        if hist_cols and len(df) > 5:
            hist_s = df[hist_cols[0]].dropna()
            if len(hist_s) > 5:
                last5 = hist_s.iloc[-5:].values
                consec_up = all(last5[i] > last5[i-1] for i in range(1, len(last5)))
                consec_dn = all(last5[i] < last5[i-1] for i in range(1, len(last5)))
                if consec_up:
                    signals["MACD_Momentum"] = {"direction": "ACCELERATING_BULL", "detail": "5 consecutive histogram increases"}
                elif consec_dn:
                    signals["MACD_Momentum"] = {"direction": "ACCELERATING_BEAR", "detail": "5 consecutive histogram decreases"}

        return signals
