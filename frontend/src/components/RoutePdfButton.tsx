import { useState } from 'react'
import { api } from '../services/api'
import { Button } from './UI'

export function RoutePdfButton({ path, name }: { path: string; name: string }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function download() {
    if (busy) return
    setBusy(true); setError('')
    try {
      const blob = await api<Blob>(path, {}, 'blob')
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `folha-rota-${name.replace(/[^a-zA-Z0-9_-]/g, '-').slice(0, 80)}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Não foi possível gerar o PDF')
    } finally { setBusy(false) }
  }
  return <span><Button type="button" variant="secondary" disabled={busy} aria-label={`Baixar PDF da rota ${name}`} onClick={download}>{busy ? 'Gerando PDF…' : 'PDF'}</Button>{error && <span role="alert"> {error}</span>}</span>
}
