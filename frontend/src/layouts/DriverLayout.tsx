import { LogOut } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { useAuth } from '../hooks/useAuth'

export function DriverLayout() {
  const { logout } = useAuth(); const navigate = useNavigate()
  return <div className="driver-shell">
    <header className="driver-header"><Brand compact/><button className="icon-button" aria-label="Sair" onClick={()=>{logout();navigate('/login')}}><LogOut size={20}/></button></header>
    <nav className="driver-task-nav" aria-label="Navegação do motorista"><NavLink to="/motorista" end>Minha rota</NavLink><NavLink to="/motorista/tarefas">Tarefas</NavLink><NavLink to="/motorista/configuracoes">Configura??es</NavLink></nav>
    <main id="main" className="driver-main"><Outlet/></main>
    <footer className="driver-footer">MODIAL • SUA MELHOR COMPRA</footer>
  </div>
}

