// One speech job at a time: create it, follow its stream, feed the player.
// States follow docs/DESIGN.md §13.

import { useCallback, useEffect, useRef, useState } from 'react'

import { api, ApiError, streamUrl, type Job, type JobCreate } from '../api/client'
import { pcm16ToFloat32 } from './pcm'
import { StreamPlayer, UrlPlayer, type Player } from './player'

export type JobStatus = 'idle' | 'queued' | 'streaming' | 'ready' | 'cancelled' | 'error'

export interface SpeechJob {
  status: JobStatus
  job: Job | null
  progress: number
  queuePosition: number | null
  estimatedSeconds: number
  url: string | null
  error: ApiError | null
  player: Player | null
}

const IDLE: SpeechJob = {
  status: 'idle',
  job: null,
  progress: 0,
  queuePosition: null,
  estimatedSeconds: 0,
  url: null,
  error: null,
  player: null,
}

const MAX_RECONNECTS = 3

type StreamEvent =
  | { type: 'started'; sample_rate: number; estimated_seconds: number }
  | { type: 'progress'; percent: number }
  | { type: 'done'; duration: number; url: string }
  | { type: 'error'; message: string }
  | { type: 'cancelled' }

export function useSpeechJob(onFinished?: (state: SpeechJob) => void) {
  const [state, setState] = useState<SpeechJob>(IDLE)
  const socket = useRef<WebSocket | null>(null)
  const pollTimer = useRef<number | null>(null)
  const playerRef = useRef<Player | null>(null)
  const finishedRef = useRef(onFinished)
  useEffect(() => {
    finishedRef.current = onFinished
  }, [onFinished])

  const update = useCallback((patch: Partial<SpeechJob>) => {
    setState((prev) => ({ ...prev, ...patch }))
  }, [])

  // Tell the page when a job ends. This runs in an effect, not inside setState: React
  // may call state updaters twice (Strict Mode), which would report the end twice.
  const lastStatus = useRef<JobStatus>('idle')
  useEffect(() => {
    const ended = ['ready', 'cancelled', 'error'].includes(state.status)
    if (ended && state.status !== lastStatus.current) finishedRef.current?.(state)
    lastStatus.current = state.status
  }, [state])

  const stopFollowing = useCallback(() => {
    if (pollTimer.current !== null) window.clearInterval(pollTimer.current)
    pollTimer.current = null
    if (socket.current) {
      socket.current.onclose = null
      socket.current.close()
      socket.current = null
    }
  }, [])

  const follow = useCallback(
    // `kept` = audio bytes already received on earlier connections. The server replays
    // a job from the start on every connection, so that much replayed audio is skipped.
    function followStream(job: Job, player: StreamPlayer, attempt = 0, kept = 0) {
      let finalSeen = false
      let messages = 0
      let replayed = 0 // audio bytes seen on this connection
      let received = kept
      const ws = new WebSocket(streamUrl(job.stream_url))
      ws.binaryType = 'arraybuffer'
      socket.current = ws

      ws.onmessage = (message) => {
        messages += 1
        if (message.data instanceof ArrayBuffer) {
          let data = message.data
          if (replayed < kept) {
            const skip = Math.min(kept - replayed, data.byteLength)
            replayed += data.byteLength
            if (skip === data.byteLength) return
            data = data.slice(skip)
          }
          if (received === 0) update({ status: 'streaming', queuePosition: null })
          received += data.byteLength
          player.append(pcm16ToFloat32(data))
          return
        }
        const event = JSON.parse(message.data as string) as StreamEvent
        switch (event.type) {
          case 'started':
            // "started" in the middle of a connection means the job was retried from the
            // start (a worker failed): drop the audio so far. As the first message of a
            // connection it's just the replay after (re)connecting.
            if (messages > 1) {
              player.reset()
              received = 0
              kept = 0
            }
            update({ estimatedSeconds: event.estimated_seconds })
            break
          case 'progress':
            update({ progress: event.percent })
            break
          case 'done':
            finalSeen = true
            player.finish()
            update({ status: 'ready', progress: 100, url: event.url })
            break
          case 'error':
            finalSeen = true
            player.finish()
            update({ status: 'error', error: new ApiError('internal', event.message) })
            break
          case 'cancelled':
            finalSeen = true
            player.pause()
            player.finish()
            update({ status: 'cancelled' })
            break
        }
      }

      ws.onclose = () => {
        if (finalSeen || socket.current !== ws) return
        if (attempt < MAX_RECONNECTS) {
          window.setTimeout(
            () => followStream(job, player, attempt + 1, received),
            500 * 2 ** attempt,
          )
        } else {
          update({
            status: 'error',
            error: new ApiError('network', 'Connection lost. Please try again.'),
          })
        }
      }
    },
    [update],
  )

  /** Call from a click/keypress handler: browsers only allow audio after a user gesture. */
  const generate = useCallback(
    async (body: JobCreate) => {
      stopFollowing()
      playerRef.current?.destroy()
      const player = new StreamPlayer()
      playerRef.current = player
      player.play() // plays as soon as audio arrives
      setState({ ...IDLE, status: 'queued', player, estimatedSeconds: 0 })

      let job: Job
      try {
        job = await api.createJob(body)
      } catch (err) {
        player.destroy()
        playerRef.current = null
        const error = err instanceof ApiError ? err : new ApiError('internal', String(err))
        update({ status: 'error', error, player: null })
        return
      }

      if (job.status === 'done' && job.url) {
        // Served from the cache: play the finished file
        player.destroy()
        const cached = new UrlPlayer(job.url)
        playerRef.current = cached
        cached.play()
        update({
          job,
          status: 'ready',
          progress: 100,
          url: job.url,
          player: cached,
          estimatedSeconds: job.estimated_seconds ?? 0,
        })
        return
      }

      update({
        job,
        queuePosition: job.queue_position ?? null,
        estimatedSeconds: job.estimated_seconds ?? 0,
      })
      follow(job, player)
      // While waiting in the queue, refresh the position now and then
      pollTimer.current = window.setInterval(async () => {
        try {
          const latest = await api.getJob(job.id)
          if (latest.status !== 'queued') {
            if (pollTimer.current !== null) window.clearInterval(pollTimer.current)
            pollTimer.current = null
          } else {
            setState((prev) =>
              prev.status === 'queued'
                ? { ...prev, queuePosition: latest.queue_position ?? null }
                : prev,
            )
          }
        } catch {
          // the stream will report problems
        }
      }, 2000)
    },
    [follow, stopFollowing, update],
  )

  const cancel = useCallback(async () => {
    const id = state.job?.id
    if (!id) return
    try {
      await api.cancelJob(id) // the "cancelled" event arrives on the stream
    } catch {
      stopFollowing()
      playerRef.current?.pause()
      update({ status: 'cancelled' })
    }
  }, [state.job, stopFollowing, update])

  useEffect(
    () => () => {
      stopFollowing()
      playerRef.current?.destroy()
    },
    [stopFollowing],
  )

  return { ...state, generate, cancel }
}
