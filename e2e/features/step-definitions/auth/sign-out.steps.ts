import type { DATAWorld } from '../../support/world'
import { Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'

When('I open the account menu', async function (this: DATAWorld) {
  const page = this.getPage()
  const trigger = page.getByRole('button', { name: 'Account' })

  await expect(trigger).toBeVisible()
  await trigger.click()
})

When('I sign out', async function (this: DATAWorld) {
  const page = this.getPage()

  await expect(page.getByText('Log out')).toBeVisible()
  await page.getByText('Log out').click()
})

Then('I should be on the sign-in page', async function (this: DATAWorld) {
  await expect(this.getPage()).toHaveURL(/\/signin/)
  await expect(this.getPage().getByRole('button', { name: /^Sign in$/i })).toBeVisible({
    timeout: 30_000,
  })
})
