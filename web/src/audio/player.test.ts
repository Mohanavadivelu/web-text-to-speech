import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { pcm16ToFloat32, peaks, SAMPLE_RATE } from './pcm'
import { StreamPlayer } from './player'

/** A fake AudioContext with a clock we control, recording what gets scheduled. */
class FakeContext {
  currentTime = 0
  started: { when: number; offset: number; length: number }[] = []
  stopped = 0
  destination = {}
  createGain() {
    return { gain: { value: 1 }, connect: () => {} }
  }
  createBuffer(_channels: number, length: number) {
    return { length, copyToChannel: () => {} }
  }
  createBufferSource() {
    const source = {
      buffer: null as null | { length: number },
      onended: null as null | (() => void),
      connect: () => {},
      start: (when: number, offset: number) =>
        this.started.push({ when, offset, length: source.buffer?.length ?? 0 }),
      stop: () => {
        this.stopped += 1
      },
    }
    return source
  }
  resume() {
    return Promise.resolve()
  }
  close() {
    return Promise.resolve()
  }
}

const seconds = (s: number) => new Float32Array(Math.round(s * SAMPLE_RATE)).fill(0.5)

describe('StreamPlayer', () => {
  let ctx: FakeContext
  let player: StreamPlayer

  beforeEach(() => {
    vi.useFakeTimers()
    ctx = new FakeContext()
    player = new StreamPlayer(() => ctx as unknown as AudioContext)
  })
  afterEach(() => vi.useRealTimers())

  it('schedules chunks back to back, without gaps', () => {
    player.play()
    player.append(seconds(1))
    player.append(seconds(2))
    const [a, b] = ctx.started
    expect(b.when - a.when).toBeCloseTo(1, 5)
    expect(player.duration).toBeCloseTo(3)
  })

  it('buffers when playback catches up with generation, then continues where it was', () => {
    player.play()
    player.append(seconds(1))
    ctx.currentTime = 5 // playback ran past the end of the audio
    expect(player.state).toBe('buffering')
    player.append(seconds(1))
    const last = ctx.started.at(-1)!
    expect(last.when).toBeGreaterThanOrEqual(5) // starts now, not in the past
    expect(last.offset).toBe(0) // from the beginning of the new chunk: nothing skipped
  })

  it('pauses, resumes and seeks within what has arrived', () => {
    player.play()
    player.append(seconds(4))
    ctx.currentTime = 2.05
    player.pause()
    expect(player.state).toBe('paused')
    expect(player.currentTime).toBeCloseTo(2, 1)
    player.seek(10) // beyond the audio: clamps to the end
    expect(player.currentTime).toBeCloseTo(4)
    player.seek(1)
    player.play()
    expect(ctx.started.at(-1)!.offset).toBeCloseTo(1, 0) // resumes ~1 s into the chunk
    expect(player.state).toBe('playing')
  })

  it('ends when all audio has played, and plays again from the start', () => {
    player.play()
    player.append(seconds(1))
    player.finish()
    ctx.currentTime = 2
    vi.advanceTimersByTime(150)
    expect(player.state).toBe('ended')
    player.play()
    expect(player.currentTime).toBe(0)
  })

  it('keeps waveform levels for the audio received', () => {
    player.append(seconds(1.5))
    expect(player.levels).toHaveLength(30) // 20 per second
    expect(Math.max(...player.levels)).toBeCloseTo(0.5)
  })

  it('reset drops the audio (job retried from the start)', () => {
    player.append(seconds(1))
    player.reset()
    expect(player.duration).toBe(0)
    expect(player.levels).toHaveLength(0)
  })
})

describe('pcm helpers', () => {
  it('decodes little-endian 16-bit PCM', () => {
    const buffer = new ArrayBuffer(6)
    const view = new DataView(buffer)
    view.setInt16(0, 0, true)
    view.setInt16(2, 16384, true)
    view.setInt16(4, -32768, true)
    expect(Array.from(pcm16ToFloat32(buffer))).toEqual([0, 0.5, -1])
  })

  it('computes peaks per block', () => {
    expect(peaks(new Float32Array([0.1, -0.8, 0.3, 0.2]), 2)).toEqual([
      expect.closeTo(0.8),
      expect.closeTo(0.3),
    ])
  })
})
