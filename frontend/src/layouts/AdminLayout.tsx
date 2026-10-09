import { ClipboardCheck, Gauge, LogOut, MapPin, Menu, Route, Settings2, TriangleAlert, Truck, Users, X } from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { useAuth } from '../hooks/useAuth'

const links = [
  {to:'/admin', label:'Visão geral', icon:Gauge, end:true},
  {to:'/admin/viagens', label:'Viagens', icon:Route},
  {to:'/admin/rastreamento', label:'Rastreamento', icon:MapPin},
  {to:'/admin/ocorrencias', label:'Ocorrências', icon:TriangleAlert},
  {to:'/admin/motoristas', label:'Motoristas', icon:Users},
  {to:'/admin/veiculos', label:'Veículos', icon:Truck},
  {to:'/admin/checklist', label:'Checklist', icon:ClipboardCheck},
  {to:'/admin/configuracoes', label:'Configurações', icon:Settings2},
]

export function AdminLayout() {
  const [open,setOpen]=useState(false); const {user,logout}=useAuth(); const navigate=useNavigate()
  return <div className="admin-shell">
    <aside className={`sidebar ${open?'sidebar--open':''}`}>
      <div className="sidebar-brand"><Brand/><button className="icon-button sidebar-close" onClick={()=>setOpen(false)} aria-label="Fechar menu"><X/></button></div>
      <nav aria-label="Navegação principal">{links.map(({to,label,icon:Icon,end})=><NavLink key={to} to={to} end={end} onClick={()=>setOpen(false)}><Icon size={20}/>{label}</NavLink>)}</nav>
      <div className="sidebar-user"><span>{user?.nome}</span><small>Gestor</small><button onClick={()=>{logout();navigate('/login')}}><LogOut size={17}/> Sair</button></div>
    </aside>
    <div className="admin-content">
      <header className="admin-topbar"><button className="icon-button menu-button" onClick={()=>setOpen(true)} aria-label="Abrir menu"><Menu/></button><div><strong>Controle de Frota</strong><span>Operação Modial</span></div><Link className="icon-button" to="/admin/configuracoes" aria-label="Abrir configurações"><Settings2 size={19}/></Link></header>
      <main id="main" className="admin-main"><Outlet/></main>
    </div>
    {open && <div className="sidebar-scrim" onClick={()=>setOpen(false)}/>} 
  </div>
}
