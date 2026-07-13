import { useState } from 'react'
import { useStore } from '../lib/store'
import { api } from '../lib/api'
import { Ic } from '../components/ui'

export default function Companies() {
  const { companies, sel, setSel, curCompany, refreshCompanies, toast } = useStore()
  const [keyName, setKeyName] = useState('')
  const [keyVal, setKeyVal] = useState('')
  const [busy, setBusy] = useState(false)
  const c = curCompany()

  async function connect() {
    try {
      const d = await api.authUrl()
      window.open(d.auth_url, 'qbo', 'width=600,height=720')
      const handler = (ev) => {
        if (ev.data && String(ev.data.type || '').startsWith('QB_AUTH')) {
          window.removeEventListener('message', handler)
          if (ev.data.type === 'QB_AUTH_SUCCESS') {
            toast('Connected: ' + ev.data.name, 'ok')
            setSel(ev.data.realm_id); refreshCompanies()
          } else toast('Connection failed', 'err')
        }
      }
      window.addEventListener('message', handler)
    } catch (e) { toast(e.message, 'err') }
  }

  async function testQbo(rid) {
    try { const d = await api.testQbo(rid); toast(`QB OK — ${d.name} (${d.country})`, 'ok'); refreshCompanies() }
    catch (e) { toast(e.message, 'err') }
  }
  async function delCompany(rid, name) {
    if (!confirm(`Delete company "${name}" and its tokens?`)) return
    try { await api.deleteCompany(rid); toast('Company removed'); await refreshCompanies() }
    catch (e) { toast(e.message, 'err') }
  }

  async function saveKey() {
    if (!sel) return toast('Select a company', 'err')
    if (!keyVal.trim()) return toast('Enter an API key', 'err')
    setBusy(true)
    try {
      await api.saveKey(sel, keyVal.trim(), keyName.trim() || 'Key', true)
      setKeyName(''); setKeyVal(''); toast('Key saved', 'ok'); await refreshCompanies()
    } catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  async function activate(id) {
    try { await api.activateKey(sel, id); toast('Key activated', 'ok'); await refreshCompanies() }
    catch (e) { toast(e.message, 'err') }
  }
  async function delKey(id) {
    if (!confirm('Delete this key?')) return
    try { await api.deleteKey(sel, id); toast('Key deleted'); await refreshCompanies() }
    catch (e) { toast(e.message, 'err') }
  }
  async function testKey() {
    try { const d = await api.testWafeq(sel); toast(`Wafeq OK — ${d.bill_count} bills`, 'ok') }
    catch (e) { toast(e.message, 'err') }
  }

  return (
    <div className="wrap">
      <div className="grid2">
        {/* companies list */}
        <div>
          <div className="card">
            <div className="card-h">
              <div className="ci ico-blue"><Ic name="building" /></div>
              <h3>QuickBooks Companies</h3>
              <button className="btn btn-mode btn-sm" onClick={connect}><Ic name="plus" /> Connect</button>
            </div>
            <div className="card-b">
              {companies.length === 0 ? (
                <div className="empty-hint" style={{ padding: '30px 10px' }}>
                  <Ic name="plug-x" /><b>No companies connected</b>
                  <div style={{ marginTop: 6 }}>Click Connect to authorize a QuickBooks company.</div>
                </div>
              ) : companies.map((co) => (
                <div key={co.realm_id} className={`co-card ${sel === co.realm_id ? 'sel' : ''}`}
                  style={{ marginBottom: 10, cursor: 'pointer' }} onClick={() => setSel(co.realm_id)}>
                  <div className="cot">
                    <span className="con">{co.name}</span>
                    <span className={`pill ${co.token_valid ? 'pill-ok' : 'pill-off'}`}>
                      <Ic name={co.token_valid ? 'circle-check' : 'circle-x'} />{co.token_valid ? 'Live' : 'Off'}</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--tx3)', display: 'flex', gap: 12, marginBottom: 10 }}>
                    <span><Ic name="world" /> {co.country}</span>
                    <span><Ic name="server" /> {co.environment}</span>
                    <span><Ic name="key" /> {(co.wafeq_keys || []).length} key(s)</span>
                    <span className="mono" style={{ opacity: .7 }}>{co.realm_id}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 7 }}>
                    <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); testQbo(co.realm_id) }}>
                      <Ic name="plug-connected" /> Test</button>
                    <button className="btn btn-danger btn-sm" onClick={(e) => { e.stopPropagation(); delCompany(co.realm_id, co.name) }}>
                      <Ic name="trash" /> Remove</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* wafeq keys */}
        <div>
          <div className="card">
            <div className="card-h">
              <div className="ci ico-purple"><Ic name="key" /></div>
              <h3>Wafeq API Keys</h3>
              <span className="hsub">{c ? c.name : '—'}</span>
            </div>
            <div className="card-b">
              {!c ? (
                <div className="empty-hint" style={{ padding: '20px 10px' }}>
                  <Ic name="arrow-left" /><div>Select a company to manage its keys.</div></div>
              ) : (
                <>
                  {(c.wafeq_keys || []).length === 0 ? (
                    <div style={{ fontSize: 12, color: 'var(--tx3)', marginBottom: 12 }}>No keys saved yet.</div>
                  ) : (
                    <div style={{ marginBottom: 14 }}>
                      {(c.wafeq_keys || []).map((k) => {
                        const active = c.wafeq_api_key === k.key
                        return (
                          <div key={k.id} className={`keyrow ${active ? 'active' : ''}`}>
                            <span className="kdot" />
                            <span className="kname" onClick={() => activate(k.id)} title="Set active">{k.name}</span>
                            {active && <span className="pill pill-ok" style={{ padding: '1px 7px' }}>Active</span>}
                            <button className="kact" onClick={() => delKey(k.id)} title="Delete"><Ic name="x" /></button>
                          </div>
                        )
                      })}
                    </div>
                  )}
                  <div className="field"><label>Key name</label>
                    <input className="inp" value={keyName} onChange={(e) => setKeyName(e.target.value)}
                      placeholder="e.g. Client Prod" /></div>
                  <div className="field"><label>API key</label>
                    <textarea className="inp" rows={2} value={keyVal} onChange={(e) => setKeyVal(e.target.value)}
                      placeholder="Paste Wafeq API key…" /></div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-mode btn-block" onClick={saveKey} disabled={busy}>
                      <Ic name="device-floppy" /> Save & Activate</button>
                    <button className="btn btn-ghost btn-sm" style={{ flex: '0 0 auto' }} onClick={testKey}
                      disabled={!c.wafeq_api_key} title="Test active key"><Ic name="plug-connected" /></button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
