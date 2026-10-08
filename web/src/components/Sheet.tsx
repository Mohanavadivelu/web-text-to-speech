// A modal panel: a drawer from the right on medium screens, a bottom sheet on phones
// (DESIGN.md §5). Built on <dialog>, which traps focus and closes on Escape.

import { X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'

import styles from './Sheet.module.css'

interface Props {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}

export function Sheet({ open, onClose, title, children }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const el = dialog.current
    if (!el) return
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()
  }, [open])

  return (
    <dialog
      ref={dialog}
      className={styles.sheet}
      aria-label={title}
      onClose={onClose}
      onClick={(e) => e.target === e.currentTarget && onClose()} // backdrop
    >
      <div className={styles.body}>
        <span className={styles.handle} aria-hidden />
        <button className={styles.close} onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>
        {children}
      </div>
    </dialog>
  )
}
