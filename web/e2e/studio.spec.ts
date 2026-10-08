import { expect, test, type Page } from '@playwright/test'

import { signIn, toast } from './helpers'

const unique = () => `Run ${Date.now()}.`
const voiceCard = (page: Page) => page.getByRole('button', { name: /^Voice: .*Change voice$/ })

test.beforeEach(async ({ page }) => {
  await page.goto('/')
  await expect(voiceCard(page)).toBeVisible() // voices loaded
})

test('Narravo Studio branding, no page links in the top bar', async ({ page }) => {
  await expect(page).toHaveTitle('Narravo Studio')
  await expect(page.getByRole('link', { name: 'Narravo Studio, home' })).toBeVisible()
  const topBar = page.locator('header')
  await expect(topBar.getByRole('link', { name: 'History' })).toHaveCount(0)
  await expect(topBar.getByRole('link', { name: 'About' })).toHaveCount(0)
})

test('type, generate, hear it while it streams, then download', async ({ page }) => {
  const editor = page.getByLabel('Text to speak')
  await editor.fill(`Hello from the browser test. ${unique()}`)
  await expect(page.getByText(/characters · \d+ words · ~\d+s/)).toBeVisible()

  await page.getByRole('button', { name: /^Generate/ }).click()
  await expect(page.getByRole('button', { name: /Cancel|Waiting/ })).toBeVisible()
  await expect(toast(page, /^Audio ready/)).toBeVisible()

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
  await signIn(page) // opening documents needs an account
  await page.locator('input[type=file]').setInputFiles({
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('“Quoted” text with a link: www.example.org.'),
  })
  const editor = page.getByLabel('Text to speak')
  await expect(editor).toHaveValue('“Quoted” text with a link: www.example.org.')

  await page.getByRole('button', { name: /Clean text/ }).click()
  await expect(editor).toHaveValue('"Quoted" text with a link:.')
  await toast(page, 'Text cleaned.').getByRole('button', { name: 'Undo' }).click()
  await expect(editor).toHaveValue('“Quoted” text with a link: www.example.org.')
})

test('choose a voice in the picker: filter, preview, mix, remembered', async ({ page }) => {
  await voiceCard(page).click()
  const picker = page.getByRole('dialog', { name: 'Choose a voice' })
  await expect(picker).toBeVisible()
  await page.screenshot({ path: 'test-results/voice-picker.png' })

  await picker.getByLabel('Language filter').selectOption({ label: 'British English' })
  await picker.getByRole('button', { name: '♂ Male' }).click()
  const voiceList = picker.getByRole('listbox', { name: 'Voices' })
  await expect(voiceList.getByRole('option')).toHaveCount(4) // UK male voices
  await picker.getByRole('button', { name: '♀ Female' }).click()
  await picker.getByRole('option', { name: /Emma/ }).click()
  await expect(picker.getByRole('option', { name: /Emma/ })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await picker.getByLabel('Mix with').selectOption({ label: 'George ♂' })
  await expect(picker.getByText(/Emma \d+%/)).toBeVisible()
  await picker.getByRole('button', { name: 'Use voice' }).click()

  await expect(voiceCard(page)).toHaveAccessibleName(/Emma, British English/)
  await expect(page.getByRole('button', { name: /Mixed with George/ })).toBeVisible()
  await page.reload()
  await expect(voiceCard(page)).toHaveAccessibleName(/Emma/) // remembered
})

test('exact values in the number boxes; pitch always visible', async ({ page }) => {
  await expect(page.getByText('Advanced')).toHaveCount(0)
  const speed = page.getByLabel('Speed value')
  await speed.fill('1.3')
  await speed.press('Enter')
  await expect(page.getByRole('slider', { name: 'Speed' })).toHaveValue('1.3')
  const pitch = page.getByLabel('Pitch value')
  await pitch.fill('9') // over the limit: clamped
  await pitch.press('Enter')
  await expect(pitch).toHaveValue('6')
})

test('the text limit blocks Generate', async ({ page }) => {
  await page.getByLabel('Text to speak').fill('x'.repeat(2001))
  await expect(page.getByRole('button', { name: /^Generate/ })).toBeDisabled()
})

test('History tab for visitors, About from the panel, theme switch', async ({ page }) => {
  await page.getByRole('tab', { name: 'History' }).click()
  await expect(page.getByText('Sign in to keep your audio for 7 days')).toBeVisible()
  await page.getByRole('tab', { name: 'Settings' }).click()

  await page.getByRole('link', { name: 'About' }).click()
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
