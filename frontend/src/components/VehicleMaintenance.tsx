import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useRealtimeEffect } from '../hooks/useRealtimeEffect'
import { api } from '../services/api'
import type { Occurrence, Page } from '../types'
import { formatDate, formatKm, labelEnum } from '../utils/format'
import { Alert, Button, Empty, StatusBadge } from './UI'

type History = Page<Occurrence> & { summary: { total: number; pending: number; last_completed_at: string | null; cost: string | number } }
const currency = (value: string | number) => Number(value).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'})
export function VehicleMaintenance({vehicleId}: {vehicleId: string}) {
  const [data,setData] = useState<History>()
  const [filters,setFilters] = useState({from:'',to:'',type:'',status:''})
  const [page,setPage] = useState(1)
  const [error,setError] = useState('')
  const [loading,setLoading] = useState(true)
  useRealtimeEffect(['occurrences'], () => {
    let active = true
    const query = new URLSearchParams({page:String(page),page_size:'20'})
    if(filters.type) query.set('maintenance_type',filters.type)
    if(filters.status) query.set('status',filters.status)
    if(filters.from) query.set('date_from',new Date(`${filters.from}T00:00:00-03:00`).toISOString())
    if(filters.to) query.set('date_to',new Date(`${filters.to}T23:59:59.999-03:00`).toISOString())
    setLoading(true); setError('')
    api<History>(`/vehicles/${vehicleId}/maintenance?${query}`).then(result => {if(active)setData(result)}).catch(e => {if(active)setError(e.message)}).finally(() => {if(active)setLoading(false)})
    return () => {active=false}
  }, [vehicleId,filters,page])
  function filter(key: keyof typeof filters,value: string) {setPage(1);setFilters({...filters,[key]:value})}
  return <section aria-labelledby="maintenance-heading" aria-busy={loading}>
    <h2 id="maintenance-heading">Manutenções</h2>
    {data && <div className="detail-metrics"><article><span>Total de manutenções<strong>{data.summary.total}</strong></span></article><article><span>Pendentes<strong>{data.summary.pending}</strong></span></article><article><span>Última conclusão<strong>{formatDate(data.summary.last_completed_at)}</strong></span></article><article><span>Custo acumulado<strong>{currency(data.summary.cost)}</strong></span></article></div>}
    <div className="filter-bar"><label>De<input type="date" value={filters.from} max={filters.to || undefined} onChange={e=>filter('from',e.target.value)}/></label><label>Até<input type="date" value={filters.to} min={filters.from || undefined} onChange={e=>filter('to',e.target.value)}/></label><label>Tipo<select value={filters.type} onChange={e=>filter('type',e.target.value)}><option value="">Todos</option>{['PREVENTIVA','CORRETIVA','EMERGENCIAL'].map(t=><option key={t} value={t}>{labelEnum(t)}</option>)}</select></label><label>Status<select value={filters.status} onChange={e=>filter('status',e.target.value)}><option value="">Todos</option>{['ABERTA','EM_ANALISE','RESOLVIDA','CANCELADA'].map(s=><option key={s} value={s}>{labelEnum(s)}</option>)}</select></label></div>
    {error && <Alert>{error}</Alert>}
    {loading ? <p role="status">Carregando manutenções...</p> : !error && <div className="panel maintenance-history">{data?.items.length ? <><ol className="maintenance-list">{data.items.map(item=><li key={item.id}><div className="maintenance-title"><strong>{labelEnum(item.maintenance_type || '')}</strong><StatusBadge value={item.status}/></div><time dateTime={item.data_hora}>{formatDate(item.data_hora)}</time><p className="maintenance-description">{item.descricao}</p><dl><div><dt>Ocorrência</dt><dd>{labelEnum(item.tipo)}</dd></div><div><dt>Quilometragem</dt><dd>{item.maintenance_km == null ? 'Não informada' : formatKm(item.maintenance_km)}</dd></div><div><dt>Responsável</dt><dd>{item.maintenance_responsible || 'Não informado'}</dd></div><div><dt>Custo</dt><dd>{item.maintenance_cost == null ? 'Não informado' : currency(item.maintenance_cost)}</dd></div></dl><Link className="table-link" to={`/admin/ocorrencias?occurrence=${item.id}`}>Ver ocorrência #{item.id}</Link></li>)}</ol><footer className="maintenance-pagination"><Button variant="ghost" disabled={page<=1} onClick={()=>setPage(page-1)}>Anterior</Button><span>Página {page} de {data.pages} · {data.total} registros</span><Button variant="ghost" disabled={page>=data.pages} onClick={()=>setPage(page+1)}>Próxima</Button></footer></> : <Empty title="Nenhuma manutenção" description="Não há manutenções registradas para este veículo nos filtros selecionados."/>}</div>}
  </section>
}
