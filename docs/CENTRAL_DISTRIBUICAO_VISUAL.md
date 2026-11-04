# Central de Distribuição Visual — implementação local

Branch: `feature/central-distribuicao-visual`. As alterações locais preexistentes em permissões, SettingsPage, TrackingPage e outros arquivos foram preservadas. Não há push, merge, deploy, consulta produtiva ou migration produtiva nesta entrega.

## Comportamento

A tela `/admin/rotas` abre a central com três áreas responsivas: notas, mapa Leaflet predominante e montagem das rotas. Os painéis podem ser recolhidos. O botão Planejamentos anteriores preserva a interface anterior e o acesso aos RoutePlan antigos.

Crie ou abra uma distribuição. Busque uma NF no Sankhya e escolha o documento por empresa/série/NUNOTA; ou cadastre manualmente. A NF pode ser salva com endereço pendente. Busque e escolha explicitamente um candidato para validar a localização: nenhum ponto fictício é gerado. Resultados sem número do imóvel mostram aviso; o mapa só recebe notas com coordenadas validadas. Notas já salvas podem ser editadas enquanto disponíveis.

Clique em marcadores ou nos checkboxes para acumular/desmarcar seleções. A lista tem busca, filtros, seleção de disponíveis do filtro e contadores. Selecionar área permite desenhar um retângulo por dois cliques em cantos opostos, com prévia geométrica, confirmação aditiva e cancelamento. Apenas notas disponíveis entram na seleção geográfica. Uma nova região substitui o desenho, preservando a seleção já confirmada.

Leaflet.draw foi considerado: a central precisa apenas de retângulo, sem edição de geometria persistida. A solução equivalente usa `L.rectangle`, bounds e eventos já disponíveis no Leaflet 1.9.4 instalado. Não houve instalação de biblioteca de desenho. Polígonos não foram implementados. Zoom e pan ficam ativos durante o desenho.

A seleção pode gerar uma rota imediatamente, ou entrar na rota em edição. Cada rota tem cor, nome, origem/retorno, motorista e veículo ativos, objetivo, ordem manual, otimização, distância, tempo e confirmação. Remover uma nota do rascunho devolve-a às disponíveis. Transferência explícita entre rascunhos exige confirmação. Notas atribuídas não entram novamente na seleção.

Inclusão/edição/exclusão de NF, criação de rota e atribuições são gravadas no backend. Campos da rota e ordem manual têm Salvar rascunho; calcular salva primeiro as alterações pendentes. Há indicador de alterações e aviso ao recarregar/sair. A falha de gravação mantém as alterações locais para revisão; um conflito exige recarregar explicitamente.

Os marcadores mantêm a mesma instância Leaflet. As camadas são separadas entre notas, percursos estimados e posições reais dos veículos. O enquadramento acompanha mudanças nas coordenadas, não cliques de seleção. Marcadores numerados usam laranja (disponível), azul (selecionado), cor da rota e cinza (entrega operacional ENTREGUE). Endereços pendentes ficam sinalizados no painel, sem marcador fictício.

## Persistência, identidade e concorrência

Migration aditiva `backend/migrations/versions/20261104_0012_distributions.py`, posterior à 0011:

- `distributions`: conjunto operacional explícito, nome, revisão, documento JSON validado com notas e atribuições, autor e timestamps.
- `distribution_versions`: snapshots imutáveis de cada revisão, incluindo atribuições e metadados; unicidade por conjunto/revisão e FK.
- `distribution_routes`: vínculo referencial de cada RoutePlan com um único conjunto, chave estável e cor; plan_id é PK/FK, distribution_id é FK indexada.

Notas e atribuições ficam no documento do conjunto, seguindo o padrão JSON dos planejamentos existentes. As referências internas são validadas no backend antes da transação: IDs únicos, identidade fiscal única, apenas localizações validadas, cada nota em no máximo uma rota e limite por rota. Não se trata de localStorage ou estado apenas do frontend.

O contexto de unicidade é **uma distribuição**. Sankhya: `(source, company, series, external_id/NUNOTA)`. Manual: empresa, série e número com normalização de espaços nas extremidades e caixa; UUID é identidade de edição, não permite contornar duplicação fiscal. Se empresa/série forem omitidas na nota manual, número é único entre notas manuais sem esses dados. Conjuntos diferentes são contextos independentes; não existe bloqueio fiscal global entre distribuições distintas. Reutilizar a mesma distribuição para o mesmo lote operacional.

