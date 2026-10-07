import { ArrowLeft, Check, Gauge } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button } from '../../components/UI'
import { api } from '../../services/api'
import type { Trip } from '../../types'
import { formatKm } from '../../utils/format'

export function FinishTripPage(){const navigate=useNavigate();const[trip,setTrip]=useState<Trip>();const[km,setKm]=useState('');const[note,setNote]=useState('');const[error,setError]=useState('');const[loading,setLoading]=useState(false);const[done,setDone]=useState(false)
useEffect(()=>{api<Trip>('/trips/current').then(setTrip).catch(e=>setError(e.message))},[]);const distance=trip&&Number(km)>=trip.km_inicial?Number(km)-trip.km_inicial:null
async function submit(e:FormEvent){e.preventDefault();setLoading(true);setError('');try{await api(`/trips/${trip?.id}/finish`,{method:'POST',body:JSON.stringify({km_final:Number(km),observacao:note||null})});setDone(true)}catch(e){setError(e instanceof Error?e.message:'Erro ao finalizar')}finally{setLoading(false)}}
if(done)return <div className="driver-page result-page"><div className="result-icon success"><Check/></div><h1>Viagem finalizada</h1><p>KM atualizado e veículo liberado com sucesso.</p><Button className="button--full button--xl" onClick={()=>navigate('/motorista',{replace:true})}>Concluir</Button></div>
return <div className="driver-page fade-in"><button className="back-link" onClick={()=>navigate(-1)}><ArrowLeft/> Voltar</button><p className="step-label">ETAPA 3 DE 3</p><h1>Finalizar viagem</h1><div className="finish-summary"><span>Veículo<strong>{trip?.vehicle_plate}</strong></span><span>KM inicial<strong>{formatKm(trip?.km_inicial)}</strong></span></div>{error&&<Alert>{error}</Alert>}<form className="driver-form" onSubmit={submit}><label>KM final<span className="input-with-icon"><Gauge/><input type="number" min={trip?.km_inicial} inputMode="numeric" value={km} onChange={e=>setKm(e.target.value)} required autoFocus/></span></label><div className="distance-preview"><span>KM percorrido</span><strong>{distance===null?'—':formatKm(distance)}</strong></div><label>Observação <small>(opcional)</small><textarea value={note} onChange={e=>setNote(e.target.value)} placeholder="Alguma informação sobre a viagem?"/></label><Button type="submit" loading={loading} className="button--full button--xl">Finalizar viagem</Button></form></div>}

