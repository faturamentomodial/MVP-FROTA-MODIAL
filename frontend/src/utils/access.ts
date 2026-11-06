import type { Role } from '../types'

export const roleLabels: Record<Role, string> = { MASTER: 'Master', ADMIN: 'Gestor', COMPRAS: 'Compras', MOTORISTA: 'Motorista' }
export function homeFor(role: Role) {
  return role === 'MOTORISTA' ? '/motorista' : role === 'COMPRAS' ? '/admin/tarefas' : '/admin'
}
export function canAccess(role: Role, path: string) {
  if (role === 'ADMIN' || role === 'MASTER') return true
  return role === 'COMPRAS' && ['/admin/tarefas', '/admin/rastreamento', '/admin/viagens'].some(base => path === base || path.startsWith(`${base}/`))
}
