import { expect, test } from '@playwright/test'

import { toast } from './helpers'

const unique = () => `Run ${Date.now()}.`

test.beforeEach(async ({ page }) => {
  await page.goto('/')
  await expect(page.getByLabel('Voice', { exact: true })).toBeVisible() // voices loaded
})

test('type, generate, hear it while it streams, then download', async ({ page }) => {
  const editor = page.getByLabel('Text to speak')
  await editor.fill(`Hello from the browser test. ${unique()}`)
  await expect(page.getByText(/characters · \d+ words · ~\d+s/)).toBeVisible()

  await page.getByRole('button', { name: /^Generate/ }).click()
  await expect(page.getByRole('button', { name: /Cancel|Waiting/ })).toBeVisible()
  await expect(toast(page, /^Audio ready/)).toBeVisible()

  // The player moved forward (audio actually played) and the download link is ready
  const position = page.getByRole('slider', { name: 'Playback position' })
  await expect
    .poll(async () => Number(await position.getAttribute('aria-valuenow')))
    .toBeGreaterThan(0)
  const download = page.getByRole('link', { name: 'Download' })
  await expect(download).not.toHaveAttribute('aria-disabled', 'true')
  await expect(download).toHaveAttribute('href', /kokoro-tts-audio\/audio\/anon\/.+\.mp3/)
  await page.screenshot({ path: 'test-results/studio-desktop.png' })
})

test('cancel a long job', async ({ page }) => {
  const paragraph =
    'The history of speech synthesis goes back centuries, to mechanical devices that imitated the human vocal tract. '
  await page.getByLabel('Text to speak').fill(paragraph.repeat(14) + unique())
  await page.getByRole('button', { name: /^Generate/ }).click()
  await page.getByRole('button', { name: /Cancel/ }).click()
  await expect(toast(page, 'Stopped.')).toBeVisible()
  await expect(page.getByRole('button', { name: /^Generate/ })).toBeEnabled()
})

test('open a text file, clean it, and undo', async ({ page }) => {
  await page.locator('input[type=file]').setInputFiles({
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('\u201cQuoted\u201d text with a link: www.example.org.'),
  })
  const editor = page.getByLabel('Text to speak')
  await expect(editor).toHaveValue('\u201cQuoted\u201d text with a link: www.example.org.')

  await page.getByRole('button', { name: /Clean text/ }).click()
  await expect(editor).toHaveValue('"Quoted" text with a link:.')
  await toast(page, 'Text cleaned.').getByRole('button', { name: 'Undo' }).click()
  await expect(editor).toHaveValue('\u201cQuoted\u201d text with a link: www.example.org.')
})

test('voice settings: language change picks its default voice, mixing shows the ratio', async ({
  page,
}) => {
  await page.getByLabel('Language').selectOption({ label: 'British English' })
  await expect(page.getByLabel('Voice', { exact: true })).toHaveValue('bf_emma')
  await page.getByLabel('Mix with').selectOption({ label: 'George ♂' })
  await expect(page.getByText(/Emma \d+%/)).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Voice', { exact: true })).toHaveValue('bf_emma') // remembered
})

test('the text limit blocks Generate', async ({ page }) => {
  await page.getByLabel('Text to speak').fill('x'.repeat(2001))
  await expect(page.getByRole('button', { name: /^Generate/ })).toBeDisabled()
})

test('about page and theme switch', async ({ page }) => {
  await page.getByRole('link', { name: 'About' }).first().click()
  await expect(page.getByRole('heading', { name: 'About' })).toBeVisible()
  await page.getByRole('button', { name: /Theme/ }).click() // system → dark
  await page.goto('/')
  await page.screenshot({ path: 'test-results/studio-dark.png' })
  await page.goto('/about')
  await page.getByRole('button', { name: /Theme/ }).click() // dark → light
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await page.goto('/')
  await page.screenshot({ path: 'test-results/studio-light.png' })
})
