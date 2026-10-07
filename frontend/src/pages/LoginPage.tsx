import { ArrowRight, Eye, EyeOff, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { Alert, Button } from '../components/UI'
import { useAuth } from '../hooks/useAuth'

export function LoginPage() {
  const {user,login}=useAuth(); const navigate=useNavigate(); const [email,setEmail]=useState(''); const [senha,setSenha]=useState(''); const [show,setShow]=useState(false); const [error,setError]=useState(''); const [loading,setLoading]=useState(false)
  if(user) return <Navigate to={user.role==='ADMIN'?'/admin':'/motorista'} replace/>
  async function submit(e:FormEvent){e.preventDefault();setError('');setLoading(true);try{const logged=await login(email,senha);navigate(logged.role==='ADMIN'?'/admin':'/motorista')}catch(err){setError(err instanceof Error?err.message:'Falha no acesso')}finally{setLoading(false)}}
  return <main className="login-page">
    <section className="login-story" aria-hidden="true"><div className="route-line"><span>01</span><span>02</span><span>03</span></div><div><p className="eyebrow">OPERAÇÃO EM MOVIMENTO</p><h1>Controle simples.<br/>Rotas mais seguras.</h1><p>Checklists, viagens e ocorrências em uma única visão operacional.</p></div><div className="login-proof"><ShieldCheck/><span>Fluxo rastreável do pátio ao retorno</span></div></section>
    <section className="login-panel"><div className="login-card"><Brand/><div><p className="eyebrow">BEM-VINDO</p><h2>Entre na sua conta</h2><p>Use suas credenciais para acessar o controle de frota.</p></div>{error&&<Alert>{error}</Alert>}<form onSubmit={submit}>
      <label>E-mail<input type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="nome@modial.com.br" required autoFocus/></label>
      <label>Senha<span className="password-field"><input type={show?'text':'password'} autoComplete="current-password" value={senha} onChange={e=>setSenha(e.target.value)} placeholder="Sua senha" required/><button type="button" onClick={()=>setShow(!show)} aria-label={show?'Ocultar senha':'Mostrar senha'}>{show?<EyeOff/>:<Eye/>}</button></span></label>
      <Button type="submit" loading={loading}>Entrar <ArrowRight size={20}/></Button>
    </form><small className="secure-note">Ambiente interno • acesso protegido</small></div></section>
  </main>
}

