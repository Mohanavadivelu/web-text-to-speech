// Sign in, History and Pronunciations.

import { Download, Mail, Pause, Play, Plus, Settings2, Trash2 } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'

import { api, ApiError, type HistoryItem, type Pronunciation } from '../api/client'
import { usePlayer } from '../audio/usePlayer'
import { Link } from '../components/Link'
import { useAuth } from '../lib/auth'
import { usePlayback } from '../lib/playback'
import { navigate } from '../lib/router'
import { DEFAULT_SETTINGS, type VoiceSettings } from '../lib/settings'
import { save } from '../lib/storage'
import { formatCount, formatDuration } from '../lib/text'
import { useToast } from '../lib/toast'
import styles from './AccountPages.module.css'

const INBOX = import.meta.env.DEV ? import.meta.env.VITE_MAIL_INBOX_URL : undefined
const LANGUAGE_NAMES: Record<string, string> = {
  a: 'US English',
  b: 'UK English',
  h: 'Hindi',
  f: 'French',
  i: 'Italian',
  e: 'Spanish',
  p: 'Portuguese',
}

/** Pages that need an account send visitors to sign in first. */
function useRequireAccount(): boolean {
  const { ready, email } = useAuth()
  useEffect(() => {
    if (ready && !email) navigate('/signin')
  }, [ready, email])
  return ready && !!email
}

// ── Sign in ──────────────────────────────────────────────────────────────────
export function SignIn() {
  const { ready, email: signedInAs, sendLink } = useAuth()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (ready && signedInAs) navigate('/')
  }, [ready, signedInAs])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await sendLink(email.trim())
      setSent(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <h1>Sign in</h1>
        <p className={styles.lead}>
          Signing in gives you longer texts (20,000 characters), opening documents, WAV downloads,
          saved pronunciations and a 7-day history.
        </p>
        {sent ? (
          <div className={styles.sent} role="status">
            <Mail size={20} />
            <div>
              <strong>Check your email.</strong> We sent a sign-in link to {email}. Open it on this
              device.
              {INBOX && (
                <p className={styles.devHint}>
                  Development: the email is in the{' '}
                  <a href={INBOX} target="_blank" rel="noreferrer">
                    local inbox
                  </a>
                  .
                </p>
              )}
            </div>
          </div>
        ) : (
          <form onSubmit={(e) => void submit(e)} className={styles.form}>
            <label className={styles.field}>
              <span>Email</span>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </label>
            {error && (
              <p className={styles.error} role="alert">
                {error}
              </p>
            )}
            <button className={styles.primary} disabled={busy}>
              {busy ? 'Sending…' : 'Email me a sign-in link'}
            </button>
          </form>
        )}
        <p className={styles.small}>
          No password needed. <Link href="/privacy">How we handle your data</Link>
        </p>
      </div>
    </div>
  )
}

