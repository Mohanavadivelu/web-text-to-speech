// Voice settings, remembered between visits.

import { useEffect, useState } from 'react'

import type { Language } from '../api/client'
import { load, save } from './storage'

export interface VoiceSettings {
  lang: string
  voice: string
  blendVoice: string | null
  blendRatio: number // share of the second voice, 0.1–0.9
  speed: number
  pitch: number
}

export const DEFAULT_SETTINGS: VoiceSettings = {
  lang: 'a',
  voice: 'af_heart',
  blendVoice: null,
  blendRatio: 0.3,
  speed: 1,
  pitch: 0,
}

const KEY = 'narravo.voice-settings'

export function useVoiceSettings() {
  const [settings, setSettings] = useState<VoiceSettings>(() => ({
    ...DEFAULT_SETTINGS,
    ...load<Partial<VoiceSettings>>(KEY, {}),
  }))
  useEffect(() => save(KEY, settings), [settings])
  return [settings, setSettings] as const
}

/** Make saved settings fit the current voice catalogue (voices can change between visits). */
export function reconcile(settings: VoiceSettings, languages: Language[]): VoiceSettings {
  const lang = languages.find((l) => l.code === settings.lang) ?? languages[0]
  if (!lang) return settings
  const ids = new Set(lang.voices.map((v) => v.id))
  const voice = ids.has(settings.voice) ? settings.voice : lang.default_voice
  const blendVoice =
    settings.blendVoice && ids.has(settings.blendVoice) && settings.blendVoice !== voice
      ? settings.blendVoice
      : null
  if (
    lang.code === settings.lang &&
    voice === settings.voice &&
    blendVoice === settings.blendVoice
  ) {
    return settings
  }
  return { ...settings, lang: lang.code, voice, blendVoice }
}
