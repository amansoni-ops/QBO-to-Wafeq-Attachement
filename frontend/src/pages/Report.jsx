import { useEffect, useState, useCallback } from 'react'
import { useStore } from '../lib/store'
import { api } from '../lib/api'
import { Ic } from '../components/ui'

export default function Report() {
  const { sel, curCompany, toast } = useStore()
  const c = curCompany()
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!sel) return
    setBusy(true)
    try { setData(await api.report(sel)) }
    catch (e) { setData(null); toast(e.message, 'err') }
    finally { setBusy(false) }
  }, [sel, toast])

  async function fixMatch(bill) {
    const wafeqType = (prompt('Wafeq record type (bill / invoice / journal):', bill.wafeq_type || 'bill') || '').trim().toLowerCase()
    if (!wafeqType) return
    const wafeqId = (prompt('Wafeq record ID to link:') || '').trim()
    if (!wafeqId) return
    try {
      const d = await api.manualMatch(sel, bill.qb_id || bill.id || bill.txn_id, wafeqId, wafeqType)
      toast(`Matched${d.wafeq_doc_number ? ' — ' + d.wafeq_doc_number : ''}`, 'ok')
      load()
    } catch (e) { toast(e.message, 'err') }
  }

  useEffect(() => { load() }, [load])

  if (!c) return <div className="wrap"><div className="empty-hint"><Ic name="building" /><b>No company selected</b></div></div>

  const s = data?.summary || {}
  const rows = data?.type_breakdown || []
  const bills = data?.bills || []

  return (
    <div className="wrap">
      <div className="card">
        <div className="card-h">
          <div className="ci ico-blue"><Ic name="chart-bar" /></div>
          <h3>Migration Report</h3><span className="hsub">{c.name}</span>
          <span style={{ flex: 1 }} />
          <button className="btn btn-ghost btn-sm" onClick={load} disabled={busy}>
            {busy ? <Ic name="loader-2" className="spin" /> : <Ic name="refresh" />} Refresh</button>
          <button className="btn btn-mode btn-sm" onClick={() => window.open(api.exportXlsxUrl(sel), '_blank')}>
            <Ic name="file-spreadsheet" /> Export XLSX</button>
        </div>
        <div className="card-b">
          {!data ? (
            <div className="empty-hint"><Ic name="report" /><div>Run a migration, then refresh to see the breakdown.</div></div>
          ) : (
            <>
              <div className="statgrid" style={{ gridTemplateColumns: 'repeat(6,1fr)', marginBottom: 18 }}>
                <div className="stat"><b>{s.total || 0}</b><span>Total</span></div>
                <div className="stat"><b>{s.total_files || 0}</b><span>Files</span></div>
                <div className="stat"><b style={{ color: 'var(--success)' }}>{s.matched || 0}</b><span>Matched</span></div>
                <div className="stat"><b style={{ color: 'var(--danger)' }}>{s.no_match || 0}</b><span>No Match</span></div>
                <div className="stat"><b style={{ color: 'var(--accent)' }}>{s.uploaded || 0}</b><span>Uploaded</span></div>
                <div className="stat"><b style={{ color: 'var(--danger)' }}>{s.failed || 0}</b><span>Failed</span></div>
              </div>

              <h4 style={{ fontSize: 12, fontWeight: 700, margin: '4px 2px 8px', color: 'var(--tx2)' }}>By Type</h4>
              <table className="tbl" style={{ marginBottom: 20 }}>
                <thead><tr><th>QBO Type</th><th>Wafeq</th><th className="num">Count</th>
                  <th className="num">Matched</th><th className="num">Uploaded</th><th className="num">Failed</th></tr></thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600 }}>{r.qbo_type}</td>
                      <td style={{ color: 'var(--tx3)' }}>{r.wafeq_type}</td>
                      <td className="num">{r.count}</td>
                      <td className="num" style={{ color: 'var(--success)' }}>{r.matched}</td>
                      <td className="num" style={{ color: 'var(--accent)' }}>{r.uploaded}</td>
                      <td className="num" style={{ color: 'var(--danger)' }}>{r.failed}</td>
                    </tr>
                  ))}
                  {rows.length === 0 && <tr><td colSpan={6} style={{ color: 'var(--tx3)' }}>No data.</td></tr>}
                </tbody>
              </table>

              <h4 style={{ fontSize: 12, fontWeight: 700, margin: '4px 2px 8px', color: 'var(--tx2)' }}>
                Transactions <span style={{ color: 'var(--tx3)', fontWeight: 500 }}>({bills.length})</span></h4>
              <div style={{ maxHeight: 340, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--r-md)' }}>
                <table className="tbl">
                  <thead><tr><th>Doc #</th><th>Type</th><th>Contact</th><th>Date</th>
                    <th className="num">Amount</th><th>Match</th><th className="num">Files</th><th></th></tr></thead>
                  <tbody>
                    {bills.slice(0, 300).map((b, i) => {
                      const ms = b.match_status || 'pending'
                      const cls = ms === 'matched' || ms === 'manual' ? 'pill-ok'
                        : ms === 'no_match' ? 'pill-off' : ms === 'duplicate' ? 'pill-warn' : 'pill-mut'
                      return (
                        <tr key={i}>
                          <td className="mono">{b.doc_number || '—'}</td>
                          <td>{b.qbo_type || 'Bill'}</td>
                          <td>{b.vendor_name || b.customer_name || '—'}</td>
                          <td className="mono">{b.txn_date || '—'}</td>
                          <td className="num">{b.total_amt ?? '—'} {b.currency || ''}</td>
                          <td><span className={`pill ${cls}`}>{ms}</span></td>
                          <td className="num">{(b.attachments || []).length}</td>
                          <td style={{ textAlign: 'right' }}>
                            {ms !== 'matched' && (
                              <button className="btn btn-ghost btn-sm" onClick={() => fixMatch(b)}>
                                <Ic name="link" /> Fix
                              </button>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
