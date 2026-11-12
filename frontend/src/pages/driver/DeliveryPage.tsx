import { DeliveryOrderActions, stopAddress } from '../../components/DeliveryOrderActions'
import { useRealtimeEffect } from '../../hooks/useRealtimeEffect'
import { ArrowLeft } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Alert, Button, StatusBadge } from '../../components/UI'
import { deliveryReasons } from '../../components/DeliveryRoute'
import { api } from '../../services/api'
import type { Trip, TripInvoice } from '../../types'
import { formatDate } from '../../utils/format'

export function DeliveryPage(){
 const navigate=useNavigate(); const {tripId,invoiceId}=useParams(); const [trip,setTrip]=useState<Trip>(); const [error,setError]=useState('');const [busy,setBusy]=useState(false);const pending=useRef(false)
 const [showOccurrence,setShowOccurrence]=useState(false);const [reason,setReason]=useState('CLIENTE_FECHADO');const [note,setNote]=useState('');const [confirmation,setConfirmation]=useState('')
 const [showPickup,setShowPickup]=useState(false);const [pickupVolume,setPickupVolume]=useState('');const [pickupDescription,setPickupDescription]=useState('')
 const load=()=>api<Trip>(`/trips/${tripId}`).then(setTrip)
 useRealtimeEffect(['trips', 'pickups', 'routes'], ()=>{load().catch(e=>setError(e.message))},[tripId,invoiceId])
 useEffect(()=>{setShowOccurrence(false);setReason('CLIENTE_FECHADO');setNote('');setShowPickup(false);setPickupVolume('');setPickupDescription('')},[tripId,invoiceId])
 const invoice=trip?.notas.find(n=>n.id===Number(invoiceId))
 const current=trip?.notas.find(n=>n.status==='PENDENTE'||n.status==='EM_ENTREGA')?.id
 const available=trip?.status==='EM_ANDAMENTO'&&current===invoice?.id
 async function act(action:'start'|'finish'|'occurrence'){
  if(pending.current)return
  pending.current=true;setBusy(true);setError('');setConfirmation('')
  try{
   const result=await api<TripInvoice>(`/trips/${tripId}/deliveries/${invoiceId}/${action}`,{method:'POST',...(action==='occurrence'?{body:JSON.stringify({motivo:reason,observacao:note})}:action==='finish'?{body:JSON.stringify(showPickup?{pickup_volume:pickupVolume?Number(pickupVolume):null,pickup_description:pickupDescription.trim()||null}:{})}:{})})
   await load()
   setShowOccurrence(false)
   setConfirmation(action==='start'?'Entrega iniciada.':action==='finish'?`Entrega finalizada com sucesso. ${result.is_address_stop?'':'NF '}${result.numero_nota} · ${formatDate(result.delivered_at)}`:`Ocorrência registrada. ${result.is_address_stop?'':'NF '}${result.numero_nota} · ${deliveryReasons[result.occurrence_reason||'']} · ${formatDate(result.occurrence_at)}`)
  }catch(e){setError(e instanceof Error?e.message:'Falha de conexão. Consulte a rota antes de tentar novamente.');await load().catch(()=>{})}
  finally{pending.current=false;setBusy(false)}
 }
 return <div className="driver-page delivery-page"><Link className="back-link" to="/motorista"><ArrowLeft/> Voltar à rota</Link>
 {error&&<><Alert>{error}</Alert><Button variant="secondary" disabled={busy} onClick={()=>{setError('');load().catch(e=>setError(e.message))}}>Atualizar entrega</Button></>}{confirmation&&<Alert tone="success">{confirmation}</Alert>}
 {!trip&&!error?<p>Carregando entrega…</p>:!invoice?<p>Entrega não encontrada nesta rota.</p>:<>
 <h1>{invoice.is_address_stop?invoice.numero_nota:`NF ${invoice.numero_nota}`}</h1>{invoice.is_address_stop&&<p>{trip&&stopAddress(trip,invoice)}</p>}<StatusBadge value={invoice.status}/>
 <section className="panel delivery-route delivery-details"><dl><dt>Rota</dt><dd>#{trip?.id}</dd><dt>Motorista</dt><dd>{trip?.driver_name}</dd>{!invoice.is_address_stop&&<><dt>Volumes</dt><dd>{invoice.volumes}</dd></>}<dt>Início</dt><dd>{formatDate(invoice.started_at)}</dd>{invoice.delivered_at&&<><dt>Finalização</dt><dd>{formatDate(invoice.delivered_at)}</dd></>}{invoice.occurrence_at&&<><dt>Ocorrência</dt><dd>{deliveryReasons[invoice.occurrence_reason||'']}<br/>{formatDate(invoice.occurrence_at)}{invoice.occurrence_note&&<p>{invoice.occurrence_note}</p>}</dd></>}{(invoice.pickup_volume!=null||invoice.pickup_description)&&<><dt>Material retirado</dt><dd>{invoice.pickup_volume!=null&&<p>{invoice.pickup_volume} volume(s)</p>}{invoice.pickup_description&&<p style={{whiteSpace:'pre-wrap'}}>{invoice.pickup_description}</p>}</dd></>}</dl></section>
 {!available&&(invoice.status==='PENDENTE'||invoice.status==='EM_ENTREGA')&&<p>{trip?.status==='EM_ANDAMENTO'?'Use a opção Fazer esta agora para atender esta entrega antes das demais.':'Inicie a viagem para operar esta entrega.'}</p>}
 {trip&&<DeliveryOrderActions trip={trip} invoiceId={invoice.id} disabled={busy} onChanged={updated=>{setTrip(updated);setShowOccurrence(false);setConfirmation('Ordem das entregas atualizada.');if(current===invoice.id){const next=updated.notas.find(n=>n.status==='PENDENTE'||n.status==='EM_ENTREGA');if(next&&next.id!==invoice.id)navigate(`/motorista/entrega/${updated.id}/${next.id}`)}}}/>}
 {available&&invoice.status==='PENDENTE'&&<Button disabled={busy} className="button--full button--xl" onClick={()=>act('start')}>{busy?'Aguarde…':'Iniciar entrega'}</Button>}
 {available&&invoice.status==='EM_ENTREGA'&&<form className="action-stack driver-form" onSubmit={e=>{e.preventDefault();act('finish')}}><label className="pickup-toggle"><input type="checkbox" checked={showPickup} disabled={busy} aria-controls="pickup-fields" aria-expanded={showPickup} onChange={e=>setShowPickup(e.target.checked)}/> Informar material retirado (opcional)</label>{showPickup&&<div id="pickup-fields" className="panel driver-form"><label>Volume retirado<input type="number" inputMode="numeric" min={1} max={1000000} step={1} disabled={busy} value={pickupVolume} onChange={e=>setPickupVolume(e.target.value)} placeholder="Quantidade de volumes"/></label><label>Descrição do material retirado<textarea maxLength={4000} disabled={busy} value={pickupDescription} onChange={e=>setPickupDescription(e.target.value)} placeholder="Descreva o que foi retirado"/></label></div>}<Button type="submit" disabled={busy} className="button--full button--xl">{busy?'Aguarde…':'Finalizar entrega'}</Button><Button type="button" disabled={busy} variant="secondary" className="button--full button--xl" onClick={()=>setShowOccurrence(!showOccurrence)}>Registrar ocorrência</Button></form>}
 {available&&showOccurrence&&<form className="panel delivery-route occurrence-form" onSubmit={e=>{e.preventDefault();act('occurrence')}}><label>Motivo<select disabled={busy} value={reason} onChange={e=>setReason(e.target.value)}>{Object.entries(deliveryReasons).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label><label>Observação{reason==='OUTRO'?' (obrigatória)':' (opcional)'}<textarea disabled={busy} required={reason==='OUTRO'} maxLength={4000} value={note} onChange={e=>setNote(e.target.value)}/></label><Button disabled={busy} className="button--full button--xl" type="submit">{busy?'Registrando…':'Confirmar ocorrência'}</Button></form>}
 {(invoice.status==='ENTREGUE'||invoice.status==='NAO_ENTREGUE')&&<Link className="button button--primary button--full button--xl delivery-open" to="/motorista">{current?'Próxima entrega':'Ver resultado da rota'}</Link>}
 </>}
 </div>
}
