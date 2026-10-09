import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Empty, StatusBadge } from '../../components/UI'
import { api } from '../../services/api'
import type { Page, Trip, TripStatus } from '../../types'
import { formatDate, formatKm } from '../../utils/format'

type Period = '' | 'day' | 'month' | 'year'

export function TripsPage() {
const navigate = useNavigate()
const [data, setData] = useState<Page<Trip>>()
const [status, setStatus] = useState<TripStatus | ''>('')
const [period, setPeriod] = useState<Period>('')
const [date, setDate] = useState('')
const [error, setError] = useState('')
const validDate = period === 'day' ? /^\d{4}-\d{2}-\d{2}$/.test(date) : period === 'month' ? /^\d{4}-\d{2}$/.test(date) : period === 'year' && /^\d{4}$/.test(date) && Number(date) >= 1900 && Number(date) <= 9999
useEffect(() => {
 let active = true
 const params = new URLSearchParams({ page_size: '100' })
 if (status) params.set('status', status)
 if (period && validDate) {
  const [year, month = 1, day = 1] = date.split('-').map(Number)
  const lastDay = period === 'year' ? 31 : period === 'month' ? new Date(year, month, 0).getDate() : day
  const first = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  const last = `${year}-${String(period === 'year' ? 12 : month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
  params.set('date_from', `${first}T00:00:00-03:00`)
  params.set('date_to', `${last}T23:59:59.999999-03:00`)
 }
 setError('')
 setData(undefined)
 api<Page<Trip>>(`/trips?${params}`).then(result => { if (active) setData(result) }).catch(e => { if (active) setError(e.message) })
 return () => { active = false }
}, [status, period, date, validDate])
return <div className="admin-page"><header className="page-heading"><div><p className="eyebrow">HISTÓRICO</p><h1>Viagens</h1><p>Saídas, retornos e quilometragem consolidada.</p></div></header>{error&&<Alert>{error}</Alert>}<section className="filter-bar trips-filters"><label>Status<select value={status} onChange={e=>setStatus(e.target.value as TripStatus|'')}><option value="">Todos</option><option>ABERTA</option><option>EM_ANDAMENTO</option><option>FINALIZADA</option><option>CANCELADA</option></select></label><label>Período<select value={period} onChange={e => { setPeriod(e.target.value as Period); setDate('') }}><option value="">Todos</option><option value="day">Dia</option><option value="month">Mês</option><option value="year">Ano</option></select></label>{period && <label>{period === 'day' ? 'Data de saída' : period === 'month' ? 'Mês de saída' : 'Ano de saída'}<input key={period} type={period === 'day' ? 'date' : period === 'month' ? 'month' : 'number'} min={period === 'year' ? '1900' : '1900-01' + (period === 'day' ? '-01' : '')} max={period === 'year' ? '9999' : '9999-12' + (period === 'day' ? '-31' : '')} placeholder={period === 'year' ? 'Ex.: 2026' : undefined} value={date} onChange={e => setDate(e.target.value)}/></label>}{(status || period) && <button className="button button--secondary" type="button" onClick={() => { setStatus(''); setPeriod(''); setDate('') }}>Limpar filtros</button>}<span className="result-count" aria-live="polite"><Search/> {data ? `${data.total} registros` : error ? '—' : 'Carregando…'}</span></section><section className="panel table-panel">{data?.items.length?<div className="table-wrap"><table><thead><tr><th>Saída</th><th>Motorista</th><th>Veículo</th><th>KM inicial</th><th>KM final</th><th>Percorrido</th><th>Status</th></tr></thead><tbody>{data.items.map(t=><tr key={t.id} onClick={()=>navigate(`/admin/viagens/${t.id}`)} tabIndex={0}><td>{formatDate(t.data_saida)}</td><td><strong>{t.driver_name}</strong></td><td className="mono">{t.vehicle_plate}</td><td>{formatKm(t.km_inicial)}</td><td>{t.km_final===undefined?'—':formatKm(t.km_final)}</td><td>{t.km_percorrido===undefined?'—':formatKm(t.km_percorrido)}</td><td><StatusBadge value={t.status}/></td></tr>)}</tbody></table></div>:data ? <Empty title="Nenhuma viagem" description={status || (period && validDate) ? 'Não há viagens para os filtros selecionados.' : 'As viagens aparecerão aqui após a primeira saída.'}/> : <p className="loading-page">{error ? 'Não foi possível carregar as viagens.' : 'Carregando viagens…'}</p>}</section></div>}

