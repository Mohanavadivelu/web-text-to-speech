import { createContext, useContext } from 'react'

export type ToastKind = 'info' | 'success' | 'warning' | 'error'

export interface ToastInput {
  kind: ToastKind
  message: string
  action?: { label: string; run: () => void }
}

export const ToastContext = createContext<(toast: ToastInput) => void>(() => {})

export function useToast() {
  return useContext(ToastContext)
}
