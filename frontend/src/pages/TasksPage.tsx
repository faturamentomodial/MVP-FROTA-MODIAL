import { useRealtimeEffect } from '../hooks/useRealtimeEffect'
import { useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Alert, Button, StatusBadge } from '../components/UI'
import { api } from '../services/api'
import { formatDate } from '../utils/format'

type Task = { id:number; titulo:string; endereco:string; observacoes:string; status:string; driver_name:string|null; created_at:string; accepted_at:string|null; completed_at:string|null }
const categories = [{key:'DISPONIVEL',label:'Disponíveis'},{key:'ACEITA',label:'Aceitas'},{key:'EM_ANDAMENTO',label:'Em andamento'},{key:'CONCLUIDA',label:'Concluídas'}]
const empty = {titulo:'',endereco:'',observacoes:''}

export function TasksPage({admin=false}:{admin?:boolean}) {
  const [items,setItems]=useState<Task[]>([])
  const [section,setSection]=useState(admin?'DISPONIVEL':'available')
  const [form,setForm]=useState(empty)
  const [error,setError]=useState('')
  const [success,setSuccess]=useState('')
  const [loading,setLoading]=useState(true)
  const [busy,setBusy]=useState<number|null>(null)
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
  async function act(task:Task){
    setBusy(task.id);setError('');setSuccess('')
    try{await api(`/tasks/${task.id}/${section==='available'?'accept':'complete'}`,{method:'POST'});setSuccess(section==='available'?'Tarefa aceita. Consulte Minhas tarefas.':'Tarefa concluída com sucesso.');await refresh.current()}
    catch(e){await refresh.current();setError((e as Error).message)}finally{setBusy(null)}
  }
  return <div className={admin?'admin-page':'tasks-driver'}>
    <header className="page-heading"><div><h1>{admin?'Central de Tarefas':'Tarefas'}</h1><p>{admin?'Publique serviços e acompanhe os responsáveis.':'Escolha as tarefas que deseja aceitar, sem interromper sua rota.'}</p></div></header>
    {admin&&<section className="panel task-publish"><h2>Publicar tarefa</h2><form className="modal-form" onSubmit={publish}>
      <label>Título da tarefa<input required maxLength={160} value={form.titulo} onChange={e=>setForm({...form,titulo:e.target.value})}/></label>
      <label>Endereço<input required maxLength={500} value={form.endereco} onChange={e=>setForm({...form,endereco:e.target.value})}/></label>
      <label>Observações gerais<textarea required maxLength={10000} rows={3} value={form.observacoes} onChange={e=>setForm({...form,observacoes:e.target.value})}/></label>
      <Button type="submit" loading={publishing} disabled={!Object.values(form).every(value=>value.trim())}>Publicar tarefa</Button>
    </form></section>}
    {error&&<Alert>{error}</Alert>}{success&&<Alert tone="success">{success}</Alert>}
    <nav className="task-tabs" aria-label="Categorias de tarefas">{(admin?categories:[{key:'available',label:'Tarefas disponíveis'},{key:'mine',label:'Minhas tarefas'},{key:'history',label:'Histórico'}]).map(tab=><Button key={tab.key} variant={section===tab.key?'primary':'secondary'} onClick={()=>{setSection(tab.key);setSuccess('')}} aria-pressed={section===tab.key}>{tab.label}</Button>)}</nav>
    {loading?<p role="status">Carregando tarefas...</p>:!items.length?<section className="panel task-card"><p>Nenhuma tarefa nesta categoria.</p></section>:<div className="task-grid">{items.map(task=><article className="panel task-card" key={task.id}>
      <header><span>#{task.id}</span><StatusBadge value={task.status}/></header><h2>{task.titulo}</h2><p className="task-address">{task.endereco}</p><p className="task-notes">{task.observacoes}</p>
      <dl><dt>Criada em</dt><dd>{formatDate(task.created_at)}</dd>{task.driver_name&&<><dt>Motorista responsável</dt><dd>{task.driver_name}</dd></>}{task.accepted_at&&<><dt>Aceita em</dt><dd>{formatDate(task.accepted_at)}</dd></>}{task.completed_at&&<><dt>Concluída em</dt><dd>{formatDate(task.completed_at)}</dd></>}</dl>
      {!admin&&section!=='history'&&<footer><Button loading={busy===task.id} disabled={busy!==null} onClick={()=>act(task)}>{section==='available'?'Aceitar tarefa':'Marcar como concluída'}</Button>{section==='available'&&<Link className="button button--secondary" to="/motorista">Continuar minha rota</Link>}</footer>}
    </article>)}</div>}
  </div>
}
