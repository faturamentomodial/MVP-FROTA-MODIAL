import { useEffect, useState } from 'react'
import { Alert, Button } from './UI'
import { api } from '../services/api'
import { LocationEditor, type GeocodingResult } from './LocationEditor'
import type { Point } from '../types/routePlans'

export function AddressPicker({label,onSelect,initialAddress=''}:{label:string;onSelect:(point:Point)=>void;initialAddress?:string}) {
  const [query,setQuery]=useState(initialAddress), [result,setResult]=useState<GeocodingResult>({candidates:[]})
  const [message,setMessage]=useState(''), [busy,setBusy]=useState(false), [correcting,setCorrecting]=useState(false)
  const suggestions = result.suggestions?.length ? result.suggestions : result.candidates
  useEffect(()=>{setQuery(initialAddress);setResult({candidates:[]});setMessage('');setCorrecting(false)},[initialAddress])
  async function search(){
    setBusy(true);setMessage('');setResult({candidates:[]})
    try {
      const found=await api<GeocodingResult>(`/route-plans/geocode?address=${encodeURIComponent(query)}`)
      setResult(found)
      if(found.selected){onSelect({address:query,latitude:found.selected.latitude,longitude:found.selected.longitude});setMessage('Localização confiável carregada. Confira o destino antes de salvar a rota.')}
      else {setMessage(found.status==='conflict'?'Provedores apresentam localizações conflitantes. Confirme o local no mapa.':found.status==='approximate'?'Localização aproximada: rua encontrada, número não confirmado. Confirme o local no mapa.':'Sem correspondência confiável. Confirme manualmente o local no mapa.');setCorrecting(true)}
      if(found.errors?.length)setMessage(previous=>previous+' Um provedor está indisponível ou aguardando limite de uso.')
    } catch(e){setMessage((e as Error).message);setCorrecting(true)}finally{setBusy(false)}
  }
  return <div><label>{label}<input disabled={busy} value={query} onChange={e=>{setQuery(e.target.value);setResult({candidates:[]});setCorrecting(false)}} placeholder="Rua, número, bairro, cidade, UF e CEP"/></label>
    <Button type="button" variant="secondary" disabled={busy||query.trim().length<5} loading={busy} onClick={search}>Buscar endereço</Button>
    <Button type="button" variant="secondary" disabled={busy||query.trim().length<5} onClick={()=>setCorrecting(v=>!v)}>Corrigir localização</Button>
    {message&&<Alert tone="info">{message}</Alert>}
    {suggestions.length>0&&<ul>{suggestions.map((p,i)=><li key={i}>{p.provider}: {p.address} — {p.precision==='building'?'Número localizado':p.precision==='street'?'Rua aproximada':'Não verificado'} ({p.latitude.toFixed(5)}, {p.longitude.toFixed(5)}) {p.datasource?.attribution} {p.datasource?.license}</li>)}</ul>}
    <small>Dados: <a href="https://www.geoapify.com/">Geoapify</a> | © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors (ODbL)</a>.</small>
    {correcting&&<LocationEditor address={query} candidates={suggestions} currentPoint={result.selected} onConfirmed={p=>{onSelect(p);setCorrecting(false);setResult({...result,selected:p});setMessage('Localização confirmada e salva para futuras roteirizações.')}}/>}
  </div>
}
