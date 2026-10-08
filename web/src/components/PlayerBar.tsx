// Player bar (DESIGN.md §8): play/pause, time, live waveform, volume, download.

import { Download, Loader2, Pause, Play, Volume2, VolumeX } from 'lucide-react'
import { useEffect, useState } from 'react'

import type { Player } from '../audio/player'
import { usePlayer } from '../audio/usePlayer'
import { formatDuration } from '../lib/text'
import styles from './PlayerBar.module.css'
import { Waveform } from './Waveform'

interface Props {
  player: Player | null
  estimatedSeconds: number
  downloadUrl: string | null
}

export function PlayerBar({ player: source, estimatedSeconds, downloadUrl }: Props) {
  const player = usePlayer(source)
  const [volume, setVolume] = useState(1)
  const [muted, setMuted] = useState(false)

  useEffect(() => player?.setVolume(muted ? 0 : volume), [player, volume, muted])

  const state = player?.state ?? 'idle'
  const time = player?.currentTime ?? 0
  const available = player?.duration ?? 0
  const total = player?.complete ? available : Math.max(estimatedSeconds, available)
  const canPlay = !!player && (available > 0 || state === 'buffering')
  const playing = state === 'playing' || state === 'buffering'

  return (
    <div className={styles.bar} aria-label="Player">
      <button
        className={styles.play}
        onClick={() => (playing ? player?.pause() : player?.play())}
        disabled={!canPlay}
        aria-label={playing ? 'Pause' : 'Play'}
      >
        {state === 'buffering' ? (
          <Loader2 size={20} className={styles.spin} />
        ) : playing ? (
          <Pause size={20} />
        ) : (
          <Play size={20} />
        )}
      </button>
      <span className={styles.time}>{formatDuration(time)}</span>
      <Waveform
        levels={player?.levels ?? []}
        currentTime={time}
        available={available}
        total={total}
        onSeek={(s) => player?.seek(s)}
      />
      <span className={styles.total}>
        {player && !player.complete && total > 0 ? '~' : ''}
        {formatDuration(total)}
      </span>
      <div className={styles.volume}>
        <button
          className={styles.icon}
          onClick={() => setMuted((m) => !m)}
          aria-label={muted ? 'Unmute' : 'Mute'}
        >
          {muted || volume === 0 ? <VolumeX size={18} /> : <Volume2 size={18} />}
        </button>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={muted ? 0 : volume}
          onChange={(e) => {
            setVolume(Number(e.target.value))
            setMuted(false)
          }}
          aria-label="Volume"
        />
      </div>
      <a
        className={styles.download}
        href={downloadUrl ?? undefined}
        aria-disabled={!downloadUrl}
        onClick={(e) => !downloadUrl && e.preventDefault()}
        download
      >
        <Download size={16} /> <span>Download</span>
      </a>
    </div>
  )
}
