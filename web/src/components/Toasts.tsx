// Toast messages (docs/DESIGN.md §11): top centre, up to three, errors stay until closed.

import { AlertOctagon, AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'

import { ToastContext, type ToastInput } from '../lib/toast'
import styles from './Toasts.module.css'

interface Toast extends ToastInput {
  id: number
}

const ICONS = { info: Info, success: CheckCircle2, warning: AlertTriangle, error: AlertOctagon }
const MAX = 3
const AUTO_CLOSE_MS = 5000

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const close = useCallback((id: number) => {
    setToasts((all) => all.filter((t) => t.id !== id))
  }, [])

  const show = useCallback(
    (toast: ToastInput) => {
      const id = nextId.current++
      setToasts((all) => [...all.slice(-(MAX - 1)), { ...toast, id }])
      if (toast.kind !== 'error') window.setTimeout(() => close(id), AUTO_CLOSE_MS)
    },
    [close],
  )

  const value = useMemo(() => show, [show])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className={styles.stack} aria-live="polite">
        {toasts.map((toast) => {
          const Icon = ICONS[toast.kind]
          return (
            <div key={toast.id} className={`${styles.toast} ${styles[toast.kind]}`} role="status">
              <Icon size={18} className={styles.icon} aria-hidden />
              <span className={styles.message}>{toast.message}</span>
              {toast.action && (
                <button
                  className={styles.action}
                  onClick={() => {
                    toast.action?.run()
                    close(toast.id)
                  }}
                >
                  {toast.action.label}
                </button>
              )}
              <button className={styles.close} onClick={() => close(toast.id)} aria-label="Dismiss">
                <X size={16} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
