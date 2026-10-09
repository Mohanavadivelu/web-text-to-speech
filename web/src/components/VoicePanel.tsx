// Voice settings (DESIGN.md §9): the chosen voice as a card (opens the voice picker),
// then speed and pitch, each with a slider and an exact number box.

import { ArrowLeftRight, Pause, Play, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import type { Language } from '../api/client'
import { DEFAULT_SETTINGS, type VoiceSettings } from '../lib/settings'
import { genderSign } from '../lib/voices'
import { VoiceAvatar } from './VoicePicker'
import styles from './VoicePanel.module.css'

interface Props {
  languages: Language[]
  settings: VoiceSettings
  onChange: (settings: VoiceSettings) => void
  onOpenPicker: () => void
  disabled?: boolean
}

export function VoicePanel({ languages, settings, onChange, onOpenPicker, disabled }: Props) {
  const lang = languages.find((l) => l.code === settings.lang) ?? languages[0]
  const voice = lang?.voices.find((v) => v.id === settings.voice) ?? lang?.voices[0]
  const blend = lang?.voices.find((v) => v.id === settings.blendVoice)
  const [previewing, setPreviewing] = useState(false)
  const preview = useRef<HTMLAudioElement | null>(null)

  useEffect(() => () => preview.current?.pause(), [])
  if (!lang || !voice) return null

  const set = (patch: Partial<VoiceSettings>) => onChange({ ...settings, ...patch })

  const togglePreview = () => {
    preview.current?.pause()
    if (previewing) {
      setPreviewing(false)
      return
    }
    const audio = new Audio(`/previews/${voice.id}.mp3`)
    audio.onended = () => setPreviewing(false)
    audio.onerror = () => setPreviewing(false)
    preview.current = audio
    setPreviewing(true)
    void audio.play().catch(() => setPreviewing(false))
  }

  return (
    <div className={styles.panel}>
      <fieldset className={styles.fields} disabled={disabled}>
        <div className={styles.field}>
          <div className={styles.labelRow}>
            <span className={styles.label}>Voice</span>
            <button
              type="button"
              className={styles.reset}
              onClick={() =>
                onChange({ ...DEFAULT_SETTINGS, lang: lang.code, voice: lang.default_voice })
              }
            >
              <RotateCcw size={13} /> Reset
            </button>
          </div>
          <div className={styles.voiceCard}>
            <button
              type="button"
              className={styles.voiceMain}
              onClick={onOpenPicker}
              aria-label={`Voice: ${voice.name}, ${lang.name}. Change voice`}
            >
              <VoiceAvatar name={voice.name} size={44} />
              <span className={styles.voiceText}>
                <span className={styles.voiceName}>
                  {voice.name} <span className={styles.muted}>{genderSign(voice.gender)}</span>
                  {voice.grade && <span className={styles.grade}>{voice.grade}</span>}
                </span>
                <span className={styles.langTag}>
                  {lang.name}
                  {lang.engine === 'indic_mio' ? ' · Indic' : ''}
                </span>
              </span>
              <ArrowLeftRight size={16} className={styles.swap} aria-hidden />
            </button>
            <button
              type="button"
              className={styles.previewButton}
              onClick={togglePreview}
              aria-label={previewing ? 'Stop preview' : `Preview ${voice.name}`}
              title={previewing ? 'Stop preview' : 'Preview this voice'}
            >
              {previewing ? <Pause size={16} /> : <Play size={16} />}
            </button>
          </div>
          <button type="button" className={styles.mixLink} onClick={onOpenPicker}>
            {blend
              ? `Mixed with ${blend.name} · ${Math.round(settings.blendRatio * 100)}%`
              : '+ Mix with another voice'}
          </button>
        </div>

        <SliderField
          label="Speed"
          value={settings.speed}
          min={0.5}
          max={2}
          step={0.05}
          unit="×"
          ends={['0.5×', '2×']}
          valueText={(v) => `${v} times`}
          onChange={(speed) => set({ speed })}
        />
        <SliderField
          label="Pitch"
          value={settings.pitch}
          min={-6}
          max={6}
          step={0.5}
          unit="st"
          ends={['−6', '+6']}
          valueText={(v) => `${v > 0 ? 'plus ' : v < 0 ? 'minus ' : ''}${Math.abs(v)} semitones`}
          onChange={(pitch) => set({ pitch })}
        />
      </fieldset>
    </div>
  )
}

function SliderField(props: {
  label: string
  value: number
  min: number
  max: number
  step: number
  unit: string
  ends: [string, string]
  valueText: (v: number) => string
  onChange: (v: number) => void
}) {
  const { label, value, min, max, step, unit, ends, valueText, onChange } = props
  const id = `slider-${label.toLowerCase()}`
  return (
    <div className={styles.field}>
      <div className={styles.labelRow}>
        <label className={styles.label} htmlFor={id}>
          {label}
        </label>
        <NumberBox
          label={`${label} value`}
          value={value}
          min={min}
          max={max}
          step={step}
          unit={unit}
          onChange={onChange}
        />
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={valueText(value)}
        onChange={(e) => onChange(Number(e.target.value))}
        onDoubleClick={() => onChange(min < 0 ? 0 : 1)}
      />
      <span className={styles.sliderLabels}>
        <span>{ends[0]}</span>
        <span>{ends[1]}</span>
      </span>
    </div>
  )
}

/** An exact value you can type; applied on Enter or when leaving the box, clamped and rounded. */
function NumberBox(props: {
  label: string
  value: number
  min: number
  max: number
  step: number
  unit: string
  onChange: (v: number) => void
}) {
  const { label, value, min, max, step, unit, onChange } = props
  const [draft, setDraft] = useState<string | null>(null)

  const commit = () => {
    if (draft === null) return
    const parsed = Number(draft.replace(',', '.'))
    if (Number.isFinite(parsed)) {
      const clamped = Math.min(max, Math.max(min, parsed))
      onChange(Number((Math.round(clamped / step) * step).toFixed(2)))
    }
    setDraft(null)
  }

  return (
    <span className={styles.numberBox}>
      <input
        aria-label={label}
        inputMode="decimal"
        value={draft ?? String(Number(value.toFixed(2)))}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            commit()
          } else if (e.key === 'Escape') {
            setDraft(null)
          }
        }}
      />
      <span className={styles.unit}>{unit}</span>
    </span>
  )
}
