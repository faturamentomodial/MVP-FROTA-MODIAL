import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { MapPin, RefreshCw } from 'lucide-react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Alert, Button, Empty } from '../../components/UI'
import { api } from '../../services/api'

interface Position { latitude:number; longitude:number; recorded_at:string; speed:number|null; address:string|null }
interface TrackedVehicle { vehicle_id:number; placa:string; modelo:string; tracker_id:string|null; tracking_active:boolean; status:string; position:Position|null; trip_id:number|null; driver_name:string|null; trip_started_at:string|null }
interface Fleet { items:TrackedVehicle[]; checked_at:string; provider_ready:boolean; message:string }
const labels:Record<string,string> = {SEM_VINCULO:'Sem rastreador vinculado',INATIVO:'Rastreamento inativo',AGUARDANDO_POSICAO:'Aguardando primeira posição',SEM_COMUNICACAO:'Sem comunicação',EM_MOVIMENTO:'Em movimento',PARADO:'Parado',DESCONHECIDO:'Velocidade indisponível'}
const filters = [['TODOS','Todos'],['EM_MOVIMENTO','Em movimento'],['PARADO','Parados'],['SEM_COMUNICACAO','Sem comunicação'],['EM_VIAGEM','Em viagem']]
const date = (value:string) => new Date(value).toLocaleString('pt-BR', {timeZone:'America/Sao_Paulo'})

