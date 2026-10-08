/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL: string
  readonly VITE_SUPABASE_PUBLISHABLE_KEY: string
  readonly VITE_TURNSTILE_SITE_KEY?: string
  readonly VITE_MAIL_INBOX_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
