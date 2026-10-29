# Módulo Rotas — Entrega A

Implementado na branch feature/modulo-rotas-entrega-a, sem commit, push ou deploy.

## Inspeção e reutilização

Inspecionados App.tsx, AdminLayout.tsx, DeliveryRoute.tsx, DeliveryOrderEditor.tsx, TrackingPage.tsx, entities.py, domain.py, router.py, trips.py, tracking.py e o histórico Alembic 0001–0007. Reutilizados require_admin, get_db, Vehicle, TimestampMixin, api, Button, Alert, layout administrativo e Leaflet. DeliveryRoute e DeliveryOrderEditor representam entregas operacionais e foram preservados. Pósitron permanece intocado.

## Persistência e API

Duas tabelas isoladas: route_plans e route_plan_versions. Notas planejadas, origem, paradas, resultado viário e matriz são documentos JSON validados por Pydantic, versionados integralmente. Não há vínculo com trips, reserva de veículo ou alteração de tabela operacional. Esta opção mantém a Entrega A pequena; normalização pode ser feita quando consultas por nota exigirem índices próprios.

Todas as APIs /api/route-plans exigem administrador:
- GET/POST na coleção: listar (limit/offset) e criar rascunho.
- GET/PUT /{id}: consultar e substituir dados do rascunho; o PUT adiciona, edita, remove notas e altera a sequência. Exige revision.
- GET /geocode?address=...: busca candidatos; seleção humana obrigatória, inclusive candidato único.
- GET /providers: capacidades e limitação de caminhões.
- POST /{id}/matrix: matriz viária e correspondência das paradas.
- POST /{id}/calculate: {revision, optimize:true|false}; calcula, salva matriz, geometria e sequência.
- POST /{id}/confirm: {revision}; exige resultado calculado e torna o plano imutável.
- GET /{id}/versions: histórico completo.

Cada gravação usa compare-and-swap por revisão e estado, retornando 409 em conflito. Falhas do provedor não gravam resultados parciais. Editar qualquer dado invalida o cálculo anterior. Notas com coordenadas idênticas são agrupadas numa parada, com seus números e volumes preservados; a sequência manual é por primeira ocorrência da parada.

## Provedores e configuração

Adaptadores reais Photon (geocodificação) e OSRM (table/route), configurados no backend, sem dependência da Pósitron. As URLs ficam vazias por padrão; sem configuração retorna 503. Configure instâncias próprias ou contratadas compatíveis com os contratos:

```dotenv
ROUTES_GEOCODER_URL=https://photon.komoot.io
ROUTES_ROUTER_URL=https://router.project-osrm.org
ROUTES_TIMEOUT_SECONDS=15
ROUTES_MIN_INTERVAL_SECONDS=1
```

As URLs acima são servidores públicos de demonstração para avaliação manual de baixo volume, sem garantia operacional. A instância OSRM deve oferecer table com annotations=duration,distance e route com GeoJSON. Os endereços são enviados ao geocodificador; coordenadas são enviadas ao roteador. O mapa utiliza tiles OpenStreetMap. Não configure segredos nas URLs. Timeout, resposta inválida, 429 e destinos inacessíveis interrompem o cálculo, sem fallback em linha reta. A limitação local é por processo e serviço; múltiplos workers exigirão limite compartilhado para respeitar a quota agregada.

Documentação: https://project-osrm.org/docs/v5.24.0/api/ e https://github.com/komoot/photon

OSRM driving NÃO suporta aqui altura/peso/eixos/restrições legais de caminhões. A interface e o resultado informam explicitamente essa limitação. O perfil truck não deve ser interpretado como validação de circulação de caminhão.

Held-Karp calcula a sequência exata de até 10 destinos em matriz assimétrica: origem fixa e retorno ao mesmo ponto, sem janelas de entrega ou capacidade. OR-Tools foi avaliado: acrescentaria dependência binária e configuração sem benefício neste limite; é indicado para múltiplos veículos, capacidades e janelas na etapa seguinte. O objetivo distância minimiza a soma das distâncias dos trechos da matriz OSRM, que representam caminhos escolhidos pelo perfil driving, normalmente por tempo; não é garantia do menor caminho global por distância na malha viária. Os tempos não incluem trânsito ao vivo ou serviço na parada.

## Executar localmente

Use PostgreSQL LOCAL e confira DATABASE_URL antes de qualquer comando Alembic. Não execute em produção.

