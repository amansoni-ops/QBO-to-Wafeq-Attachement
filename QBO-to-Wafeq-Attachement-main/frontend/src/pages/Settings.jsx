import { useState } from 'react'
import { useStore } from '../lib/store'
import { api } from '../lib/api'
import { Ic } from '../components/ui'

export default function Settings() {
  const { me, theme, setTheme, toast } = useStore()
  const [pw, setPw] = useState({ old_password: '', new_password: '', confirm: '' })
  const [busy, setBusy] = useState(false)

  async function change() {
    if (!pw.old_password || !pw.new_password) return toast('Fill both password fields', 'err')
    if (pw.new_password !== pw.confirm) return toast('New passwords do not match', 'err')
    setBusy(true)
    try { await api.changePassword(pw.old_password, pw.new_password)
      toast('Password changed', 'ok'); setPw({ old_password: '', new_password: '', confirm: '' }) }
    catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }

  return (
    <div className="wrap" style={{ maxWidth: 640 }}>
      <div className="card">
        <div className="card-h"><div className="ci ico-indigo"><Ic name="user-circle" /></div>
          <h3>Account</h3></div>
        <div className="card-b">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <div className="avatar" style={{ width: 44, height: 44, fontSize: 18 }}>{(me?.user || 'A')[0].toUpperCase()}</div>
            <div><b style={{ fontSize: 15 }}>{me?.user}</b>
              <div><span className={`pill ${me?.role === 'admin' ? 'pill-ok' : 'pill-mut'}`}>{me?.role || 'user'}</span></div></div>
          </div>
          <h4 style={{ fontSize: 12, fontWeight: 700, margin: '4px 2px 10px', color: 'var(--tx2)' }}>Change Password</h4>
          <div className="field"><label>Current password</label>
            <input className="inp" type="password" value={pw.old_password}
              onChange={(e) => setPw({ ...pw, old_password: e.target.value })} /></div>
          <div className="row">
            <div className="field"><label>New password</label>
              <input className="inp" type="password" value={pw.new_password}
                onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></div>
            <div className="field"><label>Confirm new</label>
              <input className="inp" type="password" value={pw.confirm}
                onChange={(e) => setPw({ ...pw, confirm: e.target.value })} /></div>
          </div>
          <button className="btn btn-mode" onClick={change} disabled={busy}><Ic name="lock" /> Update Password</button>
        </div>
      </div>

      <div className="card">
        <div className="card-h"><div className="ci ico-purple"><Ic name="palette" /></div><h3>Appearance</h3></div>
        <div className="card-b">
          <div style={{ display: 'flex', gap: 10 }}>
            {['light', 'dark'].map((t) => (
              <button key={t} className={`btn ${theme === t ? 'btn-mode' : 'btn-ghost'}`}
                style={{ flex: 1 }} onClick={() => setTheme(t)}>
                <Ic name={t === 'dark' ? 'moon' : 'sun'} /> {t[0].toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
