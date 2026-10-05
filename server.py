"""
FastAPI backend for the realtime TradingView dashboard.

Serves
  • /ws/quotes          WebSocket push of live quotes (client pull loop)
  • /api/quotes         latest quote snapshot
  • /api/watchlist      watched groups (with live prices merged)
  • /api/ohlcv/{sym}    OHLCV bars for the chart (SQL-cached)
  • /api/analysis/{sym} full MTF + per-timeframe plans + action plan
  • /                   built React app (web/dist)

Run (background):
  .venv\\Scripts\\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8502
"""
import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response
import json as _json
import math

class _SafeEncoder(_json.JSONEncoder):
    def default(self, o):
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
            return None
        return super().default(o)

    def encode(self, o):
        return super().encode(self._clean(o))

    def _clean(self, o):
        if isinstance(o, float):
            if math.isnan(o) or math.isinf(o):
                return None
            return o
        if isinstance(o, dict):
            return {k: self._clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [self._clean(v) for v in o]
        return o

import pandas as pd
import config as cfg
from tv_scraper_pro import TVScraperPro
from core.multi_timeframe import MTFAnalyzer
from core.analysis_plans import build_action_plan, build_per_tf_plans
from core.market_psychology import analyze_psychology
from core.darvas import detect_boxes, summarize as darvas_summarize
from core.levels import analyze_structure
from core.backtester import BacktestEngine
from core.indicators import TechnicalAnalyzer
from core.ai_advisor import analyze as ai_analyze
import realtime
from realtime import RealtimeEngine

engine: RealtimeEngine = None
_scraper = TVScraperPro()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    engine = RealtimeEngine()
    engine.start()
    # Start Telegram bot polling (signal_bot + price_feed_bot + market_news_bot)
    try:
        from core.telegram_bot import start_polling, _state as tg_state
        sb_token = tg_state.get("signal_bot", {}).get("bot_token")
        pfb_token = tg_state.get("price_feed_bot", {}).get("bot_token")
        nb_token = tg_state.get("market_news_bot", {}).get("bot_token")
        if sb_token or pfb_token or nb_token:
            start_polling()
            print(f"[TG] Bot polling started (signal: {'yes' if sb_token else 'no'}, price_feed: {'yes' if pfb_token else 'no'}, news: {'yes' if nb_token else 'no'})")
        else:
            print("[TG] No bot tokens configured — polling skipped")
    except Exception as e:
        print(f"[TG] Bot polling start failed: {e}")
    yield
    engine.stop()


app = FastAPI(title="Trading Dashboard Realtime", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
def health():
    n = len(engine.snapshot()) if engine else 0
    return {"status": "ok", "quotes": n, "time": time.time()}


@app.post("/api/restart")
def restart_server():
    """Restart the TradeBoardAPI task (kill python + rerun task)."""
    import subprocess, threading
    def _do_restart():
        time.sleep(1)
        subprocess.run(["taskkill", "/F", "/IM", "python.exe"], capture_output=True)
        time.sleep(2)
        subprocess.run(["schtasks", "/run", "/tn", "TradeBoardAPI"], capture_output=True)
    threading.Thread(target=_do_restart, daemon=True).start()
    return {"status": "restarting"}


@app.get("/api/watchlist")
def watchlist():
    groups = [dict(g) for g in engine.groups]
    state = engine.snapshot()
    by_sym = {q["sym"]: q for q in state}
    for g in groups:
        g["items"] = [
            {**it, "quote": by_sym.get(it["sym"])} for it in g["items"]
        ]
    return {"groups": groups, "focused": sorted(realtime.FOCUS_SYMS)}


@app.get("/api/quotes")
def quotes():
    return {"quotes": engine.snapshot(), "time": time.time()}


@app.websocket("/ws/quotes")
async def ws_quotes(ws: WebSocket):
    await ws.accept()
    last = 0.0
    prev_text = ""
    try:
        while True:
            await asyncio.sleep(0.4)
            data = engine.snapshot()
            if not data:
                continue
            text = json_dumps({"quotes": data, "time": time.time()})
            if text != prev_text:
                prev_text = text
                await ws.send_text(text)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, cls=_SafeEncoder, allow_nan=False)


def df_to_bars(df) -> list:
    if df is None or df.empty:
        return []
    bars = []
    for ts, row in df.iterrows():
        bars.append([
            int(ts.timestamp() * 1000),
            float(row["open"]), float(row["high"]),
            float(row["low"]), float(row["close"]),
            float(row["volume"]) if "volume" in df.columns else 0.0,
        ])
    return bars


@app.get("/api/ohlcv/{sym:path}")
def ohlcv(sym: str, interval: str = "1H", bars: int = 200):
    df = _scraper.scrape_yfinance(sym, interval=interval)
    if df is None or df.empty:
        return JSONResponse({"error": "no data", "symbol": sym}, status_code=404)
    return {"symbol": sym, "interval": interval, "bars": df_to_bars(df.tail(bars))}


@app.get("/api/analysis/{sym:path}")
def analysis(sym: str, interval: str = "1H"):
    t0 = time.time()
    try:
        mtf = MTFAnalyzer(sym, cfg.MTF_TIMEFRAMES).run(_scraper)
    except Exception as exc:
        import traceback; traceback.print_exc()
        return JSONResponse({"error": f"analysis failed: {exc}"}, status_code=500)
    if not mtf or not mtf.get("results"):
        return JSONResponse({"error": "no multi-timeframe data", "symbol": sym}, status_code=404)

    try:
        tf_plans = build_per_tf_plans(mtf)
    except Exception:
        tf_plans = {}

    try:
        action = build_action_plan(mtf, None)
    except Exception:
        action = {}

    chart_df = _scraper.scrape_yfinance(sym, interval=interval)
    quote = None
    if engine:
        quote = engine.state.get(sym)

    # ── Market Psychology ──────────────────────────────────────
    psychology = None
    signals = {}
    try:
        if chart_df is not None and len(chart_df) >= 20:
            tf_result = mtf.get("results", {}).get(interval, {})
            signals = tf_result.get("signals", tf_result.get("indicators", {}))
            psychology = analyze_psychology(chart_df, signals)
    except Exception:
        psychology = None

    # ── Darvas Boxes ───────────────────────────────────────────
    darvas = None
    try:
        if chart_df is not None and len(chart_df) >= 20:
            boxes = detect_boxes(chart_df, lookback=20, tolerance_pct=3.0, min_bars=5)
            darvas = darvas_summarize(boxes, float(chart_df["close"].iloc[-1]) if len(chart_df) > 0 else None)
    except Exception:
        darvas = None

    # ── Market Structure (BOS + ChoCh) ─────────────────────────
    market_structure = None
    try:
        if chart_df is not None and len(chart_df) >= 20:
            from core.market_structure import detect_bos_choch
            market_structure = detect_bos_choch(chart_df, lookback=5)
    except Exception:
        market_structure = None

    # ── Structural Levels (S/R, Trendlines, Fib, Confluence) ──
    structure = None
    try:
        if chart_df is not None and len(chart_df) >= 20:
            structure = analyze_structure(chart_df)
    except Exception:
        structure = None

    # ── Extract overlay data for chart rendering ───────────────
    overlays = {}
    if structure:
        overlays["support_resistance"] = [
            {"price": s["price"], "type": s["type"], "strength": s.get("strength", 0)}
            for s in (structure.get("support_resistance", []) or [])
        ]
        overlays["trendlines"] = []
        for t in (structure.get("trendlines") or []):
            tl = {
                "type": t.get("type", ""),
                "slope": t.get("slope", 0),
                "confidence": t.get("confidence", 0),
            }
            if t.get("type") == "ascending":
                tl["price"] = t.get("support_price", 0)
            else:
                tl["price"] = t.get("resistance_price", 0)
            overlays["trendlines"].append(tl)
        overlays["fibonacci"] = structure.get("fibonacci_levels", {})
        overlays["confluence_zones"] = [
            {"price": z["price"], "strength": z.get("strength", 0), "sources": z.get("sources", [])}
            for z in (structure.get("confluence_zones", []) or [])
        ]
    if darvas and darvas.get("current_box"):
        cb = darvas["current_box"]
        overlays["darvas_box"] = {"top": cb["top"], "bottom": cb["bottom"]}

    # Market structure (BOS + ChoCh)
    if market_structure:
        overlays["market_structure"] = {
            "trend": market_structure.get("structure", "NEUTRAL"),
            "swing_highs": market_structure.get("swing_highs", []),
            "swing_lows": market_structure.get("swing_lows", []),
            "events": market_structure.get("events", []),
            "last_bos": market_structure.get("last_bos"),
            "last_choch": market_structure.get("last_choch"),
        }

    # ── Signal markers (recent signals on chart) ────────────────
    markers = []
    try:
        if chart_df is not None and signals:
            last_idx = len(chart_df) - 1
            last_time = int(chart_df.index[last_idx].timestamp())
            # RSI overbought/oversold
            rsi = signals.get("RSI", {})
            if isinstance(rsi, dict):
                sig = rsi.get("signal", "")
                if sig == "OVERBOUGHT":
                    markers.append({"time": last_time, "position": "aboveBar", "color": "#d32f2f", "shape": "arrowDown", "text": "RSI OB"})
                elif sig == "OVERSOLD":
                    markers.append({"time": last_time, "position": "belowBar", "color": "#1b8a5a", "shape": "arrowUp", "text": "RSI OS"})
            # MACD direction
            macd = signals.get("MACD", {})
            if isinstance(macd, dict) and macd.get("direction"):
                d = macd["direction"]
                color = "#1b8a5a" if d == "BULLISH" else "#d32f2f"
                shape = "arrowUp" if d == "BULLISH" else "arrowDown"
                pos = "belowBar" if d == "BULLISH" else "aboveBar"
                markers.append({"time": last_time, "position": pos, "color": color, "shape": shape, "text": f"MACD {d}"})
            # EMA Cross
            ema = signals.get("EMA_Cross", {})
            if isinstance(ema, dict) and ema.get("signal") in ("GOLDEN", "DEATH"):
                sig = ema["signal"]
                color = "#1b8a5a" if sig == "GOLDEN" else "#d32f2f"
                shape = "arrowUp" if sig == "GOLDEN" else "arrowDown"
                pos = "belowBar" if sig == "GOLDEN" else "aboveBar"
                markers.append({"time": last_time, "position": pos, "color": color, "shape": shape, "text": sig})
            # Bollinger
            bb = signals.get("Bollinger", {})
            if isinstance(bb, dict) and bb.get("signal") in ("OVERBOUGHT", "OVERSOLD"):
                sig = bb["signal"]
                color = "#d32f2f" if sig == "OVERBOUGHT" else "#1b8a5a"
                shape = "arrowDown" if sig == "OVERBOUGHT" else "arrowUp"
                pos = "aboveBar" if sig == "OVERBOUGHT" else "belowBar"
                markers.append({"time": last_time, "position": pos, "color": color, "shape": shape, "text": f"BB {sig}"})
            # Supertrend
            st = signals.get("Supertrend", {})
            if isinstance(st, dict) and st.get("direction") in ("BULL", "BEAR"):
                d = st["direction"]
                color = "#1b8a5a" if d == "BULL" else "#d32f2f"
                shape = "arrowUp" if d == "BULL" else "arrowDown"
                pos = "belowBar" if d == "BULL" else "aboveBar"
                markers.append({"time": last_time, "position": pos, "color": color, "shape": shape, "text": f"ST {d}"})
            # RSI Divergence
            div = signals.get("RSI_Divergence", {})
            if isinstance(div, dict) and div.get("type"):
                dtype = div["type"]
                color = "#1b8a5a" if dtype == "BULLISH" else "#d32f2f"
                shape = "arrowUp" if dtype == "BULLISH" else "arrowDown"
                pos = "belowBar" if dtype == "BULLISH" else "aboveBar"
                markers.append({"time": last_time, "position": pos, "color": color, "shape": shape, "text": f"Div {dtype}"})
            # Stochastic
            stoch = signals.get("Stochastic", {})
            if isinstance(stoch, dict) and stoch.get("signal") in ("OVERBOUGHT", "OVERSOLD"):
                sig = stoch["signal"]
                color = "#d32f2f" if sig == "OVERBOUGHT" else "#1b8a5a"
                shape = "arrowDown" if sig == "OVERBOUGHT" else "arrowUp"
                pos = "aboveBar" if sig == "OVERBOUGHT" else "belowBar"
                markers.append({"time": last_time, "position": pos, "color": color, "shape": shape, "text": f"Stoch {sig}"})
            # MFI
            mfi = signals.get("MFI", {})
            if isinstance(mfi, dict) and mfi.get("signal") in ("OVERBOUGHT", "OVERSOLD"):
                sig = mfi["signal"]
                color = "#d32f2f" if sig == "OVERBOUGHT" else "#1b8a5a"
                shape = "arrowDown" if sig == "OVERBOUGHT" else "arrowUp"
                pos = "aboveBar" if sig == "OVERBOUGHT" else "belowBar"
                markers.append({"time": last_time, "position": pos, "color": color, "shape": shape, "text": f"MFI {sig}"})
    except Exception:
        pass
    overlays["markers"] = markers

    # ── Nearest S/R for entry/exit ─────────────────────────────
    entry_exit = {}
    if structure:
        last_price = float(chart_df["close"].iloc[-1]) if chart_df is not None and len(chart_df) > 0 else None
        if last_price:
            sr = structure.get("support_resistance", []) or []
            nearest_sup = max([s["price"] for s in sr if s["type"] == "support" and s["price"] < last_price], default=None)
            nearest_res = min([s["price"] for s in sr if s["type"] == "resistance" and s["price"] > last_price], default=None)
            entry_exit = {
                "last_price": last_price,
                "nearest_support": nearest_sup,
                "nearest_resistance": nearest_res,
                "suggested_entry": nearest_sup if action.get("bias") == "LONG" else nearest_res,
                "suggested_stop": nearest_sup * 0.99 if action.get("bias") == "LONG" else nearest_res * 1.01 if action.get("bias") == "SHORT" else None,
                "suggested_tp1": nearest_res if action.get("bias") == "LONG" else nearest_sup,
            }

    # ── Indicator overlays for chart ──────────────────────────────────
    indicator_overlays = {}
    custom = {}
    try:
        if chart_df is not None and len(chart_df) >= 20:
            ta = TechnicalAnalyzer(chart_df)
            ta.compute_all()
            df_ind = ta.df
            times = [int(t.timestamp()) for t in df_ind.index]

            bb_upper = [c for c in df_ind.columns if c.startswith("BBU")]
            bb_lower = [c for c in df_ind.columns if c.startswith("BBL")]
            bb_mid = [c for c in df_ind.columns if c.startswith("BBM")]
            if bb_upper and bb_lower:
                indicator_overlays["bollinger"] = {
                    "upper": [{"time": times[i], "value": round(float(df_ind[bb_upper[0]].iloc[i]), 2)} for i in range(len(df_ind)) if pd.notna(df_ind[bb_upper[0]].iloc[i])],
                    "lower": [{"time": times[i], "value": round(float(df_ind[bb_lower[0]].iloc[i]), 2)} for i in range(len(df_ind)) if pd.notna(df_ind[bb_lower[0]].iloc[i])],
                    "middle": [{"time": times[i], "value": round(float(df_ind[bb_mid[0]].iloc[i]), 2)} for i in range(len(df_ind))] if bb_mid else [],
                }

            ema_cols = sorted([c for c in df_ind.columns if c.startswith("EMA_")])
            ema_data = {}
            for col in ema_cols[:5]:
                name = col.replace("EMA_", "")
                ema_data[name] = [{"time": times[i], "value": round(float(df_ind[col].iloc[i]), 2)} for i in range(len(df_ind)) if pd.notna(df_ind[col].iloc[i])]
            indicator_overlays["ema"] = ema_data

            st_cols = [c for c in df_ind.columns if "SUPERT" in c and "SUPERTd" not in c]
            if st_cols:
                indicator_overlays["supertrend"] = [
                    {"time": times[i], "value": round(float(df_ind[st_cols[0]].iloc[i]), 2)}
                    for i in range(len(df_ind)) if pd.notna(df_ind[st_cols[0]].iloc[i])
                ]

            vwap_cols = [c for c in df_ind.columns if "VWAP" in c]
            if vwap_cols:
                indicator_overlays["vwap"] = [
                    {"time": times[i], "value": round(float(df_ind[vwap_cols[0]].iloc[i]), 2)}
                    for i in range(len(df_ind)) if pd.notna(df_ind[vwap_cols[0]].iloc[i])
                ]
    except Exception:
        pass
    overlays["indicators"] = indicator_overlays

    # ── Custom indicators ─────────────────────────────────────────────
    try:
        from core.custom_indicators import winners_scalper_pro, entry_exit_tool, volume_profile
        if chart_df is not None and len(chart_df) >= 20:
            custom["scalper"] = winners_scalper_pro(chart_df)
            custom["entry_exit_tool"] = entry_exit_tool(chart_df)
            custom["volume_profile"] = volume_profile(chart_df)
    except Exception:
        pass
    overlays["custom"] = custom

    result = {
        "symbol": sym,
        "interval": interval,
        "quote": quote,
        "consensus": mtf.get("consensus", {}),
        "timeframes": tf_plans,
        "action_plan": action,
        "psychology": psychology,
        "darvas": darvas,
        "structure": structure,
        "overlays": overlays,
        "entry_exit": entry_exit,
        "signals": signals,
        "chart": {"bars": df_to_bars(chart_df) if chart_df is not None else []},
        "elapsed_s": round(time.time() - t0, 2),
    }
    body = _json.dumps(result, cls=_SafeEncoder, allow_nan=False)
    return Response(content=body, media_type="application/json")


_DIST = Path(__file__).parent / "web" / "dist"


@app.get("/api/structure/{sym:path}")
def get_structure(sym: str, interval: str = "1H"):
    """Get market structure (BOS + ChoCh) for chart rendering."""
    from core.market_structure import detect_bos_choch
    t0 = time.time()

    chart_df = None
    try:
        chart_df = _scraper.scrape_yfinance(sym, interval=interval)
    except Exception:
        pass

    if chart_df is None or chart_df.empty or len(chart_df) < 20:
        return JSONResponse({"error": "insufficient data", "symbol": sym}, status_code=404)

    result = detect_bos_choch(chart_df, lookback=5)

    return {
        "symbol": sym,
        "interval": interval,
        "elapsed_s": round(time.time() - t0, 2),
        "structure": result,
    }


@app.get("/api/ai-advice/{sym:path}")
def ai_advice(sym: str, interval: str = "1H"):
    """Instant rule-based trading analysis (no LLM)."""
    from core.rule_engine import analyze as rule_analyze
    t0 = time.time()

    # Get cached data from MTF if available, otherwise fetch
    mtf_consensus = None
    entry_exit = {}
    signals = {}
    psychology = None
    darvas = None
    structure = None

    # Try to get from MTF cache first (fast)
    try:
        mtf = MTFAnalyzer(sym, cfg.MTF_TIMEFRAMES).run(_scraper)
        if mtf:
            mtf_consensus = mtf.get("consensus", {})
            tf_res = mtf.get("results", {}).get(interval, {})
            signals = tf_res.get("signals", {})
            chart_df = tf_res.get("df")
    except Exception:
        chart_df = None

    # Fallback: fetch chart directly
    if chart_df is None:
        try:
            chart_df = _scraper.scrape_yfinance(sym, interval=interval)
        except Exception:
            pass

    if chart_df is None or chart_df.empty or len(chart_df) < 20:
        return JSONResponse({"error": "insufficient data", "symbol": sym}, status_code=404)

    # Compute signals if not from MTF
    if not signals:
        try:
            ta = TechnicalAnalyzer(chart_df)
            ta.compute_all()
            signals = ta.get_latest_signals()
        except Exception:
            pass

    try:
        psychology = analyze_psychology(chart_df, signals)
    except Exception:
        pass

    try:
        boxes = detect_boxes(chart_df, lookback=20, tolerance_pct=3.0)
        darvas = darvas_summarize(boxes, float(chart_df["close"].iloc[-1]) if len(chart_df) > 0 else None)
    except Exception:
        pass

    try:
        structure = analyze_structure(chart_df)
    except Exception:
        pass

    try:
        last_price = float(chart_df["close"].iloc[-1])
        sr = structure.get("support_resistance", []) if structure else []
        nearest_sup = max([s["price"] for s in sr if s["type"] == "support" and s["price"] < last_price], default=None)
        nearest_res = min([s["price"] for s in sr if s["type"] == "resistance" and s["price"] > last_price], default=None)
        entry_exit = {
            "last_price": last_price,
            "nearest_support": nearest_sup,
            "nearest_resistance": nearest_res,
        }
    except Exception:
        pass

    result = rule_analyze(
        symbol=sym,
        signals=signals,
        psychology=psychology,
        darvas=darvas,
        structure=structure,
        mtf_consensus=mtf_consensus,
        entry_exit=entry_exit,
    )

    return {
        "symbol": sym,
        "interval": interval,
        "elapsed_s": round(time.time() - t0, 2),
        "advice": result,
    }


@app.get("/api/backtest/{sym:path}")
def backtest(sym: str, interval: str = "1H"):
    """Run backtesting on 3 strategies and return results."""
    chart_df = _scraper.scrape_yfinance(sym, interval=interval)
    if chart_df is None or chart_df.empty or len(chart_df) < 50:
        return JSONResponse({"error": "insufficient data for backtest", "symbol": sym}, status_code=404)

    try:
        engine_bt = BacktestEngine(chart_df)
        results = engine_bt.run_all_strategies()
    except Exception as exc:
        return JSONResponse({"error": f"backtest failed: {exc}"}, status_code=500)

    # Format results for frontend
    strategies = []
    best_sharpe = -999
    best_idx = 0
    best_name = results.pop("_best_strategy", "")
    for name, res in results.items():
        strat = {
            "name": name,
            "total_return": round(res.get("Total Return [%]", 0), 2),
            "sharpe_ratio": round(res.get("Sharpe Ratio", 0), 3),
            "max_drawdown": round(res.get("Max. Drawdown [%]", 0), 2),
            "win_rate": round(res.get("Win Rate [%]", 0), 1),
            "profit_factor": round(res.get("Profit Factor", 0), 2),
            "num_trades": int(res.get("# Trades", 0)),
            "expectancy": round(res.get("Expectancy [%]", 0), 2),
            "is_best": name == best_name,
        }
        strategies.append(strat)

    return {
        "symbol": sym,
        "interval": interval,
        "bars_used": len(chart_df),
        "strategies": strategies,
        "best_strategy": best_name,
    }


_alert_scan_thread = None
_alert_last_result = {"alerts": [], "total": 0, "interval": "1H"}

@app.get("/api/alerts")
def get_alerts(interval: str = "1H", limit: int = 50, full: bool = False):
    """Scan watchlist symbols for candlestick + indicator alerts.
    Returns cached results instantly; triggers background scan if stale."""
    global _alert_scan_thread, _alert_last_result
    from core.alerts import scan_all, _scan_ts, SCAN_INTERVAL
    import threading

    # Return cached if fresh enough
    if time.time() - _scan_ts < SCAN_INTERVAL and _alert_last_result["alerts"]:
        return {"alerts": _alert_last_result["alerts"][:limit],
                "total": _alert_last_result["total"], "interval": interval}

    # Return cached even if stale (fast response)
    if _alert_last_result["alerts"]:
        if _alert_scan_thread is None or not _alert_scan_thread.is_alive():
            def _bg_scan():
                global _alert_last_result, _alert_scan_thread
                try:
                    result = scan_all(interval=interval, full=full)
                    _alert_last_result = {"alerts": result, "total": len(result), "interval": interval}
                    try:
                        from core.telegram_bot import push_alerts, push_plans, push_charts, push_price_feed, push_news, get_subscribed, _state as tg_state
                        push_alerts(result)
                        # Push plans every 15min (force regenerate when due)
                        from core.alerts import generate_plans_all
                        import time as _time
                        force_plan = (_time.time() - tg_state.get("last_plan_sent", 0)) >= tg_state.get("plan_interval", 900)
                        # Use subscriptions if set
                        subs = get_subscribed()
                        plan_symbols = subs if subs else None
                        plans = generate_plans_all(symbols=plan_symbols, interval=interval, force=force_plan, limit=30 if not plan_symbols else len(plan_symbols))
                        push_plans(plans)
                        # Push charts every 10min (multi-TF)
                        push_charts(timeframes=["5m", "15m", "1H", "4H"])
                        # Push price feed (XAUUSD + chart mỗi 5 phút)
                        push_price_feed()
                        # Push market news (gold, DXY, USD, WTI...)
                        push_news()
                    except Exception:
                        pass
                except Exception:
                    pass
                _alert_scan_thread = None
            _alert_scan_thread = threading.Thread(target=_bg_scan, daemon=True)
            _alert_scan_thread.start()
        return {"alerts": _alert_last_result["alerts"][:limit],
                "total": _alert_last_result["total"], "interval": interval, "stale": True}

    # First load — background scan, return empty
    def _first_scan():
        global _alert_last_result, _alert_scan_thread
        try:
            result = scan_all(interval=interval, full=full)
            _alert_last_result = {"alerts": result, "total": len(result), "interval": interval}
            try:
                from core.telegram_bot import push_alerts, push_plans, push_charts
                push_alerts(result)
                from core.alerts import generate_plans_all
                plans = generate_plans_all(interval=interval)
                push_plans(plans)
                push_charts(interval="5m")
            except Exception:
                pass
        except Exception:
            pass
        _alert_scan_thread = None
    _alert_scan_thread = threading.Thread(target=_first_scan, daemon=True)
    _alert_scan_thread.start()
    return {"alerts": [], "total": 0, "interval": interval, "loading": True}


# ── Telegram Bot Endpoints ────────────────────────────────────────
@app.get("/api/telegram/config")
def tg_get_config():
    from core.telegram_bot import get_config
    return get_config()

@app.post("/api/telegram/signal-bot")
def tg_set_signal_bot(
    enabled: bool = None,
    bot_token: str = None,
    chat_id: str = None,
    min_strength: float = None,
    send_interval: int = None,
    plan_enabled: bool = None,
    plan_interval: int = None,
    chart_enabled: bool = None,
    chart_interval: int = None,
    chart_symbols: str = None,
):
    from core.telegram_bot import set_signal_bot
    kwargs = {}
    if enabled is not None: kwargs["enabled"] = enabled
    if bot_token is not None: kwargs["bot_token"] = bot_token
    if chat_id is not None: kwargs["chat_id"] = chat_id
    if min_strength is not None: kwargs["min_strength"] = min_strength
    if send_interval is not None: kwargs["send_interval"] = send_interval
    if plan_enabled is not None: kwargs["plan_enabled"] = plan_enabled
    if plan_interval is not None: kwargs["plan_interval"] = plan_interval
    if chart_enabled is not None: kwargs["chart_enabled"] = chart_enabled
    if chart_interval is not None: kwargs["chart_interval"] = chart_interval
    if chart_symbols is not None:
        kwargs["chart_symbols"] = [s.strip() for s in chart_symbols.split(",") if s.strip()]
    return set_signal_bot(**kwargs)

@app.post("/api/telegram/price-feed-bot")
def tg_set_price_feed_bot(
    enabled: bool = None,
    bot_token: str = None,
    chat_id: str = None,
    symbols: str = None,
    timeframes: str = None,
    interval: int = None,
):
    from core.telegram_bot import set_price_feed_bot
    kwargs = {}
    if enabled is not None: kwargs["enabled"] = enabled
    if bot_token is not None: kwargs["bot_token"] = bot_token
    if chat_id is not None: kwargs["chat_id"] = chat_id
    if symbols is not None:
        kwargs["symbols"] = [s.strip() for s in symbols.split(",") if s.strip()]
    if timeframes is not None:
        kwargs["timeframes"] = [s.strip() for s in timeframes.split(",") if s.strip()]
    if interval is not None: kwargs["interval"] = interval
    return set_price_feed_bot(**kwargs)

@app.post("/api/telegram/market-news-bot")
def tg_set_market_news_bot(
    enabled: bool = None,
    bot_token: str = None,
    chat_id: str = None,
    keywords: str = None,
    interval: int = None,
    max_news: int = None,
):
    from core.telegram_bot import set_market_news_bot
    kwargs = {}
    if enabled is not None: kwargs["enabled"] = enabled
    if bot_token is not None: kwargs["bot_token"] = bot_token
    if chat_id is not None: kwargs["chat_id"] = chat_id
    if keywords is not None:
        kwargs["keywords"] = [s.strip() for s in keywords.split(",") if s.strip()]
    if interval is not None: kwargs["interval"] = interval
    if max_news is not None: kwargs["max_news"] = max_news
    return set_market_news_bot(**kwargs)

@app.post("/api/telegram/test")
def tg_test(target: str = "signal"):
    from core.telegram_bot import test_connection
    return test_connection(target=target)

@app.post("/api/telegram/send")
def tg_send_now(interval: str = "1H"):
    """Manually send current alerts to signal_bot now."""
    from core.telegram_bot import push_alerts, _state
    from core.alerts import scan_all
    sb = _state["signal_bot"]
    if not sb["enabled"]:
        return {"ok": False, "error": "Signal bot chưa được bật"}
    alerts = scan_all(interval=interval)
    if not alerts:
        return {"ok": True, "message": "Không có tín hiệu nào"}
    push_alerts(alerts)
    return {"ok": True, "message": f"Đã gửi {len(alerts)} tín hiệu"}

@app.post("/api/telegram/send-plans")
def tg_send_plans_now(interval: str = "1H", limit: int = 10):
    """Manually send current MTF plans to signal_bot now."""
    from core.telegram_bot import _state, _send_message, format_plan_message, get_subscribed
    from core.alerts import generate_plans_all
    sb = _state["signal_bot"]
    if not sb["enabled"]:
        return {"ok": False, "error": "Signal bot chưa được bật"}

    # Use signal_bot's chart_symbols first
    plan_symbols = sb.get("chart_symbols", [])[:limit] or get_subscribed()[:limit] or None
    plans = generate_plans_all(symbols=plan_symbols, interval=interval, force=True, limit=limit)
    if not plans:
        return {"ok": True, "message": "Không có plan nào"}

    batch = plans[:5]
    header = f"📋 *PLAN GIAO DỊCH*\n{'═' * 22}"
    lines = [header]
    for p in batch:
        lines.append(format_plan_message(p))
        lines.append("═" * 18)
    text = "\n\n".join(lines)
    result = _send_message(text, target="signal")
    if result.get("ok"):
        _state["last_plan_sent"] = time.time()
        return {"ok": True, "message": f"Đã gửi {len(batch)} plan"}
    return {"ok": False, "error": result.get("error", "Lỗi gửi")}

@app.post("/api/telegram/send-charts")
def tg_send_charts_now(limit: int = 10):
    """Manually send multi-TF chart images to signal_bot now."""
    from core.telegram_bot import _state, push_charts
    sb = _state["signal_bot"]
    if not sb["enabled"]:
        return {"ok": False, "error": "Signal bot chưa được bật"}

    symbols = sb.get("chart_symbols", [])[:limit] or None
    _state["last_chart_sent"] = 0
    push_charts(symbols=symbols, timeframes=["5m", "15m", "1H", "4H"])
    sym_count = len(symbols) if symbols else limit
    return {"ok": True, "message": f"Đã gửi chart cho {sym_count} symbols × 4 khung"}


@app.post("/api/telegram/send-price-feed")
def tg_send_price_feed_now():
    """Manually send price feed to price_feed_bot now."""
    from core.telegram_bot import _state, push_price_feed
    pfb = _state["price_feed_bot"]
    if not pfb["enabled"]:
        return {"ok": False, "error": "Price feed bot chưa được bật"}

    _state["last_price_feed"] = 0
    push_price_feed()
    syms = pfb.get("symbols", [])
    tfs = pfb.get("timeframes", [])
    return {"ok": True, "message": f"Đã gửi price feed {len(syms)} symbol × {len(tfs)} khung"}


@app.post("/api/telegram/send-news")
def tg_send_news_now():
    """Manually send market news to market_news_bot now."""
    from core.telegram_bot import _state, push_news
    nb = _state["market_news_bot"]
    if not nb["enabled"]:
        return {"ok": False, "error": "News bot chưa được bật"}

    _state["last_news"] = 0
    push_news()
    return {"ok": True, "message": "Đã gửi tin tức thị trường"}


if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="web")
else:
    @app.get("/")
    def no_web():
        return JSONResponse({"error": "web/dist chưa build — chạy npm run build trong web/"})


if __name__ == "__main__":
    import uvicorn
    # Start Telegram bot polling on server startup
    try:
        from core.telegram_bot import start_polling, _state as tg_state
        if (tg_state.get("signal_bot", {}).get("bot_token") or
            tg_state.get("price_feed_bot", {}).get("bot_token") or
            tg_state.get("market_news_bot", {}).get("bot_token")):
            start_polling()
            print("[TG] Bot polling started (3 bots)")
    except Exception as e:
        print(f"[TG] Bot polling start failed: {e}")
    uvicorn.run("server:app", host="0.0.0.0", port=8502)