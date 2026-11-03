import { Alert } from './UI'

const days: Record<string, string> = {
  '1': 'Segunda-feira', '2': 'Segunda-feira',
  '3': 'Terça-feira', '4': 'Terça-feira',
  '5': 'Quarta-feira', '6': 'Quarta-feira',
  '7': 'Quinta-feira', '8': 'Quinta-feira',
  '9': 'Sexta-feira', '0': 'Sexta-feira',
}

export function restrictionPreview(plate: string): string | null {
  const normalized = plate.replace(/[- ]/g, '').toUpperCase()
  return /^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$/.test(normalized) ? days[normalized.slice(-1)] : null
}

export function VehicleRestriction({day}: {day: string | null}) {
  return <Alert tone="info"><div><strong>Rodízio municipal de São Paulo: {day || 'não identificado; confira a placa'}{day && ' · 7h às 10h e 17h às 20h'}.</strong><p>Regra semanal no Centro Expandido e vias limítrofes, exceto feriados. Verifique isenções e suspensões da CET antes da saída. Caminhões também possuem outras restrições de circulação.</p><a href="https://ssl.cetsp.com.br/consultas/rodizio-municipal/como-funciona.aspx" target="_blank" rel="noreferrer">Consultar regra na CET</a></div></Alert>
}
