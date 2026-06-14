import { describe, expect, it } from 'vitest'
import { resolveBuildInfo } from '../../scripts/lib/resolve-buildinfo.js'

const FIXED_DATE = new Date('2026-05-09T12:00:00.000Z')
const fixedNow = () => FIXED_DATE
const noGit = () => null
// Stub the package.json reader so tests exercise the "no sources" path
// without coupling to the live cli/package.json#datactl.compat values.
const noPkg = () => ({})

describe('resolveBuildInfo', () => {
  it('uses env values when fully populated', () => {
    const info = resolveBuildInfo({
      env: {
        DATACTL_VERSION: '1.2.3',
        DATACTL_COMMIT: 'abcdef0123456789',
        DATACTL_BUILD_DATE: '2026-01-01T00:00:00.000Z',
        DATACTL_CHANNEL: 'stable',
      },
      git: () => 'should-not-be-called',
      now: fixedNow,
      pkg: noPkg,
    })
    expect(info).toStrictEqual({
      version: '1.2.3',
      commit: 'abcdef0123456789',
      buildDate: '2026-01-01T00:00:00.000Z',
      channel: 'stable',
      minDATA: '0.0.0',
      maxDATA: '0.0.0',
    })
  })

  it('falls back to git probes when env unset', () => {
    const calls: string[] = []
    const git = (cmd: string) => {
      calls.push(cmd)
      if (cmd.startsWith('git describe'))
        return 'v1.0.0-5-gabc1234-dirty'
      if (cmd.startsWith('git rev-parse'))
        return '1234567890abcdef'
      return null
    }
    const info = resolveBuildInfo({ env: {}, git, now: fixedNow, pkg: noPkg })
    expect(info).toStrictEqual({
      version: 'v1.0.0-5-gabc1234-dirty',
      commit: '1234567890abcdef',
      buildDate: '2026-05-09T12:00:00.000Z',
      channel: 'dev',
      minDATA: '0.0.0',
      maxDATA: '0.0.0',
    })
    expect(calls).toStrictEqual([
      'git describe --tags --dirty --always',
      'git rev-parse HEAD',
    ])
  })

  it('uses string defaults when env unset, git unavailable, and package.json empty', () => {
    const info = resolveBuildInfo({ env: {}, git: noGit, now: fixedNow, pkg: noPkg })
    expect(info).toStrictEqual({
      version: '0.0.0-dev',
      commit: 'none',
      buildDate: '2026-05-09T12:00:00.000Z',
      channel: 'dev',
      minDATA: '0.0.0',
      maxDATA: '0.0.0',
    })
  })

  it('throws on invalid channel', () => {
    expect(() =>
      resolveBuildInfo({ env: { DATACTL_CHANNEL: 'beta' }, git: noGit, now: fixedNow, pkg: noPkg }),
    ).toThrow(/invalid DATACTL_CHANNEL: beta/)
  })

  it('throws on removed nightly channel', () => {
    expect(() =>
      resolveBuildInfo({ env: { DATACTL_CHANNEL: 'nightly' }, git: noGit, now: fixedNow, pkg: noPkg }),
    ).toThrow(/invalid DATACTL_CHANNEL: nightly/)
  })

  it('accepts rc channel', () => {
    const info = resolveBuildInfo({
      env: {
        DATACTL_VERSION: '0.1.0-rc.1',
        DATACTL_CHANNEL: 'rc',
        DATACTL_COMMIT: 'abc',
        DATACTL_BUILD_DATE: '2026-01-01T00:00:00.000Z',
      },
      git: noGit,
      now: fixedNow,
      pkg: noPkg,
    })
    expect(info.channel).toBe('rc')
  })

  it('mixes env and git fallbacks per field', () => {
    const git = (cmd: string) => (cmd.startsWith('git describe') ? 'v9.9.9' : null)
    const info = resolveBuildInfo({
      env: { DATACTL_COMMIT: 'pinned-sha' },
      git,
      now: fixedNow,
      pkg: noPkg,
    })
    expect(info.version).toBe('v9.9.9')
    expect(info.commit).toBe('pinned-sha')
    expect(info.channel).toBe('dev')
  })

  it('reads minDATA and maxDATA from env', () => {
    const info = resolveBuildInfo({
      env: {
        DATACTL_VERSION: '0.1.0-rc.1',
        DATACTL_CHANNEL: 'rc',
        DATACTL_COMMIT: 'abc',
        DATACTL_BUILD_DATE: '2026-01-01T00:00:00.000Z',
        DATACTL_MIN_DATA: '1.6.0',
        DATACTL_MAX_DATA: '1.7.0',
      },
      git: noGit,
      now: fixedNow,
      pkg: noPkg,
    })
    expect(info.minDATA).toBe('1.6.0')
    expect(info.maxDATA).toBe('1.7.0')
  })

  it('defaults minDATA and maxDATA to 0.0.0 when env and package.json are unset', () => {
    const info = resolveBuildInfo({ env: {}, git: noGit, now: fixedNow, pkg: noPkg })
    expect(info.minDATA).toBe('0.0.0')
    expect(info.maxDATA).toBe('0.0.0')
  })

  it('falls back to package.json#datactl.compat when env unset', () => {
    const pkg = () => ({ datactl: { compat: { minDATA: '1.6.0', maxDATA: '1.7.0' }, channel: 'rc' } })
    const info = resolveBuildInfo({ env: {}, git: noGit, now: fixedNow, pkg })
    expect(info.minDATA).toBe('1.6.0')
    expect(info.maxDATA).toBe('1.7.0')
    expect(info.channel).toBe('rc')
  })

  it('env wins over package.json for compat range and channel', () => {
    const pkg = () => ({ datactl: { compat: { minDATA: '1.6.0', maxDATA: '1.7.0' }, channel: 'rc' } })
    const info = resolveBuildInfo({
      env: {
        DATACTL_MIN_DATA: '2.0.0',
        DATACTL_MAX_DATA: '2.1.0',
        DATACTL_CHANNEL: 'stable',
      },
      git: noGit,
      now: fixedNow,
      pkg,
    })
    expect(info.minDATA).toBe('2.0.0')
    expect(info.maxDATA).toBe('2.1.0')
    expect(info.channel).toBe('stable')
  })
})
