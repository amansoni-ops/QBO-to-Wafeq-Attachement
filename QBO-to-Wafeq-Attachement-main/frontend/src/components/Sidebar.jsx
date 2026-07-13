import { useState } from 'react'
import { useStore } from '../lib/store'
import { api } from '../lib/api'
import { Ic } from './ui'

const NAV = [
  { id: 'migrate', label: 'Migrate', icon: 'arrows-transfer-up', c1: '#4f52d9', c2: '#7c3aed' },
  { id: 'companies', label: 'Companies', icon: 'building', c1: '#0d9e6e', c2: '#34d399', adminOnly: false },
  { id: 'report', label: 'Report', icon: 'chart-bar', c1: '#d97706', c2: '#fbbf24' },
  { id: 'mapping', label: 'Mapping', icon: 'link', c1: '#0891b2', c2: '#22d3ee' },
  { id: 'admin', label: 'Admin', icon: 'shield-lock', c1: '#ea580c', c2: '#fb923c', adminOnly: true },
  { id: 'settings', label: 'Settings', icon: 'settings', c1: '#dc2626', c2: '#f87171' },
]

export default function Sidebar({ page, setPage }) {
  const { me, setMe, companies, sel, setSel, curCompany, theme, setTheme } = useStore()
  const [open, setOpen] = useState(false)
  const c = curCompany()
  const activeKeyName = c ? (c.wafeq_keys || []).find((k) => k.key === c.wafeq_api_key)?.name : null
  const isAdmin = me?.role === 'admin'

  async function logout() { await api.logout(); setMe(null); location.reload() }

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-logos">
          <div className="ltile"><img className="lflip" src={import.meta.env.BASE_URL + "brand/qbo.png"} alt="QuickBooks" /></div>
          <div className="brand-arrow">
            <span className="ba-line" />
            <i className="ti ti-caret-right-filled ba-head" />
          </div>
          <div className="ltile"><img className="lflip d2" src={import.meta.env.BASE_URL + "brand/wafeq.png"} alt="Wafeq" /></div>
        </div>
      </div>

      <div className="side-scroll">
        <div className="side-label"><Ic name="building" /> Active Company</div>
        <div className="co-switch">
          <div className="co-current" onClick={() => setOpen((o) => !o)}>
            <div className="cc-name">
              <Ic name="briefcase" style={{ color: 'var(--accent)' }} />
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {c ? c.name : 'No company'}
              </span>
              <Ic name={open ? 'chevron-up' : 'chevron-down'} style={{ color: 'var(--tx3)' }} />
            </div>
            {c && (
              <div className="co-badges">
                <span className="cbadge qbo"><span className="cdot" />QBO Connected</span>
                {activeKeyName && <span className="cbadge wafeq"><span className="cdot" />Wafeq: {activeKeyName}</span>}
              </div>
            )}
          </div>
          {open && (
            <div className="co-drop">
              {companies.length === 0 && (
                <div className="co-opt" style={{ color: 'var(--tx3)' }}>No companies â€” connect one</div>
              )}
              {companies.map((co) => (
                <div key={co.realm_id}
                  className={`co-opt ${sel === co.realm_id ? 'sel' : ''}`}
                  onClick={() => { setSel(co.realm_id); setOpen(false) }}>
                  <span className={`pill ${co.token_valid ? 'pill-ok' : 'pill-off'}`} style={{ padding: '1px 6px' }}>
                    <Ic name={co.token_valid ? 'circle-check' : 'circle-x'} />
                  </span>
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {co.name}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="side-label" style={{ marginTop: 16 }}><Ic name="layout-grid" /> Navigation</div>
        {NAV.filter((n) => !n.adminOnly || isAdmin).map((n) => (
          <button key={n.id} className={`nav-item ${page === n.id ? 'active' : ''}`} onClick={() => setPage(n.id)}
            style={{ '--c1': n.c1, '--c2': n.c2 }}>
            <span className="nav-tile"><Ic name={n.icon} /></span>
            {n.label}
          </button>
        ))}
      </div>

      <div className="side-foot">
        <div className="avatar">{(me?.user || 'A')[0].toUpperCase()}</div>
        <div className="who"><b>{me?.user}</b><span>{me?.role || 'user'}</span></div>
        <button className="icobtn" title="Theme" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
          <Ic name={theme === 'dark' ? 'sun' : 'moon'} />
        </button>
        <button className="icobtn" title="Logout" onClick={logout}><Ic name="logout" /></button>
      </div>
    </aside>
  )
}
