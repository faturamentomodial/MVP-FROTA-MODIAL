import { ArrowRight, ClipboardCheck, Pencil, Plus, Power, Search, ShieldCheck, Users } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Alert, Button, Empty, Modal, StatusBadge } from '../../components/UI'
import { useAuth } from '../../hooks/useAuth'
import { api } from '../../services/api'
import type { User } from '../../types'

const empty = { nome: '', email: '', senha: '', confirmar: '', ativo: true }

export function SettingsPage() {
  const { user, updateUser } = useAuth()
  const [items, setItems] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<User>()
  const [statusTarget, setStatusTarget] = useState<User>()
  const [form, setForm] = useState(empty)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function load() {
    setLoading(true)
    try { setItems(await api<User[]>('/users')) }
    catch (e) { setError((e as Error).message) }
    finally { setLoading(false) }
  }
  useEffect(() => { void load() }, [])

  function show(item?: User) {
    setEditing(item)
    setForm(item ? { nome: item.nome, email: item.email, senha: '', confirmar: '', ativo: item.ativo } : empty)
    setError(''); setSuccess(''); setOpen(true)
  }

  async function save(e: FormEvent) {
    e.preventDefault(); setError('')
    if (form.senha !== form.confirmar) { setError('As senhas não coincidem.'); return }
    setSaving(true)
    try {
      const result = await api<User>(editing ? `/users/${editing.id}` : '/users', {
        method: editing ? 'PUT' : 'POST',
        body: JSON.stringify({ nome: form.nome.trim(), email: form.email.trim(), ativo: form.ativo, senha: form.senha || undefined }),
      })
      if (result.id === user?.id) updateUser(result)
      setOpen(false); setSuccess(editing ? 'Dados do gestor atualizados.' : 'Gestor criado. O acesso já pode ser feito com o e-mail e a senha cadastrados.')
      await load()
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  async function toggle() {
    if (!statusTarget) return
    setSaving(true); setError(''); setSuccess('')
    try {
      await api(`/users/${statusTarget.id}/status`, { method: 'PATCH', body: JSON.stringify({ ativo: !statusTarget.ativo }) })
      setSuccess(statusTarget.ativo ? 'Acesso do gestor desativado.' : 'Acesso do gestor ativado.')
      setStatusTarget(undefined); await load()
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }

  const visible = items.filter(item => `${item.nome} ${item.email}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
  return <div className="admin-page">
    <header className="page-heading"><div><p className="eyebrow">ADMINISTRAÇÃO</p><h1>Configurações</h1><p>Gerencie os acessos de gestores e as configurações da operação.</p></div><Button onClick={() => show()}><Plus size={20}/> Novo gestor</Button></header>
    {error && !open && !statusTarget && <Alert>{error}</Alert>}
    {success && <Alert tone="success">{success}</Alert>}

    <section className="panel manager-panel" aria-labelledby="managers-title">
      <div className="manager-heading"><div><h2 id="managers-title"><ShieldCheck size={22}/> Usuários gestores</h2><p>Cada gestor tem seu próprio login e acesso completo ao painel.</p></div><span className="manager-count">{items.filter(item => item.ativo).length} ativos / {items.length} cadastrados</span></div>
      <label className="manager-search"><Search size={18}/><span className="sr-only">Buscar gestor por nome ou e-mail</span><input type="search" placeholder="Buscar por nome ou e-mail" value={search} onChange={e => setSearch(e.target.value)}/></label>
      {loading ? <p className="loading-page" role="status">Carregando gestores…</p> : visible.length ? <div className="table-wrap"><table><thead><tr><th>Nome</th><th>E-mail de acesso</th><th>Perfil</th><th>Status</th><th aria-label="Ações"/></tr></thead><tbody>{visible.map(item => <tr key={item.id}>
        <td><strong>{item.nome}</strong>{item.id === user?.id && <small className="manager-self">Seu acesso</small>}</td><td>{item.email}</td><td>Gestor</td><td><StatusBadge value={item.ativo ? 'ATIVO' : 'INATIVO'}/></td>
        <td className="row-actions"><button onClick={() => show(item)} aria-label={`Editar ${item.nome}`} title="Editar dados ou trocar senha"><Pencil/></button><button disabled={item.id === user?.id} onClick={() => { setStatusTarget(item); setError(''); setSuccess('') }} aria-label={`${item.ativo ? 'Desativar' : 'Ativar'} ${item.nome}`} title={item.id === user?.id ? 'Seu próprio acesso não pode ser desativado' : item.ativo ? 'Desativar acesso' : 'Ativar acesso'}><Power/></button></td>
      </tr>)}</tbody></table></div> : <Empty title={search ? 'Nenhum gestor encontrado' : 'Nenhum gestor cadastrado'} description={search ? 'Tente outro nome ou e-mail.' : 'Crie um gestor para dar acesso ao painel.'}/>}
      <p className="manager-note">Contas inativas não podem acessar o sistema. Seu próprio acesso não pode ser desativado.</p>
    </section>

    <div className="settings-shortcuts">
      <section className="panel settings-shortcut"><ClipboardCheck/><h2>Itens do checklist</h2><p>Defina as verificações, a ordem e os itens obrigatórios antes de cada viagem.</p><Link to="/admin/checklist">Configurar checklist <ArrowRight size={18}/></Link></section>
      <section className="panel settings-shortcut"><Users/><h2>Acessos de motoristas</h2><p>Cadastre motoristas e gerencie seus dados, senhas e acesso ao fluxo de viagens.</p><Link to="/admin/motoristas">Gerenciar motoristas <ArrowRight size={18}/></Link></section>
      <section className="panel settings-shortcut"><ShieldCheck/><h2>Minha conta</h2><p>{user?.nome}<br/>{user?.email}</p><button className="text-button" onClick={() => show(user || undefined)}>Editar meus dados e senha <ArrowRight size={18}/></button></section>
    </div>

    <Modal open={open} onClose={() => { if (!saving) { setOpen(false); setError('') } }} title={editing ? 'Editar gestor' : 'Novo gestor'}>
      {error && <Alert>{error}</Alert>}
      <form className="modal-form" onSubmit={save}>
        <p>Perfil: <strong>Gestor</strong>. Acesso completo aos cadastros, viagens, ocorrências e configurações.</p>
        <label>Nome completo<input autoComplete="name" value={form.nome} onChange={e => setForm({ ...form, nome: e.target.value })} required minLength={2} maxLength={160}/></label>
        <label>E-mail de acesso<input type="email" autoComplete="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required maxLength={255}/></label>
        <label>{editing ? 'Nova senha' : 'Senha'}{editing && <small>Deixe em branco para manter a senha atual.</small>}<input type="password" autoComplete="new-password" value={form.senha} onChange={e => setForm({ ...form, senha: e.target.value })} required={!editing} minLength={8} maxLength={128}/></label>
        <label>Confirmar senha<input type="password" autoComplete="new-password" value={form.confirmar} onChange={e => setForm({ ...form, confirmar: e.target.value })} required={!editing || !!form.senha} maxLength={128}/></label>
        <small>Use pelo menos 8 caracteres. Informe a senha ao gestor para o primeiro acesso.</small>
        <label className="switch"><input type="checkbox" checked={form.ativo} disabled={editing?.id === user?.id} onChange={e => setForm({ ...form, ativo: e.target.checked })}/><span/>Acesso ativo</label>
        <footer><Button type="button" variant="ghost" disabled={saving} onClick={() => { setOpen(false); setError('') }}>Cancelar</Button><Button type="submit" loading={saving}>Salvar gestor</Button></footer>
      </form>
    </Modal>
    <Modal open={!!statusTarget} title={statusTarget?.ativo ? 'Desativar acesso' : 'Ativar acesso'} onClose={() => { if (!saving) { setStatusTarget(undefined); setError('') } }}>
      {error && <Alert>{error}</Alert>}
      <div className="modal-form"><p>{statusTarget?.ativo ? 'Ao desativar' : 'Ao ativar'} o acesso de <strong>{statusTarget?.nome}</strong>, {statusTarget?.ativo ? 'essa pessoa deixará de acessar o sistema, inclusive com uma sessão já aberta.' : 'essa pessoa poderá entrar usando o e-mail e a senha cadastrados.'}</p><footer><Button variant="ghost" disabled={saving} onClick={() => { setStatusTarget(undefined); setError('') }}>Cancelar</Button><Button variant={statusTarget?.ativo ? 'danger' : 'primary'} loading={saving} onClick={toggle}>{statusTarget?.ativo ? 'Desativar' : 'Ativar'} acesso</Button></footer></div>
    </Modal>
  </div>
}
