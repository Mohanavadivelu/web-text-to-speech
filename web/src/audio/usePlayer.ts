import { useEffect, useReducer } from 'react'

import type { Player } from './player'

/** Re-render whenever the player changes (time, state, new audio). */
export function usePlayer(player: Player | null): Player | null {
  const [, rerender] = useReducer((n: number) => n + 1, 0)
  useEffect(() => player?.subscribe(rerender), [player])
  return player
}
