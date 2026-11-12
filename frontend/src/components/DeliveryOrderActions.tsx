import { useRef, useState } from 'react'
import { Alert, Button } from './UI'
import { api } from '../services/api'
import type { Trip, TripInvoice } from '../types'

const pending = (invoice: TripInvoice) => invoice.status === 'PENDENTE' || invoice.status === 'EM_ENTREGA'

export function stopAddress(trip: Trip, invoice: TripInvoice) {
  // Address-only stops retain their original name when execution order changes.
  const original = /^Parada (\d+)$/.exec(invoice.numero_nota)
  return trip.route_plan?.addresses?.[(original ? Number(original[1]) : invoice.position) - 1]?.address
}

export function DeliveryOrderActions({ trip, invoiceId, onChanged, disabled = false }: { trip: Trip; invoiceId: number; onChanged: (trip: Trip) => void; disabled?: boolean }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const saving = useRef(false)
  const unresolved = trip.notas.filter(pending)
  if (trip.status !== 'EM_ANDAMENTO' || unresolved.length < 2 || !unresolved.some(n => n.id === invoiceId)) return null
  const current = unresolved[0].id === invoiceId

  async function changeOrder() {
    if (saving.current) return
    saving.current = true
    setBusy(true)
    setError('')
    const rest = unresolved.filter(n => n.id !== invoiceId).map(n => n.id)
    const order = current ? [...rest, invoiceId] : [invoiceId, ...rest]
    let index = 0
    const invoice_ids = trip.notas.map(n => pending(n) ? order[index++] : n.id)
    try {
      onChanged(await api<Trip>(`/trips/${trip.id}/driver-delivery-order`, { method: 'PUT', body: JSON.stringify({ invoice_ids, revision: trip.delivery_revision }) }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Não foi possível reorganizar as entregas.')
      await api<Trip>(`/trips/${trip.id}`).then(onChanged).catch(() => {})
    } finally {
      saving.current = false
      setBusy(false)
    }
  }

  return <div className="action-stack">
    {error && <Alert>{error}</Alert>}
    <Button variant="secondary" className="button--full" disabled={disabled || busy} onClick={changeOrder}>{busy ? 'Salvando…' : current ? 'Pular para depois' : 'Fazer esta agora'}</Button>
    {current && <p>A entrega continuará pendente e irá para o fim da fila.</p>}
  </div>
}
