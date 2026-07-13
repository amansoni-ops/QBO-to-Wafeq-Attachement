import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react'
import { api } from './api'

const Ctx = createContext(null)
export const useStore = () => useContext(Ctx)

export const PHASE_META = {
  1: { color: '#4f52d9', label: 'FETCH', short: 'F' },
  2: { color: '#ea8a0c', label: 'MATCH', short: 'M' },
  3: { color: '#15a34a', label: 'UPLOAD', short: 'U' },
}

export function StoreProvider({ children }) {
  const [me, setMe] = useState(null)
  const [booting, setBooting] = useState(true)
  const [companies, setCompanies] = useState([])
  const [sel, setSel] = useState(null)
  const [theme, setTheme] = useState('light')
  const [toasts, setToasts] = useState([])

  // logs shared across pages: {phase,msg,type,t}
  const [logs, setLogs] = useState([])
  // per-phase progress: {state,pct,lines}
  const [phases, setPhases] = useState({
    1: { state: 'idle', pct: 0, lines: 0 },
    2: { state: 'idle', pct: 0, lines: 0 },
    3: { state: 'idle', pct: 0, lines: 0 },
  })
  const esRef = useRef(null)
  const [running, setRunning] = useState(null)

  useEffect(() => { document.body.dataset.theme = theme }, [theme])

  const toast = useCallback((msg, kind = '') => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t, { id, msg, kind }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200)
  }, [])

  const refreshCompanies = useCallback(async () => {
    const list = await api.companies()
    setCompanies(list)
    setSel((cur) => cur || (list[0] ? list[0].realm_id : null))
    return list
  }, [])

  const boot = useCallback(async () => {
    try {
      const u = await api.me()
      setMe(u)
      await refreshCompanies()
    } catch {
      setMe(null)
    } finally {
      setBooting(false)
    }
  }, [refreshCompanies])

  useEffect(() => { boot() }, [boot])

  const setMode = useCallback((phase) => {
    document.documentElement.style.setProperty('--mode', phase ? PHASE_META[phase].color : '#4f52d9')
  }, [])

  const pushLog = useCallback((phase, msg, type = 'info') => {
    const t = new Date().toLocaleTimeString('en-GB', { hour12: false })
    setLogs((L) => {
      const next = [...L, { phase, msg, type, t }]
      return next.length > 3000 ? next.slice(-3000) : next
    })
  }, [])
  const clearLogs = useCallback(() => setLogs([]), [])

  const setPhase = useCallback((n, patch) => {
    setPhases((p) => ({ ...p, [n]: { ...p[n], ...patch } }))
  }, [])

  function parsePct(msg) {
    const m = String(msg).match(/(\d+)\s*\/\s*(\d+)/)
    if (m) { const a = +m[1], b = +m[2]; if (b > 0) return Math.min(100, (a / b) * 100) }
    return null
  }

  const stopStream = useCallback(() => {
    if (esRef.current) { esRef.current.close(); esRef.current = null }
    if (running) { setPhase(running, { state: 'idle' }); pushLog(running, '⏹ Stopped by user', 'warn') }
    setRunning(null); setMode(null)
  }, [running, setPhase, pushLog, setMode])

  // Run a phase via SSE. Returns a promise resolving true(done)/false(error).
  const runPhase = useCallback((phase, url) => new Promise((resolve) => {
    if (esRef.current) { toast('A phase is already running', 'err'); return resolve(false) }
    setRunning(phase); setMode(phase)
    setPhase(phase, { state: 'run', pct: 0, lines: 0 })
    let lines = 0
    let softPct = 0
    const es = new EventSource(url)
    esRef.current = es
    es.onmessage = (ev) => {
      if (ev.data === '__DONE__') {
        es.close(); esRef.current = null; setRunning(null); setMode(null)
        setPhase(phase, { state: 'done', pct: 100 })
        pushLog(phase, '✔ Phase complete', 'ok')
        resolve(true); return
      }
      let d
      try { d = JSON.parse(ev.data) } catch { d = { msg: ev.data, type: 'info' } }
      lines++
      const type = d.type === 'err' ? 'err' : d.type
      pushLog(phase, d.msg, type)
      const pct = parsePct(d.msg)
      // No explicit x/y progress in this line → nudge the bar forward so it
      // keeps visibly moving instead of sitting at 0% until __DONE__ arrives.
      if (pct != null) softPct = pct
      else softPct = Math.min(92, softPct + 3)
      setPhase(phase, { lines, pct: softPct })
    }
    es.onerror = () => {
      if (esRef.current) { es.close(); esRef.current = null }
      setRunning(null); setMode(null)
      setPhase(phase, { state: 'err' })
      pushLog(phase, '✖ Connection error / stream ended', 'err')
      resolve(false)
    }
  }), [toast, setMode, setPhase, pushLog])

  const value = {
    me, setMe, booting,
    companies, setCompanies, refreshCompanies,
    sel, setSel,
    curCompany: () => companies.find((c) => c.realm_id === sel),
    theme, setTheme,
    toast, toasts,
    logs, pushLog, clearLogs,
    phases, setPhase, running, runPhase, stopStream,
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
