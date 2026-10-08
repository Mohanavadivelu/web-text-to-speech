import { expect, test } from '@playwright/test'

import { toast } from './helpers'

test('phone: voice, settings and history above Generate; no sideways scrolling', async ({
  page,
}) => {
  await page.goto('/')
  const voiceChip = page.getByRole('button', { name: /^Voice: .*Change voice$/ })
  await expect(voiceChip).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(0)
  await page.screenshot({ path: 'test-results/studio-phone.png' })

  // The voice picker opens full screen
  await voiceChip.click()
  const picker = page.getByRole('dialog', { name: 'Choose a voice' })
  await picker.getByLabel('Language filter').selectOption({ label: 'Hindi' })
  await picker
    .getByRole('listbox', { name: 'Voices' })
    .getByRole('option', { name: /Alpha/ })
    .click()
  await page.screenshot({ path: 'test-results/voice-picker-phone.png' })
  await picker.getByRole('button', { name: 'Use voice' }).click()
  await expect(voiceChip).toHaveAccessibleName(/Alpha/)

  // Speed and pitch in a bottom sheet
  await page.getByRole('button', { name: 'Voice settings' }).click()
  const sheet = page.getByRole('dialog', { name: 'Voice settings' })
  await expect(sheet.getByLabel('Pitch value')).toBeVisible()
  await page.screenshot({ path: 'test-results/studio-phone-sheet.png' })
  await sheet.getByRole('button', { name: 'Close' }).click()

  await page.getByLabel('Text to speak').fill(`नमस्ते, यह एक परीक्षण है। ${Date.now()}`)
  await page.getByRole('button', { name: /^Generate/ }).click()
  await expect(toast(page, /^Audio ready/)).toBeVisible()
})
