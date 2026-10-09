// Choose a voice (DESIGN.md §9): search, filter by language and gender, sort, preview
// any voice, and optionally mix in a second voice of the same language.

import { Check, Pause, Play, Search, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import type { Language, Voice } from '../api/client'
import type { VoiceSettings } from '../lib/settings'
import { ENGINE_LABELS, genderSign } from '../lib/voices'
import styles from './VoicePicker.module.css'

// Render it only while it should be open: it opens on mount and starts from the
// current settings each time.
interface Props {
  onClose: () => void
  languages: Language[]
  settings: VoiceSettings
  onChoose: (patch: Pick<VoiceSettings, 'lang' | 'voice' | 'blendVoice' | 'blendRatio'>) => void
}

type Gender = 'all' | 'female' | 'male'
type Sort = 'recommended' | 'grade' | 'name'

const GRADE_ORDER = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F+', 'F']
const gradeRank = (grade: string | null | undefined) =>
  grade ? GRADE_ORDER.indexOf(grade) : GRADE_ORDER.length

export function VoiceAvatar({ name, size = 36 }: { name: string; size?: number }) {
  return (
    <span className={styles.avatar} style={{ width: size, height: size }} aria-hidden>
      {name.charAt(0)}
    </span>
  )
}

export function VoicePicker({ onClose, languages, settings, onChoose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [query, setQuery] = useState('')

  const [gender, setGender] = useState<Gender>('all')
  const [sort, setSort] = useState<Sort>('recommended')
  const [selected, setSelected] = useState({ lang: settings.lang, voice: settings.voice })
  const [blendVoice, setBlendVoice] = useState<string | null>(settings.blendVoice)
  const [blendRatio, setBlendRatio] = useState(settings.blendRatio)
  const [previewing, setPreviewing] = useState<string | null>(null)
  const preview = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    dialog.current?.showModal()
    return () => preview.current?.pause()
  }, [])

  const selectedLang = languages.find((l) => l.code === selected.lang) ?? languages[0]

  // One language at a time: Indic voices speak all 23 Indian languages, so an
  // "all languages" list would repeat them 23 times
  const voices = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = (selectedLang?.voices ?? [])
      .filter((v) => gender === 'all' || v.gender === gender)
      .filter((v) => !q || v.name.toLowerCase().includes(q))
    if (sort === 'name') return [...list].sort((a, b) => a.name.localeCompare(b.name))
    if (sort === 'grade') {
      return [...list].sort(
        (a, b) => gradeRank(a.grade) - gradeRank(b.grade) || a.name.localeCompare(b.name),
      )
    }
    return list // the engine's own order: its recommended voices first
  }, [selectedLang, query, gender, sort])

  const changeLanguage = (code: string) => {
    const next = languages.find((l) => l.code === code)
    if (!next) return
    // Keep the voice if this language has it (Indic voices speak every Indian language)
    const keep = next.voices.some((v) => v.id === selected.voice)
    setSelected({ lang: next.code, voice: keep ? selected.voice : next.default_voice })
    if (!next.voices.some((v) => v.id === blendVoice)) setBlendVoice(null)
  }
  const selectedVoice = selectedLang?.voices.find((v) => v.id === selected.voice)
  const blend = selectedLang?.voices.find((v) => v.id === blendVoice)
  const blendPercent = Math.round(blendRatio * 100)

  const pick = (lang: Language, voice: Voice) => {
    setSelected({ lang: lang.code, voice: voice.id })
    // A mix only works within one language, and not with itself
    if (lang.code !== selected.lang || blendVoice === voice.id) setBlendVoice(null)
  }

  const togglePreview = (voiceId: string) => {
    preview.current?.pause()
    if (previewing === voiceId) {
      setPreviewing(null)
      return
    }
    const audio = new Audio(`/previews/${voiceId}.mp3`)
    audio.onended = () => setPreviewing(null)
    audio.onerror = () => setPreviewing(null)
    preview.current = audio
    setPreviewing(voiceId)
    void audio.play().catch(() => setPreviewing(null))
  }

  return (
    <dialog
      ref={dialog}
      className={styles.dialog}
      aria-label="Choose a voice"
      onClose={onClose}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className={styles.body}>
        <header className={styles.header}>
          <h2>Choose a voice</h2>
          <button className={styles.iconButton} onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>

        <div className={styles.filters}>
          <label className={styles.search}>
            <Search size={16} aria-hidden />
            <input
              type="search"
              placeholder="Search voices…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search voices"
            />
          </label>
          <select
            value={selected.lang}
            onChange={(e) => changeLanguage(e.target.value)}
            aria-label="Language"
          >
            {(['kokoro', 'indic_mio'] as const).map((engine) => (
              <optgroup key={engine} label={ENGINE_LABELS[engine]}>
                {languages
                  .filter((l) => l.engine === engine)
                  .map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.name}
                    </option>
                  ))}
              </optgroup>
            ))}
          </select>
          <div className={styles.chips} role="group" aria-label="Gender">
            {(['all', 'female', 'male'] as const).map((g) => (
              <button
                key={g}
                className={styles.chip}
                aria-pressed={gender === g}
                onClick={() => setGender(g)}
              >
                {g === 'all' ? 'All' : g === 'female' ? '♀ Female' : '♂ Male'}
              </button>
            ))}
          </div>
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort">
            <option value="recommended">Recommended</option>
            <option value="grade">Best grade</option>
            <option value="name">Name</option>
          </select>
        </div>

        <div className={styles.list} role="listbox" aria-label="Voices">
          {voices.length === 0 && <p className={styles.empty}>No voices match.</p>}
          {selectedLang && voices.length > 0 && (
            <section>
              <h3 className={styles.group}>
                {selectedLang.name} · {ENGINE_LABELS[selectedLang.engine]}
              </h3>
              {voices.map((voice) => {
                const lang = selectedLang
                const isSelected = selected.voice === voice.id
                return (
                  <div
                    key={voice.id}
                    className={styles.row}
                    role="option"
                    aria-selected={isSelected}
                    tabIndex={0}
                    onClick={() => pick(lang, voice)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        pick(lang, voice)
                      }
                    }}
                  >
                    <VoiceAvatar name={voice.name} />
                    <span className={styles.voiceName}>
                      {voice.name} <span className={styles.gender}>{genderSign(voice.gender)}</span>
                    </span>
                    {voice.grade && <span className={styles.grade}>{voice.grade}</span>}
                    {voice.tags?.includes('native') && <span className={styles.tag}>Native</span>}
                    <span className={styles.spacer} />
                    <button
                      className={styles.iconButton}
                      onClick={(e) => {
                        e.stopPropagation()
                        togglePreview(voice.id)
                      }}
                      aria-label={
                        previewing === voice.id ? 'Stop preview' : `Preview ${voice.name}`
                      }
                    >
                      {previewing === voice.id ? <Pause size={16} /> : <Play size={16} />}
                    </button>
                    <span className={styles.check} aria-hidden>
                      {isSelected && <Check size={18} />}
                    </span>
                  </div>
                )
              })}
            </section>
          )}
        </div>

        <footer className={styles.footer}>
          <div className={styles.mix}>
            <label className={styles.mixLabel}>
              <span>Mix with</span>
              <select
                value={blendVoice ?? ''}
                onChange={(e) => setBlendVoice(e.target.value || null)}
                aria-label="Mix with"
              >
                <option value="">No mix</option>
                {selectedLang?.voices
                  .filter((v) => v.id !== selected.voice)
                  .map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name} {genderSign(v.gender)}
                    </option>
                  ))}
              </select>
            </label>
            {blend && selectedVoice && (
              <label className={styles.ratio}>
                <span>
                  {selectedVoice.name} {100 - blendPercent}%
                </span>
                <input
                  type="range"
                  min={0.1}
                  max={0.9}
                  step={0.1}
                  value={blendRatio}
                  onChange={(e) => setBlendRatio(Number(e.target.value))}
                  aria-label="Mix ratio"
                  aria-valuetext={`${100 - blendPercent}% ${selectedVoice.name}, ${blendPercent}% ${blend.name}`}
                />
                <span>
                  {blendPercent}% {blend.name}
                </span>
              </label>
            )}
          </div>
          <div className={styles.actions}>
            <button className={styles.secondary} onClick={onClose}>
              Cancel
            </button>
            <button
              className={styles.primary}
              onClick={() => {
                onChoose({ ...selected, blendVoice, blendRatio })
                onClose()
              }}
            >
              Use voice
            </button>
          </div>
        </footer>
      </div>
    </dialog>
  )
}
