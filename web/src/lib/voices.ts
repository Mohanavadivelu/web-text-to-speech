// Small helpers for showing voices.

import type { HistoryItem } from '../api/client'

/** How the two speech engines are presented. */
export const ENGINE_LABELS: Record<string, string> = {
  kokoro: 'Narravo Standard',
  indic_mio: 'Narravo Indic',
}

export const LANGUAGE_NAMES: Record<string, string> = {
  a: 'US English',
  b: 'UK English',
  h: 'Hindi',
  f: 'French',
  i: 'Italian',
  e: 'Spanish',
  p: 'Portuguese',
}

export function genderSign(gender: string): string {
  return gender === 'female' ? '♀' : '♂'
}

/** "af_heart" → "Heart" */
export function voiceName(id: string): string {
  const name = id.split('_')[1] ?? id
  return name.charAt(0).toUpperCase() + name.slice(1)
}

/** "Heart · US English": how a finished item is named in the player bar. */
export function trackTitle(item: Pick<HistoryItem, 'voice' | 'lang'>): string {
  return `${voiceName(item.voice)} · ${LANGUAGE_NAMES[item.lang] ?? item.lang}`
}
