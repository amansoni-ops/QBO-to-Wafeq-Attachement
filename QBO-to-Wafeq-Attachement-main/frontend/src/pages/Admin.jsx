import { useEffect, useState, useCallback } from 'react'
import { useStore } from '../lib/store'
import { api } from '../lib/api'
import { Ic } from '../components/ui'

export default function Admin() {
  const { toast } = useStore()
  const [users, setUsers] = useState([])
  const [audit, setAudit] = useState([])
  const [nu, setNu] = useState({ username: '', password: '', role: 'user' })
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [u, a] = await Promise.all([api.adminUsers(), api.auditLog(300)])
      setUsers(Array.isArray(u) ? u : [])
      setAudit(Array.isArray(a) ? a : [])
    } catch (e) { toast(e.message, 'err') }
  }, [toast])

  useEffect(() => { load() }, [load])

  async function create() {
    if (!nu.username || !nu.password) return toast('Username & password required', 'err')
    setBusy(true)
    try { await api.createUser(nu.username, nu.password, nu.role); toast('User created', 'ok')
      setNu({ username: '', password: '', role: 'user' }); await load() }
    catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  async function resetPw(target) {
    const pw = prompt(`New password for "${target}":`); if (!pw) return
    try { await api.resetPassword(target, pw); toast('Password reset', 'ok') }
    catch (e) { toast(e.message, 'err') }
  }
  async function del(target) {
    if (!confirm(`Delete user "${target}"?`)) return
    try { await api.deleteUser(target); toast('User deleted'); await load() }
    catch (e) { toast(e.message, 'err') }
  }

  return (
    <div className="wrap">
      <div className="grid2">
        <div>
          <div className="card">
            <div className="card-h"><div className="ci ico-indigo"><Ic name="users" /></div>
              <h3>Users</h3><span className="hsub">{users.length} total</span></div>
            <div className="card-b">
              <table className="tbl" style={{ marginBottom: 16 }}>
                <thead><tr><th>Username</th><th>Role</th><th></th></tr></thead>
                <tbody>
                  {users.map((u) => {
                    const name = u.username || u.user || u.name
                    return (
                      <tr key={name}>
                        <td style={{ fontWeight: 600 }}>{name}</td>
                        <td><span className={`pill ${u.role === 'admin' ? 'pill-ok' : 'pill-mut'}`}>{u.role || 'user'}</span></td>
                        <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                          <button className="btn btn-ghost btn-sm" onClick={() => resetPw(name)}><Ic name="key" /> Reset</button>
                          <button className="btn btn-danger btn-sm" style={{ marginLeft: 6 }} onClick={() => del(name)}>
                            <Ic name="trash" /></button>
                        </td>
                      </tr>
                    )
                  })}
                  {users.length === 0 && <tr><td colSpan={3} style={{ color: 'var(--tx3)' }}>No users.</td></tr>}
                </tbody>
              </table>

              <h4 style={{ fontSize: 12, fontWeight: 700, margin: '4px 2px 10px', color: 'var(--tx2)' }}>Create User</h4>
              <div className="row" style={{ marginBottom: 10 }}>
                <div className="field" style={{ margin: 0 }}><label>Username</label>
                  <input className="inp" value={nu.username} onChange={(e) => setNu({ ...nu, username: e.target.value })} /></div>
                <div className="field" style={{ margin: 0 }}><label>Password</label>
                  <input className="inp" type="password" value={nu.password}
                    onChange={(e) => setNu({ ...nu, password: e.target.value })} /></div>
                <div className="field" style={{ margin: 0, flex: '0 0 110px' }}><label>Role</label>
                  <select className="inp" value={nu.role} onChange={(e) => setNu({ ...nu, role: e.target.value })}>
                    <option value="user">user</option><option value="admin">admin</option></select></div>
              </div>
              <button className="btn btn-mode" onClick={create} disabled={busy}><Ic name="user-plus" /> Create User</button>
            </div>
          </div>
        </div>

        <div>
          <div className="card">
            <div className="card-h"><div className="ci ico-amber"><Ic name="history" /></div>
              <h3>Audit Log</h3><span className="hsub">{audit.length} events</span>
              <span style={{ flex: 1 }} />
              <button className="btn btn-ghost btn-sm" onClick={load}><Ic name="refresh" /></button></div>
            <div className="card-b" style={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}>
              <table className="tbl">
                <thead><tr><th>Time</th><th>User</th><th>Action</th></tr></thead>
                <tbody>
                  {audit.map((e, i) => (
                    <tr key={i}>
                      <td className="mono" style={{ fontSize: 10.5, color: 'var(--tx3)' }}>
                        {(e.timestamp || e.time || e.ts || '').toString().replace('T', ' ').slice(0, 19)}</td>
                      <td style={{ fontWeight: 600 }}>{e.user || e.username || '—'}</td>
                      <td>{e.action}{e.details ? <span style={{ color: 'var(--tx3)' }}> · {typeof e.details === 'object'
                        ? JSON.stringify(e.details) : e.details}</span> : ''}</td>
                    </tr>
                  ))}
                  {audit.length === 0 && <tr><td colSpan={3} style={{ color: 'var(--tx3)' }}>No events.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
