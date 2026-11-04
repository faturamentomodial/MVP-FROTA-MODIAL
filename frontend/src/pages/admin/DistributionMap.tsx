import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Note, Route, TrackedVehicle } from "./distribution";
import { insideRectangle } from "./distribution";

type Props = {
  notes: Note[];
  routes: Route[];
  selected: string[];
  onToggle: (id: string) => void;
  drawing: boolean;
  onArea: (ids: string[]) => void;
  vehicles: TrackedVehicle[];
};
export function DistributionMap(props: Props) {
  const container = useRef<HTMLDivElement>(null),
    map = useRef<L.Map>(),
    markers = useRef(new Map<string, L.Marker>()),
    lines = useRef<L.LayerGroup>(),
    trucks = useRef<L.LayerGroup>(),
    rectangle = useRef<L.Rectangle>(),
    start = useRef<L.LatLng>(),
    latest = useRef(props),
    fitKey = useRef("");
  latest.current = props;
  useEffect(() => {
    if (!container.current) return;
    const instance = L.map(container.current).setView([-14.2, -51.9], 4);
    map.current = instance;
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors",
    }).addTo(instance);
    lines.current = L.layerGroup().addTo(instance);
    trucks.current = L.layerGroup().addTo(instance);
    instance.on("click", (e: L.LeafletMouseEvent) => {
      if (!latest.current.drawing) return;
      if (!start.current) {
        rectangle.current?.remove();
        start.current = e.latlng;
        rectangle.current = L.rectangle(L.latLngBounds(e.latlng, e.latlng), {
          color: "#002fa7",
          weight: 2,
        }).addTo(instance);
      } else {
        const a = start.current;
        rectangle.current?.setBounds(L.latLngBounds(a, e.latlng));
        start.current = undefined;
        const assigned = new Set(
          latest.current.routes.flatMap((r) => r.invoice_ids),
        );
        latest.current.onArea(
          latest.current.notes
            .filter(
              (n) =>
                !assigned.has(n.id) &&
                n.destination &&
                insideRectangle(n.destination, a, e.latlng),
            )
            .map((n) => n.id),
        );
      }
    });
    instance.on("mousemove", (e: L.LeafletMouseEvent) => {
      if (latest.current.drawing && start.current)
        rectangle.current?.setBounds(L.latLngBounds(start.current, e.latlng));
    });
    const observer = new ResizeObserver(() => instance.invalidateSize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      instance.remove();
      map.current = undefined;
      markers.current.clear();
      fitKey.current = "";
    };
  }, []);
  useEffect(() => {
    if (!props.drawing) {
      start.current = undefined;
      rectangle.current?.remove();
      rectangle.current = undefined;
    }
  }, [props.drawing]);
  useEffect(() => {
    if (!map.current) return;
    const valid = new Set(
      props.notes.filter((n) => n.destination).map((n) => n.id),
    );
    for (const [id, marker] of markers.current)
      if (!valid.has(id)) {
        marker.remove();
        markers.current.delete(id);
      }
    const points: L.LatLngTuple[] = [];
    props.notes.forEach((n, index) => {
      if (!n.destination) return;
      const p: L.LatLngTuple = [
        n.destination.latitude,
        n.destination.longitude,
      ];
      points.push(p);
      const route = props.routes.find((r) => r.invoice_ids.includes(n.id)),
        done = route?.delivery_statuses?.[n.number] === "ENTREGUE",
        selected = props.selected.includes(n.id),
        color = done
          ? "#777"
          : (route?.color ?? (selected ? "#002fa7" : "#ff4f00"));
      const html = document.createElement("span");
      html.className = "distribution-dot";
      html.style.backgroundColor = color;
      html.textContent = String(index + 1);
      if (selected) html.classList.add("selected");
      const icon = L.divIcon({
        className: "distribution-marker",
        html,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });
      let marker = markers.current.get(n.id);
      if (!marker) {
        marker = L.marker(p, {
          icon,
          keyboard: true,
          title: `NF ${n.number}`,
        }).addTo(map.current!);
        markers.current.set(n.id, marker);
        marker.on("click", () => {
          if (!latest.current.drawing) latest.current.onToggle(n.id);
        });
      }
      marker.setLatLng(p).setIcon(icon);
      const popup = document.createElement("div"),
        title = document.createElement("strong"),
        body = document.createElement("p"),
        button = document.createElement("button");
      title.textContent = `NF ${n.number} · ${n.partner || "Destinatário não informado"}`;
      body.textContent = `${n.destination.address} · ${n.volumes} volumes · ${route?.plan.name ?? "Disponível"}`;
      popup.append(title, body);
      if (!route) {
        button.type = "button";
        button.textContent = selected ? "Remover da seleção" : "Selecionar";
        button.onclick = () => latest.current.onToggle(n.id);
        popup.append(button);
      }
      marker.bindPopup(popup);
    });
    // Only new/changed coordinates trigger framing; selecting and editing routes
    // keep the user's current zoom and pan, and preserve the Leaflet instance.
    const key = props.notes
      .filter((n) => n.destination)
      .map(
        (n) => `${n.id}:${n.destination!.latitude},${n.destination!.longitude}`,
      )
      .join("|");
    if (key !== fitKey.current && points.length) {
      map.current.fitBounds(points, { padding: [36, 36], maxZoom: 15 });
      fitKey.current = key;
    }
  }, [props.notes, props.routes, props.selected]);
  useEffect(() => {
    if (!lines.current) return;
    lines.current.clearLayers();
    for (const r of props.routes) {
      if (r.plan.result)
        L.polyline(
          r.plan.result.geometry.coordinates.map(
            (p) => [p[1], p[0]] as L.LatLngTuple,
          ),
          { color: r.color, weight: 4, opacity: 0.75 },
        )
          .bindTooltip(`${r.plan.name} · percurso estimado`)
          .addTo(lines.current);
      if (r.plan.origin) {
        const label = document.createElement("span");
        label.textContent = `Origem e retorno · ${r.plan.name}`;
        L.circleMarker([r.plan.origin.latitude, r.plan.origin.longitude], {
          color: r.color,
          radius: 7,
          fillOpacity: 1,
        })
          .bindPopup(label)
          .addTo(lines.current);
      }
    }
  }, [props.routes]);
  useEffect(() => {
    trucks.current?.clearLayers();
    for (const v of props.vehicles) {
      if (!v.position || !v.tracking_active) continue;
      const popup = document.createElement("div");
      popup.textContent = `Veículo ${v.placa} · ${v.status} · Última posição: ${new Date(v.position.recorded_at).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" })}`;
      L.marker([v.position.latitude, v.position.longitude], {
        icon: L.divIcon({
          className: "distribution-truck",
          html: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 3h14v13H1zM15 8h4l3 4v4h-7"/><circle cx="5" cy="18" r="2"/><circle cx="18" cy="18" r="2"/></svg>',
          iconSize: [34, 34],
        }),
      })
        .bindPopup(popup)
        .addTo(trucks.current!);
    }
  }, [props.vehicles]);
  return (
    <div
      ref={container}
      className={`distribution-map ${props.drawing ? "drawing" : ""}`}
      aria-label="Mapa de notas fiscais. Para selecionar área, clique em dois cantos opostos."
    />
  );
}
