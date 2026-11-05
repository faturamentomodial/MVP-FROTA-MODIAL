import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { RouteMap, type PickupMarker } from '../../components/RouteMap'
import { Alert, Button } from '../../components/UI'
import { api } from '../../services/api'
import type { Plan, Point } from '../../types/routePlans'

type Pickup = { id: number; nome: string; endereco: string; ativo: boolean; tipo: PickupMarker['tipo'] }

export function RouteMapPage() {
  const [params, setParams] = useSearchParams()
  const selectedId = Number(params.get('planejamento'))
  const [plans, setPlans] = useState<Plan[]>([])
  const [selected, setSelected] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [pickups, setPickups] = useState<PickupMarker[]>([])
  const [locating, setLocating] = useState(false)
  const [pickupError, setPickupError] = useState('')
  const [failed, setFailed] = useState<string[]>([])
  const [unlocated, setUnlocated] = useState<string[]>([])
  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    setPickups([]); setUnlocated([]); setFailed([]); setPickupError(''); setLocating(true)
    async function loadPickups() {
      const items = await api<Pickup[]>('/pickups', { signal })
      const cache = new Map<string, Point | undefined>()
      for (const item of items.filter(item => item.ativo)) {
        if (signal.aborted) return
        try {
          if (!cache.has(item.endereco)) {
            // Space requests to respect the shared geocoding provider's rate limit.
            await new Promise<void>(resolve => {
              const timer = window.setTimeout(done, 1100)
              function done() { window.clearTimeout(timer); signal.removeEventListener('abort', done); resolve() }
              signal.addEventListener('abort', done, { once: true })
            })
            if (signal.aborted) return
            const result = await api<{ candidates: Point[] }>(`/route-plans/geocode?address=${encodeURIComponent(item.endereco)}`, { signal })
            cache.set(item.endereco, result.candidates[0])
          }
          const point = cache.get(item.endereco)
          if (signal.aborted) return
          if (point) setPickups(previous => [...previous, { ...point, id: item.id, nome: item.nome, tipo: item.tipo, address: item.endereco }])
          else setUnlocated(previous => [...previous, item.nome])
        } catch (e) {
          if (signal.aborted) return
          setFailed(previous => [...previous, item.nome])
          setPickupError((e as Error).message)
        }
      }
    }
    loadPickups().catch(e => { if (!signal.aborted) setPickupError((e as Error).message) }).finally(() => { if (!signal.aborted) setLocating(false) })
    return () => controller.abort()
  }, [refresh])
  useEffect(() => {
    let active = true
    setLoading(true); setError(''); setSelected(null)
    async function load() {
      const items: Plan[] = []
      let batch: Plan[]
      do {
        batch = await api<Plan[]>(`/route-plans?limit=100&offset=${items.length}`)
        items.push(...batch)
      } while (batch.length === 100)
      const plan = selectedId ? await api<Plan>(`/route-plans/${selectedId}`) : null
      if (plan && !items.some(item => item.id === plan.id)) items.unshift(plan)
      if (active) { setPlans(items); setSelected(plan) }
    }
    load().catch(e => { if (active) setError((e as Error).message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [selectedId, refresh])
  return <div className="admin-page route-map-page">
    <header className="page-heading"><div><p className="eyebrow">PLANEJAMENTO</p><h1>Mapa rotas</h1><p>Visualize os locais de coleta cadastrados e os destinos das rotas.</p></div><Button variant="secondary" disabled={loading} onClick={() => setRefresh(value => value + 1)}>Atualizar mapa</Button></header>
    {error && <Alert>{error}</Alert>}
    {loading ? <p role="status">Carregando rotas...</p> : !error && <>
        <div className="route-map-toolbar"><label>Planejamento<select value={selected?.id ?? ''} onChange={e => setParams(e.target.value ? {planejamento:e.target.value} : {})}><option value="">Somente locais de coleta</option>{plans.map(plan => <option key={plan.id} value={plan.id}>{plan.name} · {plan.status}</option>)}</select></label>{selected && <p>{selected.invoices.length} notas · {selected.result ? `${(selected.result.distance / 1000).toFixed(1)} km · ${Math.round(selected.result.duration / 60)} min estimados` : 'Percurso ainda não calculado'}</p>}</div>
        <section className="route-map-view" aria-label="Mapa das entregas"><RouteMap plan={selected} pickups={pickups}/>{!selected && <p className="route-map-notice">Os locais de coleta ativos aparecem em azul (C), com localização aproximada pelo endereço. Selecione um planejamento para visualizar também as entregas.</p>}{selected && !selected.origin && selected.invoices.length === 0 && <p className="route-map-notice">Adicione a origem e as notas deste planejamento em Rotas.</p>}{selected && !selected.result && selected.invoices.length > 0 && <p className="route-map-notice">Os marcadores mostram os destinos cadastrados. Calcule e salve o percurso em Rotas para visualizar o trajeto.</p>}{selected?.result?.warning && <Alert tone="info">{selected.result.warning}</Alert>}</section>
      {locating && <p role="status">Localizando endereços de coleta… {pickups.length} no mapa.</p>}
      {failed.length > 0 && <Alert tone="info">Consulta pendente para: {failed.join(', ')}. Use Atualizar mapa para tentar novamente.</Alert>}
      {pickupError && <Alert>Não foi possível localizar todas as coletas: {pickupError}</Alert>}
      {unlocated.length > 0 && <Alert tone="info">Confira os endereços das coletas sem localização: {unlocated.join(', ')}.</Alert>}
      {!locating && pickups.length === 0 && !pickupError && unlocated.length === 0 && <p>Nenhuma coleta ativa cadastrada. <Link to="/admin/coletas">Cadastrar coleta</Link></p>}

    </>}
  </div>
}
