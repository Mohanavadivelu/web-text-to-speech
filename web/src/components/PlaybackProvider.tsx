// Holds the speech job and the player for the whole app, so playback survives
// moving between pages. Also owns what belongs to the job rather than a page: the
// status dot, finished-job toasts, screen-reader announcements, the leave-page
// warning and the Space play/pause shortcut.

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { UrlPlayer } from '../audio/player'
import { useSpeechJob, type SpeechJob } from '../audio/useSpeechJob'
import { errorToast } from '../lib/errors'
import { useMe } from '../lib/me'
import { activePlayer, PlaybackContext, type Playback, type Track } from '../lib/playback'
import { useAppStatus } from '../lib/status'
import { formatDuration } from '../lib/text'
import { useToast } from '../lib/toast'

export function PlaybackProvider({ children }: { children: ReactNode }) {
  const toast = useToast()
  const { refresh: refreshMe } = useMe()
  const { setStatus } = useAppStatus()
  const [showing, setShowing] = useState<'job' | 'track'>('job')
  const [track, setTrack] = useState<Track | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const showingRef = useRef(showing)
  useEffect(() => {
    showingRef.current = showing
  }, [showing])

  const showJobRef = useRef<() => void>(() => {})

  const onFinished = useCallback(
    (job: SpeechJob) => {
      refreshMe() // today's usage changed
      if (job.status === 'ready') {
        const seconds = job.player?.duration || job.job?.audio_seconds || 0
        const elsewhere = showingRef.current === 'track'
        toast({
          kind: 'success',
          message: `Audio ready${seconds ? `: ${formatDuration(seconds)}` : ''}.`,
          action: elsewhere ? { label: 'Play', run: () => showJobRef.current() } : undefined,
        })
        setAnnouncement('Audio ready.')
      } else if (job.status === 'cancelled') {
        toast({ kind: 'info', message: 'Stopped.' })
        setAnnouncement('Generation stopped.')
      } else if (job.status === 'error' && job.error) {
        toast(errorToast(job.error))
        setAnnouncement(job.error.message)
      }
    },
    [toast, refreshMe],
  )
  const speech = useSpeechJob(onFinished)
  const busy = speech.status === 'queued' || speech.status === 'streaming'

  // The current track lives in a ref too: creating and destroying players must not
  // happen inside state updaters, which React may run twice
  const trackRef = useRef<Track | null>(null)
  const stopTrack = useCallback(() => {
    trackRef.current?.player.destroy()
    trackRef.current = null
    setTrack(null)
  }, [])

  const generate = useCallback<Playback['generate']>(
    (body, getBotToken) => {
      stopTrack()
      setShowing('job')
      setAnnouncement('Generating speech…')
      void speech.generate(body, getBotToken)
    },
    [speech, stopTrack],
  )

  const playTrack = useCallback<Playback['playTrack']>(
    (input) => {
      speech.player?.pause()
      trackRef.current?.player.destroy()
      const player = new UrlPlayer(input.url)
      player.play()
      const next = { ...input, player }
      trackRef.current = next
      setTrack(next)
      setShowing('track')
    },
    [speech.player],
  )

  const showJob = useCallback(() => {
    stopTrack()
    setShowing('job')
    speech.player?.play()
  }, [speech.player, stopTrack])
  useEffect(() => {
    showJobRef.current = showJob
  }, [showJob])

  useEffect(() => () => trackRef.current?.player.destroy(), [])

  // Status dot in the top bar, whichever page is open
  useEffect(() => {
    if (speech.status === 'queued') {
      setStatus({
        level: 'busy',
        text: speech.queuePosition ? `Waiting · ${speech.queuePosition} ahead` : 'Starting…',
      })
    } else if (speech.status === 'streaming') {
      setStatus({ level: 'busy', text: `Generating ${speech.progress}%` })
    } else if (speech.status === 'error') {
      setStatus({ level: 'error', text: 'Error' })
    } else {
      setStatus({ level: 'ok', text: 'Ready' })
    }
  }, [speech.status, speech.progress, speech.queuePosition, setStatus])

  // Leaving the site while a job runs loses it (anonymous visitors can't find it again)
  useEffect(() => {
    if (!busy) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [busy])

  const value = useMemo<Playback>(
    () => ({
      speech,
      showing,
      track,
      generate,
      playTrack,
      showJob,
      announce: setAnnouncement,
    }),
    [speech, showing, track, generate, playTrack, showJob],
  )

  // Space (outside text fields) or Ctrl/⌘+Space: play or pause, on every page
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey
      const inField = (e.target as HTMLElement).closest('textarea, input, select, button, a')
      if (e.code !== 'Space' || (!mod && inField)) return
      const player = activePlayer(value)
      if (!player) return
      e.preventDefault()
      if (player.state === 'playing' || player.state === 'buffering') player.pause()
      else player.play()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [value])

  // Progress in quarters while streaming; other moments come from `announcement`
  const quarter = Math.floor(speech.progress / 25) * 25
  const liveMessage =
    speech.status === 'streaming' && quarter > 0 && quarter < 100
      ? `Generating, ${quarter}%`
      : announcement

  return (
    <PlaybackContext.Provider value={value}>
      {children}
      <div className="visually-hidden" aria-live="polite">
        {liveMessage}
      </div>
    </PlaybackContext.Provider>
  )
}
