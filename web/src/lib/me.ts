// The visitor's limits and today's usage (GET /v1/me), shared by the top bar and Studio.

import { createContext, useContext } from 'react'

import type { Me } from '../api/client'

export const ANONYMOUS: Me = {
  signed_in: false,
  email: null,
  limits: { max_chars: 2000, daily_chars: 10_000, max_active_jobs: 2, uploads: false, wav: false },
  chars_today: 0,
}

export const MeContext = createContext<{ me: Me; refresh: () => void }>({
  me: ANONYMOUS,
  refresh: () => {},
})

export function useMe() {
  return useContext(MeContext)
}
