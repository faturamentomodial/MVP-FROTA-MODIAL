import { ArrowRight, CheckCircle2, Circle, LockKeyhole, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { DeliveryOrderEditor } from './DeliveryOrderEditor'
import { StatusBadge } from './UI'
import type { Trip } from '../types'
import { formatDate } from '../utils/format'

export const deliveryLabels = {PENDENTE:'Pendente', EM_ENTREGA:'Em entrega', ENTREGUE:'Entregue', NAO_ENTREGUE:'Não entregue · ocorrência'}
export const deliveryReasons: Record<string,string> = {CLIENTE_FECHADO:'Cliente fechado', CLIENTE_RECUSOU:'Cliente não quis receber', CLIENTE_AUSENTE:'Destinatário ausente', ENDERECO_NAO_LOCALIZADO:'Endereço não localizado', MERCADORIA_RECUSADA:'Mercadoria recusada', OUTRO:'Outro'}

export function DeliveryRoute({trip,admin=false,onChanged}:{trip:Trip;admin?:boolean;onChanged?:(trip:Trip)=>void}) {
 const done=trip.notas.filter(n=>n.status==='ENTREGUE').length
 const failed=trip.notas.filter(n=>n.status==='NAO_ENTREGUE').length
 const current=trip.notas.find(n=>n.status==='PENDENTE'||n.status==='EM_ENTREGA')?.id
 return <section className="panel delivery-route" aria-label="Entregas da rota">
  <header><h2>Rota #{trip.id}</h2><p>{trip.driver_name}</p><div className="delivery-counts"><span><strong>{trip.notas.length}</strong> entregas</span><span><strong>{done}</strong> entregues</span><span><strong>{failed}</strong> ocorrências</span><span><strong>{trip.notas.length-done-failed}</strong> pendentes</span></div>
  <progress value={done+failed} max={Math.max(1,trip.notas.length)} aria-label="Entregas tratadas"/>
  {!admin&&onChanged&&<DeliveryOrderEditor trip={trip} onSaved={onChanged}/>}
  </header>
  <ol>{trip.notas.map((n,index)=>{const resolved=n.status==='ENTREGUE'||n.status==='NAO_ENTREGUE';const Icon=n.status==='ENTREGUE'?CheckCircle2:n.status==='NAO_ENTREGUE'?TriangleAlert:n.status==='EM_ENTREGA'?ArrowRight:n.id!==current?LockKeyhole:Circle
   return <li key={n.id} className={n.id===current?'delivery-current':''}><div className={`delivery-stop delivery-stop--${n.status.toLowerCase()}`}><span className="delivery-number">{String(index+1).padStart(2,'0')}</span><Icon aria-hidden="true"/><div><h3>NF {n.numero_nota}</h3><p>{n.volumes} volumes</p><StatusBadge value={n.status}/>{n.delivered_at&&<p>Entregue em {formatDate(n.delivered_at)}</p>}{n.occurrence_at&&<p>{deliveryReasons[n.occurrence_reason||'']} · {formatDate(n.occurrence_at)}</p>}</div></div>
   {admin?<div className="delivery-history"><p>Início: {formatDate(n.started_at)}</p>{n.occurrence_note&&<p>{n.occurrence_note}</p>}</div>:<Link className={`button button--${!resolved&&n.id===current?'primary':'secondary'} button--full delivery-open`} to={`/motorista/entrega/${trip.id}/${n.id}`}>{resolved?'Ver histórico':n.id===current?'Abrir entrega':'Consultar entrega'}<ArrowRight size={18}/></Link>}
   </li>})}</ol>
 </section>
}
