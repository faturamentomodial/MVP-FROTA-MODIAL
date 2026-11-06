import { useEffect, useState } from 'react'
import { Alert, Button } from './UI'
import { api } from '../services/api'
import type { Point } from '../types/routePlans'

type Pickup = { id: number; nome: string; endereco: string; ativo: boolean }
const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR')

export function PickupStopPicker({ onAdd, disabled }: { onAdd: (point: Point) => void; disabled: boolean }) {
  const [items, setItems] = useState<Pickup[]>([])
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Pickup | null>(null)
  const [candidates, setCandidates] = useState<Point[]>([])
  const [loading, setLoading] = useState(true)
  const [locating, setLocating] = useState(false)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError('')
    api<Pickup[]>('/pickups', { signal: controller.signal })
      .then(result => { setItems(result.filter(item => item.ativo)); setSelected(null); setCandidates([]) })
      .catch(e => { if (!controller.signal.aborted) setError((e as Error).message) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [refresh])

  useEffect(() => {
    if (!selected) return
    const controller = new AbortController()
    setLocating(true); setError(''); setCandidates([])
    api<{ candidates: Point[] }>(`/route-plans/geocode?address=${encodeURIComponent(selected.endereco)}`, { signal: controller.signal })
      .then(result => {
        setCandidates(result.candidates)
        if (!result.candidates.length) setError('Endereço não localizado. Confira o endereço no cadastro da coleta ou adicione a parada manualmente.')
      })
      .catch(e => { if (!controller.signal.aborted) setError((e as Error).message) })
      .finally(() => { if (!controller.signal.aborted) setLocating(false) })
    return () => controller.abort()
  }, [selected])

  const matches = items.filter(item => normalize(item.nome).includes(normalize(query.trim())))
  return <div>
    <label>Pesquisar coleta pelo nome<input value={query} onChange={e => { setQuery(e.target.value); setSelected(null); setCandidates([]); setLocating(false); setError('') }}/></label>
    <Button variant="secondary" loading={loading} onClick={() => setRefresh(value => value + 1)}>Atualizar coletas</Button>
    {error && <Alert>{error}</Alert>}
    {!loading && query.trim() && !selected && <div>
      <p role="status">{matches.length ? `${matches.length} coleta(s) encontrada(s). Selecione para localizar o endereço.` : 'Nenhuma coleta ativa encontrada com esse nome.'}</p>
      {matches.slice(0, 20).map(item => <Button key={item.id} variant="secondary" disabled={disabled} onClick={() => setSelected(item)}>{item.nome} · {item.endereco}</Button>)}
      {matches.length > 20 && <p>Digite mais do nome para refinar a busca.</p>}
    </div>}
    {selected && <div>
      <p><strong>{selected.nome}</strong> · {selected.endereco}</p>
      {locating && <p role="status">Localizando endereço da coleta…</p>}
      {candidates.length > 0 && <p>Confira a localização e adicione a coleta à rota.</p>}
      {candidates.map((point, index) => <div key={index}>
        <p>{point.address} ({point.latitude.toFixed(5)}, {point.longitude.toFixed(5)}){point.house_number_found === false && ' — Número não localizado; confira o ponto no mapa.'}</p>
        <Button disabled={disabled || loading} onClick={() => {
          const address = `${selected.nome} · ${selected.endereco}`.slice(0, 500)
          onAdd({ address, latitude: point.latitude, longitude: point.longitude })
          setQuery(''); setSelected(null); setCandidates([])
        }}>Adicionar coleta à rota</Button>
      </div>)}
    </div>}
  </div>
}
