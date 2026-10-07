export const formatKm = (value?: number | null) => `${new Intl.NumberFormat('pt-BR').format(value || 0)} km`
export const formatDate = (value?: string | null) => value ? new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Sao_Paulo' }).format(new Date(value)) : '—'
export const labelEnum = (value: string) => value.replaceAll('_', ' ').toLocaleLowerCase('pt-BR').replace(/(^|\s)\S/g, letter => letter.toUpperCase())
export const formatCpf = (value: string) => value.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4')

