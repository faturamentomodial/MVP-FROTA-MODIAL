import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { RouteMap, type PickupMarker } from '../../components/RouteMap'
import { Alert, Button } from '../../components/UI'
import { api } from '../../services/api'
import { useAuth } from '../../hooks/useAuth'
import { canAccess } from '../../utils/access'
import type { Plan, Point } from '../../types/routePlans'

type Pickup = { id: number; nome: string; endereco: string; ativo: boolean; tipo: PickupMarker['tipo']; location?: Point | null }

export function RouteMapPage() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const selectedId = Number(params.get('planejamento'))
  const templateId = Number(params.get('rota'))
  const [templates, setTemplates] = useState<Plan[]>([])
  const [plans, setPlans] = useState<Plan[]>([])
  const [selected, setSelected] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [pickups, setPickups] = useState<PickupMarker[]>([])
  const [locating, setLocating] = useState(true)
  const [locationProgress, setLocationProgress] = useState({ completed: 0, total: 0 })
  const [pickupError, setPickupError] = useState('')
  const [failed, setFailed] = useState<string[]>([])
  const [unlocated, setUnlocated] = useState<string[]>([])
  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    setPickupError(''); setLocating(true); setFailed([]); setUnlocated([])
    setLocationProgress({ completed: 0, total: 0 })
    async function loadPickups() {
      const items = await api<Pickup[]>('/pickups', { signal })
      const cache = new Map<string, Point>()
      for (const item of items) if (item.location) cache.set(item.endereco, item.location)
      const markers: PickupMarker[] = []
      const missing: string[] = []
      const failures: string[] = []
      let lastError = ''
      const activeItems = items.filter(item => item.ativo)
      // Display cached contacts before waiting for any external lookup.
      const orderedItems = [...activeItems.filter(item => cache.has(item.endereco)), ...activeItems.filter(item => !cache.has(item.endereco))]
      setPickups([])
      setLocationProgress({ completed: 0, total: activeItems.length })
      for (const [index, item] of orderedItems.entries()) {
        if (signal.aborted) return
        try {
          const point = cache.get(item.endereco)
          if (signal.aborted) return
          if (point) markers.push({ ...point, id: item.id, nome: item.nome, tipo: item.tipo, address: item.endereco })
          else missing.push(item.nome)
        } catch (e) {
          if (signal.aborted) return
          failures.push(item.nome)
          lastError = (e as Error).message
        }
        if (!signal.aborted) {
          setPickups([...markers])
          setUnlocated([...missing])
          setFailed([...failures])
          setPickupError(lastError)
          setLocationProgress({ completed: index + 1, total: activeItems.length })
        }
      }
      if (!signal.aborted) {
        setPickups(markers)
        setUnlocated(missing)
        setFailed(failures)
        setPickupError(lastError)
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
      const routeItems: Plan[] = []
      let routeBatch: Plan[]
      do {
        routeBatch = await api<Plan[]>(`/route-templates?limit=100&offset=${routeItems.length}`)
        routeItems.push(...routeBatch)
      } while (routeBatch.length === 100)
      const plan = templateId ? await api<Plan>(`/route-templates/${templateId}`) : selectedId ? await api<Plan>(`/route-plans/${selectedId}`) : null
      if (plan && !templateId && !items.some(item => item.id === plan.id)) items.unshift(plan)
      if (active) { setPlans(items); setTemplates(routeItems); setSelected(plan) }
    }
    load().catch(e => { if (active) setError((e as Error).message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [selectedId, templateId, refresh])
  return <div className="admin-page route-map-page">
    <header className="page-heading"><div><p className="eyebrow">PLANEJAMENTO</p><h1>Mapa rotas</h1><p>Visualize os locais de coleta cadastrados e os destinos das rotas.</p></div><Button variant="secondary" disabled={loading || locating} onClick={() => setRefresh(value => value + 1)}>Atualizar mapa</Button></header>
    {error && <Alert>{error}</Alert>}
    {loading ? <p role="status">Carregando rotas...</p> : !error && <>
        <div className="route-map-toolbar"><label>Rota<select value={selected ? `${templateId?'rota':'planejamento'}:${selected.id}` : ''} onChange={e => {const [kind,id]=e.target.value.split(':');setParams(id?{[kind]:id}:{})}}><option value="">Somente locais de coleta</option>{templates.map(plan => <option key={`rota:${plan.id}`} value={`rota:${plan.id}`}>{plan.name} - {plan.status}</option>)}{plans.map(plan => <option key={plan.id} value={`planejamento:${plan.id}`}>{plan.name} · {plan.status}</option>)}</select></label>{selected && <p>{selected.addresses?.length||0} paradas por endereço - {selected.invoices.length} notas · {selected.result ? `${(selected.result.distance / 1000).toFixed(1)} km · ${Math.round(selected.result.duration / 60)} min estimados` : 'Percurso ainda não calculado'}</p>}</div>
        <section className="route-map-view" aria-label="Mapa das entregas"><RouteMap plan={selected} pickups={pickups}/>{!selected && <p className="route-map-notice">Os locais de coleta ativos aparecem em azul (C), com as localizações salvas. Confira a precisão de cada marcador. Selecione um planejamento para visualizar também as entregas.</p>}{selected && !selected.origin && selected.invoices.length === 0 && <p className="route-map-notice">Adicione a origem e as notas deste planejamento em Rotas.</p>}{selected && !selected.result && selected.invoices.length > 0 && <p className="route-map-notice">Os marcadores mostram os destinos cadastrados. Calcule e salve o percurso em Rotas para visualizar o trajeto.</p>}{selected?.result?.warning && <Alert tone="info">{selected.result.warning}</Alert>}</section>
      {locating && <p role="status">Localizando coletas: {locationProgress.completed} de {locationProgress.total} consultadas - {pickups.length} no mapa...</p>}
      {failed.length > 0 && <Alert tone="info">Consulta pendente para: {failed.join(', ')}. Confira a localização em Coletas.</Alert>}
      {pickupError && <Alert>Não foi possível localizar todas as coletas: {pickupError}</Alert>}
      {unlocated.length > 0 && <Alert tone="info">Confira os endereços das coletas sem localização: {unlocated.join(', ')}. Use Corrigir localização em Coletas.</Alert>}
      {!locating && pickups.length === 0 && !pickupError && unlocated.length === 0 && <p>Nenhuma coleta ativa cadastrada. {user && canAccess(user.role, '/admin/coletas') && <Link to="/admin/coletas">Cadastrar coleta</Link>}</p>}

    </>}
  </div>
}
