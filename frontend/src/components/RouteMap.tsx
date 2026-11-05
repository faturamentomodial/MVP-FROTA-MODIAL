import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Plan, Point } from '../types/routePlans'

export type PickupMarker = Point & { id: number; nome: string; tipo: 'COSTUREIRA' | 'FLORISTA' | null }
const noPickups: PickupMarker[] = []

export function RouteMap({plan, pickups = noPickups}:{plan:Plan|null; pickups?:PickupMarker[]}) {
  const container=useRef<HTMLDivElement>(null)
  useEffect(()=>{if(!container.current)return;const map=L.map(container.current).setView([-14.2,-51.9],4);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors',maxZoom:19}).addTo(map);const points:L.LatLngTuple[]=[]
    const stops=plan?.result?plan.stops:plan?.addresses?.length?plan.addresses.map(p=>({...p,invoices:[]})):(plan?.invoices ?? []).map(n=>({...n.destination,invoices:[n.number]}))
    for(const [i,p] of [plan?.origin,...stops].entries()){if(!p)continue;const point:L.LatLngTuple=[p.latitude,p.longitude];points.push(point);const text=document.createElement('span');text.textContent=`${i===0?(plan?.result?.return_to_origin?'Origem e retorno':'Origem'):`Parada ${i}`} · ${p.address}${p && 'invoices' in p && Array.isArray(p.invoices) && p.invoices.length ? ` · NF ${p.invoices.join(', ')}` : ''}`;L.marker(point,{icon:L.divIcon({className:'tracking-marker',html:`<span>${i}</span>`,iconSize:[30,30]})}).bindPopup(text).addTo(map)}
    if(plan?.return_point&&!plan.result?.return_to_origin){const p=plan.return_point;const point:L.LatLngTuple=[p.latitude,p.longitude];points.push(point);const label=document.createElement('span');label.textContent=`Retorno - ${p.address}`;L.marker(point,{icon:L.divIcon({className:'tracking-marker',html:'<span>R</span>',iconSize:[30,30]})}).bindPopup(label).addTo(map)}
    for (const pickup of pickups) {
      const point: L.LatLngTuple = [pickup.latitude, pickup.longitude]
      points.push(point)
      const text = document.createElement('span')
      const kind = pickup.tipo === 'COSTUREIRA' ? 'Costureira' : pickup.tipo === 'FLORISTA' ? 'Florista' : 'Coleta'
      text.textContent = `${kind} · ${pickup.nome} · ${pickup.address} · Localização aproximada`
      L.marker(point, {title: pickup.nome, icon: L.divIcon({className: 'tracking-marker', html: '<span style="border-color:#2563eb;color:#2563eb;font-size:16px">C</span>', iconSize: [36,36], iconAnchor: [18,18]})}).bindPopup(text).addTo(map)
    }
    if(plan?.result){const line=plan?.result.geometry.coordinates.map(p=>[p[1],p[0]] as L.LatLngTuple);L.polyline(line,{color:'#ef7c20'}).addTo(map);points.push(...line)}if(points.length)map.fitBounds(points,{padding:[30,30],maxZoom:15});const observer=new ResizeObserver(()=>map.invalidateSize());observer.observe(container.current);return()=>{observer.disconnect();map.remove()}
  },[plan, pickups]);return <div ref={container} className="route-map-canvas" aria-label="Mapa do planejamento"/>
}

