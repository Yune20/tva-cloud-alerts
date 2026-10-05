import React, { useEffect, useRef, useState } from 'react'
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts'

const TFS = ['1m', '5m', '15m', '30m', '1H', '4H', '1D']
const DIRC = { LONG: 'var(--up)', SHORT: 'var(--down)', NEUTRAL: 'var(--muted)' }
const ZONE_CLR = { EXTREME_FEAR: '#c62828', FEAR: '#e53935', NEUTRAL: '#78909c', GREED: '#2e7d32', EXTREME_GREED: '#1b5e20' }
const PHASE_CLR = { ACCUMULATION: '#1565c0', MARKUP: '#2e7d32', DISTRIBUTION: '#ef6c00', MARKDOWN: '#c62828' }

export default function SymbolView({ sym, name, fmt, catOf, quote, onClose }) {
  const [tf, setTf] = useState('1H')
  const [data, setData] = useState(null)
  const [btData, setBtData] = useState(null)
  const [aiData, setAiData] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState('analysis')
  const [toggles, setToggles] = useState({
    sr: true, entry_exit: false, fibonacci: false, confluence: false,
    darvas: false, trendlines: false, markers: true,
    structure: false, swing: false,
    bb: false, ema: false, supertrend: false, vwap: false,
    scalper: false, eet: false, vp: false,
  })
  const boxRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)
  const barsRef = useRef([])
  const priceLinesRef = useRef([])

  const fetchAiAdvice = () => {
    setAiLoading(true)
    setAiData(null)
    fetch(`/api/ai-advice/${encodeURIComponent(sym)}?interval=${tf}`)
      .then(r => r.json())
      .then(d => setAiData(d))
      .catch(() => setAiData(null))
      .finally(() => setAiLoading(false))
  }

  useEffect(() => {
    setLoading(true)
    fetch(`/api/analysis/${encodeURIComponent(sym)}?interval=${tf}`)
      .then(r => r.json())
      .then(d => { setData(d); barsRef.current = d.chart?.bars || []; })
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [sym, tf])

  useEffect(() => {
    fetch(`/api/backtest/${encodeURIComponent(sym)}?interval=${tf}`)
      .then(r => r.json())
      .then(d => setBtData(d))
      .catch(() => setBtData(null))
  }, [sym, tf])

  // ── Chart creation (runs once per symbol/timeframe change) ──
  useEffect(() => {
    if (!data || !boxRef.current) return
    if (chartRef.current) { try { chartRef.current.remove() } catch(e) {} chartRef.current = null; seriesRef.current = null }
    const chart = createChart(boxRef.current, {
      width: boxRef.current.clientWidth,
      height: 380,
      layout: { background: { type: ColorType.Solid, color: '#ffffff' }, textColor: '#37474f' },
      grid: { vertLines: { color: '#eceff1' }, horzLines: { color: '#eceff1' } },
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: { borderColor: '#e0e0e0' },
      rightPriceScale: { borderColor: '#e0e0e0' },
    })
    const series = chart.addCandlestickSeries({
      upColor: '#1b8a5a', downColor: '#d32f2f',
      borderUpColor: '#1b8a5a', borderDownColor: '#d32f2f',
      wickUpColor: '#1b8a5a', wickDownColor: '#d32f2f',
    })
    const chartBars = barsRef.current.map(b => ({
      time: Math.floor(b[0] / 1000),
      open: b[1], high: b[2], low: b[3], close: b[4],
    }))
    series.setData(chartBars)
    chart.timeScale().fitContent()
    seriesRef.current = series
    chartRef.current = chart
    priceLinesRef.current = []
    return () => { try { chart.remove() } catch (e) {} chartRef.current = null; seriesRef.current = null; priceLinesRef.current = [] }
  }, [sym, tf, data])

  // ── Draw overlays (runs on every toggle change) ──
  useEffect(() => {
    const series = seriesRef.current
    if (!series || !data) return
    priceLinesRef.current.forEach(pl => { try { series.removePriceLine(pl) } catch(e) {} })
    priceLinesRef.current = []
    const markers = []
    const ov = data.overlays || {}
    const pl = (opts) => { const line = series.createPriceLine(opts); priceLinesRef.current.push(line); return line }

    if (toggles.darvas && ov.darvas_box) {
      const db = ov.darvas_box
      pl({ price: db.top, color: '#7b1fa2', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'Box Top' })
      pl({ price: db.bottom, color: '#7b1fa2', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'Box Bot' })
    }
    if (toggles.sr) {
      (ov.support_resistance || []).slice(0, 6).forEach(s => {
        const color = s.type === 'support' ? '#1b8a5a' : '#d32f2f'
        pl({ price: s.price, color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: s.type === 'support' ? 'S' : 'R' })
      })
    }
    if (toggles.fibonacci) {
      const fib = ov.fibonacci || {}
      Object.entries(fib).forEach(([name, price]) => {
        if (typeof price === 'number' && price > 0) {
          pl({ price, color: '#ef6c00', lineWidth: 1, lineStyle: 3, axisLabelVisible: false })
        }
      })
    }
    if (toggles.confluence) {
      (ov.confluence_zones || []).slice(0, 3).forEach(z => {
        pl({ price: z.price, color: '#8e24aa', lineWidth: 2, lineStyle: 0, axisLabelVisible: true, title: 'Confluence' })
      })
    }
    if (toggles.entry_exit) {
      const ee = data.entry_exit || {}
      if (ee.suggested_entry) pl({ price: ee.suggested_entry, color: '#1565c0', lineWidth: 2, lineStyle: 0, axisLabelVisible: true, title: 'VÀO' })
      if (ee.suggested_stop) pl({ price: ee.suggested_stop, color: '#d32f2f', lineWidth: 1, lineStyle: 1, axisLabelVisible: true, title: 'SL' })
      if (ee.suggested_tp1) pl({ price: ee.suggested_tp1, color: '#1b8a5a', lineWidth: 1, lineStyle: 1, axisLabelVisible: true, title: 'TP1' })
    }
    if (toggles.trendlines) {
      (ov.trendlines || []).forEach(tl => {
        if (!tl.price || tl.price <= 0) return
        const color = tl.type === 'ascending' ? '#1565c0' : '#d32f2f'
        pl({ price: tl.price, color, lineWidth: 2, lineStyle: 0, axisLabelVisible: true, title: tl.type === 'ascending' ? 'Trend ↑' : 'Trend ↓' })
      })
    }
    if (toggles.markers) {
      (ov.markers || []).forEach(m => markers.push({ ...m }))
    }
    if (toggles.structure) {
      const ms = ov.market_structure || {}
      ;(ms.events || []).forEach(e => {
        if (e.type === 'BOS') {
          pl({ price: e.price, color: e.direction === 'BULLISH' ? '#1565c0' : '#d32f2f', lineWidth: 2, lineStyle: 1, axisLabelVisible: true, title: `BOS ${e.direction}` })
        } else {
          pl({ price: e.price, color: e.direction === 'BULLISH' ? '#2e7d32' : '#c62828', lineWidth: 2, lineStyle: 0, axisLabelVisible: true, title: `ChoCh ${e.direction}` })
        }
      })
    }
    if (toggles.swing) {
      const ms = ov.market_structure || {}
      ;(ms.swing_highs || []).forEach(sh => {
        pl({ price: sh.price, color: '#7b1fa2', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: 'SwingH' })
      })
      ;(ms.swing_lows || []).forEach(sl => {
        pl({ price: sl.price, color: '#7b1fa2', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: 'SwingL' })
      })
    }
    if (toggles.bb && ov.indicators?.bollinger) {
      const bb = ov.indicators.bollinger
      if (bb.upper) bb.upper.forEach(p => pl({ price: p.value, color: '#ef6c00', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: 'BB Upper' }))
      if (bb.lower) bb.lower.forEach(p => pl({ price: p.value, color: '#ef6c00', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: 'BB Lower' }))
      if (bb.middle) bb.middle.forEach(p => pl({ price: p.value, color: '#ef6c00', lineWidth: 1, lineStyle: 0, axisLabelVisible: false, title: 'BB Mid' }))
    }
    if (toggles.ema && ov.indicators?.ema) {
      const emaColors = { '9': '#e91e63', '21': '#2196f3', '50': '#ff9800', '100': '#9c27b0', '200': '#607d8b' }
      Object.entries(ov.indicators.ema).forEach(([period, pts]) => {
        if (!pts || pts.length === 0) return
        const lastPt = pts[pts.length - 1]
        pl({ price: lastPt.value, color: emaColors[period] || '#78909c', lineWidth: 1, lineStyle: 0, axisLabelVisible: true, title: `EMA ${period}` })
      })
    }
    if (toggles.supertrend && ov.indicators?.supertrend?.length > 0) {
      const lastSt = ov.indicators.supertrend[ov.indicators.supertrend.length - 1]
      pl({ price: lastSt.value, color: '#00bcd4', lineWidth: 2, lineStyle: 0, axisLabelVisible: true, title: 'Supertrend' })
    }
    if (toggles.vwap && ov.indicators?.vwap?.length > 0) {
      const lastVwap = ov.indicators.vwap[ov.indicators.vwap.length - 1]
      pl({ price: lastVwap.value, color: '#795548', lineWidth: 1, lineStyle: 1, axisLabelVisible: true, title: 'VWAP' })
    }
    if (toggles.scalper && ov.custom?.scalper?.entries) {
      ov.custom.scalper.entries.forEach(e => markers.push({ time: e.time, position: e.position, color: e.color, shape: e.shape, text: e.text }))
    }
    if (toggles.eet && ov.custom?.entry_exit_tool?.entry) {
      const eet = ov.custom.entry_exit_tool
      pl({ price: eet.entry, color: '#1565c0', lineWidth: 2, lineStyle: 0, axisLabelVisible: true, title: 'ENTRY' })
      pl({ price: eet.stop_loss, color: '#d32f2f', lineWidth: 1, lineStyle: 1, axisLabelVisible: true, title: 'STOP' })
      pl({ price: eet.take_profit_1, color: '#1b8a5a', lineWidth: 1, lineStyle: 1, axisLabelVisible: true, title: 'TP1' })
      pl({ price: eet.take_profit_2, color: '#2e7d32', lineWidth: 1, lineStyle: 1, axisLabelVisible: true, title: 'TP2' })
    }
    if (toggles.vp && ov.custom?.volume_profile?.poc) {
      const vp = ov.custom.volume_profile
      pl({ price: vp.poc, color: '#ff6f00', lineWidth: 2, lineStyle: 0, axisLabelVisible: true, title: 'POC' })
      pl({ price: vp.value_area_high, color: '#ff6f00', lineWidth: 1, lineStyle: 2, axisLabelVisible: false })
      pl({ price: vp.value_area_low, color: '#ff6f00', lineWidth: 1, lineStyle: 2, axisLabelVisible: false })
    }
    if (markers.length > 0) {
      series.setMarkers(markers.sort((a, b) => a.time - b.time))
    } else {
      series.setMarkers([])
    }
  }, [data, toggles])

  useEffect(() => {
    const s = seriesRef.current
    const bars = barsRef.current
    if (!s || !bars.length || !quote || quote.price == null) return
    const last = bars[bars.length - 1]
    const upd = { time: Math.floor(last[0] / 1000), open: last[1], high: Math.max(last[2], quote.price), low: Math.min(last[3], quote.price), close: quote.price }
    try { s.update(upd) } catch (e) {}
  }, [quote])

  const cat = catOf(sym)
  const chg = quote ? quote.chg : null
  const px = quote ? quote.price : (data && data.chart?.bars?.length ? data.chart.bars[data.chart.bars.length - 1][4] : null)
  const pxCls = chg > 0.03 ? 'up' : chg < -0.03 ? 'down' : 'flat'
  const cons = data?.consensus || {}
  const plans = data?.timeframes || []
  const action = data?.action_plan || {}
  const psych = data?.psychology
  const darvas = data?.darvas
  const ee = data?.entry_exit || {}

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <div className="drawer">
        <div className="dh">
          <div>
            <h2>{name} <span style={{ color: 'var(--muted)', fontWeight: 400 }}>{sym}</span></h2>
          </div>
          <div className={`price ${pxCls}`}>{px != null ? fmt(px, cat) : '…'}</div>
          <div className={`chg ${pxCls}`}>{chg != null ? `${chg > 0 ? '+' : ''}${chg}%` : ''}</div>
          <div className="stretch" />
          <button className="close" onClick={onClose}>✕</button>
        </div>

        {/* ── Tabs ───────────────────────────────────────── */}
        <div className="tabs">
          {[['analysis', '📊 Phân Tích'], ['trade', '🎯 Kế Hoạch'], ['ai', '🤖 Tư Vấn'], ['backtest', '📈 Thử Nghiệm']].map(([k, l]) => (
            <button key={k} className={`tab ${tab === k ? 'active' : ''}`} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>

        {/* ── Timeframe selector ─────────────────────────── */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
          {TFS.map(t => (
            <button key={t} className="btn" style={t === tf ? { borderColor: 'var(--primary)', color: 'var(--primary)' } : {}} onClick={() => setTf(t)}>{t}</button>
          ))}
        </div>

        {loading && <div className="loading">Đang phân tích đa khung (7 khung)…</div>}

        {data && tab === 'analysis' && (
          <>
            {/* ── Overlay Toggles ────────────────────────────── */}
            <div className="toggle-bar">
              <span className="toggle-title">CHỈ BÁO:</span>
              {[
                ['sr', 'S/R', '#1b8a5a'],
                ['entry_exit', 'Entry/Exit', '#1565c0'],
                ['markers', 'Markers', '#78909c'],
                ['bb', 'Bollinger', '#ef6c00'],
                ['ema', 'EMA', '#2196f3'],
                ['supertrend', 'Supertrend', '#00bcd4'],
                ['vwap', 'VWAP', '#795548'],
                ['structure', 'BOS/ChoCh', '#c62828'],
                ['swing', 'Swing H/L', '#7b1fa2'],
                ['darvas', 'Darvas', '#7b1fa2'],
                ['fibonacci', 'Fibonacci', '#ef6c00'],
                ['confluence', 'Confluence', '#8e24aa'],
                ['trendlines', 'Trendlines', '#1565c0'],
                ['scalper', 'Scalper', '#1565c0'],
                ['eet', 'Entry-Exit Tool', '#1565c0'],
                ['vp', 'Volume Profile', '#ff6f00'],
              ].map(([key, label, color]) => (
                <button
                  key={key}
                  className={`toggle-chip ${toggles[key] ? 'on' : ''}`}
                  style={toggles[key] ? { background: color, color: '#fff', borderColor: color } : {}}
                  onClick={() => setToggles(prev => ({ ...prev, [key]: !prev[key] }))}
                >{label}</button>
              ))}
            </div>

            {/* ── Chart ───────────────────────────────────── */}
            <div className="chart-box" ref={boxRef} style={{ visibility: loading ? 'hidden' : 'visible' }} />

            {/* ── Technical Indicators Panel ────────────────── */}
            {data.signals && Object.keys(data.signals).length > 0 && (
              <>
                <div className="sec">CHỈ BÁO KỸ THUẬT</div>
                <div className="ind-grid">
                  {data.signals.RSI && (
                    <div className="ind-card">
                      <div className="ind-name">RSI (14)</div>
                      <div className="ind-val" style={{ color: data.signals.RSI.signal === 'OVERBOUGHT' ? 'var(--down)' : data.signals.RSI.signal === 'OVERSOLD' ? 'var(--up)' : 'var(--text)' }}>
                        {data.signals.RSI.value}
                      </div>
                      <div className={`ind-sig ${data.signals.RSI.signal === 'OVERBOUGHT' ? 'sig-down' : data.signals.RSI.signal === 'OVERSOLD' ? 'sig-up' : ''}`}>
                        {data.signals.RSI.signal === 'OVERBOUGHT' ? 'Mua quá' : data.signals.RSI.signal === 'OVERSOLD' ? 'Bán quá' : 'Trung tính'}
                      </div>
                    </div>
                  )}
                  {data.signals.MACD && (
                    <div className="ind-card">
                      <div className="ind-name">MACD</div>
                      <div className="ind-val" style={{ color: data.signals.MACD.direction === 'BULLISH' ? 'var(--up)' : 'var(--down)' }}>
                        {data.signals.MACD.direction}
                      </div>
                      <div className="ind-sub">Hist: {data.signals.MACD.histogram?.toFixed(4)}</div>
                    </div>
                  )}
                  {data.signals.ADX && (
                    <div className="ind-card">
                      <div className="ind-name">ADX</div>
                      <div className="ind-val">{data.signals.ADX.value}</div>
                      <div className={`ind-sig ${data.signals.ADX.trend_strength === 'STRONG' ? 'sig-up' : ''}`}>
                        {data.signals.ADX.trend_strength === 'STRONG' ? 'Mạnh' : 'Yếu'}
                      </div>
                    </div>
                  )}
                  {data.signals['EMA_Cross'] && (
                    <div className="ind-card">
                      <div className="ind-name">EMA Cross</div>
                      <div className="ind-val" style={{ color: data.signals['EMA_Cross'].signal === 'GOLDEN' ? 'var(--up)' : 'var(--down)' }}>
                        {data.signals['EMA_Cross'].signal === 'GOLDEN' ? 'Thập vàng' : 'Thập tử'}
                      </div>
                      <div className="ind-sub">9: {data.signals['EMA_Cross'].short?.toFixed(2)} / 21: {data.signals['EMA_Cross'].long?.toFixed(2)}</div>
                    </div>
                  )}
                  {data.signals.Bollinger && (
                    <div className="ind-card">
                      <div className="ind-name">Bollinger</div>
                      <div className="ind-val">{data.signals.Bollinger.position?.toFixed(1)}%</div>
                      <div className={`ind-sig ${data.signals.Bollinger.signal === 'OVERBOUGHT' ? 'sig-down' : data.signals.Bollinger.signal === 'OVERSOLD' ? 'sig-up' : ''}`}>
                        {data.signals.Bollinger.signal === 'OVERBOUGHT' ? 'Trên band' : data.signals.Bollinger.signal === 'OVERSOLD' ? 'Dưới band' : 'Trong band'}
                      </div>
                    </div>
                  )}
                  {data.signals.Supertrend && (
                    <div className="ind-card">
                      <div className="ind-name">Supertrend</div>
                      <div className="ind-val" style={{ color: data.signals.Supertrend.direction === 'BULL' ? 'var(--up)' : 'var(--down)' }}>
                        {data.signals.Supertrend.direction === 'BULL' ? 'BULL' : 'BEAR'}
                      </div>
                      <div className="ind-sub">{data.signals.Supertrend.value?.toFixed(2)}</div>
                    </div>
                  )}
                  {data.signals.Stochastic && (
                    <div className="ind-card">
                      <div className="ind-name">Stochastic</div>
                      <div className="ind-val">{data.signals.Stochastic.K?.toFixed(1)} / {data.signals.Stochastic.D?.toFixed(1)}</div>
                      <div className={`ind-sig ${data.signals.Stochastic.signal === 'OVERBOUGHT' ? 'sig-down' : data.signals.Stochastic.signal === 'OVERSOLD' ? 'sig-up' : ''}`}>
                        {data.signals.Stochastic.signal === 'OVERBOUGHT' ? 'Mua quá' : data.signals.Stochastic.signal === 'OVERSOLD' ? 'Bán quá' : 'TB'}
                      </div>
                    </div>
                  )}
                  {data.signals.MFI && (
                    <div className="ind-card">
                      <div className="ind-name">MFI</div>
                      <div className="ind-val">{data.signals.MFI.value}</div>
                      <div className={`ind-sig ${data.signals.MFI.signal === 'OVERBOUGHT' ? 'sig-down' : data.signals.MFI.signal === 'OVERSOLD' ? 'sig-up' : ''}`}>
                        {data.signals.MFI.signal === 'OVERBOUGHT' ? 'Mua quá' : data.signals.MFI.signal === 'OVERSOLD' ? 'Bán quá' : 'TB'}
                      </div>
                    </div>
                  )}
                  {data.signals.ATR && (
                    <div className="ind-card">
                      <div className="ind-name">ATR</div>
                      <div className="ind-val">{data.signals.ATR.percent?.toFixed(2)}%</div>
                      <div className="ind-sub">{data.signals.ATR.value?.toFixed(4)}</div>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* ── Winners Scalper Pro ───────────────────── */}
            {data.overlays?.custom?.scalper && (() => {
              const sc = data.overlays.custom.scalper
              const sigClr = sc.signal === 'BULL' ? 'var(--up)' : sc.signal === 'BEAR' ? 'var(--down)' : 'var(--muted)'
              return (
                <>
                  <div className="sec">🏆 WINNERS SCALPER PRO</div>
                  <div className="scalper-panel">
                    <div className="scalper-signal" style={{ color: sigClr }}>
                      {sc.signal === 'BULL' ? '🟢 BULL' : sc.signal === 'BEAR' ? '🔴 BEAR' : '⚪ NEUTRAL'}
                      <span className="scalper-str">{sc.strength}%</span>
                    </div>
                    <div className="scalper-bar">
                      <div className="scalper-fill" style={{ width: `${sc.bull_count || 0}%`, background: 'var(--up)' }} />
                      <div className="scalper-fill" style={{ width: `${sc.bear_count || 0}%`, background: 'var(--down)' }} />
                    </div>
                    <div className="scalper-labels">
                      <span>BULL {sc.bull_count || 0}</span>
                      <span>BEAR {sc.bear_count || 0}</span>
                    </div>
                  </div>
                </>
              )
            })()}

            {/* ── Entry-to-Exit Tool ────────────────────── */}
            {data.overlays?.custom?.entry_exit_tool && (() => {
              const eet = data.overlays.custom.entry_exit_tool
              return (
                <>
                  <div className="sec">🎯 ENTRY-TO-EXIT TOOL</div>
                  <div className="eet-panel">
                    <div className="eet-trend" style={{ color: eet.trend === 'UPTREND' ? 'var(--up)' : eet.trend === 'DOWNTREND' ? 'var(--down)' : 'var(--muted)' }}>
                      {eet.trend === 'UPTREND' ? '📈' : eet.trend === 'DOWNTREND' ? '📉' : '➡️'} {eet.trend}
                    </div>
                    <div className="eet-grid">
                      <div className="eet-box eet-entry">
                        <div className="eet-label">ENTRY</div>
                        <div className="eet-val">{fmt(eet.entry, cat)}</div>
                      </div>
                      <div className="eet-box eet-sl">
                        <div className="eet-label">STOP LOSS</div>
                        <div className="eet-val">{fmt(eet.stop_loss, cat)}</div>
                      </div>
                      <div className="eet-box eet-tp1">
                        <div className="eet-label">TP1</div>
                        <div className="eet-val">{fmt(eet.take_profit_1, cat)}</div>
                      </div>
                      <div className="eet-box eet-tp2">
                        <div className="eet-label">TP2</div>
                        <div className="eet-val">{fmt(eet.take_profit_2, cat)}</div>
                      </div>
                    </div>
                    <div className="eet-meta">
                      <span>R:R {eet.risk_reward}</span>
                      <span>ATR {eet.atr_percent}%</span>
                      <span>EMA9 {fmt(eet.ema9, cat)}</span>
                      <span>EMA21 {fmt(eet.ema21, cat)}</span>
                    </div>
                  </div>
                </>
              )
            })()}

            {/* ── Volume Profile ────────────────────────── */}
            {data.overlays?.custom?.volume_profile && (() => {
              const vp = data.overlays.custom.volume_profile
              return (
                <>
                  <div className="sec">📊 VOLUME PROFILE</div>
                  <div className="vp-panel">
                    <div className="vp-stats">
                      <div className="vp-stat">
                        <span className="vp-stat-label">POC</span>
                        <span className="vp-stat-val vp-poc">{fmt(vp.poc, cat)}</span>
                      </div>
                      <div className="vp-stat">
                        <span className="vp-stat-label">VA High</span>
                        <span className="vp-stat-val">{fmt(vp.value_area_high, cat)}</span>
                      </div>
                      <div className="vp-stat">
                        <span className="vp-stat-label">VA Low</span>
                        <span className="vp-stat-val">{fmt(vp.value_area_low, cat)}</span>
                      </div>
                      <div className="vp-stat">
                        <span className="vp-stat-label">Vol Ratio</span>
                        <span className="vp-stat-val" style={{ color: vp.current_volume_ratio > 1.5 ? 'var(--up)' : vp.current_volume_ratio < 0.5 ? 'var(--down)' : 'var(--text)' }}>
                          {vp.current_volume_ratio}x
                        </span>
                      </div>
                    </div>
                    {/* Volume bar chart */}
                    <div className="vp-bars">
                      {(vp.zones || []).slice().reverse().map((z, i) => (
                        <div key={i} className="vp-row">
                          <span className="vp-price">{fmt(z.price, cat)}</span>
                          <div className="vp-bar-bg">
                            <div className="vp-bar-fill" style={{ width: `${Math.min(100, z.pct * 5)}%`, background: z.volume > (vp.avg_volume_20 || 0) * 1.5 ? '#1565c0' : z.volume < (vp.avg_volume_20 || 0) * 0.5 ? '#90a4ae' : '#42a5f5' }} />
                          </div>
                          <span className="vp-pct">{z.pct}%</span>
                        </div>
                      ))}
                    </div>
                    {vp.high_volume_zones?.length > 0 && (
                      <div className="vp-zones">
                        <span className="vp-zone-label">Vùng mua/bán mạnh:</span>
                        {vp.high_volume_zones.map((p, i) => <span key={i} className="vp-zone vp-zone-high">{fmt(p, cat)}</span>)}
                      </div>
                    )}
                  </div>
                </>
              )
            })()}

            {/* ── Psychology Zone ─────────────────────────── */}
            {psych && (
              <>
                <div className="sec">TÂM LÝ THỊ TRƯỜNG</div>
                <div className="psych-bar">
                  <div className="psych-gauge">
                    <div className="psych-fill" style={{ width: `${psych.score}%`, background: ZONE_CLR[psych.zone] || '#78909c' }} />
                  </div>
                  <div className="psych-label" style={{ color: ZONE_CLR[psych.zone] }}>
                    {psych.zone_info?.emoji} {psych.zone_info?.label_vi} ({psych.score}/100)
                  </div>
                </div>
                <div className="psych-phase" style={{ borderLeftColor: PHASE_CLR[psych.phase] || '#78909c' }}>
                  <b>{psych.phase_info?.label_vi}</b> — {psych.phase_desc}
                </div>
                {psych.signals_detail?.length > 0 && (
                  <div className="psych-signals">
                    {psych.signals_detail.map((s, i) => <div key={i} className="psig">• {s}</div>)}
                  </div>
                )}
              </>
            )}

            {/* ── Darvas Box ──────────────────────────────── */}
            {darvas && darvas.current_box && (
              <>
                <div className="sec">HỘP DARVAS</div>
                <div className="darvas-info">
                  <span>Hộp: {fmt(darvas.current_box.bottom, cat)} — {fmt(darvas.current_box.top, cat)}</span>
                  <span className="sep">│</span>
                  <span>{darvas.current_box.bars_in_box} nến · {darvas.current_box.range_pct}%</span>
                  {darvas.current_box.breakout && (
                    <span className={`brk ${darvas.current_box.breakout === 'UP' ? 'up' : 'down'}`}>
                      ⚡ Phá vỡ {darvas.current_box.breakout === 'UP' ? 'LÊN' : 'XUỐNG'}
                    </span>
                  )}
                </div>
                <div className="darvas-trend">{darvas.trend_vi}</div>
                {darvas.summary_vi?.map((s, i) => <div key={i} className="s">{s}</div>)}
              </>
            )}

            {/* ── Market Structure (BOS + ChoCh) ─────────── */}
            {data.overlays?.market_structure && (() => {
              const ms = data.overlays.market_structure
              const trend = ms.trend || 'NEUTRAL'
              const events = ms.events || []
              const bosCount = events.filter(e => e.type === 'BOS').length
              const chochCount = events.filter(e => e.type === 'ChoCh').length
              const lastBos = ms.last_bos
              const lastChoch = ms.last_choch
              const trendClr = trend === 'UPTREND' ? 'var(--up)' : trend === 'DOWNTREND' ? 'var(--down)' : 'var(--muted)'
              return (
                <>
                  <div className="sec">CẤU TRÚC THỊ TRƯỜNG</div>
                  <div className="ms-panel">
                    <div className="ms-trend" style={{ color: trendClr }}>
                      {trend === 'UPTREND' ? '📈' : trend === 'DOWNTREND' ? '📉' : '➡️'} {trend}
                    </div>
                    <div className="ms-stats">
                      <div className="ms-stat">
                        <span className="ms-stat-label">BOS</span>
                        <span className="ms-stat-val" style={{ color: '#1565c0' }}>{bosCount}</span>
                      </div>
                      <div className="ms-stat">
                        <span className="ms-stat-label">ChoCh</span>
                        <span className="ms-stat-val" style={{ color: '#c62828' }}>{chochCount}</span>
                      </div>
                      <div className="ms-stat">
                        <span className="ms-stat-label">Swing H</span>
                        <span className="ms-stat-val">{(ms.swing_highs || []).length}</span>
                      </div>
                      <div className="ms-stat">
                        <span className="ms-stat-label">Swing L</span>
                        <span className="ms-stat-val">{(ms.swing_lows || []).length}</span>
                      </div>
                    </div>
                    {lastBos && (
                      <div className="ms-event">
                        <span className="ms-badge ms-bos">BOS</span>
                        <span style={{ color: lastBos.direction === 'BULLISH' ? 'var(--up)' : 'var(--down)' }}>
                          {lastBos.direction} @ {fmt(lastBos.price, cat)}
                        </span>
                      </div>
                    )}
                    {lastChoch && (
                      <div className="ms-event">
                        <span className="ms-badge ms-choch">ChoCh</span>
                        <span style={{ color: lastChoch.direction === 'BULLISH' ? 'var(--up)' : 'var(--down)' }}>
                          {lastChoch.direction} @ {fmt(lastChoch.price, cat)}
                        </span>
                      </div>
                    )}
                    {events.length > 0 && (
                      <div className="ms-events-list">
                        {events.slice(-5).reverse().map((e, i) => (
                          <div key={i} className="ms-ev">
                            <span className={`ms-badge ${e.type === 'BOS' ? 'ms-bos' : 'ms-choch'}`}>{e.type}</span>
                            <span style={{ color: e.direction === 'BULLISH' ? 'var(--up)' : 'var(--down)' }}>{e.direction}</span>
                            <span className="ms-ev-price">{fmt(e.price, cat)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )
            })()}

            {/* ── Entry / Exit Levels ─────────────────────── */}
            {ee.last_price && (
              <>
                <div className="sec">VÙNG VÀO / THOÁT LỆNH</div>
                <div className="entry-exit">
                  <div className="ee-item"><span className="ee-label">Giá hiện tại</span><span className="ee-val">{fmt(ee.last_price, cat)}</span></div>
                  {ee.nearest_support && <div className="ee-item support"><span className="ee-label">Hỗ trợ gần</span><span className="ee-val up">{fmt(ee.nearest_support, cat)}</span></div>}
                  {ee.nearest_resistance && <div className="ee-item resistance"><span className="ee-label">Kháng cự gần</span><span className="ee-val down">{fmt(ee.nearest_resistance, cat)}</span></div>}
                  {ee.suggested_entry && <div className="ee-item entry"><span className="ee-label">Vào lệnh</span><span className="ee-val" style={{ color: 'var(--primary)' }}>{fmt(ee.suggested_entry, cat)}</span></div>}
                  {ee.suggested_stop && <div className="ee-item stop"><span className="ee-label">Cắt lỗ (SL)</span><span className="ee-val down">{fmt(ee.suggested_stop, cat)}</span></div>}
                  {ee.suggested_tp1 && <div className="ee-item tp"><span className="ee-label">Chốt lời (TP1)</span><span className="ee-val up">{fmt(ee.suggested_tp1, cat)}</span></div>}
                </div>
              </>
            )}

            {/* ── Multi-TF Consensus ─────────────────────── */}
            <div className="sec">ĐỒNG THUẬN ĐA KHUNG</div>
            {cons.direction && (
              <div className="consensus">
                <span className="dir" style={{ color: DIRC[cons.direction] }}>{cons.direction}</span>
                <span className="sep">│</span> Mạnh {Math.round((cons.strength || 0) * 100)}%
                <span className="sep">│</span> Đồng thuận {cons.aligned}/{cons.total}
                {(cons.active_breakouts || []).map(b => (
                  <span className="brk" key={b.tf}>⚡ {b.tf} {b.type} @ {fmt(b.level, cat)}</span>
                ))}
              </div>
            )}

            {/* ── Per-TF Plans ───────────────────────────── */}
            <div className="sec">KẾ HOẠCH TỪNG KHUNG</div>
            <div className="cards">
              {plans.map(p => {
                const c = DIRC[p.direction] || 'var(--muted)'
                return (
                  <div className="card" key={p.tf} style={{ borderTopColor: c }}>
                    <h4>
                      <span>{p.tf}</span>
                      <span style={{ color: c }}>{p.direction} {Math.round(p.confidence * 100)}%</span>
                    </h4>
                    <div className="sig">{p.score >= 0 ? '+' : ''}{p.score} · {p.bars} nến {p.last_close != null ? `· ${fmt(p.last_close, cat)}` : ''}</div>
                    <div className="sig">{p.reasons.join(' · ') || '—'}</div>
                    <div className="sr">S {p.support != null ? fmt(p.support, cat) : '—'} │ R {p.resistance != null ? fmt(p.resistance, cat) : '—'}</div>
                    {p.entry && (
                      <div className="card-plan">
                        <div className="card-plan-row"><span className="cpl entry-c">Vào</span><span>{fmt(p.entry, cat)}</span></div>
                        {p.stop_loss && <div className="card-plan-row"><span className="cpl sl-c">SL</span><span>{fmt(p.stop_loss, cat)}</span></div>}
                        {p.take_profit_1 && <div className="card-plan-row"><span className="cpl tp-c">TP1</span><span>{fmt(p.take_profit_1, cat)}</span></div>}
                        {p.take_profit_2 && <div className="card-plan-row"><span className="cpl tp2-c">TP2</span><span>{fmt(p.take_profit_2, cat)}</span></div>}
                        {p.risk_reward && <div className="card-plan-row"><span className="cpl rr-c">R:R</span><span>{p.risk_reward}</span></div>}
                      </div>
                    )}
                    {p.breakout_type && <div className="brk">⚡ {p.breakout_type}: {p.breakout_detail}</div>}
                    <div className="action">→ {p.action}</div>
                  </div>
                )
              })}
            </div>

            {/* ── Action Plan ─────────────────────────────── */}
            <div className="sec">PHƯƠNG ÁN XỬ LÝ</div>
            <div className="action-box">
              <div style={{ marginBottom: 4 }}>
                Xu hướng <b style={{ color: DIRC[action.bias] || 'var(--muted)' }}>{action.bias}</b>
                <span className="sep"> · </span>
                Khung lớn {action.series?.HTF || '—'} / Khung giữa {action.series?.MID || '—'} / Khung ngắn {action.series?.STF || '—'}
              </div>
              {(action.steps || []).map((s, i) => <div className="s" key={i}>▸ {s}</div>)}
              {(action.confluence || []).map((s, i) => <div className="s con" key={i}>● {s}</div>)}
              {(action.conflicts || []).map((s, i) => <div className="s conf" key={i}>⚠ {s}</div>)}
            </div>
          </>
        )}

        {data && tab === 'trade' && (
          <>
            <div className="chart-box" ref={boxRef} style={{ visibility: loading ? 'hidden' : 'visible' }} />

            {/* ── Psychology Zone (compact) ───────────────── */}
            {psych && (
              <div className="psych-compact">
                <span className="psych-badge" style={{ background: ZONE_CLR[psych.zone] }}>
                  {psych.zone_info?.emoji} {psych.zone_info?.label_vi}
                </span>
                <span className="psych-phase-badge" style={{ borderColor: PHASE_CLR[psych.phase] }}>
                  {psych.phase_info?.label_vi}
                </span>
                <span className="psych-score">Điểm: {psych.score}/100</span>
              </div>
            )}

            {/* ── Entry / Exit (detailed) ─────────────────── */}
            {ee.last_price && (
              <>
                <div className="sec">KẾ HOẠCH GIAO DỊCH</div>
                <div className="trade-plan">
                  <div className="tp-row">
                    <div className="tp-label">Giá hiện tại</div>
                    <div className="tp-val">{fmt(ee.last_price, cat)}</div>
                  </div>
                  {ee.nearest_support && (
                    <div className="tp-row support-row">
                      <div className="tp-label">Hỗ trợ (S)</div>
                      <div className="tp-val up">{fmt(ee.nearest_support, cat)}</div>
                      <div className="tp-pct">{((ee.nearest_support - ee.last_price) / ee.last_price * 100).toFixed(2)}%</div>
                    </div>
                  )}
                  {ee.nearest_resistance && (
                    <div className="tp-row resistance-row">
                      <div className="tp-label">Kháng cự (R)</div>
                      <div className="tp-val down">{fmt(ee.nearest_resistance, cat)}</div>
                      <div className="tp-pct">{((ee.nearest_resistance - ee.last_price) / ee.last_price * 100).toFixed(2)}%</div>
                    </div>
                  )}
                  <div className="tp-divider" />
                  {ee.suggested_entry && (
                    <div className="tp-row entry-row">
                      <div className="tp-label">Vào lệnh</div>
                      <div className="tp-val" style={{ color: 'var(--primary)' }}>{fmt(ee.suggested_entry, cat)}</div>
                    </div>
                  )}
                  {ee.suggested_stop && (
                    <div className="tp-row stop-row">
                      <div className="tp-label">Cắt lỗ (SL)</div>
                      <div className="tp-val down">{fmt(ee.suggested_stop, cat)}</div>
                      <div className="tp-pct">{((ee.suggested_stop - ee.last_price) / ee.last_price * 100).toFixed(2)}%</div>
                    </div>
                  )}
                  {ee.suggested_tp1 && (
                    <div className="tp-row tp-row-1">
                      <div className="tp-label">Chốt lời (TP1)</div>
                      <div className="tp-val up">{fmt(ee.suggested_tp1, cat)}</div>
                      <div className="tp-pct">{((ee.suggested_tp1 - ee.last_price) / ee.last_price * 100).toFixed(2)}%</div>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* ── Darvas Box (compact) ────────────────────── */}
            {darvas && darvas.current_box && (
              <>
                <div className="sec">HỘP DARVAS</div>
                <div className="darvas-compact">
                  <div className="darvas-range">
                    <span>{fmt(darvas.current_box.bottom, cat)} — {fmt(darvas.current_box.top, cat)}</span>
                    {darvas.current_box.breakout && (
                      <span className={`brk ${darvas.current_box.breakout === 'UP' ? 'up' : 'down'}`}>
                        {darvas.current_box.breakout === 'UP' ? '▲ PHÁ VỠ LÊN' : '▼ PHÁ VỠ XUỐNG'}
                      </span>
                    )}
                  </div>
                  <div className="darvas-trend-compact">{darvas.trend_vi}</div>
                </div>
              </>
            )}

            {/* ── Action Plan (compact) ───────────────────── */}
            <div className="sec">PHƯƠNG ÁN</div>
            <div className="action-box">
              <div style={{ marginBottom: 4 }}>
                Xu hướng <b style={{ color: DIRC[action.bias] || 'var(--muted)' }}>{action.bias}</b>
                <span className="sep"> · </span>
                HTF {action.series?.HTF || '—'} / MID {action.series?.MID || '—'} / STF {action.series?.STF || '—'}
              </div>
              {(action.steps || []).map((s, i) => <div className="s" key={i}>▸ {s}</div>)}
              {(action.confluence || []).map((s, i) => <div className="s con" key={i}>● {s}</div>)}
              {(action.conflicts || []).map((s, i) => <div className="s conf" key={i}>⚠ {s}</div>)}
            </div>
          </>
        )}

        {data && tab === 'ai' && (
          <>
            <div className="chart-box" ref={boxRef} style={{ visibility: loading ? 'hidden' : 'visible' }} />

            {!aiData && !aiLoading && (
              <div className="ai-start">
                <div className="ai-icon">🤖</div>
                <div className="ai-desc">Phân tích nhanh từ RSI, MACD, EMA, Bollinger, Supertrend, tâm lý thị trường, Darvas, MTF consensus.</div>
                <button className="ai-btn" onClick={fetchAiAdvice}>Phân tích ngay</button>
              </div>
            )}

            {aiLoading && (
              <div className="ai-loading">
                <div className="ai-spinner" />
                <div>Đang phân tích…</div>
              </div>
            )}

            {aiData && aiData.advice && (
              <div className="ai-result">
                <div className="ai-strategy-header">
                  <div className={`ai-dir ai-dir-${(aiData.advice.direction || '').toLowerCase()}`}>
                    {aiData.advice.direction}
                  </div>
                  <div className="ai-conf">Confidence: {aiData.advice.confidence} ({aiData.advice.confidence_pct}%)</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>⏱ {aiData.elapsed_s}s</div>
                </div>

                {/* Score bar */}
                <div style={{ display: 'flex', gap: 4, marginBottom: 10, alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color: 'var(--up)', fontWeight: 700 }}>Bull {aiData.advice.bull_score}</span>
                  <div style={{ flex: 1, height: 8, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${Math.min(100, (aiData.advice.bull_score / (aiData.advice.bull_score + aiData.advice.bear_score + 1)) * 100)}%`, background: 'var(--up)', borderRadius: 4 }} />
                  </div>
                  <div style={{ flex: 1, height: 8, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${Math.min(100, (aiData.advice.bear_score / (aiData.advice.bull_score + aiData.advice.bear_score + 1)) * 100)}%`, background: 'var(--down)', borderRadius: 4, float: 'right' }} />
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--down)', fontWeight: 700 }}>Bear {aiData.advice.bear_score}</span>
                </div>

                {/* Entry / SL / TP */}
                {aiData.advice.entry && (
                  <div className="ai-grid">
                    <div className="ai-box ai-entry">
                      <div className="ai-box-label">VÀO LỆNH</div>
                      <div className="ai-box-val">{fmt(aiData.advice.entry, catOf(sym))}</div>
                    </div>
                    {aiData.advice.stop_loss && (
                      <div className="ai-box ai-sl">
                        <div className="ai-box-label">CẮT LỖ</div>
                        <div className="ai-box-val">{fmt(aiData.advice.stop_loss, catOf(sym))}</div>
                      </div>
                    )}
                    {aiData.advice.take_profit_1 && (
                      <div className="ai-box ai-tp">
                        <div className="ai-box-label">CHỐT LỜI 1</div>
                        <div className="ai-box-val">{fmt(aiData.advice.take_profit_1, catOf(sym))}</div>
                      </div>
                    )}
                    {aiData.advice.take_profit_2 && (
                      <div className="ai-box ai-tp2">
                        <div className="ai-box-label">CHỐT LỜI 2</div>
                        <div className="ai-box-val">{fmt(aiData.advice.take_profit_2, catOf(sym))}</div>
                      </div>
                    )}
                  </div>
                )}

                {/* Risk row */}
                <div className="ai-risk-row">
                  {aiData.advice.risk_reward && <span className="ai-risk-item">R:R {aiData.advice.risk_reward}</span>}
                  <span className="ai-risk-item">Risk: {aiData.advice.position_size}</span>
                  {aiData.advice.support && <span className="ai-risk-item">S: {fmt(aiData.advice.support, catOf(sym))}</span>}
                  {aiData.advice.resistance && <span className="ai-risk-item">R: {fmt(aiData.advice.resistance, catOf(sym))}</span>}
                </div>

                {/* Reasons */}
                {aiData.advice.reasons && aiData.advice.reasons.length > 0 && (
                  <div className="ai-reasoning">
                    <div className="ai-reasoning-title">Lý do:</div>
                    {aiData.advice.reasons.map((r, i) => <div key={i}>▸ {r}</div>)}
                  </div>
                )}

                {/* Warnings */}
                {aiData.advice.warnings && aiData.advice.warnings.length > 0 && (
                  <div className="ai-warnings">
                    {aiData.advice.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
                  </div>
                )}

                <button className="ai-btn ai-retry" onClick={fetchAiAdvice}>Phân tích lại</button>
              </div>
            )}
          </>
        )}

        {data && tab === 'backtest' && (
          <>
            <div className="chart-box" ref={boxRef} style={{ visibility: loading ? 'hidden' : 'visible' }} />

            {btData && btData.strategies ? (
              <>
                <div className="sec">THỬ NGHIỆM — {btData.bars_used} NẾN · {btData.interval}</div>
                <div className="bt-best">Chiến lược tốt nhất: <b>{btData.best_strategy}</b></div>
                <div className="bt-grid">
                  {btData.strategies.map(s => (
                    <div key={s.name} className={`bt-card ${s.is_best ? 'best' : ''}`}>
                      <h4>{s.name} {s.is_best && <span className="bt-crown">👑</span>}</h4>
                      <div className="bt-row"><span>Lợi nhuận</span><span className={s.total_return >= 0 ? 'up' : 'down'}>{s.total_return > 0 ? '+' : ''}{s.total_return}%</span></div>
                      <div className="bt-row"><span>Sharpe</span><span>{s.sharpe_ratio}</span></div>
                      <div className="bt-row"><span>Lỗ max</span><span className="down">{s.max_drawdown}%</span></div>
                      <div className="bt-row"><span>Tỷ lệ thắng</span><span>{s.win_rate}%</span></div>
                      <div className="bt-row"><span>Hệ số LN</span><span>{s.profit_factor}</span></div>
                      <div className="bt-row"><span>Giao dịch</span><span>{s.num_trades}</span></div>
                      <div className="bt-row"><span>Kỳ vọng</span><span className={s.expectancy >= 0 ? 'up' : 'down'}>{s.expectancy > 0 ? '+' : ''}{s.expectancy}%</span></div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="loading">Đang chạy thử nghiệm…</div>
            )}
          </>
        )}

        {!loading && !data && <div className="loading">Không lấy được phân tích cho mã này.</div>}
      </div>
    </>
  )
}
