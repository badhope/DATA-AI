import type { DATAWorld } from '../../support/world'
import { Then, When } from '@cucumber/cucumber'
import { expect } from '@playwright/test'

When('I open the publish panel', async function (this: DATAWorld) {
  await this.getPage().getByRole('button', { name: 'Publish' }).first().click()
})

When('I publish the app', async function (this: DATAWorld) {
  await this.getPage()
    .getByRole('button', { name: /Publish Update/ })
    .click()
})

Then('the app should be marked as published', async function (this: DATAWorld) {
  await expect(this.getPage().getByRole('button', { name: 'Published' })).toBeVisible({
    timeout: 30_000,
  })
})
