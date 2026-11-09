import { useEffect, useState } from 'react'
import { Alert, Button } from './UI'
import { api } from '../services/api'
import type { GeocodingResult } from './LocationEditor'
import type { Point } from '../types/routePlans'

export function AddressPicker({label,onSelect,initialAddress=''}:{label:string;onSelect:(point:Point)=>void;initialAddress?:string}) {
  const [query,setQuery]=useState(initialAddress)
  const [message,setMessage]=useState(''), [busy,setBusy]=useState(false)
  useEffect(()=>{setQuery(initialAddress);setMessage('')},[initialAddress])
  async function search(){
    setBusy(true);setMessage('')
    try {
      const found=await api<GeocodingResult>(`/route-plans/geocode?address=${encodeURIComponent(query)}`)
      const point=found.selected || found.candidates.find(p => p.precision === 'building' || p.precision === 'street') || found.candidates.find(p => p.street_found)
      if(point){
        onSelect({address:query,latitude:point.latitude,longitude:point.longitude})
        setMessage(point.manual_confirmed || point.precision === 'building' ? 'Localização carregada.' : 'Localização carregada pela rua. O provedor não identificou o número do imóvel.')
      } else if(found.errors?.length){
        setMessage('O provedor está indisponível ou aguardando limite de uso. Tente novamente em instantes.')
      } else {
        setMessage('Endereço não encontrado. Inclua rua, cidade e UF ou CEP e busque novamente.')
      }
    } catch(e){setMessage((e as Error).message)}finally{setBusy(false)}
  }
  return <div><label>{label}<input disabled={busy} value={query} onChange={e=>{setQuery(e.target.value);setMessage('')}} placeholder="Rua, número, bairro, cidade, UF e CEP"/></label>
    <Button type="button" variant="secondary" disabled={busy||query.trim().length<5} loading={busy} onClick={search}>Buscar endereço</Button>
    {message&&<Alert tone="info">{message}</Alert>}
    <small>Dados: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors (ODbL)</a>.</small>
  </div>
}
