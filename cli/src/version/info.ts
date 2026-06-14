import { arch, platform } from '@/sys/index'
import { compatString } from './compat'

export type Channel = 'dev' | 'rc' | 'stable'

export type VersionInfo = {
  version: string
  commit: string
  buildDate: string
  channel: Channel
}

export const versionInfo: VersionInfo = {
  version: __DATACTL_VERSION__,
  commit: __DATACTL_COMMIT__,
  buildDate: __DATACTL_BUILD_DATE__,
  channel: __DATACTL_CHANNEL__ as Channel,
}

export function shortVersion(): string {
  return versionInfo.version
}

export function longVersion(): string {
  const { version, commit, buildDate, channel } = versionInfo
  return `datactl ${version} (commit ${commit.slice(0, 7)}, built ${buildDate}, channel ${channel})\n`
    + `compat: ${compatString()}`
}

export function userAgent(): string {
  return `datactl/${versionInfo.version} (${platform()}; ${arch()}; ${versionInfo.channel})`
}