export function TrackingPage() {
  const [fleet,setFleet]=useState<Fleet>(); const [error,setError]=useState(''); const [loading,setLoading]=useState(false)
  const [filter,setFilter]=useState('TODOS'); const [search,setSearch]=useState(''); const [selected,setSelected]=useState<number>()
  const [history,setHistory]=useState<Position[]>([]); const [historyMessage,setHistoryMessage]=useState(''); const [historyLoading,setHistoryLoading]=useState(false)
  const historyRequest=useRef(0); const refreshRequest=useRef(false)
  const container=useRef<HTMLDivElement>(null); const map=useRef<L.Map>(); const layer=useRef<L.LayerGroup>()
  const load=useCallback(async()=>{if(refreshRequest.current)return;refreshRequest.current=true;setLoading(true);try{setFleet(await api<Fleet>('/tracking'));setError('')}catch(e){setError((e as Error).message)}finally{refreshRequest.current=false;setLoading(false)}},[])
  useEffect(()=>{load();const timer=setInterval(load,30000);return()=>clearInterval(timer)},[load])
  useEffect(()=>{
    if(!container.current)return
    const instance=L.map(container.current).setView([-14.2,-51.9],4);map.current=instance
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(instance)
    layer.current=L.layerGroup().addTo(instance)
    const observer=new ResizeObserver(()=>instance.invalidateSize());observer.observe(container.current)
    return()=>{observer.disconnect();instance.remove();map.current=undefined}
  },[])
  const vehicles=(fleet?.items||[]).filter(v=>(filter==='TODOS'||(filter==='EM_VIAGEM'?v.trip_id!==null:v.status===filter))&&`${v.placa} ${v.driver_name||''}`.toLowerCase().includes(search.toLowerCase()))
  const current=fleet?.items.find(v=>v.vehicle_id===selected)
  useEffect(()=>{
    if(!map.current||!layer.current)return
    layer.current.clearLayers(); const bounds:L.LatLngTuple[]=[]
    for(const v of vehicles){if(!v.position)continue;const p:L.LatLngTuple=[v.position.latitude,v.position.longitude];bounds.push(p)
      const popup=document.createElement('div');popup.textContent=`${v.placa} · ${v.driver_name||'Sem viagem atual'} · ${labels[v.status]}`
      L.marker(p,{title:v.placa,icon:L.divIcon({className:'tracking-marker',html:'<span>🚚</span>',iconSize:[36,36],iconAnchor:[18,18]})}).bindPopup(popup).on('click',()=>choose(v.vehicle_id)).addTo(layer.current)
    }
    if(history.length){const points=history.map(p=>[p.latitude,p.longitude] as L.LatLngTuple);L.polyline(points,{color:'#ef7c20',weight:4}).addTo(layer.current);map.current.fitBounds(L.latLngBounds(points),{padding:[40,40],maxZoom:15})}
    else if(current?.position)map.current.setView([current.position.latitude,current.position.longitude],14)
    else if(bounds.length)map.current.fitBounds(L.latLngBounds(bounds),{padding:[40,40],maxZoom:14})
  },[fleet,filter,search,selected,history])
  function choose(id:number){historyRequest.current++;setSelected(id);setHistory([]);setHistoryMessage('');setHistoryLoading(false)}
  async function showHistory(){if(!selected)return;const request=++historyRequest.current;setHistoryLoading(true);try{const positions=await api<Position[]>(`/tracking/${selected}/history`);if(request!==historyRequest.current)return;setHistory(positions);setHistoryMessage(positions.length?`${positions.length} posições nas últimas 24 horas.`:'Nenhuma posição registrada nas últimas 24 horas.')}catch(e){if(request===historyRequest.current)setHistoryMessage((e as Error).message)}finally{if(request===historyRequest.current)setHistoryLoading(false)}}
  return <div className="admin-page"><header className="page-heading"><div><p className="eyebrow">MONITORAMENTO DA FROTA</p><h1>Rastreamento</h1><p>Localização, comunicação e viagens dos veículos.</p></div><Button variant="secondary" loading={loading} onClick={load}><RefreshCw size={18}/> Atualizar</Button></header>
    {error&&<Alert>{error}</Alert>}{fleet&&!fleet.provider_ready&&<Alert tone="info">{fleet.message} Os veículos aparecerão no mapa quando houver posições reais disponíveis.</Alert>}
    <div className="tracking-toolbar"><div className="tracking-filters" role="group" aria-label="Filtrar veículos">{filters.map(([value,label])=><button key={value} aria-pressed={filter===value} className={filter===value?'active':''} onClick={()=>{setFilter(value);choose(0)}}>{label}</button>)}</div><small aria-live="polite">{fleet?`Consulta ao sistema: ${date(fleet.checked_at)}`:'Carregando veículos…'}</small></div>
    <section className="tracking-layout panel"><aside className="tracking-vehicles"><label>Buscar placa ou motorista<input value={search} onChange={e=>{setSearch(e.target.value);choose(0)}} placeholder="Buscar veículo"/></label><p>{vehicles.length} veículos</p>
      {vehicles.map(v=><button className={`tracking-vehicle ${selected===v.vehicle_id?'selected':''}`} key={v.vehicle_id} onClick={()=>choose(v.vehicle_id)}><strong>{v.placa}</strong><span>{v.modelo}</span><span>{v.driver_name||'Sem viagem atual'}</span><small>{labels[v.status]}{v.position?.speed!=null?` · ${v.position.speed} km/h`:''}</small></button>)}
      {!vehicles.length&&<Empty title="Nenhum veículo" description="Verifique os filtros ou cadastre veículos."/>}</aside>
      <div className="tracking-map-wrap"><div ref={container} className="tracking-map" aria-label="Mapa da frota"/>{!vehicles.some(v=>v.position)&&<div className="tracking-map-notice"><MapPin/><strong>Sem posições disponíveis</strong><span>O mapa exibirá somente localizações recebidas dos rastreadores.</span></div>}</div>
    </section>
    {current&&<section className="panel tracking-details"><header><h2>{current.placa}</h2><Link to={`/admin/veiculos/${current.vehicle_id}`}>Ver veículo</Link></header><dl><div><dt>Motorista</dt><dd>{current.driver_name||'Sem viagem atual'}</dd></div><div><dt>Status</dt><dd>{labels[current.status]}</dd></div><div><dt>Rastreador Pósitron</dt><dd>{current.tracker_id||'Não vinculado'}</dd></div><div><dt>Velocidade</dt><dd>{current.position?.speed!=null?`${current.position.speed} km/h`:'Indisponível'}</dd></div><div><dt>Última posição</dt><dd>{current.position?date(current.position.recorded_at):'Não recebida'}</dd></div><div><dt>Latitude / longitude</dt><dd>{current.position?`${current.position.latitude}, ${current.position.longitude}`:'Indisponível'}</dd></div><div><dt>Endereço aproximado</dt><dd>{current.position?.address||'Indisponível'}</dd></div><div><dt>Viagem atual</dt><dd>{current.trip_id?<Link to={`/admin/viagens/${current.trip_id}`}>Viagem #{current.trip_id}</Link>:'Sem viagem atual'}</dd></div><div><dt>Início da viagem</dt><dd>{current.trip_started_at?date(current.trip_started_at):'—'}</dd></div></dl><Button variant="secondary" onClick={showHistory} loading={historyLoading}>Ver rota percorrida · 24 horas</Button>{historyMessage&&<p role="status">{historyMessage}</p>}</section>}
  </div>
}
