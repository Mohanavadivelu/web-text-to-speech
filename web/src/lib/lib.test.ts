import { describe, expect, it } from 'vitest'

import type { Language } from '../api/client'
import { ApiError } from '../api/client'
import { errorToast } from './errors'
import { DEFAULT_SETTINGS, reconcile } from './settings'
import { countWords, estimateSeconds, formatDuration, formatEstimate, formatShort } from './text'

describe('text helpers', () => {
  it('estimates like the server (server/engine/text.py)', () => {
    const sample = 'x'.repeat(1400)
    expect(estimateSeconds(sample, 'a')).toBe(100)
    expect(estimateSeconds(sample, 'a', 2)).toBe(50)
    expect(estimateSeconds(sample, 'f')).toBeCloseTo(63.64, 1)
    expect(estimateSeconds('   ')).toBe(0)
  })

  it('counts words and formats times', () => {
    expect(countWords('  one two\nthree  ')).toBe(3)
    expect(countWords('')).toBe(0)
    expect(formatDuration(7)).toBe('0:07')
    expect(formatDuration(86)).toBe('1:26')
    expect(formatDuration(3723)).toBe('1:02:03')
    expect(formatEstimate(86)).toBe('~1m 26s')
    expect(formatEstimate(12)).toBe('~12s')
    expect(formatShort(2000)).toBe('2k')
    expect(formatShort(1234)).toBe('1.2k')
  })
})

const LANGUAGES = [
  {
    code: 'a',
    name: 'American English',
    default_voice: 'af_heart',
    preview_text: '',
    voices: [
      { id: 'af_heart', name: 'Heart', gender: 'female', grade: 'A' },
      { id: 'af_bella', name: 'Bella', gender: 'female', grade: 'A-' },
    ],
  },
  {
    code: 'h',
    name: 'Hindi',
    default_voice: 'hf_alpha',
    preview_text: '',
    voices: [{ id: 'hf_alpha', name: 'Alpha', gender: 'female', grade: 'C' }],
  },
] as Language[]

describe('reconcile saved settings with the voice catalogue', () => {
  it('keeps valid settings unchanged', () => {
    const s = { ...DEFAULT_SETTINGS, blendVoice: 'af_bella' }
    expect(reconcile(s, LANGUAGES)).toBe(s)
  })

  it('replaces a voice that no longer exists with the language default', () => {
    const s = { ...DEFAULT_SETTINGS, lang: 'h', voice: 'hf_gone', blendVoice: 'af_bella' }
    expect(reconcile(s, LANGUAGES)).toMatchObject({
      lang: 'h',
      voice: 'hf_alpha',
      blendVoice: null,
    })
  })

  it('falls back to the first language for an unknown one', () => {
    expect(reconcile({ ...DEFAULT_SETTINGS, lang: 'zz' }, LANGUAGES).lang).toBe('a')
  })
})

describe('error toasts', () => {
  it('offers Retry only where retrying can help', () => {
    const retry = () => {}
    expect(errorToast(new ApiError('busy', 'Busy.'), retry).action?.label).toBe('Retry')
    expect(errorToast(new ApiError('invalid_input', 'Bad voice.'), retry).action).toBeUndefined()
    expect(errorToast(new ApiError('too_long', 'Too long.'))).toEqual({
      kind: 'error',
      message: 'Too long.',
    })
  })
})
