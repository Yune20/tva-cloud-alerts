"""
SQLite Database for Trade History, Signals, Daily Summary, Pattern Library.
"""
import sqlite3
import json
import os
from datetime import datetime, date
from typing import Dict, List, Optional

import config as cfg


class TradeDatabase:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or cfg.DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            status TEXT DEFAULT 'OPEN',
            tp1_price REAL, tp1_hit INTEGER DEFAULT 0, tp1_pnl REAL DEFAULT 0,
            tp2_price REAL, tp2_hit INTEGER DEFAULT 0, tp2_pnl REAL DEFAULT 0,
            tp3_price REAL, tp3_hit INTEGER DEFAULT 0, tp3_pnl REAL DEFAULT 0,
            tp4_price REAL, tp4_hit INTEGER DEFAULT 0, tp4_pnl REAL DEFAULT 0,
            tp5_price REAL, tp5_hit INTEGER DEFAULT 0, tp5_pnl REAL DEFAULT 0,
            sl1_price REAL, sl1_hit INTEGER DEFAULT 0, sl1_pnl REAL DEFAULT 0,
            sl2_price REAL, sl2_hit INTEGER DEFAULT 0, sl2_pnl REAL DEFAULT 0,
            sl3_price REAL, sl3_hit INTEGER DEFAULT 0, sl3_pnl REAL DEFAULT 0,
            total_pnl REAL DEFAULT 0, total_pnl_pct REAL DEFAULT 0,
            r_multiple REAL DEFAULT 0, risk_amount REAL DEFAULT 0,
            position_size REAL DEFAULT 1.0,
            daily_capital_at_entry REAL,
            confidence REAL DEFAULT 0, quality TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS trade_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
            symbol TEXT NOT NULL, interval TEXT NOT NULL, timestamp TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            rsi REAL, macd REAL, macd_signal REAL, macd_hist REAL,
            bb_upper REAL, bb_lower REAL, bb_position REAL,
            adx REAL, atr REAL, stoch_k REAL, stoch_d REAL,
            ema_short REAL, ema_long REAL, obv REAL, cci REAL, willr REAL, mfi REAL,
            pattern_name TEXT, pattern_dir TEXT, pattern_strength REAL,
            trend_direction TEXT, trend_strength REAL,
            mtf_direction TEXT, mtf_strength REAL, mtf_aligned INTEGER, mtf_total INTEGER,
            fib_0 REAL, fib_236 REAL, fib_382 REAL, fib_500 REAL,
            fib_618 REAL, fib_786 REAL, fib_100 REAL,
            fib_1272 REAL, fib_1618 REAL, fib_nearest REAL, fib_distance_pct REAL,
            nearest_support REAL, nearest_resistance REAL,
            support_touches INTEGER, resistance_touches INTEGER, sr_distance_pct REAL,
            trendline_type TEXT, trendline_slope REAL, trendline_confidence REAL, trendline_price REAL,
            confluence_score REAL, confluence_levels TEXT,
            chart_data_50 TEXT, chart_data_100 TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS daily_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            start_capital REAL NOT NULL, end_capital REAL,
            pnl REAL DEFAULT 0, pnl_pct REAL DEFAULT 0,
            total_trades INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, win_rate REAL DEFAULT 0,
            best_trade_pnl REAL DEFAULT 0, worst_trade_pnl REAL DEFAULT 0,
            best_trade_sym TEXT, worst_trade_sym TEXT,
            avg_r_multiple REAL DEFAULT 0, max_r_achieved REAL DEFAULT 0,
            total_risk_taken REAL DEFAULT 0, risk_budget_used_pct REAL DEFAULT 0,
            long_trades INTEGER DEFAULT 0, long_pnl REAL DEFAULT 0,
            short_trades INTEGER DEFAULT 0, short_pnl REAL DEFAULT 0,
            tf_breakdown TEXT, sym_breakdown TEXT, notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS pattern_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL, interval TEXT NOT NULL,
            pattern_type TEXT NOT NULL, pattern_name TEXT NOT NULL,
            rsi_range TEXT, macd_direction TEXT, bb_position TEXT,
            adx_value TEXT, fib_level REAL, sr_distance_pct REAL, trendline_type TEXT,
            total_occurrences INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0,
            avg_pnl_pct REAL DEFAULT 0, avg_r_multiple REAL DEFAULT 0,
            sample_signals TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
            alert_type TEXT NOT NULL, alert_message TEXT NOT NULL,
            confidence REAL, related_trade_id INTEGER,
            pattern_library_id INTEGER, acknowledged INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date);
        CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
        CREATE INDEX IF NOT EXISTS idx_trade_signals_trade_id ON trade_signals(trade_id);
        CREATE INDEX IF NOT EXISTS idx_daily_summary_date ON daily_summary(date);
        CREATE INDEX IF NOT EXISTS idx_alert_history_date ON alert_history(date);
        """)
        self.conn.commit()

    def save_trade(self, data: dict) -> int:
        cols = [k for k in data if k in (
            "date","symbol","interval","direction","entry_price","exit_price",
            "entry_time","exit_time","status",
            "tp1_price","tp1_hit","tp1_pnl","tp2_price","tp2_hit","tp2_pnl",
            "tp3_price","tp3_hit","tp3_pnl","tp4_price","tp4_hit","tp4_pnl",
            "tp5_price","tp5_hit","tp5_pnl",
            "sl1_price","sl1_hit","sl1_pnl","sl2_price","sl2_hit","sl2_pnl",
            "sl3_price","sl3_hit","sl3_pnl",
            "total_pnl","total_pnl_pct","r_multiple","risk_amount","position_size",
            "daily_capital_at_entry","confidence","quality","notes",
        )]
        vals = [data[k] for k in cols]
        placeholders = ",".join(["?"] * len(cols))
        col_names = ",".join(cols)
        cur = self.conn.execute(f"INSERT INTO trades ({col_names}) VALUES ({placeholders})", vals)
        self.conn.commit()
        return cur.lastrowid

    def update_trade(self, trade_id: int, updates: dict):
        sets = []
        vals = []
        for k, v in updates.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        sets.append("updated_at = datetime('now')")
        vals.append(trade_id)
        self.conn.execute(f"UPDATE trades SET {','.join(sets)} WHERE id = ?", vals)
        self.conn.commit()

    def save_trade_signals(self, trade_id: int, signals: dict):
        flat = {"trade_id": trade_id}
        flat["symbol"] = signals.get("symbol", "")
        flat["interval"] = signals.get("interval", "")
        flat["timestamp"] = signals.get("timestamp", datetime.now().isoformat())
        for k in ("open","high","low","close","volume","rsi","macd","macd_signal","macd_hist",
                   "bb_upper","bb_lower","bb_position","adx","atr","stoch_k","stoch_d",
                   "ema_short","ema_long","obv","cci","willr","mfi",
                   "pattern_name","pattern_dir","pattern_strength",
                   "trend_direction","trend_strength",
                   "mtf_direction","mtf_strength","mtf_aligned","mtf_total",
                   "fib_0","fib_236","fib_382","fib_500","fib_618","fib_786","fib_100",
                   "fib_1272","fib_1618","fib_nearest","fib_distance_pct",
                   "nearest_support","nearest_resistance","support_touches","resistance_touches","sr_distance_pct",
                   "trendline_type","trendline_slope","trendline_confidence","trendline_price",
                   "confluence_score","confluence_levels","chart_data_50","chart_data_100"):
            flat[k] = signals.get(k)
        cols = [k for k in flat if flat[k] is not None]
        vals = [flat[k] for k in cols]
        placeholders = ",".join(["?"] * len(cols))
        col_names = ",".join(cols)
        self.conn.execute(f"INSERT INTO trade_signals ({col_names}) VALUES ({placeholders})", vals)
        self.conn.commit()

    def save_daily_summary(self, data: dict):
        cols = [k for k in data if k in (
            "date","start_capital","end_capital","pnl","pnl_pct",
            "total_trades","wins","losses","win_rate",
            "best_trade_pnl","worst_trade_pnl","best_trade_sym","worst_trade_sym",
            "avg_r_multiple","max_r_achieved","total_risk_taken","risk_budget_used_pct",
            "long_trades","long_pnl","short_trades","short_pnl",
            "tf_breakdown","sym_breakdown","notes",
        )]
        vals = [data[k] for k in cols]
        placeholders = ",".join(["?"] * len(cols))
        col_names = ",".join(cols)
        self.conn.execute(
            f"INSERT OR REPLACE INTO daily_summary ({col_names}) VALUES ({placeholders})", vals
        )
        self.conn.commit()

    def get_trades(self, date=None, symbol=None, status=None, limit=50) -> list:
        q = "SELECT * FROM trades WHERE 1=1"
        params = []
        if date:
            q += " AND date = ?"; params.append(date)
        if symbol:
            q += " AND symbol = ?"; params.append(symbol)
        if status:
            q += " AND status = ?"; params.append(status)
        q += " ORDER BY id DESC LIMIT ?"; params.append(limit)
        return [dict(r) for r in self.conn.execute(q, params).fetchall()]

    def get_trade_with_signals(self, trade_id: int) -> dict:
        trade = self.conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if not trade:
            return {}
        signals = self.conn.execute(
            "SELECT * FROM trade_signals WHERE trade_id = ? ORDER BY id DESC LIMIT 1", (trade_id,)
        ).fetchone()
        result = dict(trade)
        if signals:
            result["signals"] = dict(signals)
        return result

    def get_daily_summary(self, date_str=None) -> dict:
        if not date_str:
            date_str = date.today().isoformat()
        row = self.conn.execute("SELECT * FROM daily_summary WHERE date = ?", (date_str,)).fetchone()
        return dict(row) if row else {}

    def get_historical_trades(self, symbol=None, interval=None, limit=500) -> list:
        q = "SELECT t.*, ts.* FROM trades t LEFT JOIN trade_signals ts ON t.id = ts.trade_id WHERE t.status = 'CLOSED'"
        params = []
        if symbol:
            q += " AND t.symbol = ?"; params.append(symbol)
        if interval:
            q += " AND t.interval = ?"; params.append(interval)
        q += " ORDER BY t.id DESC LIMIT ?"; params.append(limit)
        rows = self.conn.execute(q, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Parse JSON fields
            for f in ("confluence_levels", "chart_data_50", "chart_data_100"):
                if d.get(f) and isinstance(d[f], str):
                    try:
                        d[f] = json.loads(d[f])
                    except Exception:
                        pass
            result.append(d)
        return result

    def get_trade_history(self, days=30) -> list:
        rows = self.conn.execute(
            "SELECT * FROM trades WHERE status = 'CLOSED' ORDER BY id DESC LIMIT ?", (days * 10,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_win_rate(self, symbol=None, interval=None) -> float:
        q = "SELECT COUNT(*) as total, SUM(CASE WHEN total_pnl > 0 THEN 1 ELSE 0 END) as wins FROM trades WHERE status = 'CLOSED'"
        params = []
        if symbol:
            q += " AND symbol = ?"; params.append(symbol)
        if interval:
            q += " AND interval = ?"; params.append(interval)
        row = self.conn.execute(q, params).fetchone()
        if row and row["total"] > 0:
            return round(row["wins"] / row["total"] * 100, 1)
        return 0.0

    def get_avg_pnl(self, symbol=None, interval=None) -> float:
        q = "SELECT AVG(total_pnl_pct) as avg_pnl FROM trades WHERE status = 'CLOSED'"
        params = []
        if symbol:
            q += " AND symbol = ?"; params.append(symbol)
        if interval:
            q += " AND interval = ?"; params.append(interval)
        row = self.conn.execute(q, params).fetchone()
        return round(row["avg_pnl"], 2) if row and row["avg_pnl"] else 0.0

    def get_equity_curve(self, start_date=None) -> list:
        q = "SELECT date, SUM(pnl) as daily_pnl FROM daily_summary"
        params = []
        if start_date:
            q += " WHERE date >= ?"; params.append(start_date)
        q += " GROUP BY date ORDER BY date"
        return [dict(r) for r in self.conn.execute(q, params).fetchall()]

    def get_alert_history(self, date_str=None, limit=20) -> list:
        q = "SELECT * FROM alert_history"
        params = []
        if date_str:
            q += " WHERE date = ?"; params.append(date_str)
        q += " ORDER BY id DESC LIMIT ?"; params.append(limit)
        return [dict(r) for r in self.conn.execute(q, params).fetchall()]

    def save_alert(self, data: dict):
        cols = [k for k in data if k in (
            "date","symbol","interval","alert_type","alert_message",
            "confidence","related_trade_id","pattern_library_id",
        )]
        vals = [data[k] for k in cols]
        placeholders = ",".join(["?"] * len(cols))
        col_names = ",".join(cols)
        self.conn.execute(f"INSERT INTO alert_history ({col_names}) VALUES ({placeholders})", vals)
        self.conn.commit()

    def save_pattern(self, data: dict):
        cols = [k for k in data if k in (
            "symbol","interval","pattern_type","pattern_name",
            "rsi_range","macd_direction","bb_position","adx_value",
            "fib_level","sr_distance_pct","trendline_type",
            "total_occurrences","wins","losses","avg_pnl_pct","avg_r_multiple",
            "sample_signals",
        )]
        vals = [data[k] for k in cols]
        placeholders = ",".join(["?"] * len(cols))
        col_names = ",".join(cols)
        self.conn.execute(f"INSERT INTO pattern_library ({col_names}) VALUES ({placeholders})", vals)
        self.conn.commit()

    def close(self):
        self.conn.close()
