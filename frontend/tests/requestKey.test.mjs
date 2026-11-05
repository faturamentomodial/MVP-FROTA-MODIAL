import assert from 'node:assert/strict'
import { test } from 'node:test'
import { webcrypto } from 'node:crypto'
import { createRequestKey } from '../src/utils/requestKey.ts'

test('booking can generate an idempotency key over HTTP without randomUUID', () => {
  const httpCrypto = { getRandomValues: array => webcrypto.getRandomValues(array) }
  assert.equal(httpCrypto.randomUUID, undefined)
  const keys = Array.from({length: 100}, () => createRequestKey(httpCrypto))
  assert.equal(new Set(keys).size, keys.length)
  for (const key of keys) {
    assert.match(key, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
    assert.ok(key.length >= 8 && key.length <= 80)
  }
})

test('HTTPS uses the available native UUID generator', () => {
  const expected = '87369c78-4d64-45cb-9eb8-e332e1b33b8b'
  assert.equal(createRequestKey({randomUUID: () => expected}), expected)
})

test('an unsupported browser gives an actionable error instead of a silent failure', () => {
  assert.throws(() => createRequestKey({}), /Atualize o navegador/)
})
