# Atualizações em tempo real

## Auditoria e decisão

O frontend usa React 18, Vite, React Router e estados locais. As leituras passam por
`frontend/src/services/api.ts`; não há React Query, Redux, cache compartilhado ou
infraestrutura anterior de eventos. Tarefas consultavam a API a cada 15 segundos;
a página inicial do motorista e o rastreamento, a cada 30 segundos.

O backend usa FastAPI, Uvicorn, SQLAlchemy 2, Alembic e PostgreSQL; os testes usam
SQLite. A autorização existente valida JWT e consulta o usuário no banco a cada
requisição. Sankhya fornece consultas de notas; Pósitron fornece posições por HTTP,
com sincronização já limitada a 30 segundos por processo.

Foi escolhido WebSocket nativo, já suportado por FastAPI/Uvicorn e pelo navegador.
Socket.IO exigiria bibliotecas de cliente e servidor sem necessidade neste protocolo
de avisos. Não foram adicionadas dependências. Referências:
[FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) e
[eventos SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/orm/session_events.html).

## Como funciona

- `backend/app/services/realtime.py` registra versões por módulo na transação que
  altera os dados. Captura flush ORM e INSERT/UPDATE/DELETE via Session.execute,
  incluindo os controles de concorrência de tarefas e rotas. Rollback desfaz versões.
- `realtime_versions` mantém uma linha por módulo, sem histórico crescente. Uma
  consulta de versões e uma consulta de identidades a cada segundo por processo
  atendem todos os sockets desse processo. Sem clientes, não há essas consultas.
  O banco compartilhado permite que um worker detecte commits de outro.
- `/api/realtime` recebe o JWT no primeiro frame, com prazo de dez segundos. Não
  há tokens na URL. A origem usa a lista `CORS_ORIGINS`. O servidor verifica usuário
  ativo e perfil, monitora revogação/alteração de perfil e expiração do JWT.
- Eventos contêm apenas `type` e nomes de módulos; não incluem IDs, registros,
  credenciais, notas, posições ou dados pessoais. Cada perfil recebe sua lista de
  módulos. Cada nova leitura continua passando pela autorização REST existente.
- `AuthProvider` mantém uma conexão por aba autenticada. Login/logout em outras
  abas são acompanhados por eventos de storage. A reconexão usa espera exponencial
  com variação aleatória e limite aproximado de 30 segundos; heartbeat e watchdog
  detectam conexões silenciosas. A conexão inicial e cada reconexão invalidam todos
  os módulos permitidos para recuperar alterações ocorridas offline.
- `useRealtimeEffect` refaz apenas os efeitos de leitura que dependem dos módulos
  alterados. Avisos próximos são agrupados em 150 ms. Não há F5, remount da árvore,
  nem reinicialização de formulários/rascunhos. Os efeitos de UI permanecem separados.
- Fila de tamanho um por cliente agrupa snapshots, e envios têm timeout. Sockets,
  assinaturas, tarefas, listeners e timers são liberados ao encerrar seus donos.

## Cobertura

Viagens e entregas, planejamentos e rotas estabelecidas/programadas, tarefas,
motoristas, veículos, coletas, ocorrências, checklists, indicadores, usuários e
rastreamento têm efeitos de leitura inscritos. O perfil exibido na navegação
também é atualizado por `/auth/me`. Respostas do checklist em preenchimento são
preservadas durante atualização da lista de itens.

O polling de tarefas e da tela inicial do motorista foi removido. O polling de
rastreamento permanece para obter novas posições da Pósitron: o provedor não envia
eventos ao sistema. A sincronização existente e as chamadas Sankhya foram mantidas.
Mudanças feitas diretamente nos provedores externos só aparecem depois da
importação/sincronização já oferecida pelo sistema.

## Arquivos e preparação para uma publicação futura

Foram adicionados serviço e endpoint de eventos, migration `20261110_0021`, hook e
cliente de WebSocket, testes backend/frontend e este documento. Foram ajustados
`main.py`, `api/router.py`, `models/__init__.py`, `useAuth.tsx`, efeitos de leitura
das páginas/componentes, `vite.config.ts` e `nginx.conf`.

Nenhum deploy é realizado por esta alteração. Antes de iniciar a versão nova em
um ambiente, aplicar `alembic upgrade head`. Não iniciar o backend novo contra
um schema sem a tabela de versões. O downgrade remove somente essa tabela.

Os proxies Vite e nginx estão preparados para upgrade WebSocket. Caddy já encaminha
WebSocket. A origem pública precisa constar em `CORS_ORIGINS`; serviços de hospedagem
também precisam permitir WebSockets. HTTPS usa `wss`. `VITE_API_URL` é respeitada.

Escritas feitas por SQL externo, scripts que não importam os modelos da aplicação
ou ferramentas diretamente no banco não passam pelos hooks. Para essas fontes,
seria necessário instrumentá-las ou adotar triggers/CDC. A solução atual cobre os
fluxos de escrita da aplicação e scripts que usam esses modelos e sessões.

## Validação

Backend: `cd backend && .venv/Scripts/python.exe -m pytest -q`.
Frontend: `cd frontend && npm test` e `npm run build`.

Os testes usam sessões WebSocket independentes para gestor, motorista e outra aba;
cobrem publicação/aceite de tarefa, retomada após desconexão, escrita em outro
processo, rollback, ausência de mudança, mutações em lote, limite de linhas,
perfis, JWT inválido/expirado, usuário desativado, origem e limpeza de assinaturas.
O cliente é testado com relógio e WebSocket simulados para agrupamento, reconexão,
ressincronização, ausência de duplicação, expiração, encerramento e watchdog.

Na execução de 10/11/2026, a suíte completa teve 159 aprovações e quatro falhas
preexistentes, reproduzidas numa cópia limpa do commit original: os testes
`test_master_full_panel_access_and_user_management`, `test_purchasing_permissions`
e `test_role_changes_apply_to_existing_sessions` tentam criar usuários como ADMIN,
embora a implementação exija MASTER; `test_purchasing_can_read_map_without_management_access`
usa um mock de geocodificação que não aceita o argumento `fetch`. Essas regras e
esses testes não foram alterados. Uma rodada complementar aprovou 33 testes de
tempo real, migrations, rastreamento e Sankhya. O frontend aprovou oito testes e o
build de produção.

A rodada final, após incluir verificações adicionais de autenticação e expiração
da conexão ativa, aprovou os 29 testes de tempo real, cache de geocodificação e
correções de localização. O encerramento por expiração também considera a diferença
de resolução entre o relógio de parede e o temporizador assíncrono no Windows.

Esses testes simulam dispositivos distintos. Não equivalem a validação física em
celulares/redes diferentes, nem a teste de carga ou integração em PostgreSQL real.
Para homologação: abrir gestor e motorista em navegadores/dispositivos diferentes;
publicar e aceitar uma tarefa, confirmar uma rota, concluir uma entrega e editar
um cadastro; verificar as telas correspondentes sem F5. Interromper a rede de um
dispositivo, alterar dados no outro e verificar a sincronização ao reconectar.
Manter um formulário parcialmente preenchido durante os avisos para verificar
a preservação do rascunho. Confirmar que perfis restritos continuam recebendo 403
nas APIs que não podem acessar.
