import React, { useState, useEffect, useRef, useCallback } from 'react'

const ICONS = {
  BULLISH: '🟢', BEARISH: '🔴', NEUTRAL: '🟡',
}
const TYPE_LABEL = { reversal: 'ĐẢO CHIỀU', entry: 'VÀO LỆNH' }

export default function AlertPanel({ onSelectSymbol }) {
  const [alerts, setAlerts] = useState([])
  const [total, setTotal] = useState(0)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('all')
  const [interval, setInterval_] = useState('1H')
  const timerRef = useRef(null)
  const prevCountRef = useRef(0)
  const [newCount, setNewCount] = useState(0)

  const [showTg, setShowTg] = useState(false)
  const [sigBot, setSigBot] = useState({ enabled: false, has_token: false, chat_id: '', min_strength: 0.7, send_interval: 600, plan_enabled: true, plan_interval: 1800, chart_enabled: true, chart_interval: 600, chart_symbols: [] })
  const [pfBot, setPfBot] = useState({ enabled: false, has_token: false, chat_id: '', symbols: ['OANDA:XAUUSD'], timeframes: ['5m','15m','30m','1H'], interval: 300 })
  const [newsBot, setNewsBot] = useState({ enabled: false, has_token: false, chat_id: '', keywords: ['XAUUSD','GOLD','DXY','USD','WTI','OIL','FED'], interval: 600, max_news: 5 })
  const [sigToken, setSigToken] = useState('')
  const [pfToken, setPfToken] = useState('')
  const [newsToken, setNewsToken] = useState('')
  const [tgStatus, setTgStatus] = useState('')
  const [sigSymbols, setSigSymbols] = useState('')
  const [pfSymbols, setPfSymbols] = useState('OANDA:XAUUSD')
  const [pfTFs, setPfTFs] = useState('5m,15m,30m,1H')
  const [newsKeywords, setNewsKeywords] = useState('XAUUSD,GOLD,DXY,USD,WTI,OIL,FED')

  const fetchAlerts = useCallback(() => {
    setLoading(true)
    fetch(`/api/alerts?interval=${interval}&limit=80`)
      .then(r => r.json())
      .then(d => {
        const a = d.alerts || []
        setAlerts(a)
        setTotal(d.total || 0)
        if (a.length > prevCountRef.current) {
          setNewCount(c => c + (a.length - prevCountRef.current))
        }
        prevCountRef.current = a.length
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [interval])

  const fetchTgConfig = () => {
    fetch('/api/telegram/config').then(r => r.json()).then(d => {
      const sb = d.signal_bot || {}
      const pfb = d.price_feed_bot || {}
      const nb = d.market_news_bot || {}
      setSigBot(sb)
      setPfBot(pfb)
      setNewsBot(nb)
      setSigSymbols((sb.chart_symbols || []).join(', '))
      setPfSymbols((pfb.symbols || []).join(', '))
      setPfTFs((pfb.timeframes || []).join(', '))
      setNewsKeywords((nb.keywords || []).join(', '))
    }).catch(() => {})
  }

  useEffect(() => {
    fetchAlerts()
    timerRef.current = setInterval(fetchAlerts, 30000)
    return () => clearInterval(timerRef.current)
  }, [fetchAlerts])

  useEffect(() => {
    if (open) {
      setNewCount(0)
      fetchTgConfig()
    }
  }, [open])

  const filtered = alerts.filter(a => {
    if (filter === 'bullish') return a.direction === 'BULLISH'
    if (filter === 'bearish') return a.direction === 'BEARISH'
    if (filter === 'reversal') return a.type === 'reversal'
    if (filter === 'entry') return a.type === 'entry'
    return true
  })

  const strengthBar = (s) => {
    const pct = Math.round((s || 0) * 100)
    const color = pct >= 80 ? '#1b8a5a' : pct >= 60 ? '#ef6c00' : '#78909c'
    return (
      <div className="alert-str-bar">
        <div className="alert-str-fill" style={{ width: `${pct}%`, background: color }} />
        <span className="alert-str-pct">{pct}%</span>
      </div>
    )
  }

  const saveSigBot = () => {
    setTgStatus('Đang lưu signal bot...')
    const params = new URLSearchParams()
    if (sigToken) params.set('bot_token', sigToken)
    params.set('chat_id', sigBot.chat_id || '')
    params.set('enabled', sigBot.enabled)
    params.set('min_strength', sigBot.min_strength)
    params.set('send_interval', sigBot.send_interval)
    params.set('plan_enabled', sigBot.plan_enabled)
    params.set('plan_interval', sigBot.plan_interval)
    params.set('chart_enabled', sigBot.chart_enabled)
    params.set('chart_interval', sigBot.chart_interval)
    params.set('chart_symbols', sigSymbols)
    fetch(`/api/telegram/signal-bot?${params}`, { method: 'POST' })
      .then(r => r.json())
      .then(d => { setSigBot(d); setSigToken(''); setTgStatus('✅ Signal bot đã lưu'); setTimeout(() => setTgStatus(''), 2000) })
      .catch(() => setTgStatus('❌ Lỗi lưu signal bot'))
  }

  const savePfBot = () => {
    setTgStatus('Đang lưu price feed bot...')
    const params = new URLSearchParams()
    if (pfToken) params.set('bot_token', pfToken)
    params.set('chat_id', pfBot.chat_id || '')
    params.set('enabled', pfBot.enabled)
    params.set('symbols', pfSymbols)
    params.set('timeframes', pfTFs)
    params.set('interval', pfBot.interval)
    fetch(`/api/telegram/price-feed-bot?${params}`, { method: 'POST' })
      .then(r => r.json())
      .then(d => { setPfBot(d.price_feed_bot || d); setPfToken(''); setTgStatus('✅ Price feed bot đã lưu'); setTimeout(() => setTgStatus(''), 2000) })
      .catch(() => setTgStatus('❌ Lỗi lưu price feed bot'))
  }

  const saveNewsBot = () => {
    setTgStatus('Đang lưu news bot...')
    const params = new URLSearchParams()
    if (newsToken) params.set('bot_token', newsToken)
    params.set('chat_id', newsBot.chat_id || '')
    params.set('enabled', newsBot.enabled)
    params.set('keywords', newsKeywords)
    params.set('interval', newsBot.interval)
    params.set('max_news', newsBot.max_news)
    fetch(`/api/telegram/market-news-bot?${params}`, { method: 'POST' })
      .then(r => r.json())
      .then(d => { setNewsBot(d.market_news_bot || d); setNewsToken(''); setTgStatus('✅ News bot đã lưu'); setTimeout(() => setTgStatus(''), 2000) })
      .catch(() => setTgStatus('❌ Lỗi lưu news bot'))
  }

  const testBot = (target) => {
    setTgStatus(`Đang gửi test ${target}...`)
    fetch(`/api/telegram/test?target=${target}`, { method: 'POST' })
      .then(r => r.json())
      .then(d => { setTgStatus(d.ok ? `✅ ${target}: ${d.message || 'Gửi thành công!'}` : `❌ ${target}: ${d.error}`) })
      .catch(() => setTgStatus(`❌ ${target}: Lỗi kết nối`))
  }

  const sendNow = () => {
    setTgStatus('Đang gửi tín hiệu...')
    fetch(`/api/telegram/send?interval=${interval}`, { method: 'POST' })
      .then(r => r.json())
      .then(d => { setTgStatus(d.ok ? `✅ ${d.message}` : `❌ ${d.error}`) })
      .catch(() => setTgStatus('❌ Lỗi'))
  }

  const sendPlansNow = () => {
    setTgStatus('Đang gửi plans...')
    fetch(`/api/telegram/send-plans?interval=${interval}`, { method: 'POST' })
      .then(r => r.json())
      .then(d => { setTgStatus(d.ok ? `✅ ${d.message}` : `❌ ${d.error}`) })
      .catch(() => setTgStatus('❌ Lỗi'))
  }

  const sendChartsNow = () => {
    setTgStatus('Đang gửi biểu đồ...')
    fetch('/api/telegram/send-charts', { method: 'POST' })
      .then(r => r.json())
      .then(d => { setTgStatus(d.ok ? `✅ ${d.message}` : `❌ ${d.error}`) })
      .catch(() => setTgStatus('❌ Lỗi'))
  }

  const sendPfNow = () => {
    setTgStatus('Đang gửi price feed...')
    fetch('/api/telegram/send-price-feed', { method: 'POST' })
      .then(r => r.json())
      .then(d => { setTgStatus(d.ok ? `✅ ${d.message}` : `❌ ${d.error}`) })
      .catch(() => setTgStatus('❌ Lỗi'))
  }

  const sendNewsNow = () => {
    setTgStatus('Đang gửi tin tức...')
    fetch('/api/telegram/send-news', { method: 'POST' })
      .then(r => r.json())
      .then(d => { setTgStatus(d.ok ? `✅ ${d.message}` : `❌ ${d.error}`) })
      .catch(() => setTgStatus('❌ Lỗi'))
  }

  return (
    <>
      <button className="alert-fab" onClick={() => setOpen(o => !o)} title="Tín hiệu giao dịch">
        <span className="alert-fab-icon">🔔</span>
        {newCount > 0 && !open && <span className="alert-badge">{newCount}</span>}
        {total > 0 && <span className="alert-fab-count">{total}</span>}
      </button>

      {open && (
        <div className="alert-panel">
          <div className="alert-header">
            <span className="alert-title">🔔 TÍN HIỆU GIAO DỊCH</span>
            <div style={{ display: 'flex', gap: 4 }}>
              <button className={`alert-tab-btn ${!showTg ? 'active' : ''}`} onClick={() => setShowTg(false)}>📡 Tín hiệu</button>
              <button className={`alert-tab-btn ${showTg ? 'active' : ''}`} onClick={() => setShowTg(true)}>✈️ Telegram</button>
            </div>
            <button className="alert-close" onClick={() => setOpen(false)}>✕</button>
          </div>

          {!showTg ? (
            <>
              <div className="alert-toolbar">
                <select className="alert-select" value={interval} onChange={e => setInterval_(e.target.value)}>
                  <option value="5m">5 phút</option>
                  <option value="15m">15 phút</option>
                  <option value="30m">30 phút</option>
                  <option value="1H">1 giờ</option>
                  <option value="4H">4 giờ</option>
                  <option value="1D">1 ngày</option>
                </select>
                <div className="alert-filters">
                  {['all', 'bullish', 'bearish', 'reversal', 'entry'].map(f => (
                    <button key={f} className={`alert-filter-btn ${filter === f ? 'active' : ''}`}
                      onClick={() => setFilter(f)}>
                      {f === 'all' ? 'Tất cả' : f === 'bullish' ? '🟢 Tăng' : f === 'bearish' ? '🔴 Giảm' : f === 'reversal' ? '↩ Đảo chiều' : '🎯 Vào lệnh'}
                    </button>
                  ))}
                </div>
                <button className="alert-refresh" onClick={fetchAlerts} disabled={loading}>
                  {loading ? '⏳' : '🔄'}
                </button>
              </div>

              <div className="alert-list">
                {filtered.length === 0 && (
                  <div className="alert-empty">{loading ? 'Đang quét...' : 'Không có tín hiệu phù hợp'}</div>
                )}
                {filtered.map((a, i) => (
                  <div key={i} className={`alert-card alert-${a.direction.toLowerCase()}`}
                    onClick={() => onSelectSymbol && onSelectSymbol(a.symbol)}>
                    <div className="alert-card-top">
                      <span className="alert-icon">{ICONS[a.direction] || '⚪'}</span>
                      <span className="alert-sym">{a.symbol}</span>
                      <span className="alert-type-badge">{TYPE_LABEL[a.type] || a.type}</span>
                      {strengthBar(a.strength)}
                    </div>
                    <div className="alert-card-mid">
                      <span className="alert-pattern">{a.pattern}</span>
                      {a.price > 0 && <span className="alert-price">{a.price.toLocaleString('en-US', { maximumFractionDigits: 2 })}</span>}
                    </div>
                    <div className="alert-desc">{a.desc}</div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="tg-settings">
              <div className="tg-divider" style={{ background: '#1a5276', color: '#5dade2' }}>📡 BOT 1 — TÍN HIỆU GIAO DỊCH</div>
              <div className="tg-row">
                <label className="tg-label">Bot Token</label>
                <input className="tg-input" type="password" placeholder="123456:ABC-DEF..."
                  value={sigToken} onChange={e => setSigToken(e.target.value)} />
                {sigBot.has_token && <span className="tg-hint">✅ Token: {sigBot.bot_token_masked}</span>}
              </div>
              <div className="tg-row">
                <label className="tg-label">Chat ID</label>
                <input className="tg-input" type="text" placeholder="-1001234567890 hoặc 123456789"
                  value={sigBot.chat_id || ''} onChange={e => setSigBot({ ...sigBot, chat_id: e.target.value })} />
              </div>
              <div className="tg-row">
                <label className="tg-label">Bật/Tắt</label>
                <label className="tg-toggle">
                  <input type="checkbox" checked={sigBot.enabled}
                    onChange={e => setSigBot({ ...sigBot, enabled: e.target.checked })} />
                  <span className="tg-toggle-slider" />
                </label>
                <span className="tg-hint">{sigBot.enabled ? 'Đang bật' : 'Đang tắt'}</span>
              </div>
              <div className="tg-row">
                <label className="tg-label">Min Strength</label>
                <input className="tg-input-sm" type="number" min="0.3" max="1" step="0.05"
                  value={sigBot.min_strength || 0.7}
                  onChange={e => setSigBot({ ...sigBot, min_strength: parseFloat(e.target.value) || 0.7 })} />
                <span className="tg-hint">({Math.round((sigBot.min_strength || 0.7) * 100)}%)</span>
              </div>
              <div className="tg-row">
                <label className="tg-label">Signal interval</label>
                <input className="tg-input-sm" type="number" min="30" max="3600" step="30"
                  value={sigBot.send_interval || 600}
                  onChange={e => setSigBot({ ...sigBot, send_interval: parseInt(e.target.value) || 600 })} />
                <span className="tg-hint">({Math.round((sigBot.send_interval || 600) / 60)} phút)</span>
              </div>
              <div className="tg-row">
                <label className="tg-label">Gửi Plan</label>
                <label className="tg-toggle">
                  <input type="checkbox" checked={sigBot.plan_enabled}
                    onChange={e => setSigBot({ ...sigBot, plan_enabled: e.target.checked })} />
                  <span className="tg-toggle-slider" />
                </label>
              </div>
              <div className="tg-row">
                <label className="tg-label">Plan interval</label>
                <input className="tg-input-sm" type="number" min="60" max="7200" step="60"
                  value={sigBot.plan_interval || 1800}
                  onChange={e => setSigBot({ ...sigBot, plan_interval: parseInt(e.target.value) || 1800 })} />
                <span className="tg-hint">({Math.round((sigBot.plan_interval || 1800) / 60)} phút)</span>
              </div>
              <div className="tg-row">
                <label className="tg-label">Gửi Chart</label>
                <label className="tg-toggle">
                  <input type="checkbox" checked={sigBot.chart_enabled}
                    onChange={e => setSigBot({ ...sigBot, chart_enabled: e.target.checked })} />
                  <span className="tg-toggle-slider" />
                </label>
              </div>
              <div className="tg-row">
                <label className="tg-label">Chart interval</label>
                <input className="tg-input-sm" type="number" min="60" max="7200" step="60"
                  value={sigBot.chart_interval || 600}
                  onChange={e => setSigBot({ ...sigBot, chart_interval: parseInt(e.target.value) || 600 })} />
                <span className="tg-hint">({Math.round((sigBot.chart_interval || 600) / 60)} phút)</span>
              </div>
              <div className="tg-row-col">
                <label className="tg-label">Mã ưu tiên (phân tách dấu phẩy)</label>
                <textarea className="tg-textarea" rows={2}
                  value={sigSymbols}
                  onChange={e => setSigSymbols(e.target.value)}
                  placeholder="BINANCE:BTCUSDT, OANDA:XAUUSD, NYMEX:CL1!, BINANCE:ETHUSDT" />
              </div>
              <div className="tg-actions">
                <button className="tg-btn tg-btn-save" onClick={saveSigBot}>💾 Lưu Bot 1</button>
                <button className="tg-btn tg-btn-test" onClick={() => testBot('signal')}>📨 Test</button>
                <button className="tg-btn tg-btn-send" onClick={sendNow}>🚀 Signal</button>
                <button className="tg-btn tg-btn-send" onClick={sendPlansNow}>📋 Plan</button>
                <button className="tg-btn tg-btn-chart" onClick={sendChartsNow}>📊 Chart</button>
              </div>

              <div className="tg-divider" style={{ background: '#1e3a5f', color: '#5dade2' }}>💰 BOT 2 — CẢNH BÁO GIÁ</div>
              <div className="tg-row">
                <label className="tg-label">Bot Token</label>
                <input className="tg-input" type="password" placeholder="123456:ABC-DEF..."
                  value={pfToken} onChange={e => setPfToken(e.target.value)} />
                {pfBot.has_token && <span className="tg-hint">✅ Token: {pfBot.bot_token_masked}</span>}
              </div>
              <div className="tg-row">
                <label className="tg-label">Chat ID</label>
                <input className="tg-input" type="text" placeholder="-1001234567890 hoặc 123456789"
                  value={pfBot.chat_id || ''} onChange={e => setPfBot({ ...pfBot, chat_id: e.target.value })} />
              </div>
              <div className="tg-row">
                <label className="tg-label">Bật/Tắt</label>
                <label className="tg-toggle">
                  <input type="checkbox" checked={pfBot.enabled}
                    onChange={e => setPfBot({ ...pfBot, enabled: e.target.checked })} />
                  <span className="tg-toggle-slider" />
                </label>
                <span className="tg-hint">{pfBot.enabled ? 'Đang bật' : 'Đang tắt'}</span>
              </div>
              <div className="tg-row">
                <label className="tg-label">Interval (giây)</label>
                <input className="tg-input-sm" type="number" min="30" max="3600" step="30"
                  value={pfBot.interval || 300}
                  onChange={e => setPfBot({ ...pfBot, interval: parseInt(e.target.value) || 300 })} />
                <span className="tg-hint">({Math.round((pfBot.interval || 300) / 60)} phút)</span>
              </div>
              <div className="tg-row-col">
                <label className="tg-label">Symbols (phân tách dấu phẩy)</label>
                <textarea className="tg-textarea" rows={2}
                  value={pfSymbols}
                  onChange={e => setPfSymbols(e.target.value)}
                  placeholder="OANDA:XAUUSD, BINANCE:BTCUSDT, NYMEX:CL1!" />
              </div>
              <div className="tg-row-col">
                <label className="tg-label">Timeframes</label>
                <input className="tg-input" type="text"
                  value={pfTFs}
                  onChange={e => setPfTFs(e.target.value)}
                  placeholder="5m,15m,30m,1H" />
              </div>
              <div className="tg-actions">
                <button className="tg-btn tg-btn-save" onClick={savePfBot}>💾 Lưu Bot 2</button>
                <button className="tg-btn tg-btn-test" onClick={() => testBot('price_feed')}>📨 Test</button>
                <button className="tg-btn tg-btn-chart" onClick={sendPfNow}>💰 Gửi ngay</button>
              </div>

              <div className="tg-divider" style={{ background: '#1a3a2a', color: '#5dade2' }}>📰 BOT 3 — TIN TỨC THỊ TRƯỜNG</div>
              <div className="tg-row">
                <label className="tg-label">Bot Token</label>
                <input className="tg-input" type="password" placeholder="123456:ABC-DEF..."
                  value={newsToken} onChange={e => setNewsToken(e.target.value)} />
                {newsBot.has_token && <span className="tg-hint">✅ Token: {newsBot.bot_token_masked}</span>}
              </div>
              <div className="tg-row">
                <label className="tg-label">Chat ID</label>
                <input className="tg-input" type="text" placeholder="-1001234567890 hoặc 123456789"
                  value={newsBot.chat_id || ''} onChange={e => setNewsBot({ ...newsBot, chat_id: e.target.value })} />
              </div>
              <div className="tg-row">
                <label className="tg-label">Bật/Tắt</label>
                <label className="tg-toggle">
                  <input type="checkbox" checked={newsBot.enabled}
                    onChange={e => setNewsBot({ ...newsBot, enabled: e.target.checked })} />
                  <span className="tg-toggle-slider" />
                </label>
                <span className="tg-hint">{newsBot.enabled ? 'Đang bật' : 'Đang tắt'}</span>
              </div>
              <div className="tg-row">
                <label className="tg-label">Interval (giây)</label>
                <input className="tg-input-sm" type="number" min="60" max="7200" step="60"
                  value={newsBot.interval || 600}
                  onChange={e => setNewsBot({ ...newsBot, interval: parseInt(e.target.value) || 600 })} />
                <span className="tg-hint">({Math.round((newsBot.interval || 600) / 60)} phút)</span>
              </div>
              <div className="tg-row">
                <label className="tg-label">Số tin tối đa</label>
                <input className="tg-input-sm" type="number" min="1" max="20"
                  value={newsBot.max_news || 5}
                  onChange={e => setNewsBot({ ...newsBot, max_news: parseInt(e.target.value) || 5 })} />
              </div>
              <div className="tg-row-col">
                <label className="tg-label">Keywords lọc tin (phân tách dấu phẩy)</label>
                <textarea className="tg-textarea" rows={2}
                  value={newsKeywords}
                  onChange={e => setNewsKeywords(e.target.value)}
                  placeholder="XAUUSD, GOLD, DXY, USD, WTI, OIL, FED, CPI, NFP" />
                <span className="tg-hint">Chỉ gửi tin chứa keyword này. VD: XAUUSD, GOLD, DXY, USD, WTI</span>
              </div>
              <div className="tg-actions">
                <button className="tg-btn tg-btn-save" onClick={saveNewsBot}>💾 Lưu Bot 3</button>
                <button className="tg-btn tg-btn-test" onClick={() => testBot('news')}>📨 Test</button>
                <button className="tg-btn tg-btn-send" onClick={sendNewsNow}>📰 Gửi ngay</button>
              </div>

              {tgStatus && <div className="tg-status">{tgStatus}</div>}
              <div className="tg-help">
                <p><strong>Hướng dẫn:</strong></p>
                <ol>
                  <li>Tạo bot với <a href="https://t.me/BotFather" target="_blank" rel="noreferrer">@BotFather</a> → copy token</li>
                  <li>Thêm bot vào group/channel cần nhận thông báo</li>
                  <li>Lấy Chat ID: gửi tin nhắn trong group → mở <code>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code></li>
                  <li>Bot 1: tín hiệu + plan + chart. Bot 2: giá + chart định kỳ.</li>
                </ol>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}
