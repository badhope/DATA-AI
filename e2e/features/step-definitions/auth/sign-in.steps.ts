import type { DATAWorld } from '../../support/world'
import { Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'
import { adminCredentials } from '../../../fixtures/auth'

When('I open the sign-in page', async function (this: DATAWorld) {
  await this.getPage().goto('/signin')
})

When('I sign in as the default E2E admin', async function (this: DATAWorld) {
  const page = this.getPage()

  await page.getByLabel('Email address').fill(adminCredentials.email)
  await page.getByLabel('Password', { exact: true }).fill(adminCredentials.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
})

Then('I should be on the apps console', async function (this: DATAWorld) {
  await expect(this.getPage()).toHaveURL(/\/apps(?:\?.*)?$/, { timeout: 30_000 })
})
