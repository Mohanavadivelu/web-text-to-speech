// The Studio: type or open text, pick a voice, hear it while it's being made.

import { AudioLines, ChevronDown } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { api, ApiError, type Config, type Language } from '../api/client'
import { Sheet } from '../components/Sheet'
import { TextEditor, type TextEditorHandle } from '../components/TextEditor'
import { VoicePanel } from '../components/VoicePanel'
import { errorToast } from '../lib/errors'
import { useMe } from '../lib/me'
import { usePlayback } from '../lib/playback'
import { navigate } from '../lib/router'
import { reconcile, useVoiceSettings } from '../lib/settings'
import { load, save } from '../lib/storage'
import { useToast } from '../lib/toast'
import { getBotToken } from '../lib/turnstile'
import { formatCount } from '../lib/text'
import { useMediaQuery } from '../lib/useMediaQuery'
import styles from './Studio.module.css'

const DRAFT_KEY = 'kokoro.draft'
const ZOOM_KEY = 'kokoro.zoom'
const FALLBACK_CONFIG: Config = {
  max_chars: 2000,
  max_upload_mb: 5,
  document_types: ['.txt', '.md', '.docx', '.pdf'],
}

export function Studio() {
  const toast = useToast()
  const { me } = useMe()
  const maxChars = me.limits.max_chars
  const wide = useMediaQuery('(min-width: 1024px)')
  const editor = useRef<TextEditorHandle>(null)

  const [languages, setLanguages] = useState<Language[]>([])
  const [config, setConfig] = useState<Config>(FALLBACK_CONFIG)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [settings, setSettings] = useVoiceSettings()
  const [text, setText] = useState(() => load(DRAFT_KEY, ''))
  const [zoom, setZoom] = useState(() => load(ZOOM_KEY, 1))
  const [sheetOpen, setSheetOpen] = useState(false)

  const playback = usePlayback()
  const { speech } = playback
  const busy = speech.status === 'queued' || speech.status === 'streaming'

  // Voices and limits
  useEffect(() => {
    let alive = true
    Promise.all([api.voices(), api.config()])
      .then(([voices, cfg]) => {
        if (!alive) return
        setLanguages(voices.languages)
        setConfig(cfg)
        setSettings((s) => reconcile(s, voices.languages))
      })
      .catch(
        (err: unknown) =>
          alive && setLoadError(err instanceof ApiError ? err.message : String(err)),
      )
    return () => {
      alive = false
    }
  }, [setSettings])

  // Draft and zoom are remembered (draft saved shortly after typing stops)
  useEffect(() => {
    const timer = window.setTimeout(() => save(DRAFT_KEY, text), 500)
    return () => window.clearTimeout(timer)
  }, [text])
  useEffect(() => save(ZOOM_KEY, zoom), [zoom])

  const generate = useCallback(() => {
    if (busy) return
    const source = editor.current?.selection() ?? text
    if (!source.trim()) return
    if (source.length > maxChars) {
      toast({
        kind: 'error',
        message: `This text is over the limit of ${formatCount(maxChars)} characters. Select a part to generate just that.`,
      })
      return
    }
    playback.generate(
      {
        text: source,
        lang: settings.lang,
        voice: settings.voice,
        speed: settings.speed,
        pitch: settings.pitch,
        blend_voice: settings.blendVoice,
        blend_ratio: settings.blendRatio,
        pronunciations: [], // signed-in users' saved pronunciations are applied by the server
      },
      me.signed_in ? undefined : getBotToken,
    )
  }, [busy, text, maxChars, settings, playback, toast, me.signed_in])

  const replaceText = useCallback(
    (next: string, message: string) => {
      const previous = text
      setText(next)
      toast({ kind: 'info', message, action: { label: 'Undo', run: () => setText(previous) } })
    },
    [text, toast],
  )

  const openFile = useCallback(
    async (file: File) => {
      if (!me.limits.uploads) {
        toast({
          kind: 'info',
          message: 'Sign in to open documents.',
          action: { label: 'Sign in', run: () => navigate('/signin') },
        })
        return
      }
      if (file.size > config.max_upload_mb * 2 ** 20) {
        toast({ kind: 'error', message: `Files can be up to ${config.max_upload_mb} MB.` })
        return
      }
      try {
        const result = await api.extractFile(file)
        replaceText(
          result.text,
          `Opened ${file.name}${result.cleaned ? ' (text cleaned)' : ''}: ${formatCount(result.characters)} characters.`,
        )
        if (result.characters > maxChars) {
          toast({
            kind: 'warning',
            message: `That's over the ${formatCount(maxChars)}-character limit. Select a part to generate it.`,
          })
        }
      } catch (err) {
        if (err instanceof ApiError) toast(errorToast(err))
      }
    },
    [config, maxChars, me.limits.uploads, replaceText, toast],
  )

  const clean = useCallback(async () => {
    if (!text.trim()) return
    try {
      const result = await api.cleanText(text)
      if (result.text === text) toast({ kind: 'info', message: 'The text was already clean.' })
      else replaceText(result.text, 'Text cleaned.')
    } catch (err) {
      if (err instanceof ApiError) toast(errorToast(err))
    }
  }, [text, replaceText, toast])

  // Keyboard shortcuts (DESIGN.md §14)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey
      if (mod && e.key === 'Enter') {
        e.preventDefault()
        generate()
      } else if (e.key === 'Escape' && busy && !sheetOpen) {
        void speech.cancel()
      } else if (mod && e.key.toLowerCase() === 'o') {
        e.preventDefault()
        editor.current?.openFilePicker()
      } else if (mod && e.shiftKey && e.key.toLowerCase() === 'l') {
        e.preventDefault()
        void clean()
      } else if (mod && e.key.toLowerCase() === 's' && speech.url) {
        e.preventDefault()
        window.location.assign(speech.url)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [generate, clean, busy, sheetOpen, speech])

  const lang = languages.find((l) => l.code === settings.lang)
  const voice = lang?.voices.find((v) => v.id === settings.voice)
  const voiceSummary = voice ? `${voice.name} · ${lang?.name} · ${settings.speed}×` : 'Voice'

  const panel = (
    <VoicePanel languages={languages} settings={settings} onChange={setSettings} disabled={busy} />
  )

  return (
    <div className={styles.studio}>
      <div className={styles.main}>
        {!wide && (
          <button
            className={styles.voiceChip}
            onClick={() => setSheetOpen(true)}
            aria-label={`Voice settings: ${voiceSummary}`}
          >
            <AudioLines size={16} />
            <span>{voiceSummary}</span>
            <ChevronDown size={16} />
          </button>
        )}
        <TextEditor
          ref={editor}
          text={text}
          onTextChange={setText}
          lang={settings.lang}
          speed={settings.speed}
          maxChars={maxChars}
          zoom={zoom}
          onZoom={setZoom}
          busy={busy}
          progress={speech.progress}
          queuePosition={speech.status === 'queued' ? speech.queuePosition : null}
          onGenerate={generate}
          onCancel={() => void speech.cancel()}
          onOpenFile={(f) => void openFile(f)}
          onClean={() => void clean()}
          documentTypes={config.document_types}
        />
        {wide && (
          <aside className={styles.side}>
            {loadError ? <p className={styles.loadError}>{loadError}</p> : panel}
          </aside>
        )}
      </div>
      {!wide && (
        <Sheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Voice settings">
          {loadError ? <p className={styles.loadError}>{loadError}</p> : panel}
        </Sheet>
      )}
    </div>
  )
}
