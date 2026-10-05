import React from 'react'

function Tile({ q, sym, name, cat, fmt, onSelect }) {
  const price = q ? q.price : null
  const chg = q ? q.chg : null
  const cls = price ? (chg > 0.03 ? 'up' : chg < -0.03 ? 'down' : 'flat') : 'flat'
  const arrow = price ? (chg > 0.03 ? '▲' : chg < -0.03 ? '▼' : '') : ''
  const flash = q && q.ts ? (
    chg > 0.03 ? 'flash-up' : chg < -0.03 ? 'flash-down' : ''
  ) : ''
  return (
    <div className="tile" onClick={() => onSelect({ sym, name })}>
      <div className="nm"><span>{name}</span><span className="sy">{sym.split(':')[1]}</span></div>
      <div className="px" key={q ? q.ts : ''}>{price !== null && price !== undefined ? fmt(price, cat) : '—'}</div>
      <div className={`chg ${cls} ${flash}`}>{q ? `${arrow} ${chg > 0 ? '+' : ''}${chg}%` : ''}</div>
    </div>
  )
}

export default function Board({ groups, quotes, fmt, focus, onSelect }) {
  return (
    <>
      {groups.map(g => {
        const shown = focus ? g.items.filter(i => g.focus.includes(i.sym)) : g.items
        if (!shown.length) return null
        return (
          <section className="group" key={g.id}>
            <div className="group-head">
              <span>{g.icon}</span> {g.label}
              <span className="cat">{shown.filter(i => quotes[i.sym]).length}/{shown.length} ● {focus ? 'tập trung' : 'tất cả'}</span>
            </div>
            <div className="tiles">
              {shown.map(it => (
                <Tile key={it.sym} q={quotes[it.sym] || null} sym={it.sym} name={it.name} cat={g.id} fmt={fmt} onSelect={onSelect} />
              ))}
            </div>
          </section>
        )
      })}
    </>
  )
}