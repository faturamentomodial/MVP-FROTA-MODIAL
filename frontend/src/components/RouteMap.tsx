import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Plan } from '../types/routePlans'

export function RouteMap({plan}:{plan:Plan}) {
  const container=useRef<HTMLDivElement>(null)
  useEffect(()=>{if(!container.current)return;const map=L.map(container.current).setView([-14.2,-51.9],4);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors',maxZoom:19}).addTo(map);const points:L.LatLngTuple[]=[]
    const stops=plan.result?plan.stops:plan.invoices.map(n=>({...n.destination,invoices:[n.number]}))
    for(const [i,p] of [plan.origin,...stops].entries()){if(!p)continue;const point:L.LatLngTuple=[p.latitude,p.longitude];points.push(point);const text=document.createElement('span');text.textContent=`${i===0?(plan.result?.return_to_origin?'Origem e retorno':'Origem'):`Parada ${i}`} · ${p.address}${p && 'invoices' in p && Array.isArray(p.invoices) ? ` · NF ${p.invoices.join(', ')}` : ''}`;L.marker(point,{icon:L.divIcon({className:'tracking-marker',html:`<span>${i}</span>`,iconSize:[30,30]})}).bindPopup(text).addTo(map)}
    if(plan.result){const line=plan.result.geometry.coordinates.map(p=>[p[1],p[0]] as L.LatLngTuple);L.polyline(line,{color:'#ef7c20'}).addTo(map);points.push(...line)}if(points.length)map.fitBounds(points,{padding:[30,30],maxZoom:15});const observer=new ResizeObserver(()=>map.invalidateSize());observer.observe(container.current);return()=>{observer.disconnect();map.remove()}
  },[plan]);return <div ref={container} className="route-map-canvas" aria-label="Mapa do planejamento"/>
}

