// Audio playback for the studio.
//
// StreamPlayer plays audio while it's still being generated: each PCM chunk from the
// WebSocket is scheduled on the Web Audio clock right after the previous one, so
// there are no gaps. If generation falls behind playback, it waits ("buffering")
// and carries on when the next chunk arrives. Seeking works within what has arrived.
//
// UrlPlayer plays a finished file (e.g. a result served from the cache) through an
// <audio> element.

import { peaks, SAMPLE_RATE } from './pcm'

export type PlayerState = 'idle' | 'buffering' | 'playing' | 'paused' | 'ended'

export interface Player {
  readonly state: PlayerState
  readonly currentTime: number
  /** Seconds available so far (the full length once `complete`). */
  readonly duration: number
  /** All audio has arrived. */
  readonly complete: boolean
  /** Waveform levels (0–1), LEVELS_PER_SECOND per second of audio received. */
  readonly levels: readonly number[]
  play(): void
  pause(): void
  seek(seconds: number): void
  setVolume(volume: number): void
  subscribe(listener: () => void): () => void
  destroy(): void
}

export const LEVELS_PER_SECOND = 20
const SAMPLES_PER_LEVEL = SAMPLE_RATE / LEVELS_PER_SECOND
const START_DELAY = 0.05 // seconds of headroom when (re)starting the schedule

abstract class Emitter {
  private listeners = new Set<() => void>()

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  protected emit(): void {
    this.listeners.forEach((l) => l())
  }
}

export class StreamPlayer extends Emitter implements Player {
  private ctx: AudioContext
  private gain: GainNode
  private chunks: { samples: Float32Array<ArrayBuffer>; offset: number }[] = []
  private received = 0 // samples
  private sources: AudioBufferSourceNode[] = []
  private ctxStart = 0 // AudioContext time at which audio position 0 plays
  private pausedAt = 0 // position while not playing
  private playing = false
  private finished = false
  private levelValues: number[] = []
  private timer: number | null = null

  /** Create inside a user gesture (e.g. the Generate click) so the browser allows audio. */
  constructor(contextFactory: () => AudioContext = () => new AudioContext()) {
    super()
    this.ctx = contextFactory()
    this.gain = this.ctx.createGain()
    this.gain.connect(this.ctx.destination)
  }

  get complete() {
    return this.finished
  }

  get duration() {
    return this.received / SAMPLE_RATE
  }

  get levels() {
    return this.levelValues
  }

  get currentTime() {
    if (!this.playing) return this.pausedAt
    return Math.min(Math.max(0, this.ctx.currentTime - this.ctxStart), this.duration)
  }

  get state(): PlayerState {
    if (this.received === 0 && !this.playing) return 'idle'
    if (!this.playing) return this.finished && this.pausedAt >= this.duration ? 'ended' : 'paused'
    return !this.finished && this.currentTime >= this.duration - 0.01 ? 'buffering' : 'playing'
  }

  /** Add the next chunk of audio. */
  append(samples: Float32Array<ArrayBuffer>): void {
    if (!samples.length) return
    const offset = this.received
    const caughtUp = this.playing && this.ctx.currentTime >= this.ctxStart + offset / SAMPLE_RATE
    this.chunks.push({ samples, offset })
    this.received += samples.length
    this.levelValues.push(...peaks(samples, SAMPLES_PER_LEVEL))
    if (this.playing) {
      if (caughtUp) {
        // Playback had reached the end of the audio: continue from here, without a jump
        this.ctxStart = this.ctx.currentTime + START_DELAY - offset / SAMPLE_RATE
      }
      this.scheduleChunk(this.chunks.length - 1)
    }
    this.emit()
  }

  /** No more audio will arrive. */
  finish(): void {
    this.finished = true
    this.emit()
  }

  /** Discard everything (e.g. the job was retried from the start). */
  reset(): void {
    this.stopSources()
    this.chunks = []
    this.received = 0
    this.levelValues = []
    this.pausedAt = 0
    this.finished = false
    if (this.playing) this.ctxStart = this.ctx.currentTime + START_DELAY
    this.emit()
  }

