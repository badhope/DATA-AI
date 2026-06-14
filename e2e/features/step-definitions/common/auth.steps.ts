import type { DATAWorld } from '../../support/world'
import { Given } from '@cucumber/cucumber'

Given('I am signed in as the default E2E admin', async function (this: DATAWorld) {
  const session = await this.getAuthSession()

  this.attach(
    `Authenticated as ${session.adminEmail} using ${session.mode} flow at ${session.baseURL}.`,
    'text/plain',
  )
})

Given('I am not signed in', async function (this: DATAWorld) {
  this.attach(
    'Using a clean browser context without the shared authenticated storage state.',
    'text/plain',
  )
})
