import type { DATAMock } from '@test/fixtures/data-mock/server'
import type { ActiveContext } from '@/auth/hosts'
import os from 'node:os'
import { join } from 'node:path'
import { DSL_YAML } from '@test/fixtures/data-mock/scenarios'
import { startMock } from '@test/fixtures/data-mock/server'
import { testHttpClient } from '@test/fixtures/http-client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { bufferStreams } from '@/sys/io/streams'
import { runExportApp } from './run.js'

const WS_ID = 'aaaaaaaa-0000-0000-0000-000000000001'

const baseActive: ActiveContext = {
  host: '127.0.0.1',
  email: 'tester@data.ai',
  ctx: {
    account: { id: 'acct-1', email: 'tester@data.ai', name: 'Test Tester' },
    workspace: { id: WS_ID, name: 'Default', role: 'owner' },
  },
  scheme: 'http',
}

describe('runExportApp', () => {
  let mock: DATAMock

  beforeEach(async () => {
    mock = await startMock({ scenario: 'happy' })
  })

  afterEach(async () => {
    await mock.stop()
  })

  function http() {
    return testHttpClient(mock.url, 'dfoa_test')
  }

  it('returns the DSL YAML string from the server', async () => {
    const result = await runExportApp({ appId: 'app-1' }, { active: baseActive, http: http() })

    expect(result.yaml).toBe(DSL_YAML)
    expect(result.writtenTo).toBeUndefined()
  })

  it('writes to file when --output is given', async () => {
    const tmpFile = join(os.tmpdir(), `datactl-test-export-${Date.now()}.yaml`)

    const result = await runExportApp(
      { appId: 'app-1', output: tmpFile },
      { active: baseActive, http: http() },
    )

    expect(result.writtenTo).toBe(tmpFile)
    const { readFileSync } = await import('node:fs')
    expect(readFileSync(tmpFile, 'utf8')).toBe(DSL_YAML)
  })

  it('err stream receives written-to path when --output is given', async () => {
    const tmpFile = join(os.tmpdir(), `datactl-test-export-${Date.now()}.yaml`)
    const io = bufferStreams()

    await runExportApp(
      { appId: 'app-1', output: tmpFile },
      { active: baseActive, http: http(), io },
    )

    expect(io.errBuf()).toContain(tmpFile)
  })
})
