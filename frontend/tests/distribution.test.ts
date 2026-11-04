import { test } from "node:test";
import assert from "node:assert/strict";
import {
  insideRectangle,
  toggleSelection,
  availableIds,
  newRoute,
  serialize,
} from "../src/pages/admin/distribution.ts";

test("seleção individual, múltipla e desmarcação preservam as demais notas", () => {
  let selected = toggleSelection([], "a");
  selected = toggleSelection(selected, "b");
  assert.deepEqual(selected, ["a", "b"]);
  assert.deepEqual(toggleSelection(selected, "a"), ["b"]);
  assert.deepEqual(toggleSelection(["a"], "a"), []);
});
test("retângulo inclui limites, aceita cantos invertidos e exclui pontos externos", () => {
  const a = { lat: -24, lng: -47 },
    b = { lat: -23, lng: -46 };
  const point = (latitude: number, longitude: number) => ({
    latitude,
    longitude,
    address: "Teste",
  });
  assert.equal(insideRectangle(point(-23.5, -46.5), a, b), true);
  assert.equal(insideRectangle(point(-24, -47), b, a), true);
  assert.equal(insideRectangle(point(-22, -46.5), a, b), false);
  assert.equal(insideRectangle(point(-23.5, -48), a, b), false);
});
test("notas atribuídas ficam fora da seleção de disponíveis", () => {
  const notes = [{ id: "a" }, { id: "b" }, { id: "c" }] as any;
  const routes = [{ invoice_ids: ["b"] }] as any;
  assert.deepEqual(availableIds(notes, routes), ["a", "c"]);
});
test("serialização mantém identidade e ordem, descarta dados operacionais somente leitura", () => {
  const route = newRoute(0);
  route.invoice_ids = ["b", "a"];
  route.plan.id = 4;
  route.plan.status = "CONFIRMADO";
  const data = serialize({
    id: 1,
    name: "Dia",
    revision: 2,
    notes: [],
    routes: [route],
  });
  assert.deepEqual(data.routes[0].invoice_ids, ["b", "a"]);
  assert.equal("status" in data.routes[0].plan, false);
  assert.equal(data.revision, 2);
});
