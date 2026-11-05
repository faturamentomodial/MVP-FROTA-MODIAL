# Rotas estabelecidas e programação semanal

Implementação na branch `feat/rotas-estabelecidas`. Sem commit, push, merge,
deploy, reinício de serviços ou alteração de banco de produção.
As alterações locais que já existiam no início do trabalho foram preservadas.

## Uso

Em **Rotas**, cadastre o percurso sem motorista e sem veículo. Informe origem,
retorno (ou reutilize a origem), perfil, objetivo, dias habituais e observações.
Escolha endereços manuais ou notas fiscais. A pesquisa de endereços e a consulta
de notas reutilizam os endpoints existentes de geocodificação e Sankhya.
Selecione explicitamente um candidato geográfico para cada ponto.

Salve e calcule a rota, com a ordem manual ou otimização. Depois use **Programar
rota**, indicando data, motorista e caminhão. Dias habituais são informativos;
não criam recorrências automaticamente. A programação aparece para o motorista
somente na respectiva data, em `America/Sao_Paulo`.

O calendário permite navegar entre semanas, filtrar data/motorista/veículo/status,
visualizar o percurso, reagendar ou cancelar uma execução ainda não iniciada.
Para execuções vinculadas a uma viagem, há acesso ao rastreamento do veículo.
O rastreamento mantém seus próprios estados de ausência de posição e comunicação.

Os planejamentos anteriores continuam acessíveis na seção expansível da página.
Não são convertidos nem reatribuídos automaticamente.

## Persistência e integração operacional

- `route_templates`: percurso permanente em JSON e revisão otimista.
- `route_executions`: reserva de motorista/veículo, intervalo UTC, chave única
  de requisição, observações e vínculo único ao planejamento operacional.
- Cada execução cria um `RoutePlan` confirmado, com cópia profunda do percurso
  e revisão de origem. Nenhuma alteração posterior no modelo modifica essa cópia.
- O início usa `/trips` e `route_plan_id`, como antes. O vínculo `trip_id` é
  adquirido atomicamente; os índices existentes também impedem viagens abertas
  simultâneas para o mesmo motorista/veículo.
- A situação da execução é derivada da viagem: preparação e viagem iniciada
  aparecem como **Em andamento**; `FINALIZADA` aparece como **Concluída**.
  Não é criado outro ciclo operacional de viagens.
- Paradas por endereço reutilizam a tabela e as transições de entregas. A coluna
  `trip_invoices.is_address_stop` distingue essas paradas das notas fiscais.
  O identificador interno é `Parada N`, os volumes são zero, a interface mostra
  o endereço e não apresenta número fiscal ou volumes artificiais.
- Alteração de carga e reordenação operacional dessas execuções são bloqueadas
  para preservar a cópia e a associação entre parada e endereço. A ordem é
  definida no modelo antes da programação. Os fluxos avulsos anteriores mantêm
  as permissões e capacidades existentes.
- O histórico do percurso fica na cópia da execução e na versão inicial do
  planejamento operacional. O modelo usa revisão para concorrência, sem uma
  tabela adicional de todas as revisões do cadastro.

## Reservas e limites

Sem horário, a reserva cobre o dia local inteiro. Com horário, cobre a duração
de direção calculada pelo OSRM mais uma hora para carga/descarga; pode atravessar
a meia-noite. Intervalos adjacentes são permitidos. Reservas concorrentes do
mesmo motorista ou veículo são serializadas por escrita nos recursos antes da
consulta de conflitos, além de comparação atômica ao reagendar/cancelar.
Reservas canceladas e viagens concluídas liberam o intervalo.

O tempo adicional de uma hora é fixo nesta versão. A estimativa não substitui
a duração real da operação; atrasos podem impedir iniciar a próxima viagem,
pela proteção existente de viagem aberta. Planejamentos legados, sem data, não
geram reservas semanais. A operação deve revisar a agenda antes da saída.

Até dez notas fiscais por rota/planejamento. Rotas somente por endereço aceitam
até cem paradas. Até dez paradas, a otimização reutiliza o solucionador exato
existente, incluindo o custo até o retorno. Acima disso usa vizinho mais próximo,
uma heurística que não garante o ótimo global. A ordem manual permanece disponível.
O cadastro utiliza uma das duas formas de parada por vez.

São preservados os avisos de restrições de caminhões não consideradas pelo OSRM.
Nenhuma posição de rastreamento é estimada ou fabricada por este módulo.

## Migration

Arquivo: `backend/migrations/versions/20261105_0016_route_templates.py`.
Revisão anterior: `20261104_0015`.

Cria as duas tabelas e acrescenta `is_address_stop`, com `false` para registros
existentes. Ajusta a restrição de volumes para aceitar zero apenas nas paradas
por endereço, mantendo volumes positivos obrigatórios nas notas fiscais.
Nenhum planejamento ou histórico existente é convertido ou removido.

Aplicar **somente em banco local ou de homologação explicitamente configurado**,
depois de backup e revisão da conexão:

```powershell
cd backend
$env:DATABASE_URL = 'sqlite+pysqlite:///./homologacao_rotas.db'
.venv/Scripts/python -m alembic upgrade head
```

