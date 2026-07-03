import { useEffect, useState, useCallback, useMemo } from 'react'
import { useStore } from '../lib/store'
import { api } from '../lib/api'
import { Ic } from '../components/ui'
import LiveLogs from '../components/LiveLogs'
import EntityTypeSelector from '../components/EntityTypeSelector'
import { ALL_LEAVES, RAW_TO_LABEL } from '../lib/entityTypes'

const PHASES = [
  { n: 1, pc: '#4f52d9', icon: 'cloud-download', title: 'Fetch', ic: 'ico-indigo',
    sub: 'Pull transactions + attachments from QuickBooks' },
  { n: 2, pc: '#ea8a0c', icon: 'git-compare', title: 'Match', ic: 'ico-amber',
    sub: 'Match QB records against Wafeq bills/invoices' },
  { n: 3, pc: '#15a34a', icon: 'cloud-upload', title: 'Upload', ic: 'ico-green',
    sub: 'Upload attachments & link to Wafeq records' },
]

export default function Migrate() {
  const { sel, curCompany, toast, phases, runPhase, stopStream, running } = useStore()
  const c = curCompany()
  const [opts, setOpts] = useState({ dateFrom: '', dateTo: '', limit: '' })
  const [selTypes, setSelTypes] = useState(new Set(ALL_LEAVES))
  const [typeOpen, setTypeOpen] = useState(false)
  const [stats, setStats] = useState({ total: 0, files: 0, matched: 0, uploaded: 0, byType: {} })

  const loadStats = useCallback(async () => {
    if (!sel) return
    try {
      const idx = await api.index(sel)
      const bills = Object.values(idx.bills || {})
      let files = 0, matched = 0, uploaded = 0
      const byType = {}
      bills.forEach((b) => {
        const a = b.attachments || []
        files += a.length
        if (b.match_status === 'matched' || b.match_status === 'manual') matched++
        uploaded += a.filter((x) => x.upload_status === 'success').length
        const label = RAW_TO_LABEL[b.qbo_type] || b.qbo_type || 'Other'
        byType[label] = (byType[label] || 0) + 1
      })
      setStats({ total: bills.length, files, matched, uploaded, byType })
    } catch { /* no index yet */ }
  }, [sel])

  useEffect(() => { loadStats() }, [loadStats])

  const typeParam = useMemo(() => Array.from(selTypes).join(','), [selTypes])

  if (!c) {
    return (
      <div className="wrap">
        <div className="empty-hint">
          <Ic name="plug-x" />
          <b>No company selected</b>
          <div style={{ marginTop: 6 }}>Connect a QuickBooks company from the Companies page to begin.</div>
        </div>
      </div>
    )
  }

  const hasKey = !!(c.wafeq_api_key)

  async function doFetch(clear = false) {
    if (selTypes.size === 0) return toast('Select at least one type to fetch', 'err')
    const params = { limit: opts.limit, date_from: opts.dateFrom, date_to: opts.dateTo, types: typeParam }
    if (clear) params.clear = '1'
    await runPhase(1, api.fetchUrl(sel, params)); loadStats()
  }
  async function doMatch() {
    if (!hasKey) return toast('Set a Wafeq API key first (Companies page)', 'err')
    await runPhase(2, api.matchUrl(sel)); loadStats()
  }
  async function doUpload(retry = false) {
    if (!hasKey) return toast('Set a Wafeq API key first (Companies page)', 'err')
    await runPhase(3, api.uploadUrl(sel, retry ? { retry_failed: '1' } : {})); loadStats()
  }
  async function runAll() {
    if (selTypes.size === 0) return toast('Select at least one type to fetch', 'err')
    const params = { limit: opts.limit, date_from: opts.dateFrom, date_to: opts.dateTo, types: typeParam }
    const ok1 = await runPhase(1, api.fetchUrl(sel, params)); loadStats()
    if (!ok1 || !hasKey) { if (!hasKey) toast('Set a Wafeq API key to continue', 'err'); return }
    const ok2 = await runPhase(2, api.matchUrl(sel)); loadStats()
    if (!ok2) return
    await runPhase(3, api.uploadUrl(sel)); loadStats()
  }

  return (
    <div className="wrap">
      <div className="statgrid" style={{ gridTemplateColumns: 'repeat(4,1fr)', marginBottom: 14 }}>
        <div className="stat">
          <span className="sic ico-indigo"><Ic name="receipt" /></span>
          <div className="stxt"><b>{stats.total}</b><span>Txns</span></div>
        </div>
        <div className="stat">
          <span className="sic ico-blue"><Ic name="paperclip" /></span>
          <div className="stxt"><b>{stats.files}</b><span>Files</span></div>
        </div>
        <div className="stat">
          <span className="sic ico-green"><Ic name="git-compare" /></span>
          <div className="stxt"><b style={{ color: 'var(--success)' }}>{stats.matched}</b><span>Matched</span></div>
        </div>
        <div className="stat">
          <span className="sic ico-purple"><Ic name="cloud-upload" /></span>
          <div className="stxt"><b style={{ color: 'var(--accent)' }}>{stats.uploaded}</b><span>Uploaded</span></div>
        </div>
      </div>
      {Object.keys(stats.byType).length > 0 && (
        <div className="chiprow" style={{ marginBottom: 20 }}>
          {Object.entries(stats.byType).map(([label, n]) => (
            <span key={label} className="chip">{label}: <b>{n}</b></span>
          ))}
        </div>
      )}

      {!hasKey && (
        <div style={{ background: 'color-mix(in srgb,var(--warn) 12%,transparent)', color: 'var(--warn)',
          borderRadius: 'var(--r-md)', padding: '9px 12px', fontSize: 12, fontWeight: 600, marginBottom: 16,
          display: 'flex', alignItems: 'center', gap: 8 }}>
          <Ic name="alert-triangle" /> No Wafeq key set — Match & Upload disabled. Add one in Companies.
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-h">
          <div className="ci ico-indigo"><Ic name="adjustments" /></div>
          <h3>Fetch Options</h3>
          <span className="hsub">{c.name}</span>
        </div>
        <div className="card-b">
          <div className="row" style={{ marginBottom: 14 }}>
            <div className="field" style={{ margin: 0 }}><label>From date</label>
              <input className="inp" type="date" value={opts.dateFrom}
                onChange={(e) => setOpts({ ...opts, dateFrom: e.target.value })} /></div>
            <div className="field" style={{ margin: 0 }}><label>To date</label>
              <input className="inp" type="date" value={opts.dateTo}
                onChange={(e) => setOpts({ ...opts, dateTo: e.target.value })} /></div>
            <div className="field" style={{ margin: 0 }}><label>Limit</label>
              <input className="inp" type="number" placeholder="all" value={opts.limit}
                onChange={(e) => setOpts({ ...opts, limit: e.target.value })} /></div>
          </div>

          <div className="type-row type-master" style={{ borderRadius: 'var(--r-md)', border: '1px solid var(--border)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 9, flex: 1, cursor: 'pointer' }}
              onClick={() => setTypeOpen((o) => !o)}>
              <Ic name="filter" style={{ color: 'var(--accent)' }} />
              <span className="tlabel">Transaction Types</span>
              <span className="tcount">{selTypes.size}/{ALL_LEAVES.length} selected</span>
            </span>
            <button className="texpand" onClick={() => setTypeOpen((o) => !o)}>
              <Ic name={typeOpen ? 'chevron-up' : 'chevron-down'} />
            </button>
          </div>
          {typeOpen && (
            <div style={{ marginTop: 8 }}>
              <EntityTypeSelector selected={selTypes} onChange={setSelTypes} />
            </div>
          )}
        </div>
      </div>

      <div className="phase-row" style={{ marginBottom: 16 }}>
        {PHASES.map((p) => {
          const st = phases[p.n]
          const isRun = st.state === 'run'
          return (
            <div key={p.n} className={`phase-card ${st.state}`} style={{ '--pc': p.pc }}>
              <div className="card-h">
                <div className="pico"><Ic name={p.icon} /></div>
                <h3>{p.title}</h3>
                <span className={`phase-stat ${st.state === 'run' ? 'st-run' : st.state === 'done' ? 'st-done'
                  : st.state === 'err' ? 'st-err' : 'st-idle'}`}>
                  {st.state === 'run' ? 'Running' : st.state === 'done' ? 'Done' : st.state === 'err' ? 'Error' : 'Idle'}
                </span>
              </div>
              <div className="card-b">
                <div className="psub">{p.sub}</div>
                <div className="pbar">
                  <i className={isRun ? 'anim' : ''} style={{ width: `${st.pct}%` }} />
                </div>
                <div className="pmeta">
                  <span>{st.lines} lines</span><span className="pct">{Math.round(st.pct)}%</span>
                </div>
                <div className="phase-btns">
                  {!isRun ? (
                    <>
                      <button className="pbtn pbtn-go" disabled={!!running}
                        onClick={() => p.n === 1 ? doFetch() : p.n === 2 ? doMatch() : doUpload()}>
                        <Ic name="player-play" /> {p.title}
                      </button>
                      {p.n === 1 && (
                        <button className="pbtn pbtn-alt" disabled={!!running}
                          title="Clear index & fetch fresh" onClick={() => doFetch(true)}><Ic name="refresh" /></button>
                      )}
                      {p.n === 3 && (
                        <button className="pbtn pbtn-alt" disabled={!!running} title="Retry failed only"
                          onClick={() => doUpload(true)}><Ic name="rotate-clockwise" /></button>
                      )}
                    </>
                  ) : (
                    <button className="pbtn pbtn-stop" onClick={stopStream}><Ic name="square" /> Stop</button>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <button className="btn btn-accent" style={{ marginBottom: 20 }} disabled={!!running} onClick={runAll}>
        <Ic name="player-track-next" /> Run All Phases
      </button>

      <LiveLogs height="480px" />
    </div>
  )
}
