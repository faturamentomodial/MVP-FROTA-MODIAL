import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { Alert, Button } from './UI'

export function VehicleTrackingLink({vehicleId}:{vehicleId:number}) {
  const [tracker,setTracker]=useState('');const[active,setActive]=useState(true);const[loading,setLoading]=useState(true);const[error,setError]=useState('');const[saved,setSaved]=useState(false);const[ready,setReady]=useState(false)
  useEffect(()=>{let live=true;api<{items:{vehicle_id:number;tracker_id:string|null;tracking_active:boolean}[]}>('/tracking').then(data=>{if(!live)return;const item=data.items.find(v=>v.vehicle_id===vehicleId);setTracker(item?.tracker_id||'');setActive(item?.tracker_id?item.tracking_active:true);setReady(true)}).catch(e=>{if(live)setError(e.message)}).finally(()=>{if(live)setLoading(false)});return()=>{live=false}},[vehicleId])
  async function save(){setLoading(true);setError('');setSaved(false);try{await api(`/tracking/${vehicleId}/link`,{method:'PUT',body:JSON.stringify({provider:'POSITRON',tracker_id:tracker,active})});setSaved(true)}catch(e){setError((e as Error).message)}finally{setLoading(false)}}
  return <fieldset className="tracking-link"><legend>Rastreamento · Pósitron</legend>{error&&<Alert>{error}</Alert>}{saved&&<Alert tone="success">Vínculo salvo.</Alert>}<label>ID do rastreador<input maxLength={120} value={tracker} disabled={!ready} onChange={e=>{setTracker(e.target.value);setSaved(false)}}/></label><label className="switch"><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/><span/>Rastreamento ativo</label><Button type="button" variant="secondary" disabled={!ready||!tracker.trim()} loading={loading} onClick={save}>Salvar vínculo</Button><p>O recebimento de posições depende da liberação da integração pela Pósitron.</p></fieldset>
}
