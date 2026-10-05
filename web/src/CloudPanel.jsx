import React, { useEffect, useState } from 'react'

export default function CloudPanel({ onSelectSymbol }) {
  const [cloudData, setCloudData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastFetch, setLastFetch] = useState(null)

  const fetchCloudData = () => {
    setLoading(true)
    fetch('/api/cloud-data')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(d => {
        setCloudData(d.data)
        setLastFetch(d.last_fetch)
        setError(null)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchCloudData()
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchCloudData, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  const refresh = () => {
    fetch('/api/cloud-data/refresh', { method: 'POST' })
      .then(() => setTimeout(fetchCloudData, 2000))
  }

  const formatAge = (ts) => {
    if (!ts) return '—'
    const age = Math.floor((Date.now() / 1000) - ts)
    if (age < 60) return `${age}s trước`
    if (age < 3600) return `${Math.floor(age / 60)} phút trước`
    if (age < 86400) return `${Math.floor(age / 3600)} giờ trước`
    return `${Math.floor(age / 86400)} ngày trước`
  }

  return (
    <div style={{
      background: 'rgba(22, 27, 34, 0.95)',
      border: '1px solid #30363d',
      borderRadius: 12,
      padding: 16,
      margin: '12px 0',
      backdropFilter: 'blur(10px)',
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 12,
      }}>
        <div style={{
          fontSize: 16,
          fontWeight: 600,
          color: '#58a6ff',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          ☁️ Cloud Analysis (GitHub Actions)
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#8b949e' }}>
            {lastFetch ? formatAge(lastFetch) : 'Chưa có data'}
          </span>
          <button
            onClick={refresh}
            style={{
              background: '#238636',
              color: '#fff',
              border: 'none',
              padding: '6px 12px',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: 12,
            }}
          >
            🔄 Refresh
          </button>
        </div>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 24, color: '#8b949e' }}>
          Đang tải cloud data...
        </div>
      )}

      {error && (
        <div style={{
          textAlign: 'center',
          padding: 24,
          color: '#f85149',
          fontSize: 13,
        }}>
          Lỗi: {error}
          <br />
          <span style={{ color: '#8b949e', fontSize: 12 }}>
            Chạy GitHub Actions trước hoặc kiểm tra server
          </span>
        </div>
      )}

      {cloudData && !loading && (
        <div style={{ display: 'grid', gap: 8 }}>
          {cloudData.symbols?.map((sym, i) => (
            <CloudSymbolCard
              key={i}
              sym={sym}
              onClick={() => onSelectSymbol?.(sym.symbol, sym.name)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function CloudSymbolCard({ sym, onClick }) {
  const ohlcv = sym.ohlcv
  if (!ohlcv || !ohlcv.close?.length) return null

  const lastClose = ohlcv.close[ohlcv.close.length - 1]
  const prevClose = ohlcv.close[ohlcv.close.length - 2] || lastClose
  const change = ((lastClose - prevClose) / prevClose * 100)
  const isUp = change >= 0

  // Extract key metrics from analysis text
  const text = sym.analysis_text || ''
  const rsiMatch = text.match(/RSI[:\s*]+([\d.]+)/i)
  const macdMatch = text.match(/MACD[:\s*]+(\w+)/i)
  const trendMatch = text.match(/Xu hướng[:\s*]+(\w+)/i)

  return (
    <div
      onClick={onClick}
      style={{
        background: '#21262d',
        border: '1px solid #30363d',
        borderRadius: 8,
        padding: '10px 14px',
        cursor: 'pointer',
        transition: 'border-color 0.2s',
      }}
      onMouseEnter={e => e.target.style.borderColor = '#58a6ff'}
      onMouseLeave={e => e.target.style.borderColor = '#30363d'}
    >
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 6,
      }}>
        <div style={{ fontWeight: 600, color: '#f0f6fc' }}>{sym.name}</div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ color: '#f0f6fc', fontSize: 14 }}>
            {lastClose.toLocaleString('en-US', {
              minimumFractionDigits: lastClose >= 1000 ? 2 : 4,
              maximumFractionDigits: lastClose >= 1000 ? 2 : 4,
            })}
          </span>
          <span style={{
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: 12,
            background: isUp ? '#1b4332' : '#5c1a1a',
            color: isUp ? '#95d5b2' : '#f4a261',
          }}>
            {isUp ? '+' : ''}{change.toFixed(2)}%
          </span>
        </div>
      </div>

      <div style={{
        display: 'flex',
        gap: 16,
        fontSize: 12,
        color: '#8b949e',
        flexWrap: 'wrap',
      }}>
        {rsiMatch && <span>RSI: <b style={{ color: '#f0f6fc' }}>{rsiMatch[1]}</b></span>}
        {macdMatch && <span>MACD: <b style={{ color: '#f0f6fc' }}>{macdMatch[1]}</b></span>}
        {trendMatch && <span>Trend: <b style={{ color: '#f0f6fc' }}>{trendMatch[1]}</b></span>}
      </div>
    </div>
  )
}
