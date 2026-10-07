import { ArrowLeft, ArrowRight, Gauge, Truck } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button } from '../../components/UI'
import { api } from '../../services/api'
import type { Page, Trip, Vehicle } from '../../types'
import { formatKm } from '../../utils/format'

export function StartTripPage(){const navigate=useNavigate();const[vehicles,setVehicles]=useState<Vehicle[]>([]);const[vehicleId,setVehicleId]=useState('');const[km,setKm]=useState('');const[error,setError]=useState('');const[loading,setLoading]=useState(false)
useEffect(()=>{api<Page<Vehicle>>('/vehicles?available=true&page_size=100').then(r=>setVehicles(r.items)).catch(e=>setError(e.message))},[])
const selected=vehicles.find(v=>v.id===Number(vehicleId));useEffect(()=>{if(selected)setKm(String(selected.km_atual))},[selected])
async function submit(e:FormEvent){e.preventDefault();setLoading(true);setError('');try{const trip=await api<Trip>('/trips',{method:'POST',body:JSON.stringify({vehicle_id:Number(vehicleId),km_inicial:Number(km)})});navigate(`/motorista/carga/${trip.id}`,{replace:true})}catch(e){setError(e instanceof Error?e.message:'Erro ao iniciar')}finally{setLoading(false)}}
return <div className="driver-page fade-in"><button className="back-link" onClick={()=>navigate(-1)}><ArrowLeft/> Voltar</button><p className="step-label">ETAPA 1 DE 4</p><h1>Iniciar saída</h1><p className="lead">Escolha o veículo e confirme a quilometragem do painel.</p>{error&&<Alert>{error}</Alert>}<form className="driver-form" onSubmit={submit}><label>Veículo<select value={vehicleId} onChange={e=>setVehicleId(e.target.value)} required><option value="">Selecione o veículo</option>{vehicles.map(v=><option key={v.id} value={v.id}>{v.placa} • {v.modelo}</option>)}</select></label>{selected&&<div className="vehicle-selection"><Truck/><span>{selected.marca} {selected.modelo}<small>Último KM: {formatKm(selected.km_atual)}</small></span></div>}<label>KM inicial<span className="input-with-icon"><Gauge/><input type="number" min={selected?.km_atual||0} inputMode="numeric" value={km} onChange={e=>setKm(e.target.value)} required/></span><small>Confira o hodômetro antes de continuar.</small></label><Button type="submit" loading={loading} className="button--full button--xl">Continuar <ArrowRight/></Button></form></div>}
