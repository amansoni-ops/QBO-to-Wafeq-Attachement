import { useState, useEffect } from 'react'
import { useStore } from './lib/store'
import { Toasts, Ic } from './components/ui'
import Sidebar from './components/Sidebar'
import Login from './pages/Login'
import Migrate from './pages/Migrate'
import Companies from './pages/Companies'
import Report from './pages/Report'
import Admin from './pages/Admin'
import Settings from './pages/Settings'

const TITLES = {
  migrate: { h: 'Migrate', sub: 'Fetch â†’ Match â†’ Upload attachments' },
  companies: { h: 'Companies', sub: 'QuickBooks connections & Wafeq keys' },
  report: { h: 'Report', sub: 'Migration summary & breakdown' },
  admin: { h: 'Admin', sub: 'Users & audit log' },
  settings: { h: 'Settings', sub: 'Account & appearance' },
}

const PAGE_COLORS = {
  migrate: '#4f52d9',
  companies: '#0d9e6e',
  report: '#d97706',
  admin: '#ea580c',
  settings: '#dc2626',
}

export default function App() {
  const { me, booting, curCompany, running } = useStore()
  const [page, setPage] = useState('migrate')

  useEffect(() => {
    if (!running) document.documentElement.style.setProperty('--mode', PAGE_COLORS[page] || PAGE_COLORS.migrate)
  }, [page, running])

  if (booting) {
    return <div style={{ display: 'grid', placeItems: 'center', height: '100vh', color: 'var(--tx3)' }}>
      <div style={{ textAlign: 'center' }}><Ic name="loader-2" className="spin" style={{ fontSize: 32 }} />
        <div style={{ marginTop: 10 }}>Loadingâ€¦</div></div></div>
  }
  if (!me) return <><Login /><Toasts /></>

  const c = curCompany()
  const t = TITLES[page] || TITLES.migrate
  const Page = { migrate: Migrate, companies: Companies, report: Report, admin: Admin, settings: Settings }[page]

  return (
    <div className="app">
      <Sidebar page={page} setPage={setPage} />
      <main className="main">
        <div className="aura" />
        <div className="topbar">
          <div><h2>{t.h}</h2><div className="sub">{t.sub}</div></div>
          <div className="spacer" />
          {c && (
            <span className="env-badge">
              <Ic name="briefcase" /> {c.name}
              {(() => {
                const k = (c.wafeq_keys || []).find((x) => x.key === c.wafeq_api_key)
                return k ? <span style={{ opacity: .7 }}> Â· Wafeq: {k.name}</span> : null
              })()}
            </span>
          )}
          <div className="topbar-mmc">
            <div className="mtile"><img src={import.meta.env.BASE_URL + "brand/mmc.png"} alt="MMC Convert" /></div>
            <span>by MMC<br />Convert</span>
          </div>
        </div>
        <div className="content"><Page /></div>
      </main>
      <Toasts />
    </div>
  )
}
