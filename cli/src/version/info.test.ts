import { describe, expect, it } from 'vitest'
import { longVersion, shortVersion, userAgent } from './info'

describe('version info', () => {
  it('shortVersion returns the build-injected version string', () => {
    expect(shortVersion()).toMatch(/^\d+\.\d+\.\d+(-[\w.]+)?$/)
  })

  it('longVersion includes commit, build date, channel, and compat range', () => {
    const out = longVersion()
    expect(out).toMatch(/^datactl /)
    expect(out).toContain('commit')
    expect(out).toContain('built')
    expect(out).toContain('channel')
    expect(out).toContain('compat:')
    expect(out).toMatch(/data >=\d+\.\d+\.\d.*, <=\d+\.\d+\.\d+/)
  })

  it('userAgent is well-formed', () => {
    expect(userAgent()).toMatch(/^datactl\/\S+ \(\S+; \S+; \S+\)$/)
  })
})
