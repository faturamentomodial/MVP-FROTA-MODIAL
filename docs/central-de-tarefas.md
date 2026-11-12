# Central de Tarefas

Implementação isolada em React/TypeScript e FastAPI/SQLAlchemy, reutilizando JWT, perfis ADMIN/MOTORISTA, cadastro Driver, API client e componentes visuais. Não altera rotas, entregas, Positron ou Sankhya. Não adiciona dependências.

## Uso

Gestor: abrir **Central de Tarefas** no menu, preencher título, endereço e observações e clicar em **Publicar tarefa**. Acompanhar Disponíveis, Aceitas, Em andamento e Concluídas; cartões mostram identificador, responsável e horários.

Motorista: abrir **Tarefas**, escolher **Aceitar tarefa** e consultar **Minhas tarefas**. Clicar em **Marcar como concluída** conclui diretamente, sem formulário. **Histórico** mostra conclusões próprias. **Continuar minha rota** apenas navega para a operação atual.

Listas atualizadas após ações e a cada 15 segundos com a página visível. Requisições não se sobrepõem; o temporizador e as requisições são cancelados ao sair. As consultas têm páginas de até 200 registros; a interface busca lotes de 100 para mostrar toda a categoria.

## API

Todas as rotas exigem autenticação:

| Método | Endpoint | Perfil / finalidade |
| --- | --- | --- |
| POST | /api/tasks | ADMIN publica; JSON: titulo, endereco, observacoes |
| GET | /api/tasks?status=ACEITA | ADMIN acompanha; status opcional |
| GET | /api/tasks/available | Motorista ativo: disponíveis |
| GET | /api/tasks/mine | Motorista ativo: aceitas e em andamento próprias |
| GET | /api/tasks/mine?completed=true | Motorista ativo: histórico próprio |
| GET | /api/tasks/{id} | ADMIN ou motorista elegível com acesso à tarefa |
| POST | /api/tasks/{id}/accept | Motorista ativo: primeiro aceite atômico |
| POST | /api/tasks/{id}/complete | Motorista ativo: conclusão própria |

Listagens aceitam offset e limit (padrão 100; máximo 200). Criação rejeita campos extras, texto vazio e limites excedidos. Identidade deriva da sessão, sem driver_id fornecido pelo cliente. Aceite usa UPDATE condicional por status e ausência de responsável: somente uma requisição vence. Disputa ou repetição retorna 409; conclusão de terceiro retorna 403. Horários são UTC, apresentados em America/Sao_Paulo.

## Banco e arquivos

Migration `20261103_0009`, após `20261028_0008`: cria somente tasks, com referências a users e drivers, índices por status e por motorista/status e restrições de consistência. Campos: id, titulo, endereco, observacoes, status, created_by, driver_id, created_at, updated_at, accepted_at, started_at, completed_at.

Criados: backend/app/models/tasks.py, backend/app/api/tasks.py, backend/migrations/versions/20261103_0009_tasks.py, backend/tests/test_tasks.py, backend/tests/test_task_migration.py, frontend/src/pages/TasksPage.tsx e este documento.

Modificados: backend/app/models/__init__.py, backend/app/api/router.py, frontend/src/App.tsx, frontend/src/layouts/AdminLayout.tsx, frontend/src/layouts/DriverLayout.tsx e frontend/src/styles.css.

## Homologação e publicação posterior

1. Usar ambiente e banco exclusivos de homologação, com backup e configuração já existente; não apontar para produção.
2. Em backend, executar `alembic upgrade head` para aplicar a tabela e iniciar a API normalmente.
3. Em frontend, executar `npm run build` e disponibilizar a interface no ambiente de homologação.
4. Validar com um gestor e dois motoristas ativos, inclusive disputa simultânea, rejeição de conclusão por terceiro e conclusão durante uma rota ativa.
5. Executar em backend `python -m pytest -q` e em frontend `npm run build`.
6. Publicação em produção requer autorização posterior, backup e aplicação da migration antes da versão que acessa tasks. Nenhum deploy, push ou migration em produção foi executado nesta entrega.

EM_ANDAMENTO é reconhecido, mas não há ação de início nesta versão: o fluxo principal é DISPONIVEL -> ACEITA -> CONCLUIDA. Sem cancelamento, edição ou localização de tarefas nesta entrega. Atualização periódica pode levar até 15 segundos para refletir ações de outros usuários. Validar também no banco de homologação utilizado na operação; os testes automatizados usam SQLite e bancos temporários.

## Validation results

- Full backend suite: 74 passed; 1 setup error caused by Windows denying access to the default pytest temporary directory.
- Targeted rerun with a writable project temporary directory: 9 passed (tasks, migration and deployment tests), including the previously blocked test and the additional active-route preservation test.
- Frontend: TypeScript and Vite production build passed.
- git diff --check: passed.
- Browser/mobile visual validation and PostgreSQL staging concurrency validation remain to be performed during homologation.

## Tarefas na rota

O aceite e a inclus?o na rota s?o at?micos: falhas na geocodifica??o ou no c?lculo desfazem o aceite. O endere?o precisa produzir uma ?nica localiza??o. O c?lculo parte da ?ltima parada preservada ou da origem e mant?m o ponto de retorno; as estimativas representam o trecho restante. Concluir pela entrega tamb?m conclui a tarefa; concluir ou cancelar pela Central resolve a parada correspondente. Sem viagem ativa, a tarefa permanece em Minhas tarefas e n?o ? inserida automaticamente em uma viagem futura. N?o exige nova migration.
