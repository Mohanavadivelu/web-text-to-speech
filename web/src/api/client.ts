// Typed access to the API. Types come from schema.d.ts, generated from the API's
// OpenAPI schema (`npm run api:types`), so a changed API shows up as a type error here.

import type { components } from './schema'

type Schemas = components['schemas']
export type Job = Schemas['JobOut']
export type JobCreate = Schemas['JobCreate']
export type Voices = Schemas['VoicesResponse']
export type Language = Schemas['LanguageOut']
export type Voice = Schemas['VoiceOut']
export type Config = Schemas['ConfigOut']
export type Extracted = Schemas['ExtractOut']
export type ErrorCode = Schemas['ErrorBody']['code']
export type Me = Schemas['MeOut']
export type HistoryItem = Schemas['HistoryItem']
export type Pronunciation = Schemas['Pronunciation']

// The signed-in user's access token (set by AuthProvider); null = anonymous visitor.
let accessToken: string | null = null
export function setAccessToken(token: string | null): void {
  accessToken = token
}

/** An API error with the server's code and a message that's safe to show. */
export class ApiError extends Error {
  readonly code: ErrorCode | 'network'
  readonly retryAfter: number | null

  constructor(code: ErrorCode | 'network', message: string, retryAfter: number | null = null) {
    super(message)
    this.code = code
    this.retryAfter = retryAfter
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  const headers = new Headers(init?.headers)
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  try {
    response = await fetch(path, { credentials: 'include', ...init, headers })
  } catch {
    throw new ApiError('network', "Can't reach the server. Check your connection and try again.")
  }
  if (response.ok) return (await response.json()) as T

  const retry = Number(response.headers.get('Retry-After')) || null
  try {
    const body = (await response.json()) as { error?: { code: ErrorCode; message: string } }
    if (body.error) throw new ApiError(body.error.code, body.error.message, retry)
  } catch (err) {
    if (err instanceof ApiError) throw err
  }
  throw new ApiError('internal', 'Something went wrong on our side. Please try again.', retry)
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  voices: () => request<Voices>('/v1/voices'),
  config: () => request<Config>('/v1/config'),
  createJob: (body: JobCreate) => request<Job>('/v1/tts/jobs', json(body)),
  getJob: (id: string) => request<Job>(`/v1/tts/jobs/${encodeURIComponent(id)}`),
  cancelJob: (id: string) =>
    request<Job>(`/v1/tts/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  cleanText: (text: string) => request<{ text: string }>('/v1/text/clean', json({ text })),
  me: () => request<Me>('/v1/me'),
  history: () => request<Schemas['HistoryOut']>('/v1/me/history'),
  pronunciations: () => request<Schemas['PronunciationsBody']>('/v1/me/pronunciations'),
  savePronunciations: (entries: Pronunciation[]) =>
    request<Schemas['PronunciationsBody']>('/v1/me/pronunciations', {
      ...json({ entries }),
      method: 'PUT',
    }),
  extractFile: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Extracted>('/v1/files/extract', { method: 'POST', body: form })
  },
}

/** Open a job's stream. Browsers can't set headers on WebSockets, so a signed-in
 * user's token travels as a subprotocol (never in the URL, which would be logged). */
export function openStream(path: string): WebSocket {
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${scheme}//${window.location.host}${path}`
  return accessToken ? new WebSocket(url, ['kokoro', `auth.${accessToken}`]) : new WebSocket(url)
}
