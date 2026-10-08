import type { Page } from '@playwright/test'

/** A toast message (role="status"), not the hidden screen-reader announcement. */
export const toast = (page: Page, text: string | RegExp) =>
  page.getByRole('status').filter({ hasText: text })
