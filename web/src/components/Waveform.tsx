// Live waveform (DESIGN.md §8): bars fill in as audio arrives; click, drag or use the
// arrow keys to seek.

import { useEffect, useRef, type KeyboardEvent, type PointerEvent } from 'react'

import { LEVELS_PER_SECOND } from '../audio/player'
import { formatDuration } from '../lib/text'
import styles from './Waveform.module.css'

interface Props {
  levels: readonly number[]
  currentTime: number
  /** Seconds of audio available (seekable). */
  available: number
  /** Length to draw: the estimate while streaming, the real length when done. */
  total: number
  onSeek: (seconds: number) => void
}

const BAR = 2
const GAP = 1

function cssVar(el: Element, name: string): string {
  return getComputedStyle(el).getPropertyValue(name).trim()
}

export function Waveform({ levels, currentTime, available, total, onSeek }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const dragging = useRef(false)

  useEffect(() => {
    const el = canvas.current
    if (!el) return
    const draw = () => {
      const width = el.clientWidth
      const height = el.clientHeight
      const ratio = window.devicePixelRatio || 1
      el.width = Math.round(width * ratio)
      el.height = Math.round(height * ratio)
      const g = el.getContext('2d')
      if (!g) return
      g.setTransform(ratio, 0, 0, ratio, 0, 0)
      g.clearRect(0, 0, width, height)

      const colors = {
        played: cssVar(el, '--wave-played'),
        unplayed: cssVar(el, '--wave-unplayed'),
        pending: cssVar(el, '--wave-pending'),
      }
      const bars = Math.max(1, Math.floor(width / (BAR + GAP)))
      const span = Math.max(total, available, 0.001)
      const playedBars = (currentTime / span) * bars
      const availableBars = (available / span) * bars
      for (let i = 0; i < bars; i++) {
        let level = 0.06
        if (levels.length && i < availableBars) {
          const from = Math.floor((i / bars) * span * LEVELS_PER_SECOND)
          const to = Math.max(from + 1, Math.floor(((i + 1) / bars) * span * LEVELS_PER_SECOND))
          for (let j = from; j < to && j < levels.length; j++) level = Math.max(level, levels[j])
        } else if (!levels.length && i < availableBars) {
          level = 0.35 // finished file without level data: a plain track
        }
        g.fillStyle =
          i < playedBars ? colors.played : i < availableBars ? colors.unplayed : colors.pending
        const h = Math.max(2, level * height * 0.9)
        g.fillRect(i * (BAR + GAP), (height - h) / 2, BAR, h)
      }
    }
    draw()
    const observer = new ResizeObserver(draw)
    observer.observe(el)
    return () => observer.disconnect()
  }, [levels, levels.length, currentTime, available, total])

  const seekAt = (event: PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const fraction = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width))
    onSeek(Math.min(available, fraction * Math.max(total, available)))
  }

  const onKey = (event: KeyboardEvent) => {
    const step = { ArrowLeft: -5, ArrowRight: 5, Home: -Infinity, End: Infinity }[event.key]
    if (step === undefined) return
    event.preventDefault()
    onSeek(Math.min(available, Math.max(0, currentTime + step)))
  }

  const empty = available === 0 && total === 0
  return (
    <div className={styles.wrap}>
      <canvas
        ref={canvas}
        className={styles.canvas}
        role="slider"
        tabIndex={empty ? -1 : 0}
        aria-label="Playback position"
        aria-valuemin={0}
        aria-valuemax={Math.round(available)}
        aria-valuenow={Math.round(currentTime)}
        aria-valuetext={`${formatDuration(currentTime)} of ${formatDuration(Math.max(total, available))}`}
        onPointerDown={(e) => {
          if (empty) return
          dragging.current = true
          e.currentTarget.setPointerCapture(e.pointerId)
          seekAt(e)
        }}
        onPointerMove={(e) => dragging.current && seekAt(e)}
        onPointerUp={() => (dragging.current = false)}
        onKeyDown={onKey}
      />
      {empty && <span className={styles.empty}>Your audio will appear here</span>}
    </div>
  )
}
