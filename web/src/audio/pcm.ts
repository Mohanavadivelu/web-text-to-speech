// PCM16 helpers for the streamed audio (see server/events.py for the format).

export const SAMPLE_RATE = 24_000

/** Little-endian 16-bit PCM → float samples in [-1, 1]. */
export function pcm16ToFloat32(buffer: ArrayBuffer): Float32Array<ArrayBuffer> {
  const view = new DataView(buffer)
  const out = new Float32Array(buffer.byteLength >> 1)
  for (let i = 0; i < out.length; i++) {
    out[i] = view.getInt16(i * 2, true) / 32768
  }
  return out
}

/** Peak level (0–1) of each block of `samplesPerPeak` samples, for drawing the waveform. */
export function peaks(samples: Float32Array, samplesPerPeak: number): number[] {
  const out: number[] = []
  for (let start = 0; start < samples.length; start += samplesPerPeak) {
    let max = 0
    const end = Math.min(samples.length, start + samplesPerPeak)
    for (let i = start; i < end; i++) {
      const v = Math.abs(samples[i])
      if (v > max) max = v
    }
    out.push(Math.min(1, max))
  }
  return out
}
