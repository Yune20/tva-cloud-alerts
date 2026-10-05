"""
Persistent SQLite cache for OHLCV frames, TradingView scanner quotes and
watchlist quotes.

Why: yfinance / TradingView are slow and rate-limit hard (HTTP 429). Keeping
each (symbol, interval) frame in local SQLite means re-analysis loads in
milliseconds and only refetches when the cached bars are older than the
interval's TTL (i.e. once per closed bar).
"""
import json
import os
import sqlite3
import threading
import time
from typing import Dict, Optional

import pandas as pd

import config as cfg

TTL_BY_INTERVAL: Dict[str, float] = {
    "1m": 45.0, "5m": 120.0, "15m": 180.0, "30m": 300.0,
    "1H": 600.0, "4H": 1800.0, "1D": 3600.0, "1W": 7200.0, "1M": 86400.0,
}
DEFAULT_TTL = 300.0
SCANNER_TTL = 30.0
QUOTE_TTL = 30.0

_OHLCV_COLS = ("open", "high", "low", "close", "volume")


class OHLCVCache:
    """Thread-safe SQLite-backed cache for market data."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or getattr(cfg, "OHLCV_CACHE_PATH", None) \
            or os.path.join(os.path.dirname(cfg.DB_PATH), "cache", "ohlcv.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS ohlcv_cache (
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'yfinance',
            fetched_at REAL NOT NULL,
            bar_count INTEGER NOT NULL DEFAULT 0,
            last_ts TEXT,
            ohlcv_json TEXT NOT NULL,
            PRIMARY KEY (symbol, interval)
        );
        CREATE TABLE IF NOT EXISTS scanner_cache (
            symbol TEXT NOT NULL PRIMARY KEY,
            fetched_at REAL NOT NULL,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS kv_cache (
            key TEXT NOT NULL PRIMARY KEY,
            fetched_at REAL NOT NULL,
            payload TEXT NOT NULL
        );
        """)
        self.conn.commit()

    # ── OHLCV frames ────────────────────────────────────────────
    def get_frame(self, symbol: str, interval: str, max_age: float = None) -> Optional[pd.DataFrame]:
        ttl = max_age if max_age is not None else \
            TTL_BY_INTERVAL.get(str(interval).upper(), DEFAULT_TTL)
        key = (str(symbol).strip().upper(), str(interval).upper())
        try:
            row = self.conn.execute(
                "SELECT fetched_at, ohlcv_json FROM ohlcv_cache "
                "WHERE symbol = ? AND interval = ?", key
            ).fetchone()
        except sqlite3.Error:
            return None
        if not row or (time.time() - row["fetched_at"]) > ttl:
            return None
        try:
            payload = json.loads(row["ohlcv_json"])
        except (ValueError, TypeError):
            return None
        if not payload or "index" not in payload:
            return None
        df = pd.DataFrame({c: payload.get(c, []) for c in _OHLCV_COLS})
        try:
            # Writers store UTC wall-times (see put_frame); restore as tz-aware UTC
            # so `int(ts.timestamp()*1000)` in server.df_to_bars yields exact epochs.
            df.index = pd.to_datetime(payload["index"], utc=True)
        except (ValueError, TypeError, KeyError):
            return None
        df.index.name = "date"
        return df

    def put_frame(self, symbol: str, interval: str, df: pd.DataFrame, source: str) -> None:
        if df is None or df.empty:
            return
        frame = df.last_valid_index()
        last_ts = frame.strftime("%Y-%m-%d %H:%M:%S") if frame is not None else None
        payload = {
            "index": [ts.strftime("%Y-%m-%d %H:%M:%S") for ts in df.index],
            "open": [float(v) if v is not None else None for v in df["open"]],
            "high": [float(v) if v is not None else None for v in df["high"]],
            "low": [float(v) if v is not None else None for v in df["low"]],
            "close": [float(v) if v is not None else None for v in df["close"]],
            "volume": [float(v) if v is not None else None for v in df["volume"]],
        }
        with self._lock:
            try:
                self.conn.execute(
                    "INSERT OR REPLACE INTO ohlcv_cache "
                    "(symbol, interval, source, fetched_at, bar_count, last_ts, ohlcv_json) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (str(symbol).strip().upper(), str(interval).upper(), source,
                     time.time(), int(len(df)), last_ts, json.dumps(payload)),
                )
                self.conn.commit()
            except sqlite3.Error:
                pass

    def purge(self, days: int = 30) -> int:
        """Delete frames older than N days (failsafe for runaway growth)."""
        cutoff = time.time() - days * 86400
        with self._lock:
            try:
                cur = self.conn.execute(
                    "DELETE FROM ohlcv_cache WHERE fetched_at < ?", (cutoff,))
                self.conn.execute("DELETE FROM scanner_cache WHERE fetched_at < ?", (cutoff,))
                self.conn.execute("DELETE FROM kv_cache WHERE fetched_at < ?", (cutoff,))
                self.conn.commit()
                return cur.rowcount
            except sqlite3.Error:
                return 0

    # ── TradingView scanner quote ───────────────────────────────
    def get_scanner(self, symbol: str, max_age: float = SCANNER_TTL) -> Optional[dict]:
        s = str(symbol).strip().upper()
        try:
            row = self.conn.execute(
                "SELECT fetched_at, payload FROM scanner_cache WHERE symbol = ?", (s,)
            ).fetchone()
        except sqlite3.Error:
            return None
        if not row or (time.time() - row["fetched_at"]) > max_age:
            return None
        try:
            return json.loads(row["payload"])
        except (ValueError, TypeError):
            return None

    def put_scanner(self, symbol: str, result: dict) -> None:
        s = str(symbol).strip().upper()
        with self._lock:
            try:
                self.conn.execute(
                    "INSERT OR REPLACE INTO scanner_cache (symbol, fetched_at, payload) "
                    "VALUES (?,?,?)", (s, time.time(), json.dumps(result)),
                )
                self.conn.commit()
            except sqlite3.Error:
                pass

    # ── Generic key/value cache (watchlist quotes etc.) ─────────
    def get_kv(self, key: str, max_age: float = QUOTE_TTL) -> Optional[dict]:
        try:
            row = self.conn.execute(
                "SELECT fetched_at, payload FROM kv_cache WHERE key = ?", (key,)
            ).fetchone()
        except sqlite3.Error:
            return None
        if not row or (time.time() - row["fetched_at"]) > max_age:
            return None
        try:
            return json.loads(row["payload"])
        except (ValueError, TypeError):
            return None

    def put_kv(self, key: str, payload: dict) -> None:
        with self._lock:
            try:
                self.conn.execute(
                    "INSERT OR REPLACE INTO kv_cache (key, fetched_at, payload) "
                    "VALUES (?,?,?)", (key, time.time(), json.dumps(payload)),
                )
                self.conn.commit()
            except sqlite3.Error:
                pass

    def close(self):
        try:
            self.conn.close()
        except sqlite3.Error:
            pass


# Shared process-wide instance (one SQLite connection, thread-safe).
_CACHE: Optional[OHLCVCache] = None
_CACHE_LOCK = threading.Lock()


def get_cache() -> OHLCVCache:
    global _CACHE
    if _CACHE is None:
        with _CACHE_LOCK:
            if _CACHE is None:
                _CACHE = OHLCVCache()
    return _CACHE