import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Alert, Button } from './UI'
import { api } from '../services/api'
import type { Point } from '../types/routePlans'

type GeocodingCandidate = Point & { provider?: string; precision?: string; street_found?: boolean; datasource?: { attribution?: string; license?: string } }
export type GeocodingResult = {
  candidates: GeocodingCandidate[]; suggestions?: GeocodingCandidate[]
  selected?: Point | null; status?: string; errors?: { provider: string; status: string | number }[]
}

export function LocationEditor({ address, candidates, currentPoint, onConfirmed }: {
  address: string; candidates: GeocodingResult['candidates']; currentPoint?: Point | null; onConfirmed: (point: Point) => void
}) {
  const container = useRef<HTMLDivElement>(null)
  const [point, setPoint] = useState<Point | null>(null)
  const [latitude, setLatitude] = useState(''), [longitude, setLongitude] = useState('')
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  useEffect(() => { setPoint(currentPoint ? {address, latitude: currentPoint.latitude, longitude: currentPoint.longitude} : null) }, [address, currentPoint])
  useEffect(() => { setLatitude(point ? String(point.latitude) : ''); setLongitude(point ? String(point.longitude) : '') }, [point])
  useEffect(() => {
    if (!container.current) return
    const center = point || candidates[0]
    const map = L.map(container.current).setView(center ? [center.latitude, center.longitude] : [-14.2, -51.9], center ? 17 : 4)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>', maxZoom: 19,
    }).addTo(map)
    const icon = (text: string) => L.divIcon({ className: 'tracking-marker', html: `<span>${text}</span>`, iconSize: [32, 32] })
    candidates.forEach((p, i) => {
      const label = document.createElement('span'); label.textContent = `${p.provider || 'Sugestão'}: ${p.address} (${p.precision || 'não verificada'})`
      L.marker([p.latitude, p.longitude], { icon: icon(String(i + 1)) }).bindTooltip(label)
        .on('click', () => setPoint({ address, latitude: p.latitude, longitude: p.longitude })).addTo(map)
    })
    if (point) {
      const marker = L.marker([point.latitude, point.longitude], { draggable: true, icon: icon('✓') }).addTo(map)
      marker.on('dragend', () => { const p = marker.getLatLng(); setPoint({ address, latitude: p.lat, longitude: p.lng }) })
    }
    map.on('click', (event: L.LeafletMouseEvent) => setPoint({ address, latitude: event.latlng.lat, longitude: event.latlng.lng }))
    const observer = new ResizeObserver(() => map.invalidateSize()); observer.observe(container.current)
    return () => { observer.disconnect(); map.remove() }
  }, [address, candidates, point])
  async function confirm() {
    if (!point) return
    setBusy(true); setError('')
    try {
      const result = await api<GeocodingResult>('/route-plans/geocode/confirm', { method: 'POST', body: JSON.stringify({ ...point, address }) })
      if (result.selected) onConfirmed({ address, latitude: result.selected.latitude, longitude: result.selected.longitude })
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <section aria-label="Corrigir localização">
    <h3>Corrigir localização</h3><p>Endereço original: <strong>{address}</strong></p>
    <p>Selecione uma sugestão ou clique no mapa. Arraste o marcador com ✓ até o local definitivo. A confirmação será reutilizada nas próximas buscas.</p>
    <div ref={container} style={{ height: 360, width: '100%', pointerEvents: busy ? 'none' : 'auto' }} aria-label="Mapa para corrigir localização" />
    <div className="form-row">
      <label>Latitude<input disabled={busy} type="number" step="any" min={-90} max={90} value={latitude} onChange={e => setLatitude(e.target.value)} /></label>
      <label>Longitude<input disabled={busy} type="number" step="any" min={-180} max={180} value={longitude} onChange={e => setLongitude(e.target.value)} /></label>
      <Button type="button" variant="secondary" disabled={busy || !latitude || !longitude || !Number.isFinite(Number(latitude)) || !Number.isFinite(Number(longitude)) || Math.abs(Number(latitude)) > 90 || Math.abs(Number(longitude)) > 180} onClick={() => setPoint({address, latitude: Number(latitude), longitude: Number(longitude)})}>Aplicar coordenadas ao mapa</Button>
    </div>
    {point && <p>Coordenada selecionada: {point.latitude.toFixed(6)}, {point.longitude.toFixed(6)}</p>}
    {error && <Alert>{error}</Alert>}
    <Button type="button" disabled={busy || !point || !latitude || !longitude || Number(latitude) !== point.latitude || Number(longitude) !== point.longitude || Math.abs(point.latitude) > 90 || Math.abs(point.longitude) > 180} loading={busy} onClick={confirm}>Confirmar localização definitiva</Button>
  </section>
}
