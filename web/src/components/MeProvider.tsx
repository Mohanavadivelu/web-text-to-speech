import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, type Me } from '../api/client'
import { useAuth } from '../lib/auth'
import { ANONYMOUS, MeContext } from '../lib/me'

export function MeProvider({ children }: { children: ReactNode }) {
  const { ready, session } = useAuth()
  const [me, setMe] = useState<Me>(ANONYMOUS)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    if (!ready) return
    let alive = true
    api
      .me()
      .then((next) => alive && setMe(next))
      .catch(() => {}) // keep the last known limits; the API reports errors where it matters
    return () => {
      alive = false
    }
  }, [ready, session?.access_token, version])

  const refresh = useCallback(() => setVersion((v) => v + 1), [])
  const value = useMemo(() => ({ me, refresh }), [me, refresh])
  return <MeContext.Provider value={value}>{children}</MeContext.Provider>
}
