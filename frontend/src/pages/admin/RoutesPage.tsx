import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  Plus,
  Square,
  Truck,
} from "lucide-react";
import { Alert, Button } from "../../components/UI";
import { api } from "../../services/api";
import type { Driver, Page, Vehicle } from "../../types";
import { LegacyRoutesPage } from "./LegacyRoutesPage";
import { DistributionMap } from "./DistributionMap";
import { AddressPicker } from "./DistributionAddress";
import {
  availableIds,
  newRoute,
  serialize,
  toggleSelection,
} from "./distribution";
import type {
  Distribution,
  Lookup,
  Note,
  Plan,
  Point,
  Route,
  TrackedVehicle,
} from "./distribution";
import "./distribution.css";

export function RoutesPage() {
  const [legacy, setLegacy] = useState(false),
    [list, setList] = useState<
      { id: number; name: string; revision: number }[]
    >([]),
    [work, setWork] = useState<Distribution | null>(null),
    [drivers, setDrivers] = useState<Driver[]>([]),
    [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [selected, setSelected] = useState<string[]>([]),
    [active, setActive] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [dirty, setDirty] = useState(false),
    [search, setSearch] = useState(""),
    [filter, setFilter] = useState("DISPONIVEL"),
    [left, setLeft] = useState(true),
    [right, setRight] = useState(true);
  const [number, setNumber] = useState(""),
    [volumes, setVolumes] = useState(1),
    [partner, setPartner] = useState(""),
    [company, setCompany] = useState(""),
    [series, setSeries] = useState(""),
    [address, setAddress] = useState(""),
    [destination, setDestination] = useState<Point | null>(null),
    [imported, setImported] = useState<Lookup | null>(null),
    [matches, setMatches] = useState<Lookup[]>([]),
    [editing, setEditing] = useState<string | null>(null);
  const [drawing, setDrawing] = useState(false),
    [area, setArea] = useState<string[] | null>(null),
    [showVehicles, setShowVehicles] = useState(false),
    [fleet, setFleet] = useState<TrackedVehicle[]>([]),
    [trackingMessage, setTrackingMessage] = useState("");
  const guard = useRef(false);
  async function run(action: () => Promise<void>) {
    if (guard.current) return;
    guard.current = true;
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      guard.current = false;
      setBusy(false);
    }
  }
  async function refreshList() {
    setList(await api("/distributions"));
  }
  useEffect(() => {
    Promise.all([
      refreshList(),
      api<Page<Driver>>("/drivers?page_size=100").then((r) =>
        setDrivers(r.items.filter((d) => d.ativo)),
      ),
      api<Page<Vehicle>>("/vehicles?page_size=100").then((r) =>
        setVehicles(r.items.filter((v) => v.ativo)),
      ),
    ]).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  useEffect(() => {
    if (!showVehicles) return;
    let alive = true;
    async function load() {
      try {
        const result = await api<{
          items: TrackedVehicle[];
          message: string | null;
        }>("/tracking");
        if (alive) {
          setFleet(result.items);
          setTrackingMessage(result.message || "");
        }
      } catch (e) {
        if (alive) setTrackingMessage((e as Error).message);
      }
    }
    load();
    const timer = setInterval(load, 30000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [showVehicles]);
  function change(next: Distribution) {
    setWork(next);
    setDirty(true);
  }
  async function persist(next: Distribution) {
    const saved = await api<Distribution>(`/distributions/${next.id}`, {
      method: "PUT",
      body: JSON.stringify(serialize(next)),
    });
    setWork(saved);
    setDirty(false);
    await refreshList();
    return saved;
  }
  async function open(id: number) {
    if (
      dirty &&
      !window.confirm(
        "Descartar alterações não salvas para abrir outra distribuição?",
      )
    )
      return;
    const saved = await api<Distribution>(`/distributions/${id}`);
    setWork(saved);
    setDirty(false);
    setSelected([]);
    setActive(saved.routes[0]?.key || "");
    setDrawing(false);
    setArea(null);
    resetNote();
  }
  function resetNote() {
    setNumber("");
    setVolumes(1);
    setPartner("");
    setCompany("");
    setSeries("");
    setAddress("");
    setDestination(null);
    setImported(null);
    setMatches([]);
    setEditing(null);
  }
  function choose(n: Lookup) {
    setImported(n);
    setNumber(n.number);
    setVolumes(n.volumes ?? 0);
    setPartner(n.partner);
    setCompany(n.company);
    setSeries(n.series);
    setAddress(n.address);
    setDestination(null);
    setMatches([]);
  }
  async function lookup() {
    setMatches([]);
    setImported(null);
    setDestination(null);
    const result = await api<{ invoices: Lookup[] }>(
      `/route-plans/invoice-lookup?number=${encodeURIComponent(number.trim())}`,
    );
    if (result.invoices.length === 1) choose(result.invoices[0]);
    else if (result.invoices.length) setMatches(result.invoices);
    else
      throw new Error(
        "NF não encontrada no Sankhya. Confira o número ou cadastre manualmente.",
      );
  }
  async function addNote() {
    if (!work) return;
    const note: Note = {
      id: editing ?? crypto.randomUUID(),
      number: number.trim(),
      volumes,
      partner,
      company,
      series,
      source: imported ? "SANKHYA" : "MANUAL",
      external_id: imported?.external_id ?? null,
      address: destination?.address ?? address,
      destination,
      geocode_status: destination ? "VALIDADO" : "PENDENTE",
    };
    const next = {
      ...work,
      notes: editing
        ? work.notes.map((n) => (n.id === editing ? note : n))
        : [...work.notes, note],
    };
    await persist(next);
    resetNote();
  }
  function toggle(id: string) {
    if (!work || !availableIds(work.notes, work.routes).includes(id)) return;
    setSelected((s) => toggleSelection(s, id));
  }
  function updateRoute(
    key: string,
    patch: Partial<Plan>,
    routePatch: Partial<Route> = {},
  ) {
    if (!work) return;
    change({
      ...work,
      routes: work.routes.map((r) =>
        r.key === key
          ? {
              ...r,
              ...routePatch,
              plan: { ...r.plan, ...patch, result: null, stops: [] },
            }
          : r,
      ),
    });
  }
  async function assign() {
    if (!work) return;
    let routes = [...work.routes],
      target = routes.find(
        (r) => r.key === active && r.plan.status !== "CONFIRMADO",
      );
    if (!target) {
      target = newRoute(routes.length);
      routes.push(target);
    }
    const ids = selected.filter(
      (id) =>
        availableIds(work.notes, work.routes).includes(id) &&
        work.notes.find((n) => n.id === id)?.destination,
    );
    if (target.invoice_ids.length + ids.length > 10)
      throw new Error(
        "Cada rota suporta até 10 notas. Crie outra rota para as demais entregas.",
      );
    routes = routes.map((r) =>
      r.key === target!.key
        ? { ...r, invoice_ids: [...r.invoice_ids, ...ids] }
        : r,
    );
    await persist({ ...work, routes });
    setActive(target.key);
    setSelected([]);
  }
  async function transfer(id: string, from: string, to: string) {
    if (!work) return;
    const target = work.routes.find((r) => r.key === to);
    if (target && target.invoice_ids.length >= 10)
      throw new Error("Rota de destino atingiu 10 notas.");
    if (
      !window.confirm(
        to
          ? "Transferir esta nota para a rota selecionada?"
          : "Remover esta nota da rota e devolvê-la às disponíveis?",
      )
    )
      return;
    await persist({
      ...work,
      routes: work.routes.map((r) =>
        r.key === from
          ? { ...r, invoice_ids: r.invoice_ids.filter((n) => n !== id) }
          : r.key === to
            ? { ...r, invoice_ids: [...r.invoice_ids, id] }
            : r,
      ),
    });
  }
  async function calculate(r: Route, optimize: boolean) {
    if (!work) return;
    const saved = dirty ? await persist(work) : work;
    const current = saved.routes.find((x) => x.key === r.key)!;
    await api(`/route-plans/${current.plan_id}/calculate`, {
      method: "POST",
      body: JSON.stringify({ revision: current.plan.revision, optimize }),
    });
    setWork(await api(`/distributions/${work.id}`));
  }
  async function confirm(r: Route) {
    if (
      !work ||
      !window.confirm(
        "Confirmar a rota? Ela ficará bloqueada para edição e disponível ao motorista designado.",
      )
    )
      return;
    if (!r.plan.driver_id)
      throw new Error("Selecione um motorista antes de confirmar.");
    await api(`/route-plans/${r.plan_id}/confirm`, {
      method: "POST",
      body: JSON.stringify({ revision: r.plan.revision }),
    });
    setWork(await api(`/distributions/${work.id}`));
  }
  function move(r: Route, index: number, delta: number) {
    if (!work) return;
    const ids = [...r.invoice_ids];
    [ids[index], ids[index + delta]] = [ids[index + delta], ids[index]];
    updateRoute(r.key, {}, { invoice_ids: ids });
  }
  if (legacy)
    return (
      <>
        <Button variant="secondary" onClick={() => setLegacy(false)}>
          Voltar à Central de Distribuição
        </Button>
        <LegacyRoutesPage />
      </>
    );
  const available = work ? availableIds(work.notes, work.routes) : [],
    visible =
      work?.notes.filter(
        (n) =>
          (filter === "TODAS" ||
            (filter === "DISPONIVEL"
              ? available.includes(n.id)
              : filter === "PENDENTE"
                ? !n.destination
                : !available.includes(n.id))) &&
          `${n.number} ${n.partner} ${n.address} ${n.company} ${n.series}`
            .toLocaleLowerCase()
            .includes(search.toLocaleLowerCase()),
      ) ?? [];
  const selectedNotes =
      work?.notes.filter((n) => selected.includes(n.id)) ?? [],
    current = work?.routes.find((r) => r.key === active),
    locked = current?.plan.status === "CONFIRMADO";
  return (
    <div className="admin-page distribution-page">
      <header className="page-heading">
        <div>
          <h1>Central de Distribuição</h1>
          <p>Selecione entregas no mapa e distribua entre rotas.</p>
        </div>
        <Button
          variant="secondary"
          onClick={() => {
            if (
              !dirty ||
              window.confirm("Sair da central com alterações não salvas?")
            )
              setLegacy(true);
          }}
        >
          Planejamentos anteriores
        </Button>
      </header>
      {error && (
        <Alert>
          {error}{" "}
          <button
            type="button"
            disabled={busy || !work}
            onClick={() => work && run(() => open(work.id))}
          >
            Recarregar distribuição
          </button>
        </Alert>
      )}
      <div className="distribution-toolbar">
        <label>
          Distribuição
          <select
            aria-label="Abrir distribuição"
            value={work?.id ?? ""}
            disabled={busy}
            onChange={(e) => run(() => open(Number(e.target.value)))}
          >
            <option value="" disabled>
              Selecione um conjunto salvo
            </option>
            {list.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <Button
          disabled={busy}
          onClick={() =>
            run(async () => {
              if (dirty && !window.confirm("Descartar alterações não salvas?"))
                return;
              const name = window.prompt(
                "Nome da distribuição",
                `Distribuição ${new Date().toLocaleDateString("pt-BR")}`,
              );
              if (!name?.trim()) return;
              const saved = await api<Distribution>("/distributions", {
                method: "POST",
                body: JSON.stringify({ name: name.trim() }),
              });
              setWork(saved);
              setDirty(false);
              setActive("");
              setSelected([]);
              resetNote();
              await refreshList();
            })
          }
        >
          <Plus size={16} /> Nova distribuição
        </Button>
        {work && (
          <>
            <span aria-live="polite">
              Revisão {work.revision} ·{" "}
              {dirty ? "Alterações não salvas" : "Salvo"}
            </span>
            <Button
              disabled={busy || !dirty}
              loading={busy}
              onClick={() =>
                run(async () => {
                  await persist(work);
                })
              }
            >
              Salvar rascunho
            </Button>
          </>
        )}
      </div>
      {!work ? (
        <section className="panel">
          <h2>Organize as próximas entregas</h2>
          <p>
            Crie uma distribuição ou reabra um conjunto salvo. Notas sem
            localização validada ficam no painel até a confirmação do endereço.
          </p>
        </section>
      ) : (
        <>
          <div className="distribution-summary">
            <label>
              Nome do conjunto
              <input
                value={work.name}
                disabled={busy}
                maxLength={160}
                onChange={(e) => change({ ...work, name: e.target.value })}
              />
            </label>
            <span>
              <b>{work.notes.length}</b> notas
            </span>
            <span>
              <b>{work.notes.reduce((s, n) => s + n.volumes, 0)}</b> volumes
            </span>
            <span>
              <b>{available.length}</b> disponíveis
            </span>
            <span>
              <b>{work.routes.length}</b> rotas
            </span>
          </div>
          <div
            className={`distribution-layout ${left ? "" : "left-closed"} ${right ? "" : "right-closed"}`}
          >
            <aside className="distribution-panel distribution-invoices">
              <header>
                <h2>{left ? "Notas fiscais" : "NFs"}</h2>
                <button
                  className="icon-button"
                  aria-label={left ? "Recolher notas" : "Expandir notas"}
                  onClick={() => setLeft(!left)}
                >
                  {left ? <ChevronLeft /> : <ChevronRight />}
                </button>
              </header>
              {left && (
                <>
                  <details open={!work.notes.length || !!editing}>
                    <summary>
                      {editing
                        ? "Validar / editar nota"
                        : "Adicionar nota fiscal"}
                    </summary>
                    <fieldset disabled={busy}>
                      <label>
                        Número da NF
                        <input
                          value={number}
                          maxLength={80}
                          onChange={(e) => {
                            setNumber(e.target.value);
                            setImported(null);
                            setMatches([]);
                            setDestination(null);
                          }}
                        />
                      </label>
                      <Button
                        variant="secondary"
                        disabled={!/^\d{1,18}$/.test(number.trim())}
                        onClick={() => run(lookup)}
                      >
                        Buscar no Sankhya
                      </Button>
                      {matches.length > 0 && (
                        <p>
                          Selecione pela empresa, série e identificador interno.
                        </p>
                      )}
                      {matches.map((n) => (
                        <button
                          className="distribution-candidate"
                          key={`${n.company}:${n.series}:${n.external_id}`}
                          onClick={() => choose(n)}
                        >
                          NF {n.number} · Empresa {n.company} · Série{" "}
                          {n.series || "—"} · ID {n.external_id}
                          <small>{n.partner}</small>
                        </button>
                      ))}
                      <label>
                        Destinatário
                        <input
                          value={partner}
                          maxLength={240}
                          onChange={(e) => setPartner(e.target.value)}
                        />
                      </label>
                      <div className="distribution-fields">
                        <label>
                          Empresa
                          <input
                            value={company}
                            disabled={!!imported}
                            maxLength={80}
                            onChange={(e) => setCompany(e.target.value)}
                          />
                        </label>
                        <label>
                          Série
                          <input
                            value={series}
                            disabled={!!imported}
                            maxLength={80}
                            onChange={(e) => setSeries(e.target.value)}
                          />
                        </label>
                      </div>
                      <label>
                        Volumes
                        <input
                          type="number"
                          min={1}
                          max={1000000}
                          value={volumes}
                          onChange={(e) => setVolumes(Number(e.target.value))}
                        />
                      </label>
                      <label>
                        Endereço para salvar pendente
                        <input
                          value={address}
                          maxLength={500}
                          onChange={(e) => {
                            setAddress(e.target.value);
                            setDestination(null);
                          }}
                        />
                      </label>
                      <AddressPicker
                        initialAddress={address}
                        label="Validar localização"
                        onSelect={setDestination}
                      />
                      {destination && (
                        <p role="status">
                          Localização escolhida: {destination.address}
                        </p>
                      )}
                      <Button
                        disabled={
                          !number.trim() ||
                          !Number.isInteger(volumes) ||
                          volumes < 1 ||
                          (destination?.address ?? address).length < 5
                        }
                        onClick={() => run(addNote)}
                      >
                        {destination
                          ? "Salvar NF com localização validada"
                          : "Salvar NF pendente"}
                      </Button>
                      {editing && (
                        <Button variant="secondary" onClick={resetNote}>
                          Cancelar edição
                        </Button>
                      )}
                    </fieldset>
                  </details>
                  <label>
                    Pesquisar notas
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="NF, destinatário ou endereço"
                    />
                  </label>
                  <label>
                    Situação
                    <select
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    >
                      <option value="DISPONIVEL">Disponíveis</option>
                      <option value="TODAS">Todas</option>
                      <option value="DISTRIBUIDA">Distribuídas</option>
                      <option value="PENDENTE">Endereço pendente</option>
                    </select>
                  </label>
                  <button
                    disabled={busy}
                    onClick={() =>
                      setSelected((s) =>
                        Array.from(
                          new Set([
                            ...s,
                            ...visible
                              .filter(
                                (n) =>
                                  available.includes(n.id) && n.destination,
                              )
                              .map((n) => n.id),
                          ]),
                        ),
                      )
                    }
                  >
                    Selecionar disponíveis do filtro
                  </button>
                  <div className="distribution-note-list">
                    {visible.map((n) => {
                      const r = work.routes.find((r) =>
                        r.invoice_ids.includes(n.id),
                      );
                      return (
                        <article
                          key={n.id}
                          className={`distribution-note ${selected.includes(n.id) ? "selected" : ""}`}
                        >
                          <label className="distribution-note-title">
                            <input
                              type="checkbox"
                              checked={selected.includes(n.id)}
                              disabled={busy || !!r || !n.destination}
                              onChange={() => toggle(n.id)}
                            />
                            <span className="distribution-index">
                              {work.notes.indexOf(n) + 1}
                            </span>
                            <strong>NF {n.number}</strong>
                          </label>
                          <p>{n.partner || "Destinatário não informado"}</p>
                          <small>{n.address}</small>
                          <p>
                            {n.volumes} volumes · Empresa {n.company || "—"} ·
                            Série {n.series || "—"}
                          </p>
                          <span
                            className={
                              !n.destination ? "distribution-pending" : ""
                            }
                          >
                            {!n.destination
                              ? "Endereço pendente de validação"
                              : r
                                ? `${r.plan.name} · ${r.delivery_statuses?.[n.number] === "ENTREGUE" ? "Entregue" : r.plan.status}`
                                : "Localização validada · Disponível"}
                          </span>
                          {!r && (
                            <div>
                              <button
                                disabled={busy}
                                onClick={() => {
                                  setEditing(n.id);
                                  setNumber(n.number);
                                  setVolumes(n.volumes);
                                  setPartner(n.partner);
                                  setCompany(n.company);
                                  setSeries(n.series);
                                  setAddress(n.address);
                                  setDestination(n.destination);
                                  setImported(
                                    n.source === "SANKHYA"
                                      ? {
                                          ...n,
                                          source: "SANKHYA",
                                          external_id: n.external_id!,
                                          volumes: n.volumes,
                                        }
                                      : null,
                                  );
                                }}
                              >
                                Editar / validar
                              </button>
                              <button
                                disabled={busy}
                                onClick={() =>
                                  run(async () => {
                                    if (
                                      window.confirm(
                                        `Excluir NF ${n.number} do conjunto? O histórico será preservado.`,
                                      )
                                    ) {
                                      await persist({
                                        ...work,
                                        notes: work.notes.filter(
                                          (x) => x.id !== n.id,
                                        ),
                                      });
                                      setSelected((s) =>
                                        s.filter((id) => id !== n.id),
                                      );
                                    }
                                  })
                                }
                              >
                                Excluir
                              </button>
                            </div>
                          )}
                        </article>
                      );
                    })}
                    {!visible.length && <p>Nenhuma nota neste filtro.</p>}
                  </div>
                </>
              )}
            </aside>
            <section className="distribution-map-panel">
              <div className="distribution-map-tools">
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => {
                    setDrawing(!drawing);
                    setArea(null);
                  }}
                >
                  <Square size={16} />
                  {drawing ? "Cancelar desenho" : "Selecionar área"}
                </Button>
                <label>
                  <input
                    type="checkbox"
                    checked={showVehicles}
                    onChange={(e) => setShowVehicles(e.target.checked)}
                  />
                  <Truck size={16} /> Veículos vinculados
                </label>
              </div>
              {drawing && (
                <div className="distribution-area" role="status">
                  Clique em dois cantos opostos para desenhar um retângulo. Zoom
                  e navegação continuam disponíveis.
                  {area !== null && (
                    <>
                      <p>{area.length} notas disponíveis nesta região.</p>
                      <Button
                        onClick={() => {
                          setSelected((s) =>
                            Array.from(new Set([...s, ...area])),
                          );
                          setDrawing(false);
                          setArea(null);
                        }}
                      >
                        Confirmar seleção da área
                      </Button>
                    </>
                  )}
                </div>
              )}
              <DistributionMap
                notes={work.notes}
                routes={work.routes}
                selected={selected}
                onToggle={toggle}
                drawing={drawing}
                onArea={setArea}
                vehicles={
                  showVehicles
                    ? fleet.filter((v) =>
                        work.routes.some(
                          (r) => r.plan.vehicle_id === v.vehicle_id,
                        ),
                      )
                    : []
                }
              />
              <div className="distribution-selection">
                <span aria-live="polite">
                  <b>{selectedNotes.length}</b> notas ·{" "}
                  <b>{selectedNotes.reduce((s, n) => s + n.volumes, 0)}</b>{" "}
                  volumes selecionados
                </span>
                <Button variant="secondary" onClick={() => setSelected([])}>
                  Limpar seleção
                </Button>
                <Button
                  disabled={busy || !selectedNotes.length}
                  onClick={() => run(assign)}
                >
                  Adicionar selecionadas à rota
                </Button>
              </div>
              <div className="distribution-legend">
                <span>
                  <i style={{ background: "#ff4f00" }} />
                  Disponível
                </span>
                <span>
                  <i style={{ background: "#002fa7" }} />
                  Selecionada
                </span>
                <span>
                  <i style={{ background: "#777" }} />
                  Entregue
                </span>
                {work.routes.map((r) => (
                  <span key={r.key}>
                    <i style={{ background: r.color }} />
                    {r.plan.name}
                  </span>
                ))}
              </div>
              {showVehicles && (
                <p className="distribution-map-caption">
                  Posições reais recebidas do rastreamento existente; veículos
                  sem vínculo ou posição não aparecem. {trackingMessage}
                </p>
              )}
              <p className="distribution-map-caption">
                Linhas são percursos estimados. OSRM driving não considera
                altura, peso, eixos ou restrições legais de caminhões. Revisão
                humana obrigatória.
              </p>
            </section>
            <aside className="distribution-panel distribution-routes">
              <header>
                <h2>{right ? "Montagem das rotas" : "Rotas"}</h2>
                <button
                  className="icon-button"
                  aria-label={right ? "Recolher rotas" : "Expandir rotas"}
                  onClick={() => setRight(!right)}
                >
                  {right ? <ChevronRight /> : <ChevronLeft />}
                </button>
              </header>
              {right && (
                <>
                  <Button
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        const r = newRoute(work.routes.length);
                        await persist({ ...work, routes: [...work.routes, r] });
                        setActive(r.key);
                      })
                    }
                  >
                    <Plus size={16} /> Criar rota
                  </Button>
                  <div className="distribution-route-tabs">
                    {work.routes.map((r) => (
                      <button
                        key={r.key}
                        aria-pressed={active === r.key}
                        onClick={() => setActive(r.key)}
                        style={{ borderLeft: `5px solid ${r.color}` }}
                      >
                        {r.plan.name}
                        <small>
                          {r.invoice_ids.length} notas · {r.plan.status}
                        </small>
                      </button>
                    ))}
                  </div>
                  {!current ? (
                    <p>Crie uma rota ou selecione notas para começar.</p>
                  ) : (
                    <>
                      {current.resource_warnings?.map((warning, i) => (
                        <Alert key={i} tone="info">
                          {warning}
                        </Alert>
                      ))}
                      <fieldset disabled={busy || locked}>
                        <label>
                          Nome da rota
                          <input
                            value={current.plan.name}
                            maxLength={160}
                            onChange={(e) =>
                              updateRoute(current.key, { name: e.target.value })
                            }
                          />
                        </label>
                        <label>
                          Cor
                          <input
                            type="color"
                            value={current.color}
                            onChange={(e) =>
                              updateRoute(
                                current.key,
                                {},
                                { color: e.target.value },
                              )
                            }
                          />
                        </label>
                        <label>
                          Motorista ativo
                          <select
                            value={current.plan.driver_id ?? ""}
                            onChange={(e) =>
                              updateRoute(current.key, {
                                driver_id: Number(e.target.value) || null,
                              })
                            }
                          >
                            <option value="">Selecione</option>
                            {drivers.map((d) => (
                              <option key={d.id} value={d.id}>
                                {d.nome}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Veículo ativo
                          <select
                            value={current.plan.vehicle_id ?? ""}
                            onChange={(e) =>
                              updateRoute(current.key, {
                                vehicle_id: Number(e.target.value) || null,
                              })
                            }
                          >
                            <option value="">Selecione</option>
                            {vehicles.map((v) => (
                              <option key={v.id} value={v.id}>
                                {v.placa} · {v.modelo}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Objetivo
                          <select
                            value={current.plan.objective}
                            onChange={(e) =>
                              updateRoute(current.key, {
                                objective: e.target.value as Plan["objective"],
                              })
                            }
                          >
                            <option value="duration">Menor tempo</option>
                            <option value="distance">
                              Menor distância na matriz viária
                            </option>
                          </select>
                        </label>
                        <AddressPicker
                          label="Origem e retorno"
                          initialAddress={current.plan.origin?.address ?? ""}
                          onSelect={(origin) =>
                            updateRoute(current.key, { origin })
                          }
                        />
                        <label>
                          Reutilizar origem
                          <select
                            value=""
                            onChange={(e) => {
                              const origin = work.routes.find(
                                (r) => r.key === e.target.value,
                              )?.plan.origin;
                              if (origin) updateRoute(current.key, { origin });
                            }}
                          >
                            <option value="">
                              Selecionar origem de outra rota
                            </option>
                            {work.routes
                              .filter(
                                (r) => r.key !== current.key && r.plan.origin,
                              )
                              .map((r) => (
                                <option key={r.key} value={r.key}>
                                  {r.plan.name} · {r.plan.origin?.address}
                                </option>
                              ))}
                          </select>
                        </label>
                        {current.plan.origin && (
                          <p>{current.plan.origin.address}</p>
                        )}
                      </fieldset>
                      <p>
                        {current.invoice_ids.length} notas ·{" "}
                        {work.notes
                          .filter((n) => current.invoice_ids.includes(n.id))
                          .reduce((s, n) => s + n.volumes, 0)}{" "}
                        volumes · até 10 notas por rota
                      </p>
                      <ol className="distribution-route-notes">
                        {current.invoice_ids.map((id, i) => {
                          const n = work.notes.find((n) => n.id === id)!;
                          return (
                            <li key={id}>
                              <strong>
                                {i + 1}. NF {n.number}
                              </strong>
                              <small>
                                {n.partner} · {n.volumes} volumes
                              </small>
                              {!locked && (
                                <>
                                  <div className="distribution-order">
                                    <button
                                      disabled={busy || i === 0}
                                      aria-label={`Subir NF ${n.number}`}
                                      onClick={() => move(current, i, -1)}
                                    >
                                      <ArrowUp size={14} />
                                    </button>
                                    <button
                                      disabled={
                                        busy ||
                                        i === current.invoice_ids.length - 1
                                      }
                                      aria-label={`Descer NF ${n.number}`}
                                      onClick={() => move(current, i, 1)}
                                    >
                                      <ArrowDown size={14} />
                                    </button>
                                    <button
                                      disabled={busy}
                                      onClick={() =>
                                        run(() => transfer(id, current.key, ""))
                                      }
                                    >
                                      Remover
                                    </button>
                                  </div>
                                  <select
                                    aria-label={`Transferir NF ${n.number}`}
                                    disabled={busy}
                                    value=""
                                    onChange={(e) =>
                                      run(() =>
                                        transfer(
                                          id,
                                          current.key,
                                          e.target.value,
                                        ),
                                      )
                                    }
                                  >
                                    <option value="" disabled>
                                      Transferir para outra rota
                                    </option>
                                    {work.routes
                                      .filter(
                                        (r) =>
                                          r.key !== current.key &&
                                          r.plan.status !== "CONFIRMADO",
                                      )
                                      .map((r) => (
                                        <option key={r.key} value={r.key}>
                                          {r.plan.name}
                                        </option>
                                      ))}
                                  </select>
                                </>
                              )}
                            </li>
                          );
                        })}
                      </ol>
                      {current.plan.result && (
                        <div className="distribution-result">
                          <strong>
                            {(current.plan.result.distance / 1000).toFixed(1)}{" "}
                            km
                          </strong>{" "}
                          · {Math.round(current.plan.result.duration / 60)} min
                          estimados
                          <p>
                            {current.plan.stops?.length ?? 0} paradas · inclui
                            retorno à origem
                          </p>
                        </div>
                      )}
                      {locked ? (
                        <Alert tone="info">
                          Rota confirmada. Alterações bloqueadas para preservar
                          a operação do motorista.
                        </Alert>
                      ) : (
                        <div className="distribution-route-actions">
                          <Button
                            disabled={
                              busy ||
                              !current.plan.origin ||
                              !current.plan.vehicle_id ||
                              !current.invoice_ids.length
                            }
                            onClick={() => run(() => calculate(current, true))}
                          >
                            Otimizar sequência
                          </Button>
                          <Button
                            variant="secondary"
                            disabled={
                              busy ||
                              !current.plan.origin ||
                              !current.plan.vehicle_id ||
                              !current.invoice_ids.length
                            }
                            onClick={() => run(() => calculate(current, false))}
                          >
                            Calcular ordem manual
                          </Button>
                          <Button
                            disabled={
                              busy ||
                              dirty ||
                              !current.plan.result ||
                              !current.plan.driver_id
                            }
                            onClick={() => run(() => confirm(current))}
                          >
                            Confirmar rota
                          </Button>
                        </div>
                      )}
                      <p>
                        <small>
                          Sem agenda de horários, a disponibilidade futura não
                          pode ser garantida. Confira motorista, veículo e
                          restrições antes de confirmar.
                        </small>
                      </p>
                    </>
                  )}
                </>
              )}
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
