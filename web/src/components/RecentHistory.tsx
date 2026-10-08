// Recent audio for the Studio's History tab (and the phone's history sheet). Items play
// in the shared player bar; the full list is on the History page.

import { Download, Pause, Play } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api, type HistoryItem } from '../api/client'
import { usePlayer } from '../audio/usePlayer'
import { useMe } from '../lib/me'
import { usePlayback } from '../lib/playback'
import { formatCount, formatDuration } from '../lib/text'
import { trackTitle } from '../lib/voices'
import { Link } from './Link'
import styles from './RecentHistory.module.css'

const SHOWN = 8

function dayLabel(iso: string): string {
  const date = new Date(iso)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  if (date.toDateString() === today.toDateString()) return 'Today'
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return date.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'short' })
}

export function RecentHistory() {
  const { me } = useMe()
  const playback = usePlayback()
  const nowPlaying = usePlayer(
    playback.showing === 'track' ? (playback.track?.player ?? null) : null,
  )
  const [items, setItems] = useState<HistoryItem[] | null>(null)
  const jobDone = playback.speech.status === 'ready' ? playback.speech.job?.id : null

  // Load when signed in, and again whenever a job finishes
  useEffect(() => {
    if (!me.signed_in) return
    let alive = true
    api
      .history()
      .then((h) => alive && setItems(h.items.slice(0, SHOWN)))
      .catch(() => alive && setItems([]))
    return () => {
      alive = false
    }
  }, [me.signed_in, jobDone])

  if (!me.signed_in) {
    return (
      <div className={styles.signedOut}>
        <p>Sign in to keep your audio for 7 days and play it again from here.</p>
        <Link href="/signin" className={styles.button}>
          Sign in
        </Link>
      </div>
    )
  }
  if (items === null) return <p className={styles.note}>Loading…</p>
  if (items.length === 0) {
    return <p className={styles.note}>Audio you generate shows up here for 7 days.</p>
  }

  const playingId =
    nowPlaying && ['playing', 'buffering'].includes(nowPlaying.state) ? playback.track?.id : null

  const toggle = (item: HistoryItem) => {
    if (!item.url) return
    if (playback.showing === 'track' && playback.track?.id === item.id) {
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
      title: trackTitle(item),
    })
  }

  // Day headings: shown above the first item of each day
  const rows = items.map((item, i) => {
    const day = dayLabel(item.created_at)
    return { item, heading: i === 0 || dayLabel(items[i - 1].created_at) !== day ? day : null }
  })
  return (
    <div className={styles.recent}>
      <ul className={styles.list}>
        {rows.map(({ item, heading }) => {
          return (
            <li key={item.id}>
              {heading && <h3 className={styles.day}>{heading}</h3>}
              <div className={styles.row}>
                <button
                  className={styles.play}
                  onClick={() => toggle(item)}
                  aria-label={playingId === item.id ? 'Pause' : `Play ${trackTitle(item)}`}
                >
                  {playingId === item.id ? <Pause size={14} /> : <Play size={14} />}
                </button>
                <span className={styles.meta}>
                  <span className={styles.title}>
                    {trackTitle(item)} <span>{formatDuration(item.audio_seconds ?? 0)}</span>
                  </span>
                  <span className={styles.sub}>
                    {new Date(item.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}{' '}
                    · {formatCount(item.chars)} chars
                  </span>
                </span>
                {item.url && (
                  <a className={styles.download} href={item.url} download aria-label="Download MP3">
                    <Download size={15} />
                  </a>
                )}
              </div>
            </li>
          )
        })}
      </ul>
      <Link href="/history" className={styles.all}>
        See all history →
      </Link>
    </div>
  )
}
