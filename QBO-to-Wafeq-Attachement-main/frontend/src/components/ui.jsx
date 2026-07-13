import { useStore } from '../lib/store'

export const Ic = ({ name, ...p }) => <i className={`ti ti-${name}`} {...p} />

export function Toasts() {
  const { toasts } = useStore()
  return (
    <div className="toast-wrap">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`}>
          <Ic name={t.kind === 'ok' ? 'circle-check' : t.kind === 'err' ? 'alert-circle' : 'info-circle'} />
          {t.msg}
        </div>
      ))}
    </div>
  )
}
