import { Pencil, Plus, Search } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Alert, Button, Empty, Modal } from '../../components/UI'
import { api } from '../../services/api'

type Pickup = { id: number; nome: string; telefone: string; endereco: string }
const empty = { nome: '', telefone: '', endereco: '' }

export function PickupsPage() {
  const [items, setItems] = useState<Pickup[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Pickup>()
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

  function show(item?: Pickup) {
    setEditing(item)
    setForm(item ? { nome: item.nome, telefone: item.telefone, endereco: item.endereco } : empty)
    setError(''); setSuccess(''); setOpen(true)
  }
  function close() { if (!saving) { setOpen(false); setError('') } }

  async function save(e: FormEvent) {
    e.preventDefault(); setError('')
    const payload = { nome: form.nome.trim(), telefone: form.telefone.trim(), endereco: form.endereco.trim() }
    if (payload.nome.length < 2 || !payload.telefone || !payload.endereco) {
      setError('Informe o nome com pelo menos 2 caracteres, telefone e endereço.'); return
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

  const visible = items.filter(item => `${item.nome} ${item.telefone} ${item.endereco}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
  return <div className="admin-page">
    <header className="page-heading"><div><p className="eyebrow">CADASTROS</p><h1>Coletas</h1><p>Cadastre os contatos e endereços fixos de costureiras e fornecedores.</p></div><Button onClick={() => show()}><Plus size={20}/> Nova coleta</Button></header>
    {error && !open && <Alert>{error}</Alert>}
    {success && <Alert tone="success">{success}</Alert>}
    <section className="panel manager-panel" aria-labelledby="pickups-title">
      <div className="manager-heading"><div><h2 id="pickups-title">Locais de coleta</h2><p>Consulte e mantenha os dados dos locais de coleta.</p></div><span className="manager-count">{items.length} cadastrados</span></div>
      <label className="manager-search"><Search size={18}/><span className="sr-only">Buscar por nome, telefone ou endereço</span><input type="search" placeholder="Buscar por nome, telefone ou endereço" value={search} onChange={e => setSearch(e.target.value)}/></label>
      {loading ? <p className="loading-page" role="status">Carregando coletas…</p> : visible.length ? <div className="table-wrap"><table><thead><tr><th>Nome</th><th>Telefone</th><th>Endereço</th><th aria-label="Ações"/></tr></thead><tbody>{visible.map(item => <tr key={item.id}><td><strong>{item.nome}</strong></td><td>{item.telefone}</td><td style={{ whiteSpace: 'normal', overflowWrap: 'anywhere' }}>{item.endereco}</td><td className="row-actions"><button onClick={() => show(item)} aria-label={`Editar ${item.nome}`} title="Editar coleta"><Pencil/></button></td></tr>)}</tbody></table></div> : <Empty title={search ? 'Nenhuma coleta encontrada' : 'Nenhuma coleta cadastrada'} description={search ? 'Tente outro nome, telefone ou endereço.' : 'Cadastre o primeiro local de coleta.'}/>}
    </section>
    <Modal open={open} title={editing ? 'Editar coleta' : 'Nova coleta'} onClose={close}>
      {error && <Alert>{error}</Alert>}
      <form className="modal-form" onSubmit={save}>
        <label>Nome<input autoComplete="name" required minLength={2} maxLength={160} value={form.nome} onChange={e => setForm({ ...form, nome: e.target.value })}/></label>
        <label>Telefone<input type="tel" autoComplete="tel" required maxLength={40} value={form.telefone} onChange={e => setForm({ ...form, telefone: e.target.value })}/></label>
        <label>Endereço<input autoComplete="street-address" required maxLength={500} placeholder="Rua, número, complemento, bairro, cidade e UF" value={form.endereco} onChange={e => setForm({ ...form, endereco: e.target.value })}/></label>
        <footer><Button type="button" variant="ghost" disabled={saving} onClick={close}>Cancelar</Button><Button type="submit" loading={saving}>Salvar coleta</Button></footer>
      </form>
    </Modal>
  </div>
}