O contrato legado TripInvoice tem unicidade `(trip_id, numero_nota)`. Para preservá-lo, documentos de mesmo número e empresas/séries diferentes podem coexistir no conjunto, mas devem ir para rotas diferentes. A API rejeita juntá-los na mesma rota, com mensagem explícita.

PUT usa compare-and-swap da revisão da distribuição e das revisões dos RoutePlan afetados; notas, vínculos, invalidação de cálculos e históricos são gravados na mesma transação. Conflitos retornam 409 e fazem rollback. A validação de unicidade ocorre dentro do documento protegido por revisão. O PUT não pode vincular RoutePlan de outro conjunto nem remover silenciosamente rotas salvas. Rotas confirmadas não permitem alterações em dados, cor, notas ou atribuições; outras rotas do conjunto continuam editáveis. Alterações diretas via PUT /route-plans em planejamentos gerenciados pela central são bloqueadas.

Cálculo/confirmação continuam usando os endpoints e revisões atuais de RoutePlan. GET da distribuição incorpora a sequência/cálculo atualizados e status de entregas pelo Trip vinculado. O início da viagem continua exclusivamente pelo fluxo atual do motorista, com validações e índices existentes contra veículo/motorista em viagens simultâneas. Não há agenda de início/fim previsto: conflitos futuros entre rascunhos não podem ser afirmados. Viagens atualmente abertas com o mesmo recurso são informadas como aviso na central; a validação operacional definitiva permanece no início da saída.

## Endpoints

Todos exigem `require_admin` (ADMIN/MASTER, conforme permissões existentes):

- `GET /api/distributions?limit=100&offset=0`: lista resumida, paginável.
- `POST /api/distributions`: `{name}` cria conjunto vazio.
- `GET /api/distributions/{id}`: conjunto, notas, RoutePlan atuais, resultados, status operacionais e avisos de recursos.
- `PUT /api/distributions/{id}`: snapshot com `{name,revision,notes,routes}`. Cada rota tem key, plan_id, color, invoice_ids ordenados e plan (campos de PlanInput/revision; invoices derivadas das notas).
- `GET /api/distributions/{id}/versions`: histórico integral de distribuição.

Alterações nos endpoints atuais: PUT de RoutePlan gerenciado orienta editar pela central; confirmação da central exige motorista e rejeita números visíveis duplicados. Demais contratos de viagens, entregas e Tasks preservados. PlanInput ganhou company, series e partner opcionais nas notas, mantendo leitura de dados antigos. Geocodificação Photon também informa ausência de número. O adaptador Sankhya preserva executeQuery e apresenta recusa/autorização de forma acionável, sem registrar a resposta potencialmente sensível.

## Limites e homologação

Até 1.000 notas por conjunto e 100 rotas; até 10 notas por rota, tanto manual quanto otimizada, preservando a capacidade operacional existente. Para um conjunto maior, criar múltiplas rotas de até 10 notas. Held-Karp tem guarda explícita de no máximo 10 paradas no serviço, sem execução exponencial fora desse limite. Não há otimização conjunta de frota, janelas de horário ou capacidade física.

OSRM driving não valida altura, peso, eixos, rodízio ou restrições legais de caminhões. As estimativas incluem retorno à origem, sem trânsito em tempo real nem tempo de atendimento. O objetivo distância compara os trechos devolvidos pela matriz viária. Falhas, limites e indisponibilidade não geram aproximação fictícia.

A visualização opcional de veículos usa apenas `GET /api/tracking`, atualizado a cada 30 segundos enquanto habilitado, filtrando veículos vinculados às rotas. Não houve alteração em tracking.py, credenciais ou integração Pósitron. Sem vínculo ativo/posição recebida, o veículo não aparece. O popup informa a última atualização em America/Sao_Paulo. Proximidade geográfica não muda entrega; cinza vem exclusivamente do status operacional ENTREGUE.

Sankhya real não consultado. É necessário homologar credenciais, permissão DbExplorerSP.executeQuery e acesso às tabelas atuais; não houve desvio para endpoints não verificados. Endereço de contato/volumes e ambiguidades devem ser conferidos no ambiente autorizado. As chamadas externas estão isoladas pelos serviços existentes e são simuladas exclusivamente nos testes.

Não há dependências de runtime adicionais. Prettier foi usado como ferramenta temporária de formatação, fora do manifesto do projeto. O teste frontend usa node:test e a execução nativa de TypeScript do Node 24 disponível nesta máquina.

## Arquivos desta entrega