// ── History ──────────────────────────────────────────────────────────────────
export function History() {
  const allowed = useRequireAccount()
  const toast = useToast()
  const [items, setItems] = useState<HistoryItem[] | null>(null)
  const [days, setDays] = useState(7)
  const playback = usePlayback()
  const nowPlaying = usePlayer(
    playback.showing === 'track' ? (playback.track?.player ?? null) : null,
  )
  const playingId =
    nowPlaying && ['playing', 'buffering'].includes(nowPlaying.state) ? playback.track?.id : null

  useEffect(() => {
    if (!allowed) return
    api
      .history()
      .then((h) => {
        setItems(h.items)
        setDays(h.days)
      })
      .catch((err: unknown) => {
        setItems([])
        if (err instanceof ApiError) toast({ kind: 'error', message: err.message })
      })
  }, [allowed, toast])

  const toggle = (item: HistoryItem) => {
    if (!item.url) return
    if (playback.showing === 'track' && playback.track?.id === item.id) {
      // Same item: pause or resume it in the player bar
      const player = playback.track.player
      if (player.state === 'playing' || player.state === 'buffering') player.pause()
      else player.play()
      return
    }
    playback.playTrack({
      id: item.id,
      url: item.url,
      wavUrl: item.wav_url,
      seconds: item.audio_seconds,
      title: `${voiceName(item.voice)} · ${LANGUAGE_NAMES[item.lang] ?? item.lang}`,
    })
  }

  const applySettings = (item: HistoryItem) => {
    const settings: VoiceSettings = {
      ...DEFAULT_SETTINGS,
      lang: item.lang,
      voice: item.voice,
      blendVoice: item.blend_voice,
      blendRatio: item.blend_ratio ?? DEFAULT_SETTINGS.blendRatio,
      speed: item.speed,
      pitch: item.pitch,
    }
    save('kokoro.voice-settings', settings)
    navigate('/')
  }

  if (!allowed) return null
  const groups = groupByDay(items ?? [])

  return (
    <div className={styles.page}>
      <div className={styles.wide}>
        <h1>History</h1>
        <p className={styles.lead}>
          Audio you made in the last {days} days. Your text is never stored.
        </p>
        {items === null ? (
          <p className={styles.small}>Loading…</p>
        ) : items.length === 0 ? (
          <p className={styles.empty}>
            Nothing here yet. Audio you generate is kept for {days} days.{' '}
            <Link href="/">Go to the Studio</Link>
          </p>
        ) : (
          groups.map(([day, rows]) => (
            <section key={day} className={styles.group}>
              <h2>{day}</h2>
              <ul className={styles.list}>
                {rows.map((item) => (
                  <li key={item.id} className={styles.row}>
                    <button
                      className={styles.play}
                      onClick={() => toggle(item)}
                      aria-label={playingId === item.id ? 'Pause' : 'Play'}
                    >
                      {playingId === item.id ? <Pause size={16} /> : <Play size={16} />}
                    </button>
                    <span className={styles.meta}>
                      <strong>{voiceName(item.voice)}</strong>
                      {item.blend_voice ? ` + ${voiceName(item.blend_voice)}` : ''} ·{' '}
                      {LANGUAGE_NAMES[item.lang] ?? item.lang} ·{' '}
                      {formatDuration(item.audio_seconds ?? 0)} · {formatCount(item.chars)} chars ·{' '}
                      {new Date(item.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                    <span className={styles.actions}>
                      {item.url && (
                        <a href={item.url} download className={styles.link}>
                          <Download size={14} /> MP3
                        </a>
                      )}
                      {item.wav_url && (
                        <a href={item.wav_url} download className={styles.link}>
                          WAV
                        </a>
                      )}
                      <button className={styles.link} onClick={() => applySettings(item)}>
                        <Settings2 size={14} /> Use these settings
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))
        )}
      </div>
    </div>
  )
}

function voiceName(id: string): string {
  const name = id.split('_')[1] ?? id
  return name.charAt(0).toUpperCase() + name.slice(1)
}

function groupByDay(items: HistoryItem[]): [string, HistoryItem[]][] {
  const groups = new Map<string, HistoryItem[]>()
  for (const item of items) {
    const day = new Date(item.created_at).toLocaleDateString([], {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
    })
    groups.set(day, [...(groups.get(day) ?? []), item])
  }
  return [...groups.entries()]
}

// ── Pronunciations ───────────────────────────────────────────────────────────
export function Pronunciations() {
  const allowed = useRequireAccount()
  const toast = useToast()
  const [rows, setRows] = useState<Pronunciation[] | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!allowed) return
    api
      .pronunciations()
      .then((p) => setRows(p.entries))
      .catch(() => setRows([]))
  }, [allowed])

  if (!allowed) return null

  const update = (index: number, patch: Partial<Pronunciation>) =>
    setRows((all) => (all ?? []).map((row, i) => (i === index ? { ...row, ...patch } : row)))

  const saveAll = async () => {
    const entries = (rows ?? []).filter((r) => r.word.trim() && r.say.trim())
    setSaving(true)
    try {
      const saved = await api.savePronunciations(entries)
      setRows(saved.entries)
      toast({ kind: 'success', message: 'Pronunciations saved. They apply to your next jobs.' })
    } catch (err) {
      toast({ kind: 'error', message: err instanceof ApiError ? err.message : String(err) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.wide}>
        <h1>Pronunciations</h1>
        <p className={styles.lead}>
          Tell the voice how to say names and acronyms. Write how it sounds (&ldquo;Kokoro&rdquo; →
          &ldquo;koh koh roh&rdquo;), or phonemes between slashes (<code>/kˈOkəɹO/</code>, English
          voices only).
        </p>
        {rows === null ? (
          <p className={styles.small}>Loading…</p>
        ) : (
          <>
            <div className={styles.table} role="table" aria-label="Pronunciations">
              {rows.map((row, i) => (
                <div className={styles.tableRow} role="row" key={i}>
                  <input
                    aria-label="Word"
                    placeholder="Word"
                    value={row.word}
                    maxLength={100}
                    onChange={(e) => update(i, { word: e.target.value })}
                  />
                  <span aria-hidden>→</span>
                  <input
                    aria-label="Say as"
                    placeholder="Say as"
                    value={row.say}
                    maxLength={200}
                    onChange={(e) => update(i, { say: e.target.value })}
                  />
                  <button
                    className={styles.iconButton}
                    onClick={() => setRows((all) => (all ?? []).filter((_, j) => j !== i))}
                    aria-label={`Remove ${row.word || 'row'}`}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
              {rows.length === 0 && <p className={styles.empty}>No pronunciations yet.</p>}
            </div>
            <div className={styles.buttons}>
              <button
                className={styles.secondary}
                onClick={() => setRows((all) => [...(all ?? []), { word: '', say: '' }])}
                disabled={rows.length >= 200}
              >
                <Plus size={16} /> Add
              </button>
              <button className={styles.primary} onClick={() => void saveAll()} disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
