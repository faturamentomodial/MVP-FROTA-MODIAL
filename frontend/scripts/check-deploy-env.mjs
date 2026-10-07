// Na Vercel nao existe o proxy local do Vite/nginx.
if (process.env.VERCEL === '1') {
  const value = process.env.VITE_API_URL?.trim()
  let valid = false
  try {
    const url = new URL(value)
    valid = url.protocol === 'https:' && url.pathname.replace(/\/+$/, '') === '/api'
      && !url.search && !url.hash && !url.username && !url.password
      && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
  } catch {}
  if (!valid) {
    console.error('Configure VITE_API_URL na Vercel com a URL publica HTTPS do backend, incluindo /api (ex.: https://api.seu-dominio.com/api).')
    process.exit(1)
  }
}