  play(): void {
    if (this.playing) return
    void this.ctx.resume()
    if (this.finished && this.pausedAt >= this.duration) this.pausedAt = 0
    this.playing = true
    this.ctxStart = this.ctx.currentTime + START_DELAY - this.pausedAt
    this.chunks.forEach((_, i) => this.scheduleChunk(i))
    this.startTimer()
    this.emit()
  }

  pause(): void {
    if (!this.playing) return
    this.pausedAt = this.currentTime
    this.playing = false
    this.stopSources()
    this.stopTimer()
    this.emit()
  }

  seek(seconds: number): void {
    const target = Math.min(Math.max(0, seconds), this.duration)
    if (this.playing) {
      this.stopSources()
      this.ctxStart = this.ctx.currentTime + START_DELAY - target
      this.chunks.forEach((_, i) => this.scheduleChunk(i))
    } else {
      this.pausedAt = target
    }
    this.emit()
  }

  setVolume(volume: number): void {
    this.gain.gain.value = Math.min(1, Math.max(0, volume))
  }

  destroy(): void {
    this.stopSources()
    this.stopTimer()
    void this.ctx.close()
  }

  private scheduleChunk(index: number): void {
    const { samples, offset } = this.chunks[index]
    const startsAt = this.ctxStart + offset / SAMPLE_RATE
    const chunkSeconds = samples.length / SAMPLE_RATE
    const now = this.ctx.currentTime
    if (startsAt + chunkSeconds <= now) return // already played past it
    const skip = Math.max(0, now - startsAt)
    const buffer = this.ctx.createBuffer(1, samples.length, SAMPLE_RATE)
    buffer.copyToChannel(samples, 0)
    const source = this.ctx.createBufferSource()
    source.buffer = buffer
    source.connect(this.gain)
    source.start(Math.max(now, startsAt), skip)
    source.onended = () => {
      this.sources = this.sources.filter((s) => s !== source)
    }
    this.sources.push(source)
  }

  private stopSources(): void {
    for (const source of this.sources) {
      try {
        source.stop()
      } catch {
        // already stopped
      }
    }
    this.sources = []
  }

  // While playing, notify listeners regularly (time display, waveform) and detect the end.
  private startTimer(): void {
    this.stopTimer()
    this.timer = window.setInterval(() => {
      if (this.playing && this.finished && this.currentTime >= this.duration - 0.005) {
        this.pausedAt = this.duration
        this.playing = false
        this.stopSources()
        this.stopTimer()
      }
      this.emit()
    }, 100)
  }

  private stopTimer(): void {
    if (this.timer !== null) window.clearInterval(this.timer)
    this.timer = null
  }
}

export class UrlPlayer extends Emitter implements Player {
  private audio: HTMLAudioElement
  readonly complete = true
  readonly levels: readonly number[] = []

  constructor(url: string) {
    super()
    this.audio = new Audio(url)
    this.audio.preload = 'auto'
    for (const event of [
      'play',
      'pause',
      'ended',
      'timeupdate',
      'loadedmetadata',
      'waiting',
      'playing',
    ]) {
      this.audio.addEventListener(event, () => this.emit())
    }
  }

  get state(): PlayerState {
    if (this.audio.ended) return 'ended'
    if (this.audio.paused) return 'paused'
    return this.audio.readyState < 3 ? 'buffering' : 'playing'
  }

  get currentTime() {
    return this.audio.currentTime
  }

  get duration() {
    return Number.isFinite(this.audio.duration) ? this.audio.duration : 0
  }

  play(): void {
    void this.audio.play()
  }

  pause(): void {
    this.audio.pause()
  }

  seek(seconds: number): void {
    this.audio.currentTime = Math.min(Math.max(0, seconds), this.duration || 0)
  }

  setVolume(volume: number): void {
    this.audio.volume = Math.min(1, Math.max(0, volume))
  }

  destroy(): void {
    this.audio.pause()
    this.audio.src = ''
  }
}
