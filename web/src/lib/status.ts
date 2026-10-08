// The app-wide status shown by the top bar's dot (ready / busy / error).

import { createContext, useContext } from 'react'

export type StatusLevel = 'ok' | 'busy' | 'error'
export interface AppStatus {
  level: StatusLevel
  text: string
}

export const READY: AppStatus = { level: 'ok', text: 'Ready' }

export const StatusContext = createContext<{
  status: AppStatus
  setStatus: (s: AppStatus) => void
}>({ status: READY, setStatus: () => {} })

export function useAppStatus() {
  return useContext(StatusContext)
}
