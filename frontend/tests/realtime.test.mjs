import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'

const source = await readFile(new URL('../src/services/realtime.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source.replace('import.meta.env.VITE_API_URL', 'undefined'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText

async function environment(context) {
  context.mock.timers.enable({ apis: ['setTimeout', 'Date'] })
  const window = new EventTarget()
  window.location = { href: 'https://fleet.example/admin' }
  const document = new EventTarget()
  document.hidden = false
  const sockets = []
  class Socket {
    constructor(url) { this.url = url; this.sent = []; this.closed = false; sockets.push(this) }
    send(value) { this.sent.push(JSON.parse(value)) }
    close() { this.closed = true; this.onclose?.({ code: 1000 }) }
    receive(message) { this.onmessage({ data: JSON.stringify(message) }) }
  }
  context.mock.method(Math, 'random', () => 0.5)
  for (const [key, value] of Object.entries({ window, document, navigator: { onLine: true }, WebSocket: Socket })) {
    const previous = Object.getOwnPropertyDescriptor(globalThis, key)
    Object.defineProperty(globalThis, key, { configurable: true, value })
    context.after(() => previous ? Object.defineProperty(globalThis, key, previous) : delete globalThis[key])
  }
  const module = await import(`data:text/javascript;base64,${Buffer.from(compiled + '\n// ' + Math.random() + process.hrtime.bigint()).toString('base64')}`)
  return { ...module, sockets, window, document, tick: value => context.mock.timers.tick(value) }
}

test('one connection, bearer in first frame, module events coalesce, unsubscribe cleans up', async context => {
  const env = await environment(context)
  const calls = []
  const unsubscribe = env.subscribeRealtime(topics => calls.push([...topics].sort()))
  const stop = env.connectRealtime('private-token', () => assert.fail('unexpected logout'))
  assert.equal(env.sockets.length, 1)
  const socket = env.sockets[0]
  assert.equal(socket.url.href, 'wss://fleet.example/api/realtime')
  assert.ok(!socket.url.href.includes('private-token'))
  socket.onopen()
  assert.deepEqual(socket.sent, [{ token: 'private-token' }])
  socket.receive({ type: 'invalidate', topics: ['trips'] })
  socket.receive({ type: 'invalidate', topics: ['trips', 'vehicles'] })
  env.tick(150)
  assert.deepEqual(calls, [['trips', 'vehicles']])
  unsubscribe()
  socket.receive({ type: 'invalidate', topics: ['tasks'] })
  env.tick(150)
  assert.equal(calls.length, 1)
  stop()
  env.tick(120000)
  assert.equal(env.sockets.length, 1)
})

test('network reconnect uses backoff, sync refreshes subscribed data, no duplicate on focus', async context => {
  const env = await environment(context)
  const calls = []
  const unsubscribe = env.subscribeRealtime(topics => calls.push([...topics]))
  const stop = env.connectRealtime('token', () => {})
  env.sockets[0].onclose({ code: 1006 })
  env.tick(999)
  assert.equal(env.sockets.length, 1)
  env.tick(1)
  assert.equal(env.sockets.length, 2)
  env.window.dispatchEvent(new Event('focus'))
  assert.equal(env.sockets.length, 2)
  env.sockets[1].receive({ type: 'sync', topics: ['tasks', 'routes'] })
  env.tick(150)
  assert.deepEqual(calls, [['tasks', 'routes']])
  stop()
  unsubscribe()
})

test('expired or revoked authentication stops retry and logs out', async context => {
  const env = await environment(context)
  let logouts = 0
  const stop = env.connectRealtime('expired', () => logouts++)
  env.sockets[0].onclose({ code: 4401 })
  env.tick(120000)
  assert.equal(logouts, 1)
  assert.equal(env.sockets.length, 1)
  stop()
})

test('cleanup during handshake prevents late socket from authenticating', async context => {
  const env = await environment(context)
  const stop = env.connectRealtime('token', () => {})
  const socket = env.sockets[0]
  stop()
  socket.onopen()
  assert.equal(socket.sent.length, 0)
  env.window.dispatchEvent(new Event('online'))
  env.tick(60000)
  assert.equal(env.sockets.length, 1)
})

test('silent connection is replaced by watchdog', async context => {
  const env = await environment(context)
  const stop = env.connectRealtime('token', () => {})
  env.tick(45000)
  assert.equal(env.sockets[0].closed, true)
  env.tick(1000)
  assert.equal(env.sockets.length, 2)
  stop()
})
