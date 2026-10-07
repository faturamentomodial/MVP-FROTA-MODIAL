import type { Attachment, AuthResponse } from '../types'

const API_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '')

// O backend retorna caminhos /uploads; as fotos continuam no servidor da API.
export function attachmentUrl(path: string): string {
  if (!path.startsWith('/uploads/')) return path
  return new URL(path, new URL(API_URL, window.location.origin)).href
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('fleet_token')
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_URL}${path}`, { ...options, headers })
  if (response.status === 401 && path !== '/auth/login') {
    localStorage.removeItem('fleet_token')
    localStorage.removeItem('fleet_user')
    window.location.assign('/login')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Não foi possível concluir a operação' }))
    const detail = Array.isArray(body.detail) ? body.detail.map((x: {msg:string}) => x.msg).join(', ') : body.detail
    throw new ApiError(response.status, detail || 'Erro inesperado')
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

export const authApi = {
  login: (email: string, senha: string) => api<AuthResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email, senha }) }),
}

export async function uploadImage(file: File): Promise<Attachment> {
  const form = new FormData()
  form.append('file', file)
  return api<Attachment>('/uploads', { method: 'POST', body: form })
}
