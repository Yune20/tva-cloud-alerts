"""
Daily Capital Management: track capital, trades, P/L per day, auto-reset.
"""
import json
import os
from datetime import datetime, date
from typing import Dict, List, Optional

import config as cfg


class DailyCapital:
    def __init__(self):
        self.daily_capital = cfg.DEFAULT_DAILY_CAPITAL
        self.start_capital = cfg.DEFAULT_DAILY_CAPITAL
        self.daily_pnl = 0.0
        self.trades_today = []
        self.wins = 0
        self.losses = 0
        self.current_date = date.today().isoformat()
        self._archive_dir = cfg.DAILY_ARCHIVE_DIR
        os.makedirs(self._archive_dir, exist_ok=True)

    def check_reset(self) -> bool:
        """Check if we need to reset for a new day. Returns True if reset happened."""
        today = date.today().isoformat()
        if self.current_date != today:
            self._archive_day()
            self._reset(today)
            return True
        return False

    def _reset(self, today: str):
        self.current_date = today
        self.daily_capital = cfg.DEFAULT_DAILY_CAPITAL
        self.start_capital = cfg.DEFAULT_DAILY_CAPITAL
        self.daily_pnl = 0.0
        self.trades_today = []
        self.wins = 0
        self.losses = 0

    def _archive_day(self):
        archive = {
            "date": self.current_date,
            "start_capital": self.start_capital,
            "end_capital": self.daily_capital,
            "pnl": self.daily_pnl,
            "trades": self.trades_today,
            "wins": self.wins,
            "losses": self.losses,
        }
        path = os.path.join(self._archive_dir, f"{self.current_date}.json")
        with open(path, "w") as f:
            json.dump(archive, f, indent=2, default=str)

    def can_trade(self) -> tuple:
        """Check if trading is allowed. Returns (can_trade, reason)."""
        max_loss = self.start_capital * cfg.MAX_DAILY_LOSS_PCT / 100
        if self.daily_pnl <= -max_loss:
            return False, f"Max daily loss reached ({cfg.MAX_DAILY_LOSS_PCT}%)"
        if len(self.trades_today) >= cfg.MAX_DAILY_TRADES:
            return False, f"Max daily trades reached ({cfg.MAX_DAILY_TRADES})"
        return True, "OK"

    def get_risk_budget(self) -> float:
        """Remaining risk budget in dollars."""
        max_loss = self.start_capital * cfg.MAX_DAILY_LOSS_PCT / 100
        remaining = max_loss + self.daily_pnl  # daily_pnl is negative when losing
        return max(0, remaining)

    def get_risk_per_trade(self) -> float:
        """Max risk amount per trade in dollars."""
        return self.daily_capital * cfg.MAX_RISK_PER_TRADE_PCT / 100

    def calculate_position_size(self, risk_amount: float, risk_per_unit: float) -> dict:
        """Calculate position size based on fixed risk method."""
        if risk_per_unit <= 0:
            return {"size": 0, "value": 0, "risk_amount": 0}

        size = risk_amount / risk_per_unit
        value = size * risk_per_unit
        return {
            "size": round(size, 4),
            "value": round(value, 2),
            "risk_amount": round(risk_amount, 2),
        }

    def record_trade(self, trade_data: dict):
        """Record a completed trade."""
        pnl = trade_data.get("total_pnl", 0)
        self.trades_today.append(trade_data)
        self.daily_pnl += pnl
        self.daily_capital += pnl
        if pnl > 0:
            self.wins += 1
        elif pnl < 0:
            self.losses += 1

    def get_summary(self) -> dict:
        """Get current daily summary."""
        total = self.wins + self.losses
        win_rate = (self.wins / total * 100) if total > 0 else 0
        pnl_pct = (self.daily_pnl / self.start_capital * 100) if self.start_capital > 0 else 0

        best_trade = max(self.trades_today, key=lambda t: t.get("total_pnl", 0)) if self.trades_today else None
        worst_trade = min(self.trades_today, key=lambda t: t.get("total_pnl", 0)) if self.trades_today else None

        long_trades = [t for t in self.trades_today if t.get("direction") == "LONG"]
        short_trades = [t for t in self.trades_today if t.get("direction") == "SHORT"]

        return {
            "date": self.current_date,
            "start_capital": self.start_capital,
            "current_capital": round(self.daily_capital, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_pnl_pct": round(pnl_pct, 2),
            "total_trades": len(self.trades_today),
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(win_rate, 1),
            "best_trade_pnl": round(best_trade["total_pnl"], 2) if best_trade else 0,
            "worst_trade_pnl": round(worst_trade["total_pnl"], 2) if worst_trade else 0,
            "best_trade_sym": best_trade.get("symbol", "") if best_trade else "",
            "worst_trade_sym": worst_trade.get("symbol", "") if worst_trade else "",
            "long_trades": len(long_trades),
            "long_pnl": round(sum(t.get("total_pnl", 0) for t in long_trades), 2),
            "short_trades": len(short_trades),
            "short_pnl": round(sum(t.get("total_pnl", 0) for t in short_trades), 2),
            "risk_budget_remaining": round(self.get_risk_budget(), 2),
            "risk_per_trade": round(self.get_risk_per_trade(), 2),
            "can_trade": self.can_trade()[0],
            "can_trade_reason": self.can_trade()[1],
            "trades": self.trades_today,
        }
