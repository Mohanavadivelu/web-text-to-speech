import { expect, type Page } from '@playwright/test'

/** A toast message (role="status"), not the hidden screen-reader announcement. */
export const toast = (page: Page, text: string | RegExp) =>
  page.getByRole('status').filter({ hasText: text })

const MAILPIT = 'http://127.0.0.1:54324'

/** The sign-in link Supabase sent to `email`, read from the local Mailpit inbox. */
async function signInLink(page: Page, email: string): Promise<string> {
  let link = ''
  await expect
    .poll(
      async () => {
        const list = await (
          await page.request.get(`${MAILPIT}/api/v1/search?query=to:${email}`)
        ).json()
        const id = list.messages?.[0]?.ID
        if (!id) return ''
        const message = await (await page.request.get(`${MAILPIT}/api/v1/message/${id}`)).json()
        link =
          /(http:\/\/127\.0\.0\.1:54321\/auth\/v1\/verify[^\s"<>]+)/.exec(message.Text)?.[1] ?? ''
        return link
      },
      { timeout: 20_000 },
    )
    .not.toBe('')
  return link.replaceAll('&amp;', '&')
}

/** Sign in through the real flow: request a link, open it from the inbox. */
export async function signIn(page: Page, email = `e2e-${Date.now()}@example.com`): Promise<string> {
  await page.goto('/signin')
  await page.getByLabel('Email').fill(email)
  await page.getByRole('button', { name: 'Email me a sign-in link' }).click()
  await expect(page.getByText('Check your email.')).toBeVisible()
  await page.goto(await signInLink(page, email))
  await expect(page.getByRole('button', { name: `Account: ${email}` })).toBeVisible()
  return email
}
