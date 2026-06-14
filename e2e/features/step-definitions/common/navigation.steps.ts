import type { DATAWorld } from '../../support/world'
import { Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'

When('I open the apps console', async function (this: DATAWorld) {
  await this.getPage().goto('/apps')
})

Then('I should stay on the apps console', async function (this: DATAWorld) {
  await expect(this.getPage()).toHaveURL(/\/apps(?:\?.*)?$/)
})

Then('I should be redirected to the signin page', async function (this: DATAWorld) {
  await expect(this.getPage()).toHaveURL(/\/signin(?:\?.*)?$/)
})

Then('I should see the {string} button', async function (this: DATAWorld, label: string) {
  await expect(this.getPage().getByRole('button', { name: label })).toBeVisible()
})

Then('I should not see the {string} button', async function (this: DATAWorld, label: string) {
  await expect(this.getPage().getByRole('button', { name: label })).not.toBeVisible()
})

Then('I should see the {string} text', async function (this: DATAWorld, text: string) {
  await expect(this.getPage().getByText(text)).toBeVisible({ timeout: 30_000 })
})