1. No backend, ative .venv e instale requirements-dev.txt quando necessário.
2. Configure DATABASE_URL para o PostgreSQL local e as variáveis ROUTES_* acima.
3. Na pasta backend, execute `python -m alembic upgrade head` somente no banco local. A migration 0008 é aditiva e possui downgrade removendo apenas as duas tabelas de planejamento. Nenhuma migration em banco externo foi executada nesta entrega.
4. Execute `python -m uvicorn app.main:app --reload`.
5. Na pasta frontend execute `npm.cmd run dev` (ou npm run dev em outros shells).
6. Entre como administrador e abra /admin/rotas. Crie nome, origem, veículo, notas/destinos; reutilize destino para duas notas no mesmo endereço; otimize, altere com setas, calcule ordem manual e confirme.

`Salvar rascunho` permite continuar depois sem origem ou veículo. Cada nota salva exige um destino selecionado. A lista mostra os 50 planos mais recentes; a API suporta paginação. Planos confirmados são somente leitura. O campo source=MANUAL e external_id fica reservado para a futura ingestão; Sankhya não foi implementado.

## Validação e limites

Testes automatizados usam respostas controladas apenas dentro do pytest, nunca expostas como roteamento real na aplicação. Cobrem dez notas/nove paradas, persistência, confirmação, revisão desatualizada, sequência manual, ambiguidade/ausência de endereço, indisponibilidade, timeout, limite local, matriz incompleta, autorização e migration upgrade/downgrade em SQLite em memória. O teste de concorrência é conflito de revisão, sem ensaio simultâneo PostgreSQL. Validação visual em navegador e consulta real dos provedores com endereços de operação continuam pendentes; build não substitui essa homologação.

Comandos: `python -m pytest tests -q -p no:cacheprovider` na pasta backend e `npm.cmd run build` na pasta frontend. Resultado final registrado no relatório da entrega.

## Entregas seguintes

B (escopo a confirmar): homologar provedor com restrições reais de caminhão, testes simultâneos PostgreSQL e UI, políticas de quota compartilhada, capacidade/janelas, retorno opcional e eventual conversão explícita em viagem operacional. A confirmação atual não inicia viagem.

C: adaptador de ingestão Sankhya, mapeamento e validação de documentos/endereços, idempotência por identificador externo, autenticação própria, reconciliação e auditoria. Nenhuma chamada ou credencial Sankhya foi adicionada.

Resultado executado em 28/10/2026: 56 testes aprovados em 102,36 s (4 avisos de depreciação preexistentes). Build frontend aprovado: TypeScript + Vite, 1622 módulos, bundle JS 442,35 kB / gzip 130,62 kB. O build foi repetido fora do sandbox após bloqueio de leitura do esbuild. Nenhum deploy foi realizado.

## Arquivos da entrega

Criados:
- backend/app/models/route_plans.py
- backend/app/schemas/route_plans.py
- backend/app/services/route_planning.py
- backend/app/api/route_plans.py
- backend/migrations/versions/20261028_0008_route_plans.py
- backend/tests/test_route_plans.py
- frontend/src/pages/admin/RoutesPage.tsx
- docs/ROTAS_ENTREGA_A.md

Modificados:
- backend/app/models/__init__.py
- backend/app/core/config.py
- backend/app/api/router.py
- frontend/src/App.tsx
- frontend/src/layouts/AdminLayout.tsx


## Busca gratuita e circuito com retorno

O provedor padrão de busca agora é Nominatim (OpenStreetMap), sem chave ou cobrança por consulta no servidor público. Configure:

```dotenv
ROUTES_GEOCODER_PROVIDER=nominatim
ROUTES_GEOCODER_URL=https://nominatim.openstreetmap.org
ROUTES_ROUTER_URL=https://router.project-osrm.org
```

Reinicie/recrie o backend após alterar o ambiente. A pesquisa manual restringe resultados ao Brasil, solicita português e detalhes do endereço. A interface avisa quando o resultado não informa número: confira o marcador no mapa antes de operar. A cobertura depende do cadastro OpenStreetMap e não há garantia de precisão por imóvel. Photon continua disponível com ROUTES_GEOCODER_PROVIDER=photon e sua URL compatível.

O servidor público limita o conjunto da aplicação a uma consulta por segundo, não permite autocomplete e não oferece SLA. O adaptador aplica intervalo mínimo de um segundo por processo e cache limitado de 256 pesquisas em períodos de 24 horas. Use um único worker para baixo volume; múltiplas instâncias exigem limite/cache compartilhado ou servidor próprio. Não envie dados pessoais ou confidenciais ao serviço público. O mapa permanece Leaflet/OpenStreetMap. Nenhuma integração com Google foi mantida.

Novos cálculos otimizados e manuais incluem a volta à origem na geometria, distância e duração. A otimização considera o custo do retorno ao escolher a ordem. Resultados antigos são preservados: recalcule rascunhos; para planos confirmados, crie outro planejamento. OSRM continua sem trânsito ao vivo ou restrições específicas de caminhão.

Referências: https://nominatim.org/release-docs/latest/api/Search/ e https://operations.osmfoundation.org/policies/nominatim/
