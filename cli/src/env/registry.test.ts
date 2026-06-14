import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  ENV_REGISTRY,
  getEnv,
  lookupEnv,
  resolveEnv,
} from './registry'

describe('env registry', () => {
  it('contains every DATA_* var from the v1.0 spec', () => {
    const names = ENV_REGISTRY.map(e => e.name)
    expect(names).toContain('DATA_TOKEN')
    expect(names).toContain('DATA_HOST')
    expect(names).toContain('DATA_WORKSPACE_ID')
    expect(names).toContain('DATA_CONFIG_DIR')
    expect(names).toContain('DATA_LIMIT')
    expect(names).toContain('DATA_FORMAT')
    expect(names).toContain('DATA_NO_PROGRESS')
    expect(names).toContain('DATA_PLAIN')
  })

  it('is sorted alphabetically (matches Go init() ordering)', () => {
    const names = ENV_REGISTRY.map(e => e.name)
    const sorted = [...names].sort()
    expect(names).toEqual(sorted)
  })

  it('marks DATA_TOKEN as sensitive', () => {
    expect(lookupEnv('DATA_TOKEN')?.sensitive).toBe(true)
  })

  it('does not mark non-secret vars as sensitive', () => {
    expect(lookupEnv('DATA_HOST')?.sensitive).toBeFalsy()
    expect(lookupEnv('DATA_LIMIT')?.sensitive).toBeFalsy()
  })

  it('lookupEnv returns undefined for unknown name', () => {
    expect(lookupEnv('DATA_NOPE')).toBeUndefined()
  })

  it('lookupEnv finds the registry entry by name', () => {
    expect(lookupEnv('DATA_HOST')?.description).toMatch(/host/i)
  })

  describe('process.env reads', () => {
    const originals: Record<string, string | undefined> = {}
    beforeEach(() => {
      originals.DATA_LIMIT = process.env.DATA_LIMIT
      originals.DATA_HOST = process.env.DATA_HOST
      originals.DATA_TEST_NONEXISTENT = process.env.DATA_TEST_NONEXISTENT
      delete process.env.DATA_LIMIT
      delete process.env.DATA_HOST
      delete process.env.DATA_TEST_NONEXISTENT
    })
    afterEach(() => {
      for (const [k, v] of Object.entries(originals)) {
        if (v === undefined)
          delete process.env[k]
        else process.env[k] = v
      }
    })

    it('getEnv returns undefined for unset var', () => {
      expect(getEnv('DATA_TEST_NONEXISTENT')).toBeUndefined()
    })

    it('getEnv returns the literal string for a set var', () => {
      process.env.DATA_HOST = 'https://cloud.data.ai'
      expect(getEnv('DATA_HOST')).toBe('https://cloud.data.ai')
    })

    it('resolveEnv returns parsed value for DATA_LIMIT (uses parseLimit)', () => {
      process.env.DATA_LIMIT = '42'
      expect(resolveEnv('DATA_LIMIT')).toBe(42)
    })

    it('resolveEnv returns the raw string for vars with no parser', () => {
      process.env.DATA_HOST = 'https://example.data.ai'
      expect(resolveEnv('DATA_HOST')).toBe('https://example.data.ai')
    })

    it('resolveEnv returns undefined when var is unset and no default', () => {
      expect(resolveEnv('DATA_HOST')).toBeUndefined()
    })

    it('resolveEnv propagates parser errors', () => {
      process.env.DATA_LIMIT = '999'
      expect(() => resolveEnv('DATA_LIMIT')).toThrow(/out of range/)
    })

    it('resolveEnv accepts unknown var name and returns undefined (no throw)', () => {
      expect(resolveEnv('DATA_NOPE')).toBeUndefined()
    })
  })
})
