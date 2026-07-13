import { useEffect, useState, useCallback, useMemo } from 'react'
import { useStore } from '../lib/store'
import { api } from '../lib/api'
import { Ic } from '../components/ui'

const STATUS_STYLE = {
  success: { color: 'var(--success)', label: 'success' },
  failed:  { color: 'var(--danger)',  label: 'failed' },
  pending: { color: 'var(--tx3)',     label: 'pending' },
  skipped: { color: 'var(--tx3)',     label: 'skipped' },
}

export default function Mapping() {
  const { sel, curCompany, toast } = useStore()
  const c = curCompany()
  const [rows, setRows] = useState([])
  const [busy, setBusy] = useState(false)
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState('all')

  const load = useCallback(async () => {
    if (!sel) return
    setBusy(true)
    try {
      const d = await api.attachmentMap(sel)
      setRows(d.rows || [])
    } catch (e) {
      setRows([])
      toast(e.message, 'err')
    } finally {
      setBusy(false)
    }
  }, [sel, toast])

  useEffect(() => { load() }, [load])

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return rows.filter((r) => {
      if (filter !== 'all' && r.upload_status !== filter) return false
      if (!needle) return true
      return (
        (r.doc_number || '').toLowerCase().includes(needle) ||
        (r.contact || '').toLowerCase().includes(needle) ||
        (r.file_name || '').toLowerCase().includes(needle) ||
        (r.wafeq_record_id || '').toLowerCase().includes(needle) ||
        (r.reason || '').toLowerCase().includes(needle)
      )
    })
  }, [rows, q, filter])

  const counts = useMemo(() => {
    const b = { all: rows.length, success: 0, failed: 0, pending: 0, skipped: 0 }
    rows.forEach((r) => { b[r.upload_status] = (b[r.upload_status] || 0) + 1 })
    return b
  }, [rows])

  if (!c) return (
    <div className="wrap"><div className="empty-hint"><Ic name="building" /><b>No company selected</b></div></div>
  )

  return (
    <div className="wrap">
      <div className="card">
        <div className="card-h">
          <div className="ci ico-blue"><Ic name="link" /></div>
          <h3>Attachment Mapping</h3><span className="hsub">{c.name}</span>
          <span style={{ flex: 1 }} />
          <button className="btn btn-ghost btn-sm" onClick={load} disabled={busy}>
            {busy ? <Ic name="loader-2" className="spin" /> : <Ic name="refresh" />} Refresh</button>
          <button className="btn btn-mode btn-sm"
            onClick={() => window.open(api.attachmentMapXlsxUrl(sel), '_blank')}
            disabled={!rows.length}>
            <Ic name="file-spreadsheet" /> Export Mapping</button>
        </div>

        <div className="card-b">
          {!rows.length && !busy ? (
            <div className="empty-hint">
              <Ic name="link-off" />
              <div>No attachments yet. Run a migration (Fetch → Match → Upload), then refresh.</div>
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 14, flexWrap: 'wrap' }}>
                <div className="inp-ico" style={{ flex: 1, minWidth: 220 }}>
                  <Ic name="search" />
                  <input placeholder="Search doc #, vendor, file name, Wafeq ID…"
                    value={q} onChange={(e) => setQ(e.target.value)} />
                </div>
                {['all', 'success', 'failed', 'pending', 'skipped'].map((f) => (
                  <button key={f}
                    className={`btn btn-sm ${filter === f ? 'btn-mode' : 'btn-ghost'}`}
                    onClick={() => setFilter(f)}>
                    {f[0].toUpperCase() + f.slice(1)} ({counts[f] || 0})
                  </button>
                ))}
              </div>

              <div style={{ fontSize: 12, color: 'var(--tx3)', marginBottom: 8 }}>
                Showing {shown.length} of {rows.length} attachment(s)
              </div>

              <table className="tbl">
                <thead>
                  <tr>
                    <th>Doc Number</th>
                    <th>Vendor / Customer</th>
                    <th>File Name</th>
                    <th>Wafeq Type</th>
                    <th>Wafeq Record ID</th>
                    <th>Upload Status</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((r, i) => {
                    const st = STATUS_STYLE[r.upload_status] || STATUS_STYLE.pending
                    return (
                      <tr key={i}>
                        <td>{r.doc_number || <span style={{ color: 'var(--tx3)' }}>—</span>}</td>
                        <td>{r.contact || <span style={{ color: 'var(--tx3)' }}>—</span>}</td>
                        <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{r.file_name}</td>
                        <td>{r.wafeq_type || <span style={{ color: 'var(--tx3)' }}>—</span>}</td>
                        <td style={{ fontFamily: 'monospace', fontSize: 12 }}>
                          {r.wafeq_record_id || <span style={{ color: 'var(--danger)' }}>not linked</span>}
                        </td>
                        <td><span style={{ color: st.color, fontWeight: 600 }}>{st.label}</span></td>
                        <td style={{ fontSize: 12, color: r.reason ? 'var(--tx2)' : 'var(--tx3)', maxWidth: 320, whiteSpace: 'normal', wordBreak: 'break-word' }}
                          title={r.reason || ''}>
                          {r.reason || '—'}
                        </td>
                      </tr>
                    )
                  })}
                  {!shown.length && (
                    <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--tx3)', padding: 20 }}>
                      No rows match your filter.</td></tr>
                  )}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
