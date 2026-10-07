import { ArrowDown, ArrowUp, ListOrdered } from 'lucide-react'
import { useRef, useState } from 'react'
import type { Trip } from '../types'
import { api } from '../services/api'
import { Alert, Button } from './UI'

export function DeliveryOrderEditor({trip,onSaved}:{trip:Trip;onSaved:(trip:Trip)=>void}) {
  const pending=trip.notas.filter(n=>n.status==='PENDENTE'||n.status==='EM_ENTREGA')
  const [editing,setEditing]=useState(false)
  const [draft,setDraft]=useState<number[]>([])
  const [revision,setRevision]=useState(0)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [success,setSuccess]=useState('')
  const saving=useRef(false)
  if(!['ABERTA','EM_ANDAMENTO'].includes(trip.status)||pending.length<2)return null
  function begin(){setDraft(pending.map(n=>n.id));setRevision(trip.delivery_revision);setEditing(true);setError('');setSuccess('')}
  function move(index:number,direction:number){setDraft(ids=>{const next=[...ids];[next[index],next[index+direction]]=[next[index+direction],next[index]];return next})}
  async function save(ids:number[],expectedRevision:number){
    if(saving.current)return
    saving.current=true;setBusy(true);setError('');setSuccess('')
    // Keep treated deliveries in place, replacing only unresolved slots.
    let index=0
    const order=trip.notas.map(n=>n.status==='PENDENTE'||n.status==='EM_ENTREGA'?ids[index++]:n.id)
    try{
      const result=await api<Trip>(`/trips/${trip.id}/delivery-order`,{method:'PUT',body:JSON.stringify({invoice_ids:order,revision:expectedRevision})})
      onSaved(result);setEditing(false);setSuccess('Ordem das entregas atualizada.')
    }catch(e){
      setError(e instanceof Error?e.message:'Não foi possível salvar. Tente novamente.')
      try{onSaved(await api<Trip>(`/trips/${trip.id}`));setEditing(false)}catch{/* Keep draft available during connection failure. */}
    }finally{saving.current=false;setBusy(false)}
  }
  return <div className="delivery-order-editor">
    {error&&<Alert>{error}</Alert>}{success&&<Alert tone="success">{success}</Alert>}
    {editing?<>
      <h3>Alterar ordem das entregas</h3>
      <p>Use as setas para escolher a sequência. Uma entrega iniciada movida para depois ficará pendente, mantendo seu horário de início.</p>
      <ul className="delivery-order-list">{draft.map((id,index)=>{const note=trip.notas.find(n=>n.id===id);return <li key={id}>
        <div><span className="delivery-number">{String(index+1).padStart(2,'0')}</span><strong>NF {note?.numero_nota}</strong></div>
        <div className="delivery-order-arrows"><Button variant="secondary" disabled={busy||index===0} aria-label={`Mover NF ${note?.numero_nota} para cima`} onClick={()=>move(index,-1)}><ArrowUp size={20}/></Button><Button variant="secondary" disabled={busy||index===draft.length-1} aria-label={`Mover NF ${note?.numero_nota} para baixo`} onClick={()=>move(index,1)}><ArrowDown size={20}/></Button></div>
      </li>})}</ul>
      <div className="action-stack"><Button loading={busy} className="button--full" onClick={()=>save(draft,revision)}>Salvar ordem</Button><Button variant="secondary" disabled={busy} className="button--full" onClick={()=>setEditing(false)}>Cancelar</Button></div>
    </>:<div className="action-stack">
      <Button variant="secondary" disabled={busy} className="button--full" onClick={begin}><ListOrdered size={20}/> Alterar ordem</Button>
      <Button variant="secondary" loading={busy} className="button--full" onClick={()=>save([...pending.slice(1).map(n=>n.id),pending[0].id],trip.delivery_revision)}>Deixar NF {pending[0].numero_nota} para depois</Button>
    </div>}
  </div>
}
