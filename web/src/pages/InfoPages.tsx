// About, Privacy, Terms and Not found. The legal pages are drafts until M6.7.

import type { ReactNode } from 'react'

import { Link } from '../components/Link'
import styles from './InfoPages.module.css'

function Page({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className={styles.page}>
      <h1>{title}</h1>
      {children}
      <nav className={styles.links} aria-label="More information">
        <Link href="/">Studio</Link>
        <Link href="/about">About</Link>
        <Link href="/privacy">Privacy</Link>
        <Link href="/terms">Terms</Link>
      </nav>
    </article>
  )
}

export function About() {
  return (
    <Page title="About">
      <p>
        Narravo turns text into natural-sounding speech in your browser. Paste text or open a
        document, choose one of 37 voices in 7 languages, and listen while it&apos;s being made.
      </p>
      <h2>How it works</h2>
      <p>
        Speech is generated on our servers by the open{' '}
        <a href="https://huggingface.co/hexgrad/Kokoro-82M">Kokoro-82M</a> model. Audio streams to
        your browser as it&apos;s made, so you can start listening after a second or two, even for
        long texts.
      </p>
      <h2>Credits</h2>
      <ul>
        <li>
          <a href="https://huggingface.co/hexgrad/Kokoro-82M">Kokoro-82M</a> by hexgrad (Apache-2.0)
        </li>
        <li>
          <a href="https://github.com/hexgrad/misaki">misaki</a> (MIT) and{' '}
          <a href="https://github.com/espeak-ng/espeak-ng">espeak-ng</a> (GPL-3.0) for turning text
          into phonemes
        </li>
        <li>
          <a href="https://onnxruntime.ai">ONNX Runtime</a> (MIT)
        </li>
      </ul>
    </Page>
  )
}

export function Privacy() {
  return (
    <Page title="Privacy">
      <p className={styles.draft}>Draft: to be reviewed before launch.</p>
      <h2>Your text</h2>
      <p>
        The text you convert is used only to make your audio. It is never stored and never written
        to our logs; we keep only its length and the voice settings.
      </p>
      <h2>Your audio</h2>
      <p>
        Generated audio is kept privately and deleted automatically after 1 day. Download links
        expire after one hour.
      </p>
      <h2>Cookies and storage</h2>
      <p>
        We set one cookie, <code>anon_id</code>, so we can show you your own jobs and keep usage
        fair. Your draft text, voice settings and theme are saved in your browser only. There are no
        advertising or tracking cookies.
      </p>
      <h2>Services we use</h2>
      <p>
        Hetzner (servers), Cloudflare (network and storage), Supabase (accounts) and Sentry (error
        reports, without your text).
      </p>
    </Page>
  )
}

export function Terms() {
  return (
    <Page title="Terms of use">
      <p className={styles.draft}>Draft: to be reviewed before launch.</p>
      <ul>
        <li>Don&apos;t use the service for anything illegal, or to impersonate real people.</li>
        <li>Daily limits keep the free service fair; they may change.</li>
        <li>You&apos;re responsible for the text you convert and how you use the audio.</li>
        <li>The service is provided as is, without guarantees of availability.</li>
      </ul>
    </Page>
  )
}

export function NotFound() {
  return (
    <Page title="Page not found">
      <p>This page doesn&apos;t exist.</p>
    </Page>
  )
}
