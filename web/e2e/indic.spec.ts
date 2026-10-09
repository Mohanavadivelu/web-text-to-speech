import { expect, test } from '@playwright/test'

import { toast } from './helpers'

// Needs the GPU stack (server/docker-compose.gpu.yml): run with E2E_INDIC=1
test.skip(!process.env.E2E_INDIC, 'Indic-Mio needs the GPU workers (set E2E_INDIC=1)')

test('Indic: Tamil with a native voice, an emotion tag, streamed to the player', async ({
  page,
}) => {
  await page.goto('/')
  await page.getByRole('button', { name: /^Voice: .*Change voice$/ }).click()
  const picker = page.getByRole('dialog', { name: 'Choose a voice' })
  await picker.getByLabel('Language').selectOption({ label: 'Tamil' })
  const voices = picker.getByRole('listbox', { name: 'Voices' })
  await expect(voices.getByRole('option')).toHaveCount(10) // every Indic voice speaks Tamil
  await expect(voices.getByText('Native')).toHaveCount(4)
  await page.screenshot({ path: 'test-results/indic-picker.png' })
  await voices.getByRole('option', { name: /Ananya/ }).click()
  await picker.getByRole('button', { name: 'Use voice' }).click()
  await expect(page.getByRole('button', { name: /^Voice: Ananya, Tamil/ })).toBeVisible()

  const editor = page.getByLabel('Text to speak')
  await editor.fill(`வணக்கம்! இன்று வானிலை மிகவும் அருமையாக இருக்கிறது. ${Date.now() % 1000}`)
  await editor.click({ position: { x: 10, y: 10 } }) // cursor in the first sentence
  await page.getByRole('button', { name: 'Add an emotion to this sentence' }).click()
  await page.getByRole('menuitem', { name: 'happy' }).click()
  await expect(editor).toHaveValue(/வணக்கம்! <happy>/)

  await page.getByRole('button', { name: /^Generate/ }).click()
  await expect(toast(page, /^Audio ready/)).toBeVisible({ timeout: 120_000 })
  const position = page.getByRole('slider', { name: 'Playback position' })
  await expect
    .poll(async () => Number(await position.getAttribute('aria-valuenow')))
    .toBeGreaterThan(0)
  await page.screenshot({ path: 'test-results/indic-studio.png' })
})
