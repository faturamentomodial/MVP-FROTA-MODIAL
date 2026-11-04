import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { RouteMap } from '../../components/RouteMap'
import { Alert, Button } from '../../components/UI'
import { api } from '../../services/api'
import type { Plan } from '../../types/routePlans'

export function RouteMapPage() {
  const [params, setParams] = useSearchParams()
  const selectedId = Number(params.get('planejamento'))
  const [plans, setPlans] = useState<Plan[]>([])
  const [selected, setSelected] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
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
      const plan = selectedId ? await api<Plan>(`/route-plans/${selectedId}`) : items[0] ?? null
      if (plan && !items.some(item => item.id === plan.id)) items.unshift(plan)
      if (active) { setPlans(items); setSelected(plan) }
    }
    load().catch(e => { if (active) setError((e as Error).message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [selectedId, refresh])
  return <div className="admin-page route-map-page">
    <header className="page-heading"><div><p className="eyebrow">PLANEJAMENTO</p><h1>Mapa rotas</h1><p>Visualize os destinos das notas cadastradas em Rotas.</p></div><Button variant="secondary" disabled={loading} onClick={() => setRefresh(value => value + 1)}>Atualizar mapa</Button></header>
    {error && <Alert>{error}</Alert>}
    {loading ? <p role="status">Carregando rotas...</p> : !error && <>
      {plans.length > 0 ? <>
        <div className="route-map-toolbar"><label>Planejamento<select value={selected?.id ?? ''} onChange={e => setParams({planejamento:e.target.value})}>{plans.map(plan => <option key={plan.id} value={plan.id}>{plan.name} · {plan.status}</option>)}</select></label>{selected && <p>{selected.invoices.length} notas · {selected.result ? `${(selected.result.distance / 1000).toFixed(1)} km · ${Math.round(selected.result.duration / 60)} min estimados` : 'Percurso ainda não calculado'}</p>}</div>
        {selected && <section className="route-map-view" aria-label="Mapa das entregas"><RouteMap plan={selected}/>{!selected.origin && selected.invoices.length === 0 && <p className="route-map-notice">Adicione a origem e as notas deste planejamento em Rotas.</p>}{!selected.result && selected.invoices.length > 0 && <p className="route-map-notice">Os marcadores mostram os destinos cadastrados. Calcule e salve o percurso em Rotas para visualizar o trajeto.</p>}{selected.result?.warning && <Alert tone="info">{selected.result.warning}</Alert>}</section>}
      </> : <section className="panel"><h2>Nenhuma rota cadastrada</h2><p>Cadastre as notas e salve um planejamento em Rotas para visualizar as entregas aqui.</p><Link className="button button--primary" to="/admin/rotas">Cadastrar rota</Link></section>}
    </>}
  </div>
}
