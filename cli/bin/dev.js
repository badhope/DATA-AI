#!/usr/bin/env -S bun

import { resolveBuildInfo } from '../scripts/lib/resolve-buildinfo.ts'

const info = resolveBuildInfo()
globalThis.__DATACTL_VERSION__ = info.version
globalThis.__DATACTL_COMMIT__ = info.commit
globalThis.__DATACTL_BUILD_DATE__ = info.buildDate
globalThis.__DATACTL_CHANNEL__ = info.channel
globalThis.__DATACTL_MIN_DATA__ = info.minDATA
globalThis.__DATACTL_MAX_DATA__ = info.maxDATA

const { commandTree } = await import('../src/commands/tree.ts')
const { run } = await import('../src/framework/run.ts')

await run(commandTree, process.argv.slice(2))
