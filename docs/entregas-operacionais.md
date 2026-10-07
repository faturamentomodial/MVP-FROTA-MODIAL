# Entregas operacionais — auditoria e implementação

## Atualização: motorista pode alterar a ordem

A ordem fixa por ID foi substituída por `TripInvoice.position`, conforme a solicitação posterior de permitir ao motorista ajustar sua rota. A migration `20261007_0004_delivery_order` adiciona `trip_invoices.position`, o índice `(trip_id, position)` e `trips.delivery_revision`. Notas existentes recebem a posição correspondente ao ID anterior, preservando a sequência de cada rota. Novas cargas recebem posições sequenciais.

`PUT /api/trips/{trip_id}/delivery-order` recebe `{ "invoice_ids": [3, 1, 2], "revision": 4 }`. A lista precisa conter todas as notas da própria rota, exatamente uma vez. A API valida motorista, rota ativa, revisão atual e manutenção das posições visuais de entregas já tratadas. Nenhuma nota é removida ou marcada como entregue por uma mudança de ordem.

Na tela da rota, **Alterar ordem** abre um editor com setas e **Salvar ordem**. **Deixar NF para depois** envia a entrega atual para o fim das pendentes. Se ela estava em andamento, volta para `PENDENTE`, preservando o primeiro `started_at`; a retomada não sobrescreve esse horário. O adiamento é registrado em `AuditLog`, sem criar ocorrência de não entrega. Entregas finalizadas e ocorrências anteriores continuam no histórico.

O backend usa a posição persistida para liberar a próxima entrega. A revisão da rota serializa operações e rejeita alterações baseadas em dados antigos, inclusive no SQLite. Ações de entrega, edição de carga, início e encerramento de viagem participam do mesmo controle. A interface só confirma a nova ordem depois da resposta do backend, e o gestor vê a sequência atualizada.

Validação desta atualização: 26 testes aprovados, 0 falhando, incluindo 8 novos cenários de ordem/adiamento; build TypeScript/Vite aprovado. Containers do localhost reconstruídos com a nova migration aplicada na inicialização.

Arquivos desta evolução: `backend/app/models/entities.py`, `backend/app/schemas/domain.py`, `backend/app/api/helpers.py`, `backend/app/api/trips.py`, `backend/app/services/deliveries.py`, `backend/app/services/trips.py`, a migration `20261007_0004_delivery_order.py`, `backend/tests/test_delivery_order.py`, `backend/tests/test_delivery_migration.py`, `frontend/src/types/index.ts`, `frontend/src/components/DeliveryOrderEditor.tsx`, `frontend/src/components/DeliveryRoute.tsx`, `frontend/src/pages/driver/DriverHome.tsx` e `frontend/src/styles.css`.

As seções abaixo descrevem a implementação inicial; referências à ordem fixa por ID e ao fluxo sem adiamento foram substituídas pelas regras desta atualização.

## Sistema existente auditado

- Frontend React/TypeScript/Vite: páginas por perfil, layouts mobile e administrativo, componentes UI compartilhados e cliente fetch com JWT.
- Backend FastAPI/Pydantic/SQLAlchemy: autenticação JWT, dependências por perfil, serviços de viagens e auditoria, paginação e uploads.
- PostgreSQL no Docker; SQLite nos testes. Evolução do banco com Alembic.
- `Trip` já representa a saída/rota, com motorista, veículo, checklist, notas e ocorrências. `TripInvoice` já permite várias notas e volumes. A ordem existente é `TripInvoice.id`; ela foi mantida.
- Cadastros de motoristas e veículos, abertura de saída, carga, checklist, início e retorno, ocorrências gerais e dashboard já existiam. Os 5 testes de regressão passaram antes das alterações.
- A nota não possui cliente, endereço, cidade, UF, telefone ou peso. Nenhum desses campos foi inventado.
- As ocorrências existentes possuem categorias como `PROBLEMA_ENTREGA` e `CLIENTE_AUSENTE`, mas não tinham vínculo com uma nota. Os motivos específicos são gravados na nota e a ocorrência reutiliza essas categorias existentes.

## Alterações de domínio e banco

Migration `20261007_0003_deliveries`, após `20260922_0002`:

- `trip_invoices`: `status` (padrão `PENDENTE`), `started_at`, `delivered_at`, `occurrence_at`, `occurrence_reason`, `occurrence_note`.
- `occurrences`: `invoice_id` opcional, FK `fk_occurrence_invoice` e restrição única `uq_occurrence_invoice`, que também garante o índice único por nota. Ocorrências gerais continuam com vínculo nulo.
- Nenhuma tabela nova. O índice existente em `trip_invoices.trip_id` atende às consultas de sequência por rota.
- Dados antigos são preservados. Notas antigas recebem `PENDENTE`, sem horários ou resultados inventados; viagens históricas não são reabertas. Para relatórios, ausência de horário indica que não há evidência operacional de entrega individual.
- A migration inicial usa `Base.metadata.create_all` com o modelo atual. A nova migration verifica a existência das colunas para também funcionar em instalações novas.

Aplicação no ambiente de execução:

```bash
cd backend
alembic upgrade head
```

Os testes aplicam a migration somente em um banco temporário isolado. O banco operacional não foi migrado nesta sessão.

## API

Todos os caminhos abaixo são relativos a `/api`:

