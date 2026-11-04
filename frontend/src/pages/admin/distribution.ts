export type Point = {
  address: string;
  latitude: number;
  longitude: number;
  house_number_found?: boolean;
};
export type Note = {
  id: string;
  number: string;
  volumes: number;
  partner: string;
  company: string;
  series: string;
  source: "MANUAL" | "SANKHYA";
  external_id: string | null;
  address: string;
  destination: Point | null;
  geocode_status: "PENDENTE" | "VALIDADO";
};
export type Lookup = {
  number: string;
  external_id: string;
  company: string;
  series: string;
  partner: string;
  volumes: number | null;
  address: string;
  source: "SANKHYA";
};
export type Plan = {
  id?: number;
  revision: number;
  status?: string;
  name: string;
  vehicle_id: number | null;
  driver_id: number | null;
  profile: "car" | "truck";
  origin: Point | null;
  invoices: Omit<Note, "id" | "address" | "geocode_status">[];
  objective: "duration" | "distance";
  stops?: Point[];
  result?: null | {
    distance: number;
    duration: number;
    geometry: { coordinates: number[][] };
  };
};
export type Route = {
  key: string;
  plan_id: number | null;
  color: string;
  invoice_ids: string[];
  plan: Plan;
  delivery_statuses?: Record<string, string>;
  resource_warnings?: string[];
};
export type Distribution = {
  id: number;
  name: string;
  revision: number;
  notes: Note[];
  routes: Route[];
};
export type TrackedVehicle = {
  vehicle_id: number;
  placa: string;
  status: string;
  tracking_active: boolean;
  position: null | { latitude: number; longitude: number; recorded_at: string };
};
export const colors = [
  "#002fa7",
  "#7c3aed",
  "#087f5b",
  "#c2255c",
  "#b35c00",
  "#0891b2",
];
export const newRoute = (index: number): Route => ({
  key: crypto.randomUUID(),
  plan_id: null,
  color: colors[index % colors.length],
  invoice_ids: [],
  plan: {
    revision: 0,
    name: `Rota ${String(index + 1).padStart(2, "0")}`,
    vehicle_id: null,
    driver_id: null,
    profile: "truck",
    origin: null,
    invoices: [],
    objective: "duration",
    result: null,
  },
});
export function serialize(d: Distribution) {
  return {
    name: d.name,
    revision: d.revision,
    notes: d.notes,
    routes: d.routes.map((r) => ({
      key: r.key,
      plan_id: r.plan_id,
      color: r.color,
      invoice_ids: r.invoice_ids,
      plan: ((p: Plan) => ({
        name: p.name,
        revision: p.revision,
        vehicle_id: p.vehicle_id,
        driver_id: p.driver_id,
        profile: p.profile,
        origin: p.origin && {
          address: p.origin.address,
          latitude: p.origin.latitude,
          longitude: p.origin.longitude,
        },
        invoices: [],
        objective: p.objective,
      }))(r.plan),
    })),
  };
}
export function toggleSelection(selected: string[], id: string) {
  return selected.includes(id)
    ? selected.filter((x) => x !== id)
    : [...selected, id];
}
export function insideRectangle(
  point: Point,
  a: { lat: number; lng: number },
  b: { lat: number; lng: number },
) {
  return (
    point.latitude >= Math.min(a.lat, b.lat) &&
    point.latitude <= Math.max(a.lat, b.lat) &&
    point.longitude >= Math.min(a.lng, b.lng) &&
    point.longitude <= Math.max(a.lng, b.lng)
  );
}
export function availableIds(notes: Note[], routes: Route[]) {
  const assigned = new Set(routes.flatMap((r) => r.invoice_ids));
  return notes.filter((n) => !assigned.has(n.id)).map((n) => n.id);
}
