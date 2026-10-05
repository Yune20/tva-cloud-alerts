# TradingView Analyzer Pro v2 — UI Rebuild Plan

## Target Layout (from screenshot)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ HEADER: Logo | Tổng quan | Biểu đồ | Phân tích AI | Cảnh báo | ...    │
├──────────┬──────────────────────────────────────┬────────────────────────┤
│          │  CHART HEADER: BTCUSDT | 15m | icons  │                        │
│  LEFT    │  OHLCV info bar                       │  RIGHT PANEL          │
│  SIDEBAR │  ┌────────────────────────────────┐  │                        │
│          │  │  CANDLESTICK CHART              │  │  📢 Cảnh báo &        │
│  Watch   │  │  + SMA/EMA + BUY/SELL markers   │  │     Tín hiệu AI      │
│  list    │  │  + TP/SL lines                  │  │  ┌──────────────┐    │
│          │  │  + current price tag             │  │  │ Alert cards  │    │
│  + Tools │  └────────────────────────────────┘  │  └──────────────┘    │
│          │  Volume | RSI | MACD | Stoch | ADX   │                        │
│          │  ┌────────────────────────────────┐  │  📊 Trạng thái &      │
│          │  │  Bottom table with tabs         │  │     Xu hướng          │
│          │  │  Lịch sử | Thống kê | Backtest  │  │  Trend status + bar  │
│          │  └────────────────────────────────┘  │                        │
│          │                                       │  💡 Gợi ý chiến lược │
│          │                                       │  AI strategy card     │
│          │                                       │                        │
│          │                                       │  🔔 Thông báo realtime│
│          │                                       │  Live notifications   │
└──────────┴──────────────────────────────────────┴────────────────────────┘
```

## Structural Changes

### 1. Header Bar (custom HTML)
- Full-width dark bar with gradient
- Logo + title + subtitle (left)
- Navigation tabs as styled radio (center) — decorative for now, could be future pages
- Status dot + refresh timer (right)

### 2. Left Sidebar (`st.sidebar`)
- **Watchlist**: Category tabs (Crypto/Forex/Index/Commodity) → filtered table with Symbol, Giá, 24h, Trend arrows
- **Analysis Tools**: Checkbox toggles for indicators (RSI, MACD, BB, MA, Volume, Ichimoku, Stochastic, ADX)
- **Drawing Tools**: Static list (Trendline, Fibonacci, Rectangle, Text, Arrow, Pitchfork) — decorative labels
- **Analyze button** at bottom

### 3. Main Content Area (center column)
- **Chart header strip**: Symbol + timeframe + OHLCV values
- **Stacked chart**: Candlestick + RSI + MACD + Volume + Stochastic + ADX sub-panels
- **BUY/SELL markers**: From trade setup signals
- **TP/SL lines**: Dashed horizontal with labels
- **Bottom table**: Tabs for signal history, statistics, backtest

### 4. Right Panel (right column)
- **Cảnh báo & Tín hiệu AI**: Alert cards with icon, title, time, description, confidence %
- **Trạng thái thị trường & Xu hướng**: Direction badge, per-TF trend status, trend strength gauge
- **Gợi ý chiến lược (AI)**: Strategy recommendation with bullet points
- **Thông báo realtime**: Live event feed with timestamps

## Files to Modify

| File | Change |
|------|--------|
| `app.py` | Complete rewrite of layout: header HTML, 3-column layout, new right panel sections |
| `dashboard/components.py` | New render functions: `render_header_bar`, `render_watchlist`, `render_alert_cards`, `render_market_status`, `render_ai_suggestion`, `render_realtime_feed`, `render_bottom_table`. Upgrade `render_stacked_chart` with BUY/SELL markers |
| `config.py` | Add WATCHLIST_SYMBOLS, ALERT_TEMPLATES |
| `core/trade_setup.py` | Add `detect_entry_signals()` for BUY/SELL markers on chart |

## CSS Theme
- Background: `#0a0e17` (deep dark blue-black)
- Cards: `#111827` with `1px solid #1e293b`
- Accent green: `#22c55e` (bullish/buy)
- Accent red: `#ef4444` (bearish/sell)
- Text primary: `#f1f5f9`
- Text secondary: `#94a3b8`
- Active tab: `#22c55e` underline
