// Top bar (DESIGN.md §6): navigation, status, today's usage, theme and account.

import { AudioLines, LogOut, Monitor, Moon, Sun } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { useAuth } from '../lib/auth'
import { useMe } from '../lib/me'
import { navigate, usePath } from '../lib/router'
import { useAppStatus } from '../lib/status'
import { formatCount, formatShort } from '../lib/text'
import { useTheme } from '../lib/theme'
import { Link } from './Link'
import styles from './TopBar.module.css'

const THEME_ICON = { system: Monitor, dark: Moon, light: Sun }
const THEME_LABEL = { system: 'Theme: system', dark: 'Theme: dark', light: 'Theme: light' }

export function TopBar() {
  const path = usePath()
  const { status } = useAppStatus()
  const { me } = useMe()
  const [theme, cycleTheme] = useTheme()
  const ThemeIcon = THEME_ICON[theme]

  const used = me.chars_today / me.limits.daily_chars
  const meterLevel = used >= 1 ? 'error' : used >= 0.8 ? 'busy' : 'ok'

  return (
    <header className={styles.bar}>
      <Link href="/" className={styles.brand} aria-label="Kokoro TTS, home">
        <span className={styles.logo} aria-hidden>
          <AudioLines size={18} />
        </span>
        <span className={styles.name}>Kokoro TTS</span>
      </Link>
      <nav className={styles.nav} aria-label="Main">
        <Link href="/" aria-current={path === '/' ? 'page' : undefined}>
          Studio
        </Link>
        {me.signed_in && (
          <Link href="/history" aria-current={path === '/history' ? 'page' : undefined}>
            History
          </Link>
        )}
        <Link href="/about" aria-current={path === '/about' ? 'page' : undefined}>
          About
        </Link>
      </nav>
      <div className={styles.spacer} />
      <span className={styles.status} title={status.text}>
        <span className={`${styles.dot} ${styles[status.level]}`} aria-hidden />
        <span className={styles.statusText}>{status.text}</span>
      </span>
      <span
        className={`${styles.usage} ${styles[meterLevel]}`}
        title={`${formatCount(me.chars_today)} of ${formatCount(me.limits.daily_chars)} characters today`}
      >
        <span className={styles.usageTrack}>
          <span className={styles.usageFill} style={{ width: `${Math.min(1, used) * 100}%` }} />
        </span>
        <span className={styles.usageText}>
          {formatShort(me.chars_today)} / {formatShort(me.limits.daily_chars)} today
        </span>
      </span>
      <button
        className={styles.iconButton}
        onClick={cycleTheme}
        aria-label={THEME_LABEL[theme]}
        title={THEME_LABEL[theme]}
      >
        <ThemeIcon size={18} />
      </button>
      <Account />
    </header>
  )
}

function Account() {
  const { email, signOut } = useAuth()
  const [open, setOpen] = useState(false)
  const menu = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent | KeyboardEvent) => {
      const outside =
        e instanceof KeyboardEvent ? e.key === 'Escape' : !menu.current?.contains(e.target as Node)
      if (outside) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  if (!email) {
    return (
      <Link href="/signin" className={styles.signIn}>
        Sign in
      </Link>
    )
  }

  const go = (path: string) => {
    setOpen(false)
    navigate(path)
  }
  return (
    <div className={styles.account} ref={menu}>
      <button
        className={styles.avatar}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account: ${email}`}
      >
        {email[0].toUpperCase()}
      </button>
      {open && (
        <div className={styles.menu} role="menu">
          <span className={styles.menuEmail}>{email}</span>
          <button role="menuitem" onClick={() => go('/history')}>
            History
          </button>
          <button role="menuitem" onClick={() => go('/pronunciations')}>
            Pronunciations
          </button>
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false)
              void signOut()
            }}
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
      )}
    </div>
  )
}
