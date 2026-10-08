// Top bar (DESIGN.md §6). Usage meter and account menu arrive with accounts (M5).

import { AudioLines, Monitor, Moon, Sun } from 'lucide-react'

import { usePath } from '../lib/router'
import { Link } from './Link'
import { useAppStatus } from '../lib/status'
import { useTheme } from '../lib/theme'
import styles from './TopBar.module.css'

const THEME_ICON = { system: Monitor, dark: Moon, light: Sun }
const THEME_LABEL = { system: 'Theme: system', dark: 'Theme: dark', light: 'Theme: light' }

export function TopBar() {
  const path = usePath()
  const { status } = useAppStatus()
  const [theme, cycleTheme] = useTheme()
  const ThemeIcon = THEME_ICON[theme]

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
        <Link href="/about" aria-current={path === '/about' ? 'page' : undefined}>
          About
        </Link>
      </nav>
      <div className={styles.spacer} />
      <span className={styles.status} title={status.text}>
        <span className={`${styles.dot} ${styles[status.level]}`} aria-hidden />
        <span className={styles.statusText}>{status.text}</span>
      </span>
      <button
        className={styles.iconButton}
        onClick={cycleTheme}
        aria-label={THEME_LABEL[theme]}
        title={THEME_LABEL[theme]}
      >
        <ThemeIcon size={18} />
      </button>
    </header>
  )
}
