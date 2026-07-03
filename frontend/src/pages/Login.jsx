import { useState } from 'react'
import { useStore } from '../lib/store'
import { api } from '../lib/api'
import { Ic } from '../components/ui'

export default function Login() {
  const { setMe, refreshCompanies } = useStore()
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit() {
    setErr(''); setBusy(true)
    try {
      const d = await api.login(user, pass)
      setMe(d)
      await refreshCompanies()
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="login-wrap">
      <div className="login-side">
        <div className="lbrand">
          <div className="logo"><Ic name="transfer-in" /></div>
          <div><h1 style={{ color: '#fff', fontSize: 15, fontWeight: 800 }}>QBO → Wafeq</h1>
            <p style={{ color: '#cbd5e1', fontSize: 11 }}>Attachment Migration</p></div>
        </div>
        <h2>Migrate attachments,<br />bill by bill.</h2>
        <p>Fetch from QuickBooks, match against Wafeq, and link every file — with full live logs and per-phase progress.</p>
      </div>
      <div className="login-main">
        <div className="login-box">
          <h3 style={{ fontSize: 20, fontWeight: 800, marginBottom: 4 }}>Welcome back</h3>
          <p style={{ color: 'var(--tx3)', marginBottom: 22 }}>Sign in to continue</p>
          <div className="field"><label>Username</label>
            <input className="inp" value={user} onChange={(e) => setUser(e.target.value)}
              placeholder="admin" onKeyDown={(e) => e.key === 'Enter' && submit()} /></div>
          <div className="field"><label>Password</label>
            <input className="inp" type="password" value={pass} onChange={(e) => setPass(e.target.value)}
              placeholder="••••••••" onKeyDown={(e) => e.key === 'Enter' && submit()} /></div>
          <button className="btn btn-accent btn-block" style={{ marginTop: 8 }} onClick={submit} disabled={busy}>
            {busy ? <Ic name="loader-2" className="spin" /> : <Ic name="login-2" />} Sign In
          </button>
          {err && <div style={{ color: 'var(--danger)', fontSize: 12, marginTop: 12, textAlign: 'center' }}>{err}</div>}
        </div>
      </div>
    </div>
  )
}
