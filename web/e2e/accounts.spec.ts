import { expect, test } from '@playwright/test'

import { signIn, toast } from './helpers'

test('sign in with an email link, generate, find it in History with a WAV', async ({ page }) => {
  await signIn(page)
  await expect(page.getByText(/\/ 100k today/)).toBeVisible() // signed-in daily limit
  await page.getByLabel('Text to speak').fill(`Signed in and speaking. ${Date.now()}`)
  await page.getByRole('button', { name: /^Generate/ }).click()
  await expect(toast(page, /^Audio ready/)).toBeVisible()
  await expect(page.getByRole('link', { name: 'WAV' })).toHaveAttribute('href', /\.wav/)

  await page.getByRole('link', { name: 'History' }).click()
  await expect(page.getByRole('heading', { name: 'History' })).toBeVisible()
  await expect(page.getByRole('listitem')).toHaveCount(1)
  await expect(page.getByRole('listitem').getByRole('link', { name: 'WAV' })).toBeVisible()
  await page.screenshot({ path: 'test-results/history.png' })
})

test('saved pronunciations', async ({ page }) => {
  await signIn(page)
  await page.goto('/pronunciations')
  await page.getByRole('button', { name: 'Add' }).click()
  await page.getByLabel('Word').fill('Kokoro')
  await page.getByLabel('Say as').fill('koh koh roh')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(toast(page, 'Pronunciations saved')).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Say as')).toHaveValue('koh koh roh')
  await page.screenshot({ path: 'test-results/pronunciations.png' })
})

test('visitors are asked to sign in to open documents', async ({ page }) => {
  await page.goto('/')
  await page.locator('input[type=file]').setInputFiles({
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Hello.'),
  })
  await expect(toast(page, 'Sign in to open documents.')).toBeVisible()
  await toast(page, 'Sign in to open documents.').getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/signin$/)
  await page.screenshot({ path: 'test-results/signin.png' })
})

test('sign out', async ({ page }) => {
  const email = await signIn(page)
  await page.getByRole('button', { name: `Account: ${email}` }).click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await expect(page.getByRole('link', { name: 'Sign in' })).toBeVisible()
  await expect(page.getByText(/\/ 10k today/)).toBeVisible()
})
