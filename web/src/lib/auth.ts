// Sign-in with Supabase (email link). The session lives in the browser; the API gets
// the access token on every request (see api/client.ts).

import { createClient, type Session } from '@supabase/supabase-js'
import { createContext, useContext } from 'react'

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY,
  { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } },
)

export interface AuthState {
  /** false until the stored session has been checked */
  ready: boolean
  session: Session | null
  email: string | null
  sendLink: (email: string) => Promise<void>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthState>({
  ready: false,
  session: null,
  email: null,
  sendLink: async () => {},
  signOut: async () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}
