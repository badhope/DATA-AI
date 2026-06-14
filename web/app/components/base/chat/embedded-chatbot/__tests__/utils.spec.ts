/**
 * Tests for embedded-chatbot utility functions.
 */

import { isDATA } from '../utils'

describe('isDATA', () => {
  const originalReferrer = document.referrer

  afterEach(() => {
    Object.defineProperty(document, 'referrer', {
      value: originalReferrer,
      writable: true,
    })
  })

  it('should return true when referrer includes data.ai', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://data.ai/something',
      writable: true,
    })

    expect(isDATA()).toBe(true)
  })

  it('should return true when referrer includes www.data.ai', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://www.data.ai/app/xyz',
      writable: true,
    })

    expect(isDATA()).toBe(true)
  })

  it('should return false when referrer does not include data.ai', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://example.com',
      writable: true,
    })

    expect(isDATA()).toBe(false)
  })

  it('should return false when referrer is empty', () => {
    Object.defineProperty(document, 'referrer', {
      value: '',
      writable: true,
    })

    expect(isDATA()).toBe(false)
  })

  it('should return false when referrer does not contain data.ai domain', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://example-data.com',
      writable: true,
    })

    expect(isDATA()).toBe(false)
  })

  it('should handle referrer without protocol', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'data.ai',
      writable: true,
    })

    expect(isDATA()).toBe(true)
  })

  it('should return true when referrer includes api.data.ai', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://api.data.ai/v1/endpoint',
      writable: true,
    })

    expect(isDATA()).toBe(true)
  })

  it('should return true when referrer includes app.data.ai', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://app.data.ai/chat',
      writable: true,
    })

    expect(isDATA()).toBe(true)
  })

  it('should return true when referrer includes docs.data.ai', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://docs.data.ai/guide',
      writable: true,
    })

    expect(isDATA()).toBe(true)
  })

  it('should return true when referrer has data.ai with query parameters', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://data.ai/?ref=test&id=123',
      writable: true,
    })

    expect(isDATA()).toBe(true)
  })

  it('should return true when referrer has data.ai with hash fragment', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://data.ai/page#section',
      writable: true,
    })

    expect(isDATA()).toBe(true)
  })

  it('should return true when referrer has data.ai with port number', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://data.ai:8080/app',
      writable: true,
    })

    expect(isDATA()).toBe(true)
  })

  it('should return true when data.ai appears after another domain', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://example.com/redirect?url=https://data.ai',
      writable: true,
    })

    expect(isDATA()).toBe(true)
  })

  it('should return true when substring contains data.ai', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://notdify.ai',
      writable: true,
    })

    expect(isDATA()).toBe(true)
  })

  it('should return true when data.ai is part of a different domain', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'https://fake-data.ai.example.com',
      writable: true,
    })

    expect(isDATA()).toBe(true)
  })

  it('should return true with multiple referrer variations', () => {
    const variations = [
      'https://data.ai',
      'http://www.data.ai',
      'http://data.ai/',
      'https://data.ai/app?token=123#section',
      'data.ai/test',
      'www.data.ai/en',
    ]

    variations.forEach((referrer) => {
      Object.defineProperty(document, 'referrer', {
        value: referrer,
        writable: true,
      })
      expect(isDATA()).toBe(true)
    })
  })

  it('should return false with multiple non-data referrer variations', () => {
    const variations = [
      'https://github.com',
      'https://google.com',
      'https://stackoverflow.com',
      'https://example.data',
      'https://dataai.com',
      '',
    ]

    variations.forEach((referrer) => {
      Object.defineProperty(document, 'referrer', {
        value: referrer,
        writable: true,
      })
      expect(isDATA()).toBe(false)
    })
  })
})
