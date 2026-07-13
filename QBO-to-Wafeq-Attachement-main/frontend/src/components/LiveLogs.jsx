import { useEffect, useRef, useState } from 'react'
import { useStore, PHASE_META } from '../lib/store'
import { Ic } from './ui'

export default function LiveLogs({ height = 'calc(100vh - 190px)' }) {
  const { logs, clearLogs, running } = useStore()
  const [filter, setFilter] = useState({ 1: true, 2: true, 3: true })
  const [autoScroll, setAutoScroll] = useState(true)
  const bodyRef = useRef(null)

  const visible = logs.filter((l) => filter[l.phase])

  useEffect(() => {
    if (autoScroll && bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [visible.length, autoScroll])

  const toggle = (f) => setFilter((s) => ({ ...s, [f]: !s[f] }))

  return (
    <div className="card log-card" style={{ height }}>
      <div className="log-h">
        <h3><Ic name="terminal-2" /> Live Logs</h3>
        <div className="log-filters">
          {[1, 2, 3].map((f) => (
            <button key={f} className={`lf f${f} ${filter[f] ? 'on' : ''}`} onClick={() => toggle(f)}>
              <span className="dot" />{PHASE_META[f].label[0] + PHASE_META[f].label.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
        <button className="icobtn" style={{ width: 28, height: 28, fontSize: 14 }} onClick={clearLogs} title="Clear logs">
          <Ic name="trash" />
        </button>
      </div>

      <div className="log-body" ref={bodyRef}>
        {visible.length === 0 ? (
          <div className="log-empty">
            <Ic name="clipboard-list" />
            <div><b>Logs will stream here</b><br />
              <span style={{ fontSize: 11 }}>All three phases shown together, color-coded.</span></div>
          </div>
        ) : (
          visible.map((l, i) => {
            const cls = l.type === 'err' ? 'err'
              : (l.type === 'ok' || l.type === 'success') ? 'ok'
              : l.type === 'warn' ? 'warn' : ''
            return (
              <div key={i} className={`log-line p${l.phase} ${cls}`}>
                <span className="lt">{l.t}</span>
                <span className="lb">{PHASE_META[l.phase].short}</span>
                <span className="lm">{l.msg}</span>
              </div>
            )
          })
        )}
      </div>

      <div className="log-foot">
        {running && <span className="livedot" />}
        <span>{running ? 'Streaming…' : 'Ready'}</span>
        <div className="spacer" />
        <label style={{ display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer', fontSize: 11 }}>
          <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)}
            style={{ accentColor: 'var(--accent)' }} /> Auto-scroll
        </label>
        <span className="mono">{logs.length} lines</span>
      </div>
    </div>
  )
}
