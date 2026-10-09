// The Studio: type or open text, pick a voice, hear it while it's being made.

import { ChevronDown, History, Settings2 } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { api, ApiError, type Config, type Language } from '../api/client'
import { Link } from '../components/Link'
import { RecentHistory } from '../components/RecentHistory'
import { Sheet } from '../components/Sheet'
import { TextEditor, type TextEditorHandle } from '../components/TextEditor'
import { VoicePanel } from '../components/VoicePanel'
import { VoiceAvatar, VoicePicker } from '../components/VoicePicker'
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

const DRAFT_KEY = 'narravo.draft'
const ZOOM_KEY = 'narravo.zoom'
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
  const [sheet, setSheet] = useState<'settings' | 'history' | null>(null)
  const [sideTab, setSideTab] = useState<'settings' | 'history'>('settings')
  const [pickerOpen, setPickerOpen] = useState(false)

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
      } else if (e.key === 'Escape' && busy && !sheet && !pickerOpen) {
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
  }, [generate, clean, busy, sheet, pickerOpen, speech])

  const lang = languages.find((l) => l.code === settings.lang)
  const voice = lang?.voices.find((v) => v.id === settings.voice)
  const loadProblem = loadError ? <p className={styles.loadError}>{loadError}</p> : null

  const settingsPanel = loadProblem ??
    (languages.length === 0 ? <p className={styles.loading}>Loading voices…</p> : null) ?? (
      <VoicePanel
        languages={languages}
        settings={settings}
        onChange={setSettings}
        onOpenPicker={() => setPickerOpen(true)}
        disabled={busy}
      />
    )

  // Phones and tablets: voice, settings and history right above Generate
  const controls = wide ? undefined : (
    <>
      <button
        className={styles.voiceChip}
        onClick={() => setPickerOpen(true)}
        aria-label={`Voice: ${voice?.name ?? ''}. Change voice`}
        disabled={busy}
      >
        {voice && <VoiceAvatar name={voice.name} size={24} />}
        <span className={styles.voiceChipText}>
          {voice?.name ?? 'Voice'} · {lang?.name ?? ''}
        </span>
        <ChevronDown size={16} />
      </button>
      <button
        className={styles.squareButton}
        onClick={() => setSheet('settings')}
        aria-label="Voice settings"
      >
        <Settings2 size={18} />
      </button>
      <button
        className={styles.squareButton}
        onClick={() => setSheet('history')}
        aria-label="Recent history"
      >
        <History size={18} />
      </button>
    </>
  )

  return (
    <div className={styles.studio}>
      <div className={styles.main}>
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
          controls={controls}
          emotions={lang?.emotions ?? []}
        />
        {wide && (
          <aside className={styles.side}>
            <div className={styles.tabs} role="tablist" aria-label="Side panel">
              {(['settings', 'history'] as const).map((tab) => (
                <button
                  key={tab}
                  role="tab"
                  id={`tab-${tab}`}
                  aria-selected={sideTab === tab}
                  aria-controls={`panel-${tab}`}
                  className={styles.tab}
                  onClick={() => setSideTab(tab)}
                >
                  {tab === 'settings' ? 'Settings' : 'History'}
                </button>
              ))}
            </div>
            <div
              className={styles.tabPanel}
              role="tabpanel"
              id={`panel-${sideTab}`}
              aria-labelledby={`tab-${sideTab}`}
            >
              {sideTab === 'settings' ? settingsPanel : <RecentHistory />}
            </div>
            <InfoLinks />
          </aside>
        )}
      </div>
      {!wide && (
        <>
          <Sheet open={sheet === 'settings'} onClose={() => setSheet(null)} title="Voice settings">
            <h2 className={styles.sheetTitle}>Voice settings</h2>
            {settingsPanel}
            <InfoLinks />
          </Sheet>
          <Sheet open={sheet === 'history'} onClose={() => setSheet(null)} title="Recent history">
            <h2 className={styles.sheetTitle}>History</h2>
            <RecentHistory />
          </Sheet>
        </>
      )}
      {pickerOpen && (
        <VoicePicker
          languages={languages}
          settings={settings}
          onChoose={(patch) => setSettings((s) => ({ ...s, ...patch }))}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </div>
  )
}

function InfoLinks() {
  return (
    <nav className={styles.infoLinks} aria-label="About Narravo">
      <Link href="/about">About</Link>
      <Link href="/privacy">Privacy</Link>
      <Link href="/terms">Terms</Link>
    </nav>
  )
}
