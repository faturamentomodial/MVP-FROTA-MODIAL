import { ArrowLeft, Check, MapPin } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button } from '../../components/UI'
import { api } from '../../services/api'
import type { OccurrenceType, Trip } from '../../types'
import { labelEnum } from '../../utils/format'

const types:OccurrenceType[]=['ACIDENTE','AVARIA','PROBLEMA_MECANICO','PROBLEMA_ELETRICO','PNEU','PROBLEMA_ENTREGA','CLIENTE_AUSENTE','ATRASO','MULTA','ABASTECIMENTO','OUTRO']
export function OccurrencePage(){const navigate=useNavigate();const[trip,setTrip]=useState<Trip>();const[tipo,setTipo]=useState<OccurrenceType|' '>(' ');const[descricao,setDescricao]=useState('');const[local,setLocal]=useState('');const[error,setError]=useState('');const[loading,setLoading]=useState(false);const[done,setDone]=useState(false)
useEffect(()=>{api<Trip>('/trips/current').then(setTrip).catch(e=>setError(e.message))},[])
async function submit(e:FormEvent){e.preventDefault();setLoading(true);setError('');try{await api('/occurrences',{method:'POST',body:JSON.stringify({trip_id:trip?.id,tipo,descricao,local:local||null})});setDone(true)}catch(e){setError(e instanceof Error?e.message:'Erro ao registrar')}finally{setLoading(false)}}
if(done)return <div className="driver-page result-page"><div className="result-icon success"><Check/></div><h1>Ocorrência registrada</h1><p>O gestor já poderá acompanhar o registro no dashboard.</p><Button className="button--full button--xl" onClick={()=>navigate('/motorista')}>Voltar para a viagem</Button></div>
return <div className="driver-page fade-in"><button className="back-link" onClick={()=>navigate(-1)}><ArrowLeft/> Voltar</button><p className="eyebrow">VIAGEM • {trip?.vehicle_plate}</p><h1>Nova ocorrência</h1><p className="lead">Registre o que aconteceu de forma clara.</p>{error&&<Alert>{error}</Alert>}<form className="driver-form" onSubmit={submit}><label>Tipo<select value={tipo} onChange={e=>setTipo(e.target.value as OccurrenceType)} required><option value=" ">Selecione</option>{types.map(t=><option key={t} value={t}>{labelEnum(t)}</option>)}</select></label><label>Descrição<textarea value={descricao} onChange={e=>setDescricao(e.target.value)} placeholder="Conte o que aconteceu" required minLength={3}/></label><label>Local<span className="input-with-icon"><MapPin/><input value={local} onChange={e=>setLocal(e.target.value)} placeholder="Ex.: Guarulhos - SP"/></span></label><Button loading={loading} type="submit" className="button--full button--xl">Registrar ocorrência</Button></form></div>}

