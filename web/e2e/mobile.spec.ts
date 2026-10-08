import { expect, test } from '@playwright/test'

import { toast } from './helpers'

test('phone layout: voice settings in a bottom sheet, no sideways scrolling', async ({ page }) => {
  await page.goto('/')
  const chip = page.getByRole('button', { name: /Voice settings:/ })
  await expect(chip).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(0)

  await chip.click()
  const sheet = page.getByRole('dialog', { name: 'Voice settings' })
  await expect(sheet).toBeVisible()
  await sheet.getByLabel('Language').selectOption({ label: 'Hindi' })
  await page.screenshot({ path: 'test-results/studio-phone-sheet.png' })
  await sheet.getByRole('button', { name: 'Close' }).click()
  await expect(chip).toContainText('Hindi')

  await page.getByLabel('Text to speak').fill(`नमस्ते, यह एक परीक्षण है। ${Date.now()}`)
  await page.getByRole('button', { name: /^Generate/ }).click()
  await expect(toast(page, /^Audio ready/)).toBeVisible()
  await page.screenshot({ path: 'test-results/studio-phone.png' })
})
