import { ClipboardCheck, Gauge, LogOut, MapPin, Menu, PanelLeftClose, PanelLeftOpen, Route, Settings2, TriangleAlert, Truck, Users, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { useAuth } from '../hooks/useAuth'

import { canAccess, roleLabels } from '../utils/access'
import './AdminLayout.css'

const links = [
  {to:'/admin/tarefas', label:'Central de Tarefas', icon:ClipboardCheck},
  {to:'/admin', label:'Visão geral', icon:Gauge, end:true},
  {to:'/admin/rotas', label:'Rotas', icon:Route},
  {to:'/admin/mapa-rotas', label:'Mapa rotas', icon:MapPin},
  {to:'/admin/viagens', label:'Viagens', icon:Route},
  {to:'/admin/rastreamento', label:'Rastreamento', icon:MapPin},
  {to:'/admin/ocorrencias', label:'Ocorrências', icon:TriangleAlert},
  {to:'/admin/motoristas', label:'Motoristas', icon:Users},
  {to:'/admin/veiculos', label:'Veículos', icon:Truck},
  {to:'/admin/coletas', label:'Coletas', icon:MapPin},
  {to:'/admin/checklist', label:'Checklist', icon:ClipboardCheck},
  {to:'/admin/configuracoes', label:'Configurações', icon:Settings2},
]

export function AdminLayout() {
  const [open,setOpen]=useState(false); const {user,logout}=useAuth(); const navigate=useNavigate()
  const [collapsed,setCollapsed]=useState(()=>{
    try{return localStorage.getItem('fleet_sidebar_collapsed')==='true'}catch{return false}
  })
  useEffect(()=>{
    try{localStorage.setItem('fleet_sidebar_collapsed',String(collapsed))}catch{/* Navigation remains available without browser storage. */}
  },[collapsed])
  return <div className={`admin-shell ${collapsed?'admin-shell--collapsed':''}`}>
    <aside id="admin-sidebar" className={`sidebar ${open?'sidebar--open':''}`}>
      <div className="sidebar-brand"><Brand/><button className="icon-button sidebar-close" onClick={()=>setOpen(false)} aria-label="Fechar menu"><X/></button></div>
      <nav aria-label="Navegação principal">{links.filter(link => user && canAccess(user.role, link.to)).map(({to,label,icon:Icon,end})=><NavLink key={to} to={to} end={end} onClick={()=>setOpen(false)} aria-label={label} title={collapsed?label:undefined}><Icon size={20} aria-hidden="true"/><span className="sidebar-link-label">{label}</span></NavLink>)}</nav>
      <div className="sidebar-user"><div className="sidebar-user-details"><span>{user?.nome}</span><small>{user && roleLabels[user.role]}</small></div><button aria-label="Sair" title={collapsed?'Sair':undefined} onClick={()=>{logout();navigate('/login')}}><LogOut size={17} aria-hidden="true"/><span className="sidebar-link-label">Sair</span></button></div>
    </aside>
    <div className="admin-content">
      <header className="admin-topbar"><button className="icon-button menu-button" onClick={()=>setOpen(true)} aria-label="Abrir menu" aria-expanded={open} aria-controls="admin-sidebar"><Menu/></button><button className="icon-button sidebar-toggle" onClick={()=>setCollapsed(value=>!value)} aria-label={collapsed?'Expandir menu lateral':'Recolher menu lateral'} title={collapsed?'Expandir menu lateral':'Recolher menu lateral'} aria-expanded={!collapsed} aria-controls="admin-sidebar">{collapsed?<PanelLeftOpen size={21}/>:<PanelLeftClose size={21}/>}</button><div><strong>Controle de Frota</strong><span>Operação Modial</span></div>{user?.role === 'ADMIN' && <Link className="icon-button" to="/admin/configuracoes" aria-label="Abrir configurações"><Settings2 size={19}/></Link>}</header>
      <main id="main" className="admin-main"><Outlet/></main>
    </div>
    {open && <div className="sidebar-scrim" onClick={()=>setOpen(false)}/>} 
  </div>
}
