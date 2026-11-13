import { useRealtimeEffect } from '../hooks/useRealtimeEffect'
import { useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Alert, Button, StatusBadge } from '../components/UI'
import { api } from '../services/api'
import { formatDate } from '../utils/format'

type Task = { id:number; titulo:string; endereco:string; observacoes:string; status:string; driver_name:string|null; created_at:string; accepted_at:string|null; completed_at:string|null }
type Location = { address:string; latitude:number; longitude:number; location_token:string }
const categories = [{key:'DISPONIVEL',label:'Disponíveis'},{key:'ACEITA',label:'Aceitas'},{key:'EM_ANDAMENTO',label:'Em andamento'},{key:'CONCLUIDA',label:'Concluídas'},{key:'CANCELADA',label:'Canceladas'}]
const empty = {titulo:'',endereco:'',observacoes:''}

export function TasksPage({admin=false}:{admin?:boolean}) {
  const [items,setItems]=useState<Task[]>([])
  const [section,setSection]=useState(admin?'DISPONIVEL':'available')
  const [form,setForm]=useState(empty)
  const [error,setError]=useState('')
  const [success,setSuccess]=useState('')
  const [loading,setLoading]=useState(true)
  const [busy,setBusy]=useState<number|null>(null)
  const [locations,setLocations]=useState<{taskId:number;candidates:Location[]}|null>(null)
  const [selectedLocation,setSelectedLocation]=useState('')
  const [publishing,setPublishing]=useState(false)
  const refresh=useRef<()=>Promise<void>>(async()=>{})
  useRealtimeEffect(['tasks'], ()=>{
    let alive=true, running=false
    const controller=new AbortController()
    async function load(){
      if(running)return
      running=true
      try{
        const path=admin?`/tasks?status=${section}`:section==='available'?'/tasks/available':`/tasks/mine?completed=${section==='history'}`
        const all:Task[]=[]
        for(let offset=0;;offset+=100){
          const page=await api<Task[]>(`${path}${path.includes('?')?'&':'?'}offset=${offset}&limit=100`,{signal:controller.signal})
          all.push(...page)
          if(page.length<100)break
        }
        if(alive){setItems(all);setError('')}
      }catch(e){if(alive)setError((e as Error).message)}finally{running=false;if(alive)setLoading(false)}
    }
    setItems([]);setLoading(true);refresh.current=load;void load()
    return()=>{alive=false;controller.abort()}
  },[admin,section])
  async function publish(e:FormEvent){
    e.preventDefault();setPublishing(true);setError('');setSuccess('')
    try{await api('/tasks',{method:'POST',body:JSON.stringify(form)});setForm(empty);setSuccess('Tarefa publicada com sucesso.');setSection('DISPONIVEL');await refresh.current()}
    catch(e){setError((e as Error).message)}finally{setPublishing(false)}
  }
  async function act(task:Task, locationToken?:string){
    setBusy(task.id);setError('');setSuccess('')
    try{
      if(section==='available'&&!locationToken){
        const result=await api<{required:boolean;candidates:Location[]}>(`/tasks/${task.id}/locations`)
        if(result.required){
          setLocations({taskId:task.id,candidates:result.candidates});setSelectedLocation('')
          if(!result.candidates.length)setError('Nenhum endereço encontrado. Solicite a revisão do endereço da tarefa.')
          return
        }
      }
      await api(`/tasks/${task.id}/${section==='available'?'accept':'complete'}`,{method:'POST',...(locationToken?{body:JSON.stringify({location_token:locationToken})}:{})})
      setLocations(null);setSelectedLocation('')
      setSuccess(section==='available'?'Tarefa aceita. Se houver viagem ativa, a parada foi incluída e a rota recalculada.':'Tarefa concluída com sucesso.')
      await refresh.current()
    }catch(e){await refresh.current();setError((e as Error).message)}finally{setBusy(null)}
  }
  async function cancel(task:Task){
    if(!window.confirm(`Cancelar a tarefa #${task.id}: ${task.titulo}?`))return
    setBusy(task.id);setError('');setSuccess('')
    try{await api(`/tasks/${task.id}/cancel`,{method:'POST'});setSuccess('Tarefa cancelada com sucesso.');await refresh.current()}
    catch(e){await refresh.current();setError((e as Error).message)}finally{setBusy(null)}
  }
  return <div className={admin?'admin-page':'tasks-driver'}>
    <header className="page-heading"><div><h1>{admin?'Central de Tarefas':'Tarefas'}</h1><p>{admin?'Publique serviços e acompanhe os responsáveis.':'Aceite tarefas para incluir novas paradas na sua viagem ativa.'}</p></div></header>
    {admin&&<section className="panel task-publish"><h2>Publicar tarefa</h2><form className="modal-form" onSubmit={publish}>
      <label>Título da tarefa<input required maxLength={160} value={form.titulo} onChange={e=>setForm({...form,titulo:e.target.value})}/></label>
      <label>Endereço<input required maxLength={500} value={form.endereco} onChange={e=>setForm({...form,endereco:e.target.value})}/></label>
      <label>Observações gerais<textarea required maxLength={10000} rows={3} value={form.observacoes} onChange={e=>setForm({...form,observacoes:e.target.value})}/></label>
      <Button type="submit" loading={publishing} disabled={!Object.values(form).every(value=>value.trim())}>Publicar tarefa</Button>
    </form></section>}
    {error&&<Alert>{error}</Alert>}{success&&<Alert tone="success">{success}</Alert>}
    <nav className="task-tabs" aria-label="Categorias de tarefas">{(admin?categories:[{key:'available',label:'Tarefas disponíveis'},{key:'mine',label:'Minhas tarefas'},{key:'history',label:'Histórico'}]).map(tab=><Button key={tab.key} variant={section===tab.key?'primary':'secondary'} onClick={()=>{setSection(tab.key);setSuccess('');setLocations(null);setSelectedLocation('')}} aria-pressed={section===tab.key}>{tab.label}</Button>)}</nav>
    {loading?<p role="status">Carregando tarefas...</p>:!items.length?<section className="panel task-card"><p>Nenhuma tarefa nesta categoria.</p></section>:<div className="task-grid">{items.map(task=><article className="panel task-card" key={task.id}>
      <header><span>#{task.id}</span><StatusBadge value={task.status}/></header><h2>{task.titulo}</h2><p className="task-address">{task.endereco}</p><p className="task-notes">{task.observacoes}</p>
      <dl><dt>Criada em</dt><dd>{formatDate(task.created_at)}</dd>{task.driver_name&&<><dt>Motorista responsável</dt><dd>{task.driver_name}</dd></>}{task.accepted_at&&<><dt>Aceita em</dt><dd>{formatDate(task.accepted_at)}</dd></>}{task.completed_at&&<><dt>Concluída em</dt><dd>{formatDate(task.completed_at)}</dd></>}</dl>
      {admin&&['DISPONIVEL','ACEITA','EM_ANDAMENTO'].includes(task.status)&&<footer><Button variant="danger" loading={busy===task.id} disabled={busy!==null} onClick={()=>cancel(task)}>Cancelar tarefa</Button></footer>}
      {!admin&&section==='available'&&locations?.taskId===task.id&&<form className="task-locations" onSubmit={e=>{e.preventDefault();void act(task,selectedLocation)}}>
        <fieldset disabled={busy!==null}>
          <legend>Selecione o endereço da parada</legend>
          <p>Confira a rua, o bairro e o CEP antes de confirmar.</p>
          {locations.candidates.map((point,index)=><div className="task-location" key={point.location_token}>
            <label><input type="radio" name={`location-${task.id}`} value={point.location_token} checked={selectedLocation===point.location_token} onChange={()=>setSelectedLocation(point.location_token)} required/><span><strong>Opção {index+1}</strong><span>{point.address}</span></span></label>
            <a href={`https://www.google.com/maps/search/?api=1&query=${point.latitude},${point.longitude}`} target="_blank" rel="noopener noreferrer">Conferir no mapa</a>
          </div>)}
        </fieldset>
        <Button type="submit" loading={busy===task.id} disabled={!selectedLocation||busy!==null}>Confirmar endereço e aceitar</Button>
        <Button type="button" variant="secondary" disabled={busy!==null} onClick={()=>{setLocations(null);setSelectedLocation('')}}>Cancelar seleção</Button>
      </form>}
      {!admin&&section!=='history'&&<footer><Button loading={busy===task.id} disabled={busy!==null||locations?.taskId===task.id} onClick={()=>act(task)}>{section==='available'?'Aceitar tarefa':'Marcar como concluída'}</Button>{section==='available'&&<Link className="button button--secondary" to="/motorista">Continuar minha rota</Link>}</footer>}
    </article>)}</div>}
  </div>
}
