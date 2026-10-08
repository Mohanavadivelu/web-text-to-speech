import { useMemo, useState, type ReactNode } from 'react'

import { READY, StatusContext, type AppStatus } from '../lib/status'

export function StatusProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AppStatus>(READY)
  const value = useMemo(() => ({ status, setStatus }), [status])
  return <StatusContext.Provider value={value}>{children}</StatusContext.Provider>
}
