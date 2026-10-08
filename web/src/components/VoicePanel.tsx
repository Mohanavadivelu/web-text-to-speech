// Voice settings (DESIGN.md §9): language, voice + preview, mix, speed, pitch.

import { Pause, Play, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import type { Language } from '../api/client'
import { DEFAULT_SETTINGS, type VoiceSettings } from '../lib/settings'
import styles from './VoicePanel.module.css'

interface Props {
  languages: Language[]
  settings: VoiceSettings
  onChange: (settings: VoiceSettings) => void
  disabled?: boolean
}

const genderSign = (gender: string) => (gender === 'female' ? '♀' : '♂')

export function VoicePanel({ languages, settings, onChange, disabled }: Props) {
  const lang = languages.find((l) => l.code === settings.lang) ?? languages[0]
  const voice = lang?.voices.find((v) => v.id === settings.voice) ?? lang?.voices[0]
  const blend = lang?.voices.find((v) => v.id === settings.blendVoice)
  const [previewing, setPreviewing] = useState(false)
  const preview = useRef<HTMLAudioElement | null>(null)

  useEffect(() => () => preview.current?.pause(), [])
  if (!lang || !voice) return null

  const set = (patch: Partial<VoiceSettings>) => onChange({ ...settings, ...patch })

  const togglePreview = () => {
    if (previewing) {
      preview.current?.pause()
      setPreviewing(false)
      return
    }
    preview.current?.pause()
    const audio = new Audio(`/previews/${voice.id}.mp3`)
    audio.onended = () => setPreviewing(false)
    audio.onerror = () => setPreviewing(false)
    preview.current = audio
    setPreviewing(true)
    void audio.play().catch(() => setPreviewing(false))
  }

  const blendPercent = Math.round(settings.blendRatio * 100)

  return (
    <section className={styles.panel} aria-label="Voice settings">
      <h2 className={styles.heading}>Voice settings</h2>
      <fieldset className={styles.fields} disabled={disabled}>
        <label className={styles.field}>
          <span className={styles.label}>Language</span>
          <select
            value={lang.code}
            onChange={(e) => {
              const next = languages.find((l) => l.code === e.target.value)
              if (next) set({ lang: next.code, voice: next.default_voice, blendVoice: null })
            }}
          >
            {languages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name}
              </option>
            ))}
          </select>
        </label>

        <div className={styles.field}>
          <label className={styles.label} htmlFor="voice">
            Voice
          </label>
          <div className={styles.row}>
            <select
              id="voice"
              value={voice.id}
              onChange={(e) =>
                set({
                  voice: e.target.value,
                  blendVoice: settings.blendVoice === e.target.value ? null : settings.blendVoice,
                })
              }
            >
              {lang.voices.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} {genderSign(v.gender)}
                  {v.grade ? `  ·  grade ${v.grade}` : ''}
                </option>
              ))}
            </select>
            <button
              type="button"
              className={styles.iconButton}
              onClick={togglePreview}
              aria-label={previewing ? 'Stop preview' : `Preview ${voice.name}`}
              title={previewing ? 'Stop preview' : 'Preview this voice'}
            >
              {previewing ? <Pause size={16} /> : <Play size={16} />}
            </button>
          </div>
        </div>

        <label className={styles.field}>
          <span className={styles.label}>Mix with</span>
          <select
            value={settings.blendVoice ?? ''}
            onChange={(e) => set({ blendVoice: e.target.value || null })}
          >
            <option value="">None</option>
            {lang.voices
              .filter((v) => v.id !== voice.id)
              .map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} {genderSign(v.gender)}
                </option>
              ))}
          </select>
        </label>
        {blend && (
          <label className={styles.field}>
            <span className={styles.sliderLabels}>
              <span>
                {voice.name} {100 - blendPercent}%
              </span>
              <span>
                {blendPercent}% {blend.name}
              </span>
            </span>
            <input
              type="range"
              min={0.1}
              max={0.9}
              step={0.1}
              value={settings.blendRatio}
              aria-valuetext={`${100 - blendPercent}% ${voice.name}, ${blendPercent}% ${blend.name}`}
              onChange={(e) => set({ blendRatio: Number(e.target.value) })}
            />
          </label>
        )}

        <label className={styles.field}>
          <span className={styles.label}>Speed</span>
          <output
            className={styles.value}
            onDoubleClick={() => set({ speed: 1 })}
            title="Double-click to reset"
          >
            {settings.speed.toFixed(2).replace(/0$/, '')}×
          </output>
          <input
            type="range"
            min={0.5}
            max={2}
            step={0.05}
            value={settings.speed}
            aria-valuetext={`${settings.speed} times`}
            onChange={(e) => set({ speed: Number(e.target.value) })}
          />
          <span className={styles.sliderLabels}>
            <span>0.5×</span>
            <span>2×</span>
          </span>
        </label>

        <details className={styles.advanced} open={settings.pitch !== 0 || undefined}>
          <summary>Advanced</summary>
          <label className={styles.field}>
            <span className={styles.label}>Pitch</span>
            <output className={styles.value}>
              {settings.pitch > 0 ? '+' : ''}
              {settings.pitch} st
            </output>
            <input
              type="range"
              min={-6}
              max={6}
              step={0.5}
              value={settings.pitch}
              aria-valuetext={`${settings.pitch > 0 ? 'plus ' : settings.pitch < 0 ? 'minus ' : ''}${Math.abs(settings.pitch)} semitones`}
              onChange={(e) => set({ pitch: Number(e.target.value) })}
            />
            <span className={styles.sliderLabels}>
              <span>−6</span>
              <span>+6</span>
            </span>
          </label>
        </details>

        <button
          type="button"
          className={styles.reset}
          onClick={() =>
            onChange({ ...DEFAULT_SETTINGS, lang: lang.code, voice: lang.default_voice })
          }
        >
          <RotateCcw size={14} /> Reset
        </button>
      </fieldset>
    </section>
  )
}
