import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { connectRealtime } from '../services/realtime'
import { useRealtimeEffect } from './useRealtimeEffect'
import { api, authApi } from '../services/api'
import type { User } from '../types'

interface AuthContextValue { user: User | null; login: (email:string, senha:string)=>Promise<User>; logout: ()=>void; updateUser: (user:User)=>void }
const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: {children: ReactNode}) {
  const [user, setUser] = useState<User | null>(() => {
    try { return JSON.parse(localStorage.getItem('fleet_user') || 'null') } catch { return null }
  })
  const token = localStorage.getItem('fleet_token')
  useRealtimeEffect(['users'], () => {
    if (!user || !token) return
    const controller = new AbortController()
    api<User>('/auth/me', { signal: controller.signal }).then(updated => {
      if (controller.signal.aborted) return
      localStorage.setItem('fleet_user', JSON.stringify(updated))
      setUser(previous => JSON.stringify(previous) === JSON.stringify(updated) ? previous : updated)
    }).catch(() => { /* Normal API authentication handles revoked credentials. */ })
    return () => controller.abort()
  }, [user?.id, token])
  useEffect(() => {
    if (!user || !token) return
    return connectRealtime(token, () => {
      localStorage.removeItem('fleet_token')
      localStorage.removeItem('fleet_user')
      setUser(null)
    })
  }, [user?.id, token])
  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key === 'fleet_user' || event.key === 'fleet_token') {
        try { setUser(JSON.parse(localStorage.getItem('fleet_user') || 'null')) }
        catch { setUser(null) }
      }
    }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [])
  const value = useMemo(() => ({
    user,
    updateUser: (updated: User) => {
      localStorage.setItem('fleet_user', JSON.stringify(updated))
      setUser(updated)
    },
    login: async (email: string, senha: string) => {
      const response = await authApi.login(email, senha)
      localStorage.setItem('fleet_token', response.access_token)
      localStorage.setItem('fleet_user', JSON.stringify(response.user))
      setUser(response.user)
      return response.user
    },
    logout: () => {
      localStorage.removeItem('fleet_token')
      localStorage.removeItem('fleet_user')
      setUser(null)
    },
  }), [user])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth deve estar dentro de AuthProvider')
  return context
}
