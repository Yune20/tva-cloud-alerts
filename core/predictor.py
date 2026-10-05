"""
ML Prediction Module
Ensemble of Random Forest, XGBoost, and LightGBM for price direction prediction.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import joblib
import os

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    from lightgbm import LGBMClassifier
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False

from config import (
    PREDICTION_LOOKBACK, PREDICTION_FORWARD,
    TRAIN_TEST_SPLIT, N_ESTIMATORS, RANDOM_STATE, CACHE_DIR,
)


class MLPredictor:
    """Ensemble ML model for price direction prediction."""

    FEATURE_COLS = [
        "returns", "log_returns", "momentum_10", "volatility_20", "price_range",
        "RSI", "MACD.macd", "MACD.signal", "MACD.hist",
        "BBU", "BBL", "BBM",
        "ADX", "ATR", "STOCH_K", "STOCH_D", "CCI", "WILLR", "MFI",
    ]

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.metrics: Dict = {}
        self.feature_importance: Dict = {}

    def prepare_features(self) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare feature matrix and target variable."""
        df = self.df.copy()

        # Ensure required indicators exist
        available = [c for c in self.FEATURE_COLS if c in df.columns]
        if len(available) < 5:
            raise ValueError(f"Too few features available: {available}")

        # Target: 1 if price goes up, 0 if down
        df["target"] = (df["close"].shift(-PREDICTION_FORWARD) > df["close"]).astype(int)

        # Drop NaN
        subset = df[available + ["target"]].dropna()
        if len(subset) < 50:
            raise ValueError(f"Not enough data for training: {len(subset)} rows")

        X = subset[available]
        y = subset["target"]

        return X, y

    def train(self, X: Optional[pd.DataFrame] = None, y: Optional[pd.Series] = None) -> Dict:
        """Train the ensemble model."""
        if X is None or y is None:
            X, y = self.prepare_features()

        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=1 - TRAIN_TEST_SPLIT,
            random_state=RANDOM_STATE, shuffle=False,
        )

        # Build ensemble
        estimators = [
            ("rf", RandomForestClassifier(
                n_estimators=N_ESTIMATORS,
                max_depth=8,
                min_samples_split=10,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )),
        ]

        if HAS_XGB:
            estimators.append(("xgb", XGBClassifier(
                n_estimators=N_ESTIMATORS,
                max_depth=6,
                learning_rate=0.1,
                use_label_encoder=False,
                eval_metric="logloss",
                random_state=RANDOM_STATE,
                verbosity=0,
            )))

        if HAS_LGBM:
            estimators.append(("lgbm", LGBMClassifier(
                n_estimators=N_ESTIMATORS,
                max_depth=6,
                learning_rate=0.1,
                random_state=RANDOM_STATE,
                verbose=-1,
            )))

        self.model = VotingClassifier(estimators=estimators, voting="soft")
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        y_proba = self.model.predict_proba(X_test)

        self.metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "classification_report": classification_report(y_test, y_pred, output_dict=True),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
            "train_size": len(X_train),
            "test_size": len(X_test),
        }

        # Feature importance (from RF only)
        rf_model = self.model.named_estimators_["rf"]
        importances = rf_model.feature_importances_
        feature_names = X.columns.tolist()
        self.feature_importance = dict(sorted(
            zip(feature_names, importances.tolist()),
            key=lambda x: x[1], reverse=True,
        ))

        self.is_trained = True
        self._save_model()

        return self.metrics

    def predict(self, X: Optional[pd.DataFrame] = None) -> Dict:
        """Make prediction on latest data."""
        if not self.is_trained:
            self._load_model()

        if self.model is None:
            return {"error": "Model not trained", "prediction": "UNKNOWN", "confidence": 0}

        if X is None:
            df = self.df.copy()
            available = [c for c in self.FEATURE_COLS if c in df.columns]
            latest = df[available].iloc[-1:].dropna()
            if latest.empty:
                return {"error": "No valid data for prediction", "prediction": "UNKNOWN", "confidence": 0}
            X = self.scaler.transform(latest)
        else:
            X = self.scaler.transform(X)

        prediction = int(self.model.predict(X)[0])
        probabilities = self.model.predict_proba(X)[0]

        direction = "LONG" if prediction == 1 else "SHORT"
        confidence = float(max(probabilities))

        return {
            "prediction": direction,
            "confidence": round(confidence, 4),
            "probability_up": round(float(probabilities[1]), 4),
            "probability_down": round(float(probabilities[0]), 4),
            "signal": direction if confidence > 0.6 else "NEUTRAL",
        }

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict for each row in dataframe (for backtesting)."""
        available = [c for c in self.FEATURE_COLS if c in df.columns]
        if not self.is_trained:
            self._load_model()
        if self.model is None:
            df["ml_signal"] = 0
            df["ml_confidence"] = 0
            return df

        valid = df[available].dropna()
        if valid.empty:
            df["ml_signal"] = 0
            df["ml_confidence"] = 0
            return df

        X_scaled = self.scaler.transform(valid)
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)

        df.loc[valid.index, "ml_signal"] = predictions
        df.loc[valid.index, "ml_confidence"] = [max(p) for p in probabilities]

        return df

    def _save_model(self) -> None:
        """Save trained model to cache."""
        path = CACHE_DIR / "ml_model.pkl"
        joblib.dump({
            "model": self.model,
            "scaler": self.scaler,
            "metrics": self.metrics,
            "feature_importance": self.feature_importance,
        }, path)

    def _load_model(self) -> bool:
        """Load cached model."""
        path = CACHE_DIR / "ml_model.pkl"
        if path.exists():
            try:
                data = joblib.load(path)
                self.model = data["model"]
                self.scaler = data["scaler"]
                self.metrics = data["metrics"]
                self.feature_importance = data["feature_importance"]
                self.is_trained = True
                return True
            except Exception:
                pass
        return False