Backend modificados: `app/api/router.py`, `app/api/route_plans.py`, `app/models/route_plans.py`, `app/schemas/route_plans.py`, `app/services/route_planning.py`, `app/services/sankhya.py`.

Backend novos: `app/api/distributions.py`, `app/schemas/distributions.py`, migration 0012 e `tests/test_distributions.py`.

Frontend: `RoutesPage.tsx` substituída pela central; novos `LegacyRoutesPage.tsx` (preservação da tela anterior), `DistributionMap.tsx`, `DistributionAddress.tsx`, `distribution.ts`, `distribution.css`, `tests/distribution.test.ts`. Documentação: este arquivo.

## Testar localmente

1. Use exclusivamente um banco de desenvolvimento local e confira DATABASE_URL antes de iniciar. Não use a configuração produtiva. No backend, ative `.venv` e execute `python -m alembic upgrade head` somente nesse banco local.
2. Configure os provedores ROUTES_* de homologação conforme ROTAS_ENTREGA_A.md. Sankhya é opcional para cadastro manual e exige credenciais/permissões autorizadas para consulta real.
3. Execute `python -m uvicorn app.main:app --reload` no backend e `npm.cmd run dev` no frontend.
4. Entre como ADMIN/MASTER em `/admin/rotas`; crie uma distribuição, inclua notas, valide endereços, selecione no mapa/lista/retângulo, crie duas rotas, transfira notas, atribua motorista/veículo e origem, calcule e confirme.
5. Recarregue para conferir persistência. Abra o mesmo conjunto em duas abas e salve ambas: a segunda deve receber conflito. Confira a rota na conta do motorista e siga checklist/saída/entregas/conclusão pelo fluxo atual.
6. Backend: `python -m pytest tests -q -p no:cacheprovider`. Frontend: `node --experimental-strip-types --test tests/distribution.test.ts` e `npm.cmd run build`.

Os testes usam exclusivamente SQLite de teste/temporário. A migration também é exercitada com integridade referencial em memória e na cadeia Alembic completa sobre arquivo temporário isolado, preservando registro legado de RoutePlan. Concorrência PostgreSQL simultânea e homologação visual em navegador com provedores reais não são substituídas pelos testes de revisão e build.

## Resultados executados em 04/11/2026

- Regressão direcionada de planejamento e Sankhya: **19 aprovados**.
- Suíte backend completa: **99 aprovados e 2 erros de preparação** em 214,17 s. Ambos foram PermissionError/WinError 5 na pasta temporária padrão do pytest, antes das asserções de SPA e migration isolada.
- Reexecução dos arquivos afetados e da central, usando `--basetemp` em diretório novo dentro do backend: **10 aprovados**, 14,15 s. Inclui cadeia Alembic até 0012, preservação de RoutePlan legado, integridade referencial, persistência, conflitos, confirmação e fluxo completo até conclusão da viagem.
- Dois testes adicionais de sequência otimizada e recusa Sankhya sem exposição de segredos: **2 aprovados**, 2,31 s.
- **103 casos backend distintos validados em execuções combinadas**. Não houve uma única execução integral verde: os dois erros de pasta temporária foram resolvidos na execução direcionada, sem modificar testes existentes.
- Testes frontend: **4 aprovados**, cobrindo seleção individual/múltipla, desmarcação, limites/exclusões do retângulo, exclusão de distribuídas e serialização.
- `npm.cmd run build`: **aprovado**, incluindo TypeScript e Vite; 1629 módulos, JS 479,17 kB (gzip 141,08 kB), CSS 55,68 kB (gzip 15,27 kB).
- `git diff --check`: aprovado. Branch confirmada como feature/central-distribuicao-visual; HEAD e main continuam no mesmo commit anterior, sem commits desta entrega.
- Permanecem avisos de depreciação existentes em Starlette/AnyIO e configuração Alembic.
- Não houve teste automatizado em navegador nem consulta real a Sankhya/OSRM/Pósitron. Homologação visual, sobreposição de marcadores no mesmo endereço, dispositivos reais, limites dos provedores e concorrência simultânea PostgreSQL continuam pendentes.

No Windows deste ambiente, use um caminho **novo e vazio** em backend para `--basetemp`, pois a pasta padrão está bloqueada. Exemplo: `python -m pytest tests -q -p no:cacheprovider --basetemp .pytest-tmp-central-NOVO-ID`. O pytest pode limpar o caminho fornecido. A pasta gerada nesta validação foi preservada no workspace.
