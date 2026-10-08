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
  try {
    response = await fetch(path, { credentials: 'include', ...init })
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
  extractFile: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Extracted>('/v1/files/extract', { method: 'POST', body: form })
  },
}

/** WebSocket URL for a job's stream_url, on the same host as the page. */
export function streamUrl(path: string): string {
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${scheme}//${window.location.host}${path}`
}
