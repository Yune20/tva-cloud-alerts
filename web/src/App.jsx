import React, { useEffect, useRef, useState } from 'react'
import Board from './Board.jsx'
import SymbolView from './SymbolView.jsx'
import AlertPanel from './AlertPanel.jsx'

export const fmt = (v, cat) => {
  if (v === null || v === undefined) return '—'
  const d = cat === 'forex' ? 4 : cat === 'crypto' ? (v >= 1000 ? 1 : 2) : 2
  return v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
}

export default function App() {
  const [groups, setGroups] = useState(null)
  const [quotes, setQuotes] = useState({})
  const [wsOn, setWsOn] = useState(false)
  const [focus, setFocus] = useState(true)
  const [sel, setSel] = useState(null)
  const [lastTick, setLastTick] = useState(0)
  const [serverOk, setServerOk] = useState(true)
  const [restarting, setRestarting] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    fetch('/api/watchlist').then(r => r.json()).then(d => setGroups(d.groups)).catch(() => {})
  }, [])

  useEffect(() => {
    let closed = false
    function connect() {
      if (closed || wsRef.current) return
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws/quotes`)
      wsRef.current = ws
      ws.onopen = () => setWsOn(true)
      ws.onclose = () => { wsRef.current = null; setWsOn(false); if (!closed) setTimeout(connect, 1500) }
      ws.onerror = () => { try { ws.close() } catch (e) {} }
      ws.onmessage = (ev) => {
        try {
          const m = JSON.parse(ev.data)
          const map = {}
          for (const q of m.quotes) map[q.sym] = q
          setQuotes(map)
          setLastTick(m.time * 1000)
        } catch (e) {}
      }
    }
    connect()
    return () => { closed = true; try { wsRef.current?.close() } catch (e) {} }
  }, [])

  const quoteFor = (sym) => quotes[sym] || null
  const catOf = (sym) => { if (!groups) return ''; for (const g of groups) if (g.items.some(i => i.sym === sym)) return g.id; return '' }

  const restartServer = () => {
    setRestarting(true)
    fetch('/api/restart', { method: 'POST' })
      .then(r => r.json())
      .then(d => { setRestarting(false); setServerOk(true) })
      .catch(() => { setRestarting(false); setServerOk(false) })
  }

  return (
    <>
      <div className="header">
        <div className="logo">⚡ BẢNG GIÁ <span>REALTIME</span></div>
        <div className="status">
          <span className={`dot ${wsOn ? 'on' : ''}`} />
          {wsOn ? 'LIVE' : 'KẾT NỐI...'}
        </div>
        <div className="stretch" />
        <div className="tick">{lastTick ? new Date(lastTick).toLocaleTimeString('vi-VN') : '--:--:--'}</div>
        <button className="btn" onClick={restartServer} disabled={restarting} style={{ marginRight: 6 }}>
          {restarting ? '⏳ Đang khởi động...' : '🔄 Khởi động lại Server'}
        </button>
        <button className="btn" onClick={() => setFocus(f => !f)}>
          {focus ? 'HIỂN THỊ TẤT CẢ' : 'CHẾ ĐỘ FOCUS'}
        </button>
      </div>
      <div className="legend">
        <b className="up">▲ tăng</b> <b className="down">▼ giảm</b>
        <span>· bấm một mã để xem nến + phân tích MTF + plan từng khung</span>
      </div>
      {groups && (
        <Board groups={groups} quotes={quotes} fmt={fmt} focus={focus} onSelect={setSel} />
      )}
      {sel && <SymbolView sym={sel.sym} name={sel.name} fmt={fmt} catOf={catOf} quote={quoteFor(sel.sym)} onClose={() => setSel(null)} />}
      <AlertPanel onSelectSymbol={(sym) => {
        if (groups) {
          for (const g of groups) {
            const item = g.items.find(i => i.sym === sym)
            if (item) { setSel(item); return }
          }
        }
      }} />
    </>
  )
}