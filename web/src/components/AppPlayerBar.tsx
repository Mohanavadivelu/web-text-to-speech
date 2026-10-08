// The player bar at the bottom of every page: the Studio's job, or a track from History.

import { activePlayer, usePlayback } from '../lib/playback'
import { PlayerBar } from './PlayerBar'

export function AppPlayerBar() {
  const playback = usePlayback()
  const { speech, showing, track } = playback

  if (showing === 'track' && track) {
    return (
      <PlayerBar
        player={activePlayer(playback)}
        estimatedSeconds={track.seconds ?? 0}
        downloadUrl={track.url}
        wavUrl={track.wavUrl ?? null}
        title={track.title}
      />
    )
  }
  return (
    <PlayerBar
      player={speech.player}
      estimatedSeconds={speech.estimatedSeconds}
      downloadUrl={speech.url}
      wavUrl={speech.wavUrl}
    />
  )
}
