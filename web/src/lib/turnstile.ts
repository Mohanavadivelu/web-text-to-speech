// Cloudflare Turnstile: proves an anonymous visitor is a person (Stage 1 plan §10).
// The widget is invisible unless Cloudflare needs the visitor to click a checkbox.
// Each token works once, so a fresh one is fetched for every job.

const SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY
const SCRIPT = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'

interface TurnstileApi {
  render: (el: HTMLElement, options: Record<string, unknown>) => string
  execute: (widget: string) => void
  reset: (widget: string) => void
}

declare global {
  interface Window {
    turnstile?: TurnstileApi
  }
}

let loading: Promise<TurnstileApi> | null = null
let widget: string | null = null
let pending: { resolve: (token: string) => void; reject: (err: Error) => void } | null = null

function load(): Promise<TurnstileApi> {
  loading ??= new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = SCRIPT
    script.async = true
    script.onload = () =>
      window.turnstile ? resolve(window.turnstile) : reject(new Error('Turnstile failed to load'))
    script.onerror = () => {
      loading = null
      reject(new Error("Couldn't load the robot check. Check your connection."))
    }
    document.head.appendChild(script)
  })
  return loading
}

/** A one-time token, or null when no site key is configured (development without Turnstile). */
export async function getBotToken(): Promise<string | null> {
  if (!SITE_KEY) return null
  const api = await load()
  if (widget === null) {
    const host = document.createElement('div')
    host.className = 'turnstile-host'
    document.body.appendChild(host)
    widget = api.render(host, {
      sitekey: SITE_KEY,
      execution: 'execute',
      appearance: 'interaction-only',
      callback: (token: string) => pending?.resolve(token),
      'error-callback': () =>
        pending?.reject(new Error('The robot check failed. Please try again.')),
    })
  } else {
    api.reset(widget)
  }
  return new Promise<string>((resolve, reject) => {
    pending = { resolve, reject }
    api.execute(widget as string)
  })
}
