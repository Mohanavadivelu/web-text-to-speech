import type { ApiError } from '../api/client'
import type { ToastInput } from './toast'

/** What to tell the visitor for an API error (DESIGN.md §11). */
export function errorToast(error: ApiError, retry?: () => void): ToastInput {
  switch (error.code) {
    case 'rate_limited':
    case 'busy':
    case 'internal':
    case 'network':
      return {
        kind: 'error',
        message: error.message,
        action: retry && { label: 'Retry', run: retry },
      }
    default:
      return { kind: 'error', message: error.message }
  }
}
