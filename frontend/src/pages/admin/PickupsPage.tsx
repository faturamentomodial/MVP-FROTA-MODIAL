import { MapPin, Pencil, Plus, Power, Search, Trash2 } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Alert, Button, Empty, Modal, StatusBadge } from '../../components/UI'
import { AddressPicker } from '../../components/AddressPicker'
import { api } from '../../services/api'
import type { RouteTemplate } from '../../types/routePlans'

type PickupType = 'COSTUREIRA' | 'FLORISTA' | 'FORNECEDOR'
const typeLabels = { COSTUREIRA: 'Costureira', FLORISTA: 'Florista', FORNECEDOR: 'Fornecedor' }
type Pickup = { route_template_id: number | null; tipo: PickupType | null; id: number; ativo: boolean; nome: string; telefone: string; endereco: string }
const empty = { route_template_id: '', tipo: '' as PickupType | '', nome: '', telefone: '', endereco: '' }

export function PickupsPage() {
  const [correcting, setCorrecting] = useState<Pickup | null>(null)
  const [items, setItems] = useState<Pickup[]>([])
  const [routes, setRoutes] = useState<RouteTemplate[]>([])
  const [routesLoading, setRoutesLoading] = useState(true)
  const [routesError, setRoutesError] = useState('')
  const [routesRefresh, setRoutesRefresh] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Pickup>()
  const [action, setAction] = useState<{ item: Pickup; kind: 'status' | 'delete' }>()
  const [form, setForm] = useState(empty)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function load() {
    setLoading(true)
    try { setItems(await api<Pickup[]>('/pickups')) }
    catch (e) { setError((e as Error).message) }
    finally { setLoading(false) }
  }
  useEffect(() => { void load() }, [])

  useEffect(() => {
    const controller = new AbortController()
    setRoutesLoading(true); setRoutesError('')
    async function loadRoutes() {
      const all: RouteTemplate[] = []
      let batch: RouteTemplate[]
      do {
        batch = await api<RouteTemplate[]>(`/route-templates?limit=100&offset=${all.length}`, { signal: controller.signal })
        all.push(...batch)
      } while (batch.length === 100)
      if (!controller.signal.aborted) setRoutes(all)
    }
    loadRoutes().catch(e => { if (!controller.signal.aborted) setRoutesError((e as Error).message) })
      .finally(() => { if (!controller.signal.aborted) setRoutesLoading(false) })
    return () => controller.abort()
  }, [open, routesRefresh])

  function show(item?: Pickup) {
    setEditing(item)
    setForm(item ? { route_template_id: item.route_template_id ? String(item.route_template_id) : '', tipo: item.tipo || '', nome: item.nome, telefone: item.telefone, endereco: item.endereco } : empty)
    setError(''); setSuccess(''); setOpen(true)
  }
  function close() { if (!saving) { setOpen(false); setError('') } }

  async function save(e: FormEvent) {
    e.preventDefault(); setError('')
    const payload = { route_template_id: form.route_template_id ? Number(form.route_template_id) : null, tipo: form.tipo, nome: form.nome.trim(), telefone: form.telefone.trim(), endereco: form.endereco.trim() }
    if (!payload.tipo || payload.nome.length < 2 || !payload.telefone || !payload.endereco) {
      setError('Selecione o tipo e informe o nome com pelo menos 2 caracteres, telefone e endereço.'); return
    }
    setSaving(true)
    try {
      await api<Pickup>(editing ? `/pickups/${editing.id}` : '/pickups', {
        method: editing ? 'PUT' : 'POST', body: JSON.stringify(payload),
      })
      setOpen(false); setSuccess(editing ? 'Coleta atualizada.' : 'Coleta cadastrada.')
      await load()
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  function ask(item: Pickup, kind: 'status' | 'delete') {
    setError(''); setSuccess(''); setAction({ item, kind })
  }
  function closeAction() { if (!saving) { setAction(undefined); setError('') } }
  async function confirmAction() {
    if (!action) return
    setSaving(true); setError('')
    try {
      await api(`/pickups/${action.item.id}${action.kind === 'status' ? '/status' : ''}`, {
        method: action.kind === 'delete' ? 'DELETE' : 'PATCH',
        ...(action.kind === 'status' ? { body: JSON.stringify({ ativo: !action.item.ativo }) } : {}),
      })
      setSuccess(action.kind === 'delete' ? 'Coleta excluída.' : action.item.ativo ? 'Coleta desativada.' : 'Coleta ativada.')
      setAction(undefined); await load()
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  const visible = items.filter(item => `${item.tipo ? typeLabels[item.tipo] : ''} ${item.nome} ${item.telefone} ${item.endereco} ${routes.find(route => route.id === item.route_template_id)?.name || ''}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
  return <div className="admin-page">
    <header className="page-heading"><div><p className="eyebrow">CADASTROS</p><h1>Coletas</h1><p>Cadastre os contatos e endereços fixos de costureiras, floristas e fornecedores.</p></div><Button onClick={() => show()}><Plus size={20}/> Nova coleta</Button></header>
    {error && !open && !action && <Alert>{error}</Alert>}
    {success && <Alert tone="success">{success}</Alert>}
    <section className="panel manager-panel" aria-labelledby="pickups-title">
      <div className="manager-heading"><div><h2 id="pickups-title">Locais de coleta</h2><p>Consulte e mantenha os dados dos locais de coleta.</p></div><span className="manager-count">{items.filter(item => item.ativo).length} ativos / {items.length} cadastrados</span></div>
      <label className="manager-search"><Search size={18}/><span className="sr-only">Buscar por nome, telefone ou endereço</span><input type="search" placeholder="Buscar por nome, telefone ou endereço" value={search} onChange={e => setSearch(e.target.value)}/></label>
      {loading ? <p className="loading-page" role="status">Carregando coletas…</p> : visible.length ? <div className="table-wrap"><table><thead><tr><th>Nome</th><th>Tipo</th><th>Telefone</th><th>Endereço</th><th>Rota estabelecida</th><th>Status</th><th aria-label="Ações"/></tr></thead><tbody>{visible.map(item => <tr key={item.id}><td><strong>{item.nome}</strong></td><td>{item.tipo ? typeLabels[item.tipo] : 'Não informado'}</td><td>{item.telefone}</td><td style={{ whiteSpace: 'normal', overflowWrap: 'anywhere' }}>{item.endereco}</td><td>{item.route_template_id ? routes.find(route => route.id === item.route_template_id)?.name || 'Rota indisponível' : 'Sem vínculo'}</td><td><StatusBadge value={item.ativo ? 'ATIVO' : 'INATIVO'}/></td><td className="row-actions"><button onClick={() => setCorrecting(item)} aria-label={`Corrigir localização de ${item.nome}`} title="Corrigir localização"><MapPin/></button><button onClick={() => show(item)} aria-label={`Editar ${item.nome}`} title="Editar coleta"><Pencil/></button><button onClick={() => ask(item, 'status')} aria-label={`${item.ativo ? 'Desativar' : 'Ativar'} ${item.nome}`} title={item.ativo ? 'Desativar coleta' : 'Ativar coleta'}><Power/></button><button onClick={() => ask(item, 'delete')} aria-label={`Excluir ${item.nome}`} title="Excluir coleta"><Trash2/></button></td></tr>)}</tbody></table></div> : <Empty title={search ? 'Nenhuma coleta encontrada' : 'Nenhuma coleta cadastrada'} description={search ? 'Tente outro nome, telefone ou endereço.' : 'Cadastre o primeiro local de coleta.'}/>}
    </section>
    <Modal open={!!correcting} title="Corrigir localização da coleta" onClose={() => setCorrecting(null)}>
      {correcting && <AddressPicker key={correcting.id} label={correcting.nome} initialAddress={correcting.endereco} onSelect={() => { setSuccess('Localização salva. Disponível para futuras roteirizações.'); void load() }} />}
    </Modal>
    <Modal open={open} title={editing ? 'Editar coleta' : 'Nova coleta'} onClose={close}>
      {error && <Alert>{error}</Alert>}
      <form className="modal-form" onSubmit={save}>
        <label>Tipo<select required value={form.tipo} onChange={e => setForm({ ...form, tipo: e.target.value as PickupType | '' })}><option value="" disabled>Selecione o tipo</option><option value="COSTUREIRA">Costureira</option><option value="FLORISTA">Florista</option><option value="FORNECEDOR">Fornecedor</option></select></label>
        <label>Nome<input autoComplete="name" required minLength={2} maxLength={160} value={form.nome} onChange={e => setForm({ ...form, nome: e.target.value })}/></label>
        <label>Telefone<input type="tel" autoComplete="tel" required maxLength={40} value={form.telefone} onChange={e => setForm({ ...form, telefone: e.target.value })}/></label>
        <label>Endereço<input autoComplete="street-address" required maxLength={500} placeholder="Rua, número, complemento, bairro, cidade e UF" value={form.endereco} onChange={e => setForm({ ...form, endereco: e.target.value })}/></label>
        <label>Rota estabelecida (opcional)<select value={form.route_template_id} disabled={saving || routesLoading || !!routesError} onChange={e => setForm({ ...form, route_template_id: e.target.value })}>
          <option value="">Sem vínculo com rota</option>
          {form.route_template_id && !routes.some(route => String(route.id) === form.route_template_id) && <option value={form.route_template_id}>Rota indisponível — selecione outra ou remova o vínculo</option>}
          {routes.map(route => <option key={route.id} value={route.id}>{route.name}{route.active ? '' : ' (inativa)'}</option>)}
        </select></label>
        {routesLoading && <p role="status">Carregando rotas estabelecidas…</p>}
        {routesError && <><Alert>{routesError}</Alert><Button type="button" variant="secondary" onClick={() => setRoutesRefresh(value => value + 1)}>Tentar carregar rotas novamente</Button></>}
        {!routesLoading && !routesError && !routes.length && <p>Nenhuma rota estabelecida cadastrada.</p>}
        <footer><Button type="button" variant="ghost" disabled={saving} onClick={close}>Cancelar</Button><Button type="submit" loading={saving} disabled={routesLoading || !!routesError}>Salvar coleta</Button></footer>
      </form>
    </Modal>
    <Modal open={!!action} title={action?.kind === 'delete' ? 'Excluir coleta' : action?.item.ativo ? 'Desativar coleta' : 'Ativar coleta'} onClose={closeAction}>
      {error && <Alert>{error}</Alert>}
      <div className="modal-form">
        <p>{action?.kind === 'delete' ? <>Excluir o cadastro de <strong>{action.item.nome}</strong>? Esta ação é permanente.</> : <>{action?.item.ativo ? 'Desativar' : 'Ativar'} o cadastro de <strong>{action?.item.nome}</strong>? O cadastro continuará disponível para consulta e edição.</>}</p>
        <footer><Button variant="ghost" disabled={saving} onClick={closeAction}>Cancelar</Button><Button variant={action?.kind === 'delete' ? 'danger' : 'primary'} loading={saving} onClick={confirmAction}>{action?.kind === 'delete' ? 'Excluir coleta' : action?.item.ativo ? 'Desativar coleta' : 'Ativar coleta'}</Button></footer>
      </div>
    </Modal>
  </div>
}
