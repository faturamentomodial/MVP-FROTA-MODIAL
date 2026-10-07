import { ArrowLeft, ArrowRight, Boxes, FileText, Plus, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Alert, Button } from '../../components/UI'
import { api } from '../../services/api'
import type { Trip } from '../../types'

type NoteForm = { key: number; numero_nota: string; volumes: string }
let nextKey = 1
const emptyNote = (): NoteForm => ({ key: nextKey++, numero_nota: '', volumes: '' })

export function CargoPage() {
  const { tripId } = useParams()
  const navigate = useNavigate()
  const [trip, setTrip] = useState<Trip>()
  const [notes, setNotes] = useState<NoteForm[]>([emptyNote()])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api<Trip>(`/trips/${tripId}`).then(current => {
      setTrip(current)
      if (current.notas.length) {
        setNotes(current.notas.map(note => ({ key: nextKey++, numero_nota: note.numero_nota, volumes: String(note.volumes) })))
      }
    }).catch(e => setError(e.message))
  }, [tripId])

  const totalVolumes = useMemo(() => notes.reduce((total, note) => total + (Number(note.volumes) || 0), 0), [notes])

  function update(key: number, field: 'numero_nota' | 'volumes', value: string) {
    setNotes(current => current.map(note => note.key === key ? { ...note, [field]: value } : note))
  }

  function remove(key: number) {
    setNotes(current => current.length === 1 ? current : current.filter(note => note.key !== key))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    const numbers = notes.map(note => note.numero_nota.trim().toLocaleLowerCase('pt-BR'))
    if (new Set(numbers).size !== numbers.length) {
      setError('Cada nota deve ser informada apenas uma vez.')
      return
    }
    setLoading(true)
    try {
      await api<Trip>(`/trips/${tripId}/cargo`, {
        method: 'PUT',
        body: JSON.stringify({ notas: notes.map(note => ({ numero_nota: note.numero_nota.trim(), volumes: Number(note.volumes) })) }),
      })
      navigate(trip?.checklist_id ? '/motorista' : `/motorista/checklist/${tripId}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao salvar a carga')
    } finally {
      setLoading(false)
    }
  }

  return <div className="driver-page cargo-page fade-in">
    <button className="back-link" onClick={() => navigate('/motorista')}><ArrowLeft/> Voltar</button>
    <p className="step-label">ETAPA 2 DE 4</p>
    <h1>Notas e volumes</h1>
    <p className="lead">Informe as notas fiscais e quantos volumes foram carregados em cada uma.</p>
    {trip && <div className="checklist-meta"><strong>{trip.vehicle_plate}</strong><span>{notes.length} {notes.length === 1 ? 'nota' : 'notas'}</span></div>}
    {error && <Alert>{error}</Alert>}
    <form className="cargo-form" onSubmit={submit}>
      <div className="cargo-list">
        {notes.map((note, index) => <fieldset className="cargo-card" key={note.key}>
          <legend><span><FileText/> NOTA {String(index + 1).padStart(2, '0')}</span>{notes.length > 1 && <button type="button" onClick={() => remove(note.key)} aria-label={`Remover nota ${index + 1}`}><Trash2/></button>}</legend>
          <div className="cargo-fields">
            <label>Número da nota<input autoFocus={index === notes.length - 1 && !note.numero_nota} type="text" inputMode="numeric" autoComplete="off" placeholder="Ex.: 128745" value={note.numero_nota} onChange={e => update(note.key, 'numero_nota', e.target.value)} required/></label>
            <label>Volumes<input type="number" inputMode="numeric" min="1" max="999999" placeholder="0" value={note.volumes} onChange={e => update(note.key, 'volumes', e.target.value)} required/></label>
          </div>
        </fieldset>)}
      </div>
      <Button type="button" variant="secondary" className="button--full cargo-add" onClick={() => setNotes(current => [...current, emptyNote()])}><Plus/> Adicionar outra nota</Button>
      <div className="cargo-total" aria-live="polite"><span><Boxes/> Total carregado</span><strong>{totalVolumes} <small>{totalVolumes === 1 ? 'volume' : 'volumes'}</small></strong></div>
      <Button type="submit" loading={loading} className="button--full button--xl">Continuar <ArrowRight/></Button>
    </form>
  </div>
}
