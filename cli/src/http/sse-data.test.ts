import type { SseEvent } from './sse'
import { describe, expect, it } from 'vitest'
import { eventNameFromDATAData, normalizeDATAStream } from './sse-data'

const enc = new TextEncoder()

function bytes(s: string): Uint8Array {
  return enc.encode(s)
}

async function* fromArray(events: SseEvent[]): AsyncGenerator<SseEvent, void, void> {
  for (const ev of events)
    yield ev
}

async function collect(iter: AsyncIterable<SseEvent>): Promise<SseEvent[]> {
  const out: SseEvent[] = []
  for await (const ev of iter)
    out.push(ev)
  return out
}

describe('eventNameFromDATAData', () => {
  it('returns empty string for zero-byte data', () => {
    expect(eventNameFromDATAData(new Uint8Array())).toBe('')
  })

  it('returns embedded event name for object payload', () => {
    expect(eventNameFromDATAData(bytes('{"event":"message","answer":"hi"}'))).toBe('message')
  })

  it('returns empty string for malformed JSON', () => {
    expect(eventNameFromDATAData(bytes('not-json'))).toBe('')
  })

  it('returns empty string for non-string event field', () => {
    expect(eventNameFromDATAData(bytes('{"event":42}'))).toBe('')
  })

  it('returns empty string for null payload', () => {
    expect(eventNameFromDATAData(bytes('null'))).toBe('')
  })

  it('returns empty string for non-object JSON values', () => {
    expect(eventNameFromDATAData(bytes('"just a string"'))).toBe('')
    expect(eventNameFromDATAData(bytes('123'))).toBe('')
    expect(eventNameFromDATAData(bytes('true'))).toBe('')
  })

  it('returns empty string for object missing event key', () => {
    expect(eventNameFromDATAData(bytes('{"answer":"hi"}'))).toBe('')
  })
})

describe('normalizeDATAStream', () => {
  it('promotes JSON event field into ev.name when transport name absent', async () => {
    const out = await collect(normalizeDATAStream(fromArray([
      { name: '', data: bytes('{"event":"workflow_started","id":"wf-1"}') },
      { name: '', data: bytes('{"event":"workflow_finished","status":"succeeded"}') },
    ])))
    expect(out.map(e => e.name)).toEqual(['workflow_started', 'workflow_finished'])
  })

  it('preserves transport-level event name over JSON event field', async () => {
    const out = await collect(normalizeDATAStream(fromArray([
      { name: 'ping', data: bytes('') },
      { name: 'foo', data: bytes('{"event":"bar"}') },
    ])))
    expect(out.map(e => e.name)).toEqual(['ping', 'foo'])
  })

  it('forwards unchanged when ev.name absent and data has no JSON event field', async () => {
    const ev: SseEvent = { name: '', data: bytes('{"answer":"hi"}') }
    const out = await collect(normalizeDATAStream(fromArray([ev])))
    expect(out).toHaveLength(1)
    expect(out[0]?.name).toBe('')
    expect(out[0]?.data).toBe(ev.data)
  })

  it('forwards unchanged when data is malformed JSON', async () => {
    const out = await collect(normalizeDATAStream(fromArray([
      { name: '', data: bytes('not-json') },
    ])))
    expect(out).toHaveLength(1)
    expect(out[0]?.name).toBe('')
  })

  it('forwards empty-data events with empty name', async () => {
    const out = await collect(normalizeDATAStream(fromArray([
      { name: '', data: bytes('') },
    ])))
    expect(out).toHaveLength(1)
    expect(out[0]?.name).toBe('')
  })
})
