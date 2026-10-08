// What the player bar is playing, shared by every page so audio keeps playing while
// you move between Studio, History and About.
//
// It plays either the current speech job (made in the Studio) or a "track" (a
// finished file, e.g. from History). Starting one pauses the other.

import { createContext, useContext } from 'react'

import type { JobCreate } from '../api/client'
import type { Player } from '../audio/player'
import type { SpeechJob } from '../audio/useSpeechJob'

export interface TrackInput {
  id: string
  url: string
  wavUrl?: string | null
  title: string
  seconds?: number | null
}

export interface Track extends TrackInput {
  player: Player
}

export interface Playback {
  speech: SpeechJob & { cancel: () => Promise<void> }
  /** What the player bar shows. */
  showing: 'job' | 'track'
  track: Track | null
  /** Start a speech job (call from a click: browsers only allow sound after one). */
  generate: (body: JobCreate, getBotToken?: () => Promise<string | null>) => void
  /** Play a finished file in the player bar. */
  playTrack: (track: TrackInput) => void
  /** Switch the player bar back to the Studio's job. */
  showJob: () => void
  /** Tell screen-reader users about something. */
  announce: (message: string) => void
}

export const PlaybackContext = createContext<Playback | null>(null)

export function usePlayback(): Playback {
  const value = useContext(PlaybackContext)
  if (!value) throw new Error('usePlayback must be used inside PlaybackProvider')
  return value
}

/** The player the bar is showing (job or track), or null. */
export function activePlayer(playback: Playback): Player | null {
  return playback.showing === 'track' ? (playback.track?.player ?? null) : playback.speech.player
}