O exemplo usa um banco de homologação local. Para PostgreSQL, configurar a URL
do banco de homologação apropriado. Não executar usando a conexão de produção.
Em SQLite, Alembic recria a tabela de entregas em modo batch para ajustar a
restrição; é necessário espaço e janela de manutenção apropriados ao volume.
O downgrade é bloqueado se houver execuções ou entregas por endereço, para não
excluir histórico ou invalidar registros. Isso exige plano específico de rollback
após começar a usar o recurso.

## Arquivos de implementação

Backend:

- `app/models/route_templates.py`, `app/models/__init__.py`
- `app/schemas/route_templates.py`, `app/schemas/domain.py`
- `app/api/route_templates.py`, `app/api/route_plans.py`, `app/api/router.py`
- `app/api/trips.py`, `app/api/helpers.py`
- `app/services/route_scheduling.py`, `app/services/trips.py`, `app/services/deliveries.py`
- `app/models/entities.py`
- `migrations/versions/20261105_0016_route_templates.py`
- `tests/test_route_templates.py`, `tests/test_rollback_migration.py`

Frontend:

- `src/pages/admin/EstablishedRoutes.tsx`, `established-routes.css`
- `src/pages/admin/RoutesPage.tsx`, `RouteMapPage.tsx`, `TrackingPage.tsx`, `TripDetailPage.tsx`
- `src/components/AddressPicker.tsx`, `RouteMap.tsx`, `DeliveryRoute.tsx`
- `src/pages/driver/DriverHome.tsx`, `StartTripPage.tsx`, `DeliveryPage.tsx`
- `src/types/routePlans.ts`, `src/types/index.ts`

`TrackingPage.tsx` e `types/index.ts` já tinham alterações locais antes desta
implementação; foram acrescentadas somente as adaptações do novo recurso.
`SettingsPage.tsx` e os demais arquivos previamente alterados não fazem parte
desta entrega.

## Homologação manual

1. Aplicar a migration em banco de homologação. Entrar como gestor, abrir Rotas
   e cadastrar uma rota com endereços, sem motorista/veículo e sem NF-e.
2. Selecionar candidatos geográficos reais; informar retorno diferente da origem,
   reordenar paradas, calcular e conferir origem, sequência, retorno, km e tempo
   no mapa. Repetir com mais de dez paradas e com o modo manual.
3. Criar outra rota usando consulta Sankhya: conferir empresa/série, endereço e
   volumes. Validar nota duplicada e limite de dez notas. Consultas externas reais
   dependem das credenciais e disponibilidade dos provedores em homologação.
4. Programar a primeira rota em dois dias, com motoristas/caminhões diferentes.
   Conferir dias, placas, nomes, horários e filtros na semana correspondente.
5. Tentar reservar motorista e veículo em intervalos sobrepostos; conferir o
   bloqueio. Validar reserva sem horário e saída próxima da meia-noite.
6. Reagendar uma execução, trocar motorista/caminhão e conferir a atribuição.
   Cancelar outra e conferir que ela não pode iniciar viagem.
7. Na data programada, entrar como motorista e iniciar a saída. Fazer checklist,
   iniciar viagem, concluir paradas e registrar uma ocorrência. Finalizar a viagem.
   Conferir que a execução aparece concluída e que repetir o início é bloqueado.
8. Editar a rota original e conferir que o percurso da execução anterior continua
   igual. Programar novamente e conferir que usa os novos dados.
9. Abrir Mapa rotas, selecionar a rota e conferir os locais de coleta existentes.
   Na execução em andamento, abrir o rastreamento e conferir o veículo vinculado;
   sem posição disponível, não deve aparecer uma localização simulada.
10. Validar planejamentos confirmados anteriores, checklist, NF-e, entregas,
    ocorrências e finalização no fluxo legado. Conferir desktop e tela móvel.

Os testes automatizados usam SQLite e provedores simulados. PostgreSQL, navegador,
Sankhya e Positron reais requerem homologação no ambiente correspondente.

## Verificações executadas

- `npm run build`: aprovado, TypeScript e Vite.
- Testes focados: **40 aprovados**, cobrindo rotas novas, planejamentos legados,
  entregas, implantação SPA e rollback. Executados em duas chamadas: 39 testes
  aprovados na seleção e o teste de rollback aprovado após corrigir sua fixture.
  O rollback agora usa o conjunto de migrations da aplicação antiga que simula,
  em vez de aplicar a versão atual sobre um schema antigo propositalmente parcial.
- Suíte completa inicial: **110 aprovados e dois erros de preparação** por falta
  de permissão no diretório temporário padrão do Windows. Ambos os testes foram
  reexecutados com `--basetemp` dentro do projeto; SPA passou e rollback passou
  após a correção descrita acima. A suíte completa não foi repetida após isso.
- Migration incremental: teste em memória com registros anteriores preservados,
  repetição segura do upgrade e downgrade antes de existir histórico novo.
- Cadeia completa `alembic upgrade head`: aprovada em SQLite descartável criado
  exclusivamente para a verificação, sem usar a conexão configurada no `.env`.
- `git diff --check`: aprovado.
- Avisos de depreciação existentes de Starlette/AnyIO e Alembic permanecem.
