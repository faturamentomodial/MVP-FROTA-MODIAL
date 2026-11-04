import { useEffect, useState } from "react";
import { Alert, Button } from "../../components/UI";
import { api } from "../../services/api";
import type { Point } from "./distribution";
export function AddressPicker({
  label,
  onSelect,
  initialAddress = "",
}: {
  label: string;
  onSelect: (point: Point) => void;
  initialAddress?: string;
}) {
  const [query, setQuery] = useState(initialAddress),
    [candidates, setCandidates] = useState<Point[]>([]),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    setQuery(initialAddress);
    setCandidates([]);
    setMessage("");
  }, [initialAddress]);
  async function search() {
    setBusy(true);
    setMessage("");
    setCandidates([]);
    try {
      const result = await api<{ candidates: Point[] }>(
        `/route-plans/geocode?address=${encodeURIComponent(query)}`,
      );
      setCandidates(result.candidates);
      if (!result.candidates.length)
        setMessage("Endereço não encontrado. Informe número, cidade e CEP.");
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="distribution-address">
      <label>
        {label}
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setCandidates([]);
          }}
          placeholder="Rua, número, cidade e CEP"
        />
      </label>
      <Button
        variant="secondary"
        disabled={query.trim().length < 5}
        loading={busy}
        onClick={search}
      >
        Buscar endereço
      </Button>
      {message && <Alert>{message}</Alert>}
      {candidates.length > 0 && (
        <div>
          <p>Confira e selecione o endereço correto.</p>
          {candidates.map((p, i) => (
            <button
              type="button"
              className="distribution-candidate"
              key={i}
              onClick={() => {
                onSelect({
                  address: p.address,
                  latitude: p.latitude,
                  longitude: p.longitude,
                });
                setCandidates([]);
              }}
            >
              {p.address}
              <small>
                {p.latitude.toFixed(5)}, {p.longitude.toFixed(5)}
                {p.house_number_found !== true
                  ? " · Número do imóvel não identificado; confira o ponto antes de validar."
                  : ""}
              </small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