- `GET /trips/{trip_id}` e `/trips/current`: notas com estado e histórico operacional.
- `GET /trips/{trip_id}/deliveries`: lista na ordem existente.
- `GET /trips/{trip_id}/deliveries/{invoice_id}`: consulta individual, inclusive futura ou histórica.
- `POST /trips/{trip_id}/deliveries/{invoice_id}/start`: `PENDENTE → EM_ENTREGA`.
- `POST /trips/{trip_id}/deliveries/{invoice_id}/finish`: `EM_ENTREGA → ENTREGUE`.
- `POST /trips/{trip_id}/deliveries/{invoice_id}/occurrence`: `EM_ENTREGA → NAO_ENTREGUE`, com `{ "motivo": "CLIENTE_FECHADO", "observacao": "Loja fechada" }`.
- `POST /trips/{trip_id}/finish`: agora impede retorno com entregas não tratadas.
- `GET /dashboard`: acrescenta `delivery_routes`, com totais, entregues, não entregues/ocorrências, pendentes e última entrega, respeitando os filtros de viagem existentes. Lista até 100 rotas mais recentes. O filtro de tipo de ocorrência continua aplicado aos indicadores de ocorrência.
- API de ocorrências existente: expõe `invoice_id` quando vinculado a uma entrega.

Motivos: cliente fechado, cliente não quis receber, destinatário ausente, endereço não localizado, mercadoria recusada e outro. Outro exige observação não vazia.

Consulta exige autenticação e propriedade da rota para motorista. Alteração exige perfil motorista, propriedade da rota, nota vinculada, viagem em andamento, estado válido e resolução de todas as notas anteriores. Gestores podem consultar, mas não executar ações do motorista.

Atualizações condicionais no banco impedem alterações duplicadas. Repetição retorna `409`, sem mudar horários nem criar outra ocorrência/auditoria. PostgreSQL também serializa ações da rota usando bloqueio de linha. Mudança de estado, ocorrência e auditoria são persistidas na mesma transação. A finalização da viagem utiliza o mesmo bloqueio de rota.

## Horários e rastreabilidade

O relógio oficial é `datetime.now(UTC)` no servidor, equivalente ao mecanismo de backend já existente. Não são usados horários do navegador. Horários em payloads de início/finalização são ignorados; no payload tipado de ocorrência, campos extras são rejeitados.

Datas são persistidas em UTC e a API retorna timezone explícito. Como SQLite perde o timezone, o serializer restaura UTC. O frontend apenas formata em `America/Sao_Paulo`.

`AuditLog` existente registra usuário, nota, rota, motorista, ação, quando, estado anterior e novo. A nota conserva os horários de início e resultado; resolver a ocorrência no painel do gestor não sobrescreve o histórico da entrega.

## Interface

- `DriverHome`: resumo e lista de entregas com progresso, ordem, status e horários. Consulta de notas futuras permitida; operação liberada somente para a atual.
- `DeliveryPage`: detalhes reais da nota, início, finalização, formulário de ocorrência, confirmação com horário retornado pela API e consulta de histórico.
- `DeliveryRoute`: componente compartilhado entre motorista e detalhe administrativo.
- Dashboard existente: tabela de resultados por rota e acesso aos detalhes.
- Ações bloqueadas durante a requisição, sem conclusão visual antes da resposta do backend. Em erro, apresenta mensagem, tenta atualizar a rota e oferece atualização manual. Não há fila offline.
- Checklist, carga, ocorrências gerais, cadastros e login mantêm os fluxos anteriores. O teste de viagem completa foi atualizado para resolver notas antes do retorno, conforme a nova regra de negócio.

## Validação

Testes automatizados em `test_deliveries.py` cobrem 1 nota, 5 notas (3 entregues, 1 ocorrência, 1 pendente), sequência, consulta futura, horários do servidor, histórico, dashboard, motivos, observação, inexistência, autenticação, outro motorista, nota de outra rota, duplicidade e concorrência de finalização/ocorrência.

`test_delivery_migration.py` valida instalação nova, atualização do esquema anterior, preservação de nota/volumes e relacionamento único da ocorrência.

```bash
cd backend
python -m pytest -q
cd ../frontend
npm run build
```

Não foi realizada validação visual em navegador nem teste em PostgreSQL real nesta sessão. Os testes de integração utilizam SQLite e o frontend é verificado por TypeScript e build Vite.

Resultado final: 5 testes existentes passando, 0 falhando; 13 novos testes passando, 0 falhando. Total: 18 testes aprovados. Build TypeScript/Vite aprovado. Permanecem avisos de depreciação das dependências Starlette/AnyIO e configuração do pytest-asyncio.

- [x] Fluxo com 1 nota
- [x] Fluxo com 5 notas
- [x] Finalização automática de data/hora
- [x] Ocorrência automática de data/hora
- [x] Bloqueio de duplicidade, inclusive requisições concorrentes
- [x] Segurança do motorista
- [x] Regressão das funcionalidades cobertas pelos testes existentes
- [ ] Validação visual em navegador
- [ ] Validação em PostgreSQL real

## Arquivos de código alterados/criados

Backend:

- `app/models/enums.py`
- `app/models/entities.py`
- `app/schemas/domain.py`
- `app/api/helpers.py`
- `app/api/trips.py`
- `app/api/dashboard.py`
- `app/services/trips.py`
- `app/services/deliveries.py` (novo)
- `migrations/versions/20261007_0003_deliveries.py` (novo)
- `tests/test_flow.py`
- `tests/test_deliveries.py` (novo)
- `tests/test_delivery_migration.py` (novo)

Frontend:

- `src/types/index.ts`
- `src/utils/format.ts`
- `src/App.tsx`
- `src/styles.css`
- `src/components/DeliveryRoute.tsx` (novo)
- `src/pages/driver/DeliveryPage.tsx` (novo)
- `src/pages/driver/DriverHome.tsx`
- `src/pages/admin/TripDetailPage.tsx`
- `src/pages/admin/DashboardPage.tsx`

O build também atualiza `frontend/dist` e `frontend/tsconfig.app.tsbuildinfo`. A execução da suíte atualiza o banco de testes e caches Python.
