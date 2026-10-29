import { DeliveryRoute } from '../../components/DeliveryRoute'
import { ArrowRight, Clock3, Gauge, MapPin, Plus, TriangleAlert, Truck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button } from '../../components/UI'
import { useAuth } from '../../hooks/useAuth'
import { api } from '../../services/api'
import type { PlannedRoute, Trip } from '../../types'
import { formatDate, formatKm } from '../../utils/format'

export function DriverHome(){
  const {user}=useAuth(); const navigate=useNavigate(); const [trip,setTrip]=useState<Trip|null|undefined>(); const [error,setError]=useState(''); const [plans,setPlans]=useState<PlannedRoute[]>([])
  useEffect(()=>{api<PlannedRoute[]>('/trips/planned').then(setPlans).catch(e=>setError(e.message));api<Trip|null>('/trips/current').then(setTrip).catch(e=>setError(e.message))},[])
  if(trip===undefined&&!error)return <div className="loading-page">Carregando sua operação…</div>
  return <div className="driver-page fade-in"><p className="eyebrow">OLÁ, {user?.nome.split(' ')[0].toUpperCase()}</p><h1>{trip?'Viagem em andamento':'Pronto para sair?'}</h1>
    {error&&<Alert>{error}</Alert>}
    {!trip?<>{plans.map(p=><section className="active-trip-card" key={p.id}><h2>{p.name}</h2><p>Veículo: {p.vehicle_plate}</p><p>Origem: {p.origin?.address}</p><p>{p.invoices.length} notas · {p.invoices.reduce((sum,n)=>sum+n.volumes,0)} volumes</p>{p.result&&<p>{(p.result.distance/1000).toFixed(1)} km · {Math.round(p.result.duration/60)} min estimados</p>}<ol>{p.invoices.map(n=><li key={n.number}>NF {n.number} · {n.volumes} volumes<p>{n.destination.address}</p></li>)}</ol><Button className="button--full" onClick={()=>navigate(`/motorista/iniciar?plan=${p.id}`)}>Iniciar saída planejada <ArrowRight/></Button></section>)}{!plans.length&&<section className="driver-empty-card"><div className="vehicle-orbit"><Truck size={42}/><span/></div><h2>Nenhuma saída em andamento</h2><p>Inicie uma nova saída e faça a inspeção do veículo antes de seguir rota.</p></section>}<Button className="button--full button--xl" onClick={()=>navigate('/motorista/iniciar')}><Plus/> Iniciar saída</Button></>:
    <><section className="active-trip-card"><div className="active-trip-top"><span className="live-dot">EM ROTA</span><Truck/></div><strong className="plate">{trip.vehicle_plate}</strong><div className="trip-data"><div><Gauge/><span>KM inicial<strong>{formatKm(trip.km_inicial)}</strong></span></div><div><Clock3/><span>Saída<strong>{formatDate(trip.data_saida)}</strong></span></div><div><MapPin/><span>Status<strong>{trip.status==='ABERTA'?'Preparando saída':'Em andamento'}</strong></span></div></div></section>
    {trip.route_plan&&<section className="panel"><h2>{trip.route_plan.name}</h2><p>Origem: {trip.route_plan.origin?.address}</p><ol>{trip.route_plan.invoices.map(n=><li key={n.number}>NF {n.number} · {n.volumes} volumes<p>{n.destination.address}</p></li>)}</ol></section>}{trip.status==='ABERTA'&&!trip.notas.length&&<Button className="button--full button--xl" onClick={()=>navigate(`/motorista/carga/${trip.id}`)}>Informar carga <ArrowRight/></Button>}
    {trip.status==='ABERTA'&&trip.notas.length>0&&!trip.checklist_id&&<Button className="button--full button--xl" onClick={()=>navigate(`/motorista/checklist/${trip.id}`)}>Continuar checklist <ArrowRight/></Button>}
    {trip.status==='ABERTA'&&trip.checklist_id&&<Button className="button--full button--xl" onClick={async()=>{try{setTrip(await api<Trip>(`/trips/${trip.id}/start`,{method:'POST'}))}catch(e){setError(e instanceof Error?e.message:'Não foi possível iniciar a viagem')}}}>Iniciar viagem <ArrowRight/></Button>}
    {trip.status==='EM_ANDAMENTO'&&<DeliveryRoute trip={trip} onChanged={setTrip}/>}
    {trip.status==='EM_ANDAMENTO'&&<div className="action-stack"><Button className="button--full button--xl" onClick={()=>navigate('/motorista/ocorrencia')}><TriangleAlert/> Registrar ocorrência</Button><Button variant="secondary" className="button--full button--xl" disabled={trip.notas.some(n=>n.status==='PENDENTE'||n.status==='EM_ENTREGA')} onClick={()=>navigate('/motorista/finalizar')}>Finalizar viagem <ArrowRight/></Button></div>}</>}
  </div>
}
