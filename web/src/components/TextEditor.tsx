// Text editor panel (DESIGN.md §7): a calm writing area in a reading font, with the
// tools, counts and the Generate button along the bottom.

import { FileUp, Play, Sparkles, Square, ZoomIn, ZoomOut } from 'lucide-react'
import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  type DragEvent,
  type ReactNode,
} from 'react'

import { countWords, estimateSeconds, formatCount, formatEstimate, formatShort } from '../lib/text'
import styles from './TextEditor.module.css'

export interface TextEditorHandle {
  /** The selected text, or null when nothing (or only whitespace) is selected. */
  selection(): string | null
  openFilePicker(): void
  focus(): void
}

interface Props {
  text: string
  onTextChange: (text: string) => void
  lang: string
  speed: number
  maxChars: number
  zoom: number
  onZoom: (zoom: number) => void
  busy: boolean
  progress: number
  queuePosition: number | null
  onGenerate: () => void
  onCancel: () => void
  onOpenFile: (file: File) => void
  onClean: () => void
  documentTypes: string[]
  /** Phones and tablets: voice, settings and history buttons, just above Generate. */
  controls?: ReactNode
}

export const TextEditor = forwardRef<TextEditorHandle, Props>(function TextEditor(props, ref) {
  const {
    text,
    onTextChange,
    lang,
    speed,
    maxChars,
    zoom,
    onZoom,
    busy,
    progress,
    queuePosition,
    onGenerate,
    onCancel,
    onOpenFile,
    onClean,
    documentTypes,
    controls,
  } = props
  const area = useRef<HTMLTextAreaElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const [hasSelection, setHasSelection] = useState(false)
  const [dragging, setDragging] = useState(false)

  useImperativeHandle(ref, () => ({
    selection() {
      const el = area.current
      if (!el || el.selectionStart === el.selectionEnd) return null
      const selected = el.value.slice(el.selectionStart, el.selectionEnd)
      return selected.trim() ? selected : null
    },
    openFilePicker: () => fileInput.current?.click(),
    focus: () => area.current?.focus(),
  }))

  const length = text.length
  const over = length > maxChars
  const usage = Math.min(1, length / maxChars)
  const meterLevel = over ? 'error' : usage >= 0.9 ? 'warn' : 'ok'
  const empty = !text.trim()
  const shortcut = navigator.platform.toLowerCase().includes('mac') ? '⌘↵' : 'Ctrl ↵'

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files[0]
    if (file) onOpenFile(file)
  }

  return (
    <section
      className={styles.panel}
      aria-label="Text"
      onDragEnter={(e) => {
        if (e.dataTransfer.types.includes('Files')) setDragging(true)
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false)
      }}
      onDrop={onDrop}
    >
      <div className={styles.editorWrap}>
        <textarea
          ref={area}
          className={styles.editor}
          style={{ fontSize: `${Math.round(16 * zoom)}px` }}
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          onSelect={(e) => {
            const el = e.currentTarget
            setHasSelection(el.selectionStart !== el.selectionEnd)
          }}
          readOnly={busy}
          placeholder="Type or paste text here, or drop a document."
          aria-label="Text to speak"
          spellCheck
        />
        {dragging && (
          <div className={styles.drop} aria-hidden>
            <FileUp size={28} />
            Drop to open
          </div>
        )}
      </div>

      <div className={styles.footer}>
        <div className={styles.tools} role="toolbar" aria-label="Text tools">
          <ToolButton
            label="Open file (Ctrl+O)"
            onClick={() => fileInput.current?.click()}
            disabled={busy}
          >
            <FileUp size={18} />
          </ToolButton>
          <ToolButton label="Clean text (Ctrl+Shift+L)" onClick={onClean} disabled={busy || empty}>
            <Sparkles size={18} />
          </ToolButton>
          <span className={styles.divider} />
          <ToolButton
            label="Smaller text"
            onClick={() => onZoom(Math.max(0.8, zoom - 0.1))}
            disabled={zoom <= 0.8}
          >
            <ZoomOut size={18} />
          </ToolButton>
          <ToolButton
            label="Larger text"
            onClick={() => onZoom(Math.min(1.6, zoom + 0.1))}
            disabled={zoom >= 1.6}
          >
            <ZoomIn size={18} />
          </ToolButton>
          <input
            ref={fileInput}
            type="file"
            accept={documentTypes.join(',')}
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) onOpenFile(file)
              e.target.value = ''
            }}
          />
        </div>
        <span className={styles.counts}>
          {formatCount(length)} characters · {formatCount(countWords(text))} words ·{' '}
          {formatEstimate(estimateSeconds(text, lang, speed))}
        </span>
        <span
          className={`${styles.meter} ${styles[meterLevel]}`}
          title={`${formatCount(length)} of ${formatCount(maxChars)} characters`}
        >
          <span className={styles.meterTrack}>
            <span className={styles.meterFill} style={{ width: `${usage * 100}%` }} />
          </span>
          {formatShort(length)} / {formatShort(maxChars)}
        </span>
        <span className={styles.spacer} />
        {controls && <div className={styles.controls}>{controls}</div>}
        {busy ? (
          <button className={`${styles.generate} ${styles.cancel}`} onClick={onCancel}>
            <span className={styles.progress} style={{ width: `${progress}%` }} aria-hidden />
            <Square size={14} />
            <span>
              {queuePosition
                ? `Waiting… ${queuePosition} ahead`
                : progress
                  ? `Cancel · ${progress}%`
                  : 'Cancel'}
            </span>
          </button>
        ) : (
          <button
            className={styles.generate}
            onClick={onGenerate}
            disabled={empty || (over && !hasSelection)}
            title={
              over && !hasSelection
                ? `Over the ${formatCount(maxChars)}-character limit`
                : undefined
            }
          >
            <Play size={16} />
            <span>{hasSelection ? 'Generate selection' : 'Generate'}</span>
            <kbd className={styles.kbd}>{shortcut}</kbd>
          </button>
        )}
      </div>
    </section>
  )
})

function ToolButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string
  onClick: () => void
  disabled?: boolean
  children: ReactNode
}) {
  return (
    <button
      className={styles.tool}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
    >
      {children}
    </button>
  )
}
