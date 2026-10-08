// Theme: follow the system, or a choice the visitor made (DESIGN.md §1).

import { useEffect, useState } from 'react'

import { load, save } from './storage'

export type ThemeChoice = 'system' | 'dark' | 'light'
const ORDER: ThemeChoice[] = ['system', 'dark', 'light']
const KEY = 'narravo.theme'

export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement
  if (choice === 'system') delete root.dataset.theme
  else root.dataset.theme = choice
}

export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(() => load<ThemeChoice>(KEY, 'system'))
  useEffect(() => {
    applyTheme(choice)
    save(KEY, choice)
  }, [choice])
  const cycle = () => setChoice((c) => ORDER[(ORDER.indexOf(c) + 1) % ORDER.length])
  return [choice, cycle] as const
}
