import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Empty, StatusBadge } from '../../components/UI'
import { api } from '../../services/api'
import type { Page, Trip, TripStatus } from '../../types'
import { formatDate, formatKm } from '../../utils/format'

export function TripsPage(){const navigate=useNavigate();const[data,setData]=useState<Page<Trip>>();const[status,setStatus]=useState<TripStatus|''>('');const[error,setError]=useState('');useEffect(()=>{api<Page<Trip>>(`/trips?page_size=100${status?`&status=${status}`:''}`).then(setData).catch(e=>setError(e.message))},[status])
return <div className="admin-page"><header className="page-heading"><div><p className="eyebrow">HISTÓRICO</p><h1>Viagens</h1><p>Saídas, retornos e quilometragem consolidada.</p></div></header>{error&&<Alert>{error}</Alert>}<section className="filter-bar filter-bar--compact"><label>Status<select value={status} onChange={e=>setStatus(e.target.value as TripStatus|'')}><option value="">Todos</option><option>ABERTA</option><option>EM_ANDAMENTO</option><option>FINALIZADA</option><option>CANCELADA</option></select></label><span className="result-count"><Search/> {data?.total||0} registros</span></section><section className="panel table-panel">{data?.items.length?<div className="table-wrap"><table><thead><tr><th>Saída</th><th>Motorista</th><th>Veículo</th><th>KM inicial</th><th>KM final</th><th>Percorrido</th><th>Status</th></tr></thead><tbody>{data.items.map(t=><tr key={t.id} onClick={()=>navigate(`/admin/viagens/${t.id}`)} tabIndex={0}><td>{formatDate(t.data_saida)}</td><td><strong>{t.driver_name}</strong></td><td className="mono">{t.vehicle_plate}</td><td>{formatKm(t.km_inicial)}</td><td>{t.km_final===undefined?'—':formatKm(t.km_final)}</td><td>{t.km_percorrido===undefined?'—':formatKm(t.km_percorrido)}</td><td><StatusBadge value={t.status}/></td></tr>)}</tbody></table></div>:<Empty title="Nenhuma viagem" description="As viagens aparecerão aqui após a primeira saída."/>}</section></div>}

