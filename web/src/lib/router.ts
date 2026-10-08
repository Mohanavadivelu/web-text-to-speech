// A tiny History-API router: the app has a handful of static pages, so a routing
// library would be more than it needs.

import { useEffect, useState } from 'react'

const EVENT = 'app:navigate'

export function navigate(path: string): void {
  if (path === window.location.pathname) return
  window.history.pushState(null, '', path)
  window.dispatchEvent(new Event(EVENT))
  window.scrollTo(0, 0)
}

export function usePath(): string {
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const onChange = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onChange)
    window.addEventListener(EVENT, onChange)
    return () => {
      window.removeEventListener('popstate', onChange)
      window.removeEventListener(EVENT, onChange)
    }
  }, [])
  return path
}
