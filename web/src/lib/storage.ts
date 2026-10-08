// localStorage for per-visitor conveniences (draft, settings, theme).
// It can be unavailable (private windows, blocked storage), so every access is guarded.

export function load<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

export function save(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // storage full or blocked: the app works without it
  }
}
