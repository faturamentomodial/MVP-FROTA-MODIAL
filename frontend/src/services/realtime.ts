export type Topic = 'users' | 'drivers' | 'vehicles' | 'trips' | 'checklists' | 'occurrences' | 'tasks' | 'pickups' | 'routes' | 'tracking'
type Listener = (topics: Set<Topic>) => void
const listeners = new Set<Listener>()
let pending = new Set<Topic>()
let flush: ReturnType<typeof setTimeout> | undefined

export function subscribeRealtime(listener: Listener) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export function invalidate(topics: Topic[]) {
  topics.forEach(topic => pending.add(topic))
  if (flush) return
  flush = setTimeout(() => {
    const changed = pending
    pending = new Set()
    flush = undefined
    listeners.forEach(listener => listener(changed))
  }, 150)
}

/** Owned once by AuthProvider; pages only subscribe to invalidations. */
export function connectRealtime(token: string, onUnauthorized: () => void) {
  let stopped = false
  let socket: WebSocket | undefined
  let retry: ReturnType<typeof setTimeout> | undefined
  let watchdog: ReturnType<typeof setTimeout> | undefined
  let attempt = 0
  let lastMessage = Date.now()
  const open = () => {
    if (stopped || socket || !navigator.onLine) return
    const base = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '')
    const url = new URL(`${base}/realtime`, window.location.href)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    const current = new WebSocket(url)
    socket = current
    const armWatchdog = () => {
      clearTimeout(watchdog)
      watchdog = setTimeout(() => current.close(), 45000)
    }
    armWatchdog()
    current.onopen = () => {
      if (stopped) { current.close(); return }
      current.send(JSON.stringify({ token }))
    }
    current.onmessage = event => {
      lastMessage = Date.now()
      armWatchdog()
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'sync' || message.type === 'invalidate') {
          attempt = 0
          if (Array.isArray(message.topics)) invalidate(message.topics)
        }
      } catch { /* A malformed notification must not break the interface. */ }
    }
    current.onerror = () => current.close()
    current.onclose = event => {
      if (socket === current) socket = undefined
      clearTimeout(watchdog)
      if (stopped) return
      if (event.code === 4401) { stopped = true; onUnauthorized(); return }
      const delay = Math.min(30000, 1000 * 2 ** Math.min(attempt++, 5))
      retry = setTimeout(open, delay * (0.8 + Math.random() * 0.4))
    }
  }
  const resume = () => {
    if (document.hidden) return
    if (socket && Date.now() - lastMessage > 40000) socket.close()
    if (!socket) { clearTimeout(retry); open() }
  }
  window.addEventListener('online', resume)
  window.addEventListener('focus', resume)
  document.addEventListener('visibilitychange', resume)
  open()
  return () => {
    stopped = true
    clearTimeout(retry)
    clearTimeout(watchdog)
    socket?.close()
    window.removeEventListener('online', resume)
    window.removeEventListener('focus', resume)
    document.removeEventListener('visibilitychange', resume)
  }
}
