# Narravo: UI Design Specification

> **Theme:** Studio Dark (default) with a matching light theme
> **Stack:** React + TypeScript, plain CSS with design tokens (`web/src/styles/tokens.css`)
> **Fonts:** Inter (interface), JetBrains Mono (editor, times, numbers), from Google Fonts with system fallbacks
> **Icons:** [Lucide](https://lucide.dev) line icons, 1.5 px stroke; no emoji in the interface
> **Supported widths:** 360 px and up; no horizontal page scrolling at any width
> **Studio redesign (October 2026), which takes precedence over the older sections below where they differ:**
> - **Name:** the app is **Narravo**; the top bar shows **Narravo Studio** (logo + name, links to the Studio) with no page links. History and About are reached from the side panel and the account menu (History, Pronunciations, About, Sign out).
> - **Side panel tabs:** **Settings | History**. History lists the last few items (play in the player bar, download) with "See all history →" to the full page; visitors see a sign-in prompt. About · Privacy · Terms links sit at the bottom of the panel.
> - **Voice card + picker:** the chosen voice is a card (avatar initial, name, gender, grade, language tag) with its own ▶ preview; clicking it opens **Choose a voice**: search, language filter, gender chips, sort by grade or name, a ▶ preview on every row, and the mix voice and ratio in the footer. Full screen on phones.
> - **Number boxes:** Speed and Pitch each have a slider and a small box for an exact value (clamped and rounded on Enter or blur). Pitch is always visible.
> - **Editor:** a reading font (Inter, 16 px × zoom), no inner box; tools (Open, Clean, zoom), counts, limit meter and Generate in one row along the bottom.
> - **Phones and tablets (< 1024 px):** above Generate, a row with the voice button (opens the picker), ⚙ (speed and pitch in a sheet) and 🕘 (recent history in a sheet).
>
> **Built so far (M5):** everything below except the playback-speed menu and the shortcuts dialog. Sign in, History and Pronunciations are full pages (§10's dialogs became pages: simpler on phones), and sign-in is by email link (Google arrives with the hosted project in M6). The editor has no undo/redo buttons: Ctrl+Z works while typing, and Clean text / Open file offer Undo in their toast.

---

## Table of Contents

1. [Colour tokens](#1-colour-tokens)
2. [Typography](#2-typography)
3. [Spacing, radius and elevation](#3-spacing-radius-and-elevation)
4. [Motion](#4-motion)
5. [Layout and breakpoints](#5-layout-and-breakpoints)
6. [Top bar](#6-top-bar)
7. [Text editor panel](#7-text-editor-panel)
8. [Player bar and waveform](#8-player-bar-and-waveform)
9. [Voice settings panel](#9-voice-settings-panel)
10. [Dialogs and overlays](#10-dialogs-and-overlays)
11. [Toasts and messages](#11-toasts-and-messages)
12. [History page](#12-history-page)
13. [States and transitions](#13-states-and-transitions)
14. [Keyboard shortcuts](#14-keyboard-shortcuts)
15. [Accessibility](#15-accessibility)

---

## 1. Colour tokens

All colours come from these CSS custom properties. Components never use raw hex values.

| Token | Dark (default) | Light | Usage |
|---|---|---|---|
| `--bg` | `#0f0f13` | `#f7f7fb` | Page background |
| `--surface` | `#1a1a24` | `#ffffff` | Panels and cards |
| `--surface-2` | `#22222f` | `#f1f1f7` | Inputs, inner surfaces, player bar |
| `--surface-3` | `#2a2a3a` | `#e7e7f0` | Hover, pressed, slider tracks |
| `--chrome` | `#13131e` | `#fbfbfe` | Top bar background |
| `--border` | `#2e2e42` | `#dcdce8` | Panel borders, dividers |
| `--border-strong` | `#3a3a52` | `#c4c4d6` | Hover borders, focused inputs (with accent) |
| `--accent` | `#7c5cbf` | `#6a48b0` | Primary buttons, slider fill, focus ring |
| `--accent-hover` | `#9370db` | `#5a3b9c` | Hover on accent; large numeric values |
| `--accent-soft` | `rgb(124 92 191 / 0.18)` | `rgb(106 72 176 / 0.10)` | Selected items, quality badges |
| `--on-accent` | `#ffffff` | `#ffffff` | Text on accent backgrounds |
| `--play` | `#1db97a` | `#14935f` | Play button |
| `--play-hover` | `#22d68e` | `#107a4f` | Play button hover |
| `--download` | `#3b8eea` | `#1f6fd1` | Download button and volume fill |
| `--danger` | `#e05252` | `#c93a3a` | Cancel, destructive actions |
| `--text` | `#e8e8f0` | `#1b1b26` | Primary text |
| `--text-2` | `#9898b8` | `#55556e` | Labels, secondary text |
| `--text-3` | `#6c6c8c` | `#7a7a92` | Hints, placeholders, metadata |
| `--status-ok` | `#4ade80` | `#16a34a` | Ready |
| `--status-busy` | `#f59e0b` | `#b45309` | Queued, generating |
| `--status-error` | `#f87171` | `#dc2626` | Errors |
| `--wave-played` | `#60a5fa` | `#2563eb` | Waveform bars before the playhead |
| `--wave-unplayed` | `#1e3a8a` | `#bfd3f5` | Waveform bars after the playhead |
| `--wave-pending` | `#2a2a3a` | `#e7e7f0` | Bars for audio not yet generated |

**Rules:**
- The theme follows the system setting (`prefers-color-scheme`) unless the user picks one in the top bar; the choice is kept in `localStorage`.
- Text and interactive elements meet WCAG AA contrast (4.5:1 for body text, 3:1 for large text and UI parts) in both themes. `--text-3` is only for hints and metadata, never for essential information.

---

## 2. Typography

| Token | Font | Size / line height | Weight | Usage |
|---|---|---|---|---|
| `--font-ui` | Inter, "Segoe UI", system-ui, sans-serif | — | — | All interface text |
| `--font-mono` | "JetBrains Mono", Consolas, monospace | — | — | Editor, times, numeric values |
| `--type-title` | ui | 16 / 24 px | 600 | App name, page titles |
| `--type-label` | ui | 13 / 20 px | 600 | Buttons, section headers |
| `--type-overline` | ui | 11 / 16 px, +0.06em, uppercase | 600 | Small section labels ("LANGUAGE", "VOICE") |
| `--type-body` | ui | 14 / 22 px | 400 | General text |
| `--type-small` | ui | 12 / 18 px | 400 | Metadata, hints, counts |
| `--type-editor` | mono | 15 / 26 px (zoom 80–160%) | 400 | Text editor |
| `--type-value` | mono | 22 / 28 px | 700 | Speed and pitch values, current time |

Numbers that change (times, counts) use `font-variant-numeric: tabular-nums` so they don't jitter.

---

## 3. Spacing, radius and elevation

| Token | Value | Usage |
|---|---|---|
| `--space-1` … `--space-8` | 4, 8, 12, 16, 20, 24, 32, 48 px | All padding and gaps |
| `--radius-sm` | 6 px | Badges, small buttons |
| `--radius-md` | 10 px | Inputs, dropdowns, cards inside panels |
| `--radius-lg` | 14 px | Panels, dialogs, bottom sheet |
| `--radius-pill` | 999 px | Primary buttons, chips |
| `--shadow-pop` | `0 8px 24px rgb(0 0 0 / 0.35)` dark, `0 8px 24px rgb(20 20 40 / 0.12)` light | Dropdowns, toasts, dialogs |
| `--gutter` | 16 px (mobile), 24 px (≥ 768 px) | Page side padding |

Panels use a 1 px `--border` instead of shadows; only floating elements get `--shadow-pop`.

---

## 4. Motion

| Token | Value | Usage |
|---|---|---|
| `--ease` | `cubic-bezier(0.2, 0, 0, 1)` | All transitions |
| `--dur-fast` | 120 ms | Hover, press, focus |
| `--dur-base` | 200 ms | Panels, toasts, accordion |
| `--dur-slow` | 320 ms | Bottom sheet, dialogs |

- The status dot pulses while busy (1.2 s loop) and is static otherwise.
- The Generate button shows a progress fill that moves with the job's percentage, never an endless animation.
- With `prefers-reduced-motion: reduce`, transitions drop to 0 ms, the dot doesn't pulse and the waveform doesn't animate.

---

## 5. Layout and breakpoints

### Wide (≥ 1024 px)

```
┌───────────────────────────────────────────────────────────────────────────┐
│ TOP BAR   logo · Studio · History              usage ▓▓░  theme  account │  56 px
├───────────────────────────────────────────────────┬───────────────────────┤
│ TEXT EDITOR PANEL                                 │ VOICE SETTINGS        │
│ toolbar: Open · Clean · Pronunciations · Undo/Redo│ Language              │
│                                                   │ Voice  [▶ preview]    │
│ editor (fills height)                             │ Mix voice + ratio     │
│                                                   │ Speed                 │
│                                                   │ Pitch                 │
│ footer: 1,204 chars · ~1m 26s · ▓▓▓░ 1.2k/20k     │                       │
│                              [ Generate  ⌘↵ ]     │                       │  flex
├───────────────────────────────────────────────────┴───────────────────────┤
│ PLAYER BAR  [▶] 00:12 ▁▃▅▇▅▃▁▃▅▇▅▃▁▂▃▅▃▂▁░░░░░░░ 01:26   vol  [Download]│  88 px
└───────────────────────────────────────────────────────────────────────────┘
```

- Content is capped at 1440 px wide and centred.
- The settings column is 320 px; the editor takes the rest.
- The page fills the viewport height (`100dvh`); only the editor scrolls.

### Medium (768–1023 px)

- The settings column becomes a 320 px drawer that slides in from the right, opened by a **Voice** button in the editor toolbar. The current voice name shows on that button.

### Narrow (< 768 px)

```
┌──────────────────────────┐
│ ◼ Narravo Studio  ◐  👤 │  top bar, 52 px
├──────────────────────────┤
│ [Heart · US · 1.0×  ▾]   │  voice summary chip → opens bottom sheet
│ toolbar (icons only)     │
│ editor                   │
│                          │
│ 1,204 chars · ~1m 26s    │
│ [      Generate      ]   │  full-width button
├──────────────────────────┤
│ [▶] ▁▃▅▇▅▃▁░░░  00:12   │  sticky player, 64 px
│              [Download]  │
└──────────────────────────┘
```

- Voice settings open in a bottom sheet (up to 85% of the viewport height, drag handle, closes on swipe down or backdrop tap).
- The player sticks to the bottom and respects `env(safe-area-inset-bottom)`.
- Touch targets are at least 44 × 44 px.

---

## 6. Top bar

| Element | Details |
|---|---|
| Logo + name | 28 px accent square with a waveform icon, then "Narravo Studio" in `--type-title` ("Studio" in `--text-2`). Links to the Studio |
| Navigation | Studio, History (History only when signed in). The current page has an accent underline |
| Usage meter | Signed in and anonymous: a small bar with "12.4k / 100k today" in `--type-small`. Turns `--status-busy` above 80% and `--status-error` at 100% |
| Theme toggle | Cycles System → Dark → Light; the icon shows the current choice |
| Account | Signed out: **Sign in** text button. Signed in: avatar initials with a menu (History, Pronunciations, Sign out) |
| Status dot | 8 px dot left of the usage meter: ready, busy or error, with a tooltip giving the status text |

Background `--chrome`, 1 px bottom `--border`.

---

## 7. Text editor panel

### Toolbar

| Control | Icon | Behaviour |
|---|---|---|
| Open file | `file-up` | Opens a picker for `.txt .md .docx .pdf`. Signed-out users see the sign-in dialog instead |
| Clean text | `sparkles` | Sends the text to `/v1/text/clean` and replaces it; one undo step reverts it |
| Pronunciations | `book-a` | Opens the pronunciations dialog (signed in only) |
| Undo / Redo | `undo-2` / `redo-2` | Editor history |
| Emotion (Indic languages) | `smile` | Menu of the language's emotion tags; inserts ` <tag>` at the end of the sentence the cursor is in. Hint: `*word*` stresses a word. Hidden for languages without emotions |
| Zoom | `zoom-in` / `zoom-out` | 80–160% in 10% steps, remembered |
| Voice (medium widths) | `audio-lines` + voice name | Opens the settings drawer |

Icon buttons are 32 px square (44 px on touch), `--radius-sm`, with a tooltip and an `aria-label`.

### Editor

- A plain `<textarea>` with `--type-editor`, `--surface-2` background and `--radius-md`; focus shows a 2 px `--accent` ring.
- Placeholder: "Type or paste text here, or drop a document."
- **Drag and drop:** dragging a file over the panel shows a dashed `--accent` overlay reading "Drop to open".
- **Selection:** when text is selected, the Generate button label changes to **Generate selection**.
- **Draft:** text is saved to `localStorage` 500 ms after the last keystroke.

### Footer

| Element | Details |
|---|---|
| Counts | "1,204 characters · 212 words · ~1m 26s" in `--type-small`, `--text-3`. Duration uses the same formula as the engine and changes with speed and language |
| Limit meter | Thin bar plus "1.2k / 20k". At 90% it turns `--status-busy`; over the limit it turns `--status-error`, the extra text is highlighted and Generate is disabled with the reason as a tooltip |
| Generate button | Pill, `--accent`, `--type-label`, icon `play`. Shortcut hint chip "Ctrl ↵" (⌘↵ on macOS) |

---

## 8. Player bar and waveform

### Player bar

| Element | Details |
|---|---|
| Play / pause | 44 px round `--play` button with `play` / `pause` icons |
| Current time | `--type-value`, tabular numbers |
| Waveform | Fills the free width; see below |
| Total time | `--type-small`, `--text-3`. While streaming it shows the estimate with a "~" prefix |
| Volume | Mute button + 80 px slider (`--download` fill). Hidden on narrow screens; the device volume is used there |
| Speed of playback | 0.75×, 1×, 1.25×, 1.5×, 2× menu. This is playback only and separate from the voice speed |
| Download | Pill button, `--download` outline. A menu offers MP3, plus WAV when signed in. Disabled until the job is done |

Background `--surface-2`, 1 px top `--border`.

The player bar is part of the app layout, not the Studio: it stays at the bottom of every page and keeps playing while you move between pages. It plays either the Studio's current job or a finished file from History (labelled with its voice and language); starting one pauses the other, and when a job finishes while History audio is playing, the "Audio ready" toast offers **Play** to switch back.

### Waveform

- Bars are 2 px wide with 1 px gaps, centred vertically, height = peak amplitude × 90% of the area height.
- Colours: `--wave-played` before the playhead, `--wave-unplayed` after it, and `--wave-pending` for the part not yet generated while streaming (its length comes from the duration estimate).
- **Streaming:** bars fill in from the left as chunks arrive; playback can start as soon as the first chunk is in.
- **Seeking:** click or drag to seek. Seeking past the generated part jumps to its end. Arrow keys move 5 s when the waveform has focus.
- **Empty:** a flat line with "Your audio will appear here" in `--text-3`.

---

## 9. Voice settings panel

```
VOICE SETTINGS
LANGUAGE        [ American English      ▾ ]
VOICE           [ Heart   A  ♀           ▾ ] [▶]
MIX WITH        [ None                   ▾ ]
                 Heart 70% ───────●─── 30% Bella
SPEED                  1.0×
                0.5× ───────●─────── 2.0×
PITCH                  +0 st
                −6 ───────●─────── +6
                                    [Reset]
```

| Control | Details |
|---|---|
| Language | Select grouped by engine: "Narravo Standard" (7 Kokoro languages) and "Narravo Indic" (23 Indic-Mio languages). Changing it keeps the voice if the new language has it, otherwise switches to the default voice; the mix voice is cleared |
| Voice | Select listing voices with a quality grade badge (`--accent-soft` chip: A, B−, C+ …) and gender icon; ordered by grade. Indic voices recorded in an Indian language carry a "Native" tag. The voice card shows the language with "· Indic" for Indic-Mio languages |
| Preview | 32 px icon button; plays a stored sample of the voice. Pressing it again stops |
| Mix with | Optional second voice of the same language. When set, a ratio slider appears (10–90%, step 10), labelled with both voice names |
| Speed | Value in `--type-value`, `--accent-hover`; slider 0.5–2.0, step 0.05; double-click the value to reset to 1.0 |
| Pitch | Slider −6 to +6 semitones, step 0.5; always visible (no "Advanced" section) |
| Reset | Text button restoring the language's defaults |

All settings are remembered in `localStorage`. Sliders show their value while dragging and support arrow keys (small step) and Page Up/Down (large step).

---

## 10. Dialogs and overlays

All dialogs are centred on wide screens and full-height sheets on narrow screens, with `--radius-lg`, `--shadow-pop` and a 50% black backdrop. Escape and the backdrop close them; focus is trapped inside and returns to the opener on close.

| Dialog | Contents |
|---|---|
| **Pronunciations** | Table of "Word" → "Say as" rows with add, edit and delete. A hint explains phonemes in slashes (`/kˈOkəɹO/`, English voices only). A **Test** button speaks the row. Saved to the account |
| **Sign in** | Shown when a signed-out user tries a signed-in feature or hits the anonymous limit. Says what signing in unlocks (higher limits, files, history, pronunciations), then email-link and Google buttons |
| **Cancel long job** | Confirmation only for jobs over 2 minutes of audio: "Stop generating? The audio so far will be discarded." |
| **Keyboard shortcuts** | Opened with `?`; lists [§14](#14-keyboard-shortcuts) |

---

## 11. Toasts and messages

Toasts appear at the top centre, just under the top bar (at the bottom they covered the Generate button), stack up to three, and close by themselves after 5 s (errors stay until dismissed). Each has an icon, a message and an optional action.

| Kind | Icon / colour | Example |
|---|---|---|
| Info | `info`, `--text` | "Text cleaned. Undo to revert." **Undo** |
| Success | `check-circle`, `--status-ok` | "Audio ready: 1m 26s." **Download** |
| Warning | `alert-triangle`, `--status-busy` | "You're at 90% of today's limit." |
| Error | `alert-octagon`, `--status-error` | "Couldn't open this PDF: it has no selectable text." |

### API error messages

| Code | Message shown | Action |
|---|---|---|
| `invalid_input` | The API's message, e.g. "Choose a voice for this language." | — |
| `too_long` | "This text is over your limit of 20,000 characters per request." | Generate selection |
| `quota_exceeded` | "You've used today's 100,000 characters. The limit resets at midnight UTC." | Sign in (anonymous only) |
| `rate_limited` | "Too many requests. Try again in a few seconds." | — |
| `busy` | "The service is busy right now. Try again in a minute." | Retry |
| `not_found` | "This audio has expired." | — |
| `internal` | "Something went wrong on our side. Please try again." | Retry |
| connection lost | "Connection lost. Reconnecting…" (keeps audio already received) | — |

---

## 12. History page

- A list of the last 7 days of generations, newest first, grouped by day.
- The input text is never stored, so each row shows voice, language, duration, character count and time, e.g. "Heart · US English · 1m 26s · 1,204 chars · 14:32".
- Row actions: play inline, download, and **Use these settings** (copies voice, mix, speed and pitch into the Studio).
- Expired rows aren't shown. Empty state: "Nothing here yet. Audio you generate is kept for 7 days."

---

## 13. States and transitions

```
IDLE ──Generate──► QUEUED ──first chunk──► STREAMING ──done──► READY
  ▲                  │                        │                  │
  │               cancel / error           cancel / error        │ edit text or settings
  └──────────────────┴────────────────────────┴──────────────────┘ (READY keeps the audio until the next Generate)
```

| State | Generate button | Editor and settings | Player | Status |
|---|---|---|---|---|
| **Idle** | Enabled ("Generate") | Editable | Empty or previous audio | Ready |
| **Queued** | Becomes **Cancel** (`--danger` outline); "Waiting… 2 ahead" below | Read-only | Empty | Busy |
| **Streaming** | **Cancel** with progress fill (percent) | Read-only | Plays as chunks arrive; Download disabled | Busy: "Generating 42%" |
| **Ready** | Enabled | Editable | Full waveform, seek, Download enabled | Ready; success toast |
| **Cancelled** | Enabled | Editable | Audio discarded | Ready; info toast |
| **Error** | Enabled | Editable | Audio so far kept if any, Download disabled | Error; error toast |

While a job runs, leaving the page asks for confirmation for anonymous users (their job can't be found again). Signed-in users can leave; the result appears in History.

---

## 14. Keyboard shortcuts

| Keys (Windows / macOS) | Action |
|---|---|
| Ctrl + Enter / ⌘ + Enter | Generate (or generate selection) |
| Esc | Cancel generation / close dialog |
| Ctrl + Space / ⌃ + Space | Play / pause (also Space when the editor isn't focused) |
| ← / → (player focused) | Seek 5 s |
| Ctrl + O / ⌘ + O | Open file |
| Ctrl + Shift + L / ⌘ + Shift + L | Clean text |
| Ctrl + Z, Ctrl + Y / ⌘ + Z, ⌘ + Shift + Z | Undo, redo |
| Ctrl + = / Ctrl + − | Editor zoom |
| Ctrl + S / ⌘ + S | Download MP3 (when ready) |
| ? | Show shortcuts |

Shortcuts never override the browser's own when the matching feature isn't available (for example, Ctrl + S does nothing special before audio exists).

---

## 15. Accessibility

- Every control is reachable and usable with the keyboard, in visual order, with a visible 2 px `--accent` focus ring (`:focus-visible`).
- Icon-only buttons have `aria-label`s and tooltips.
- Status changes (queued, generating percentage at 25% steps, ready, errors) are announced through one polite `aria-live` region.
- Sliders are native `<input type="range">` with `aria-valuetext` ("1.25 times", "plus 2 semitones").
- The waveform is a `role="slider"` for the playhead with the current and total time as its value text.
- Colour is never the only signal: status has text, limit warnings have text, waveform progress also shows the time.
- Works at 200% browser zoom without loss of content.
- Tested with keyboard only, NVDA (Windows) and VoiceOver (macOS and iOS) before launch.
