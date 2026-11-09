# Geocodificação Nominatim + Geoapify

Implementação na branch `feat/geocoding-dual-provider`, em 09/11/2026. Sem deploy, conexão ao banco configurado como produção ou execução de migrations nesse banco. Alterações locais anteriores foram preservadas.

## Diagnóstico anterior à implementação

- `backend/app/services/route_planning.py`: adaptadores Nominatim/Photon e transporte HTTP com timeout; o fluxo anterior tentava variantes progressivamente mais amplas do endereço. Configuração efetiva verificada: Nominatim em `https://nominatim.openstreetmap.org`, portanto **público**, sem evidência de serviço interno ou contratado. O ambiente local está marcado como `production`, por isso nenhum banco configurado foi consultado.
- `Pickup.endereco`: endereço original em texto. As alterações locais já continham `GeocodedAddress`, tabela `geocoded_addresses`, com endereço como chave e resultado JSON compartilhado. Planejamentos, versões e rotas estabelecidas guardam pontos em JSON com `address`, `latitude` e `longitude`.
- Cadastro manual: `PickupsPage` → `/pickups`; endereços de origem, retorno e paradas usam `AddressPicker`. Não havia confirmação persistente com marcador arrastável.
- NF-e: `/route-plans/invoice-lookup` → `sankhya.lookup_invoice`, consulta de leitura com contato de entrega e parceiro, retornando endereço completo. A interface usa o mesmo `AddressPicker` para resolver esse endereço; importar a nota não dispara consulta geográfica em lote.
- Roteirizador: `points_and_stops`, `matrix`, `geometry` e OSRM usam diretamente os pontos selecionados. A correção vale para seleções futuras; planejamentos e execuções já salvos mantêm seus pontos e revisões. Rastreamento Positron, motoristas, veículos e conclusão de entregas não foram alterados.
- O mapa anterior consultava automaticamente todas as coletas sem cache e adotava o primeiro candidato. Agora carrega apenas localizações salvas no backend; pesquisas e correções são individuais em Coletas/seletores de endereço.

## Decisão e persistência

`geocoding_cache.geocode` consulta confirmação manual e cache antes de `dual_geocoding.lookup`. São feitas, no máximo, uma busca pelo endereço completo no principal e uma no Geoapify. Não há retries nem variações automáticas na API nova. Photon continua aceito para compatibilidade de configurações anteriores.

Seleção automática exige município, país, rua e número correspondentes, tipo de resultado de edifício e, se o endereço informar bairro, correspondência do bairro por padrão. O Geoapify também exige `confidence`, `confidence_street_level` e `confidence_building_level` >= 0,95 e `match_type` igual a `full_match` ou `match_by_building`. Campo ausente não conta como confiança alta. Ruas numeradas não perdem o número do próprio logradouro. Rua genérica como “Rua A” exige evidência do bairro.

Somente rua compatível: `approximate`, sem `selected`. Centro municipal/bairro, outro município ou outra rua: não verificado. Sugestões permanecem visíveis para revisão, com provedor, precisão e atribuição. Dois candidatos compatíveis distantes mais de 200 m geram `conflict`, inclusive ambiguidades dentro do mesmo provedor. O secundário não é chamado quando o principal já resolve com precisão; conflitos são avaliados sobre os resultados efetivamente disponíveis.

JSON persistido: endereço original, candidatos e seus componentes, coordenadas, provedor, `rank`, `result_type`, precisão/status, `verified_at` em Unix UTC, expiração, erros sanitizados, atribuição e confirmação manual. Resultados antigos continuam legíveis, mas são reavaliados na próxima busca individual. A confirmação manual armazena também o usuário responsável, preserva sugestões anteriores e gera auditoria. Confirmação não expira nem é sobrescrita por consulta automática concorrente. Editar o endereço cria outra chave e não herda a confirmação anterior.

`POST /api/route-plans/geocode/confirm` aceita apenas gestores autorizados e coordenadas finitas dentro dos limites. “Corrigir localização” permite ver o endereço, escolher sugestão, clicar ou arrastar marcador, informar coordenadas e confirmar. O mapa não escolhe uma coordenada definitiva quando não há evidência.

## Limites e configuração

- `GEOAPIFY_API_KEY`: `SecretStr`, somente backend. A chave fornecida foi salva no `backend/.env`, ignorado pelo Git. Não aparece nos relatórios ou respostas. O adaptador não registra URLs/exceções que contêm a chave.
- Regras e intervalos estão documentados no `.env.example`. `GEOCODING_PRIMARY_ENABLED=false` permite suspender o principal sem atualização do código. URLs internas/contratadas continuam configuráveis.
- `geocoding_quotas` faz reservas atômicas no banco compartilhado por processos/workers. O principal público tem intervalo mínimo de 1,1 s; Geoapify usa intervalo configurável conforme plano. Uma reserva por endereço evita chamadas simultâneas duplicadas. Todos os workers precisam compartilhar o mesmo banco; não usar bancos separados por réplica.
- Sem espera bloqueante na API por quota: falha do principal permite fallback. HTTP 429/indisponibilidade impõem cooldown compartilhado, respeitando `Retry-After` numérico quando maior. Timeout configurável de até 60 s por provedor. Um pedido pode esperar até dois timeouts; as demais funcionalidades não dependem desse resultado.
- Cache positivo: 30 dias por padrão. Respostas vazias, erros e indisponibilidade: 5 minutos. Confirmação manual: permanente. Sem renovação automática em massa. O script legado de validação em lote rejeita Nominatim público.
- Migrations `0018` (já existente nas alterações locais) e `0019` (quotas) são aditivas. Devem ser aplicadas pelo processo normal antes de ativar a versão; não foram aplicadas em produção.

## Política, armazenamento e atribuição

O [Nominatim público](https://operations.osmfoundation.org/policies/nominatim/) permite buscas explícitas de usuários com tráfego moderado, exige identificação da aplicação, atribuição, cache e limite agregado de 1 req/s. Não usar autocomplete nem processamento regular em massa. Para escalar, configurar instância interna ou contratada. A auditoria desta entrega foi uma investigação explícita, serial e limitada a cinco endereços, sem ampliar consultas ou repetir falhas.

O [Geoapify documenta os indicadores de confiança e tipos de correspondência](https://apidocs.geoapify.com/docs/geocoding/forward-geocoding/). Seus [termos](https://www.geoapify.com/terms-and-conditions/) exigem atribuição OSM e atribuição Geoapify no plano gratuito. A política de armazenamento da [Geocoding API](https://www.geoapify.com/geocoding-api/) admite guardar resultados; os dados mantêm suas licenças de origem. Candidatos preservam `datasource` e suas atribuições/licenças, incluindo OpenAddresses quando retornado. A interface mostra atribuição Geoapify/OSM e as fontes dos candidatos. Confirmar limites e condições particulares do plano contratado antes de operar em escala; a chave por si só não informa esse contrato.

## Auditoria real dos cinco endereços

Evidência integral sanitizada: [geocoding-audit-2026-11-09.json](geocoding-audit-2026-11-09.json). Foram feitas dez consultas externas, sem consultar ou gravar coletas no banco de produção. Após adicionar a regra de bairro, as mesmas respostas foram reavaliadas offline, sem novas chamadas. Nenhuma coordenada foi inventada ou confirmada automaticamente.

| ID | Nominatim, endereço completo | Geoapify | Decisão final |
| --- | --- | --- | --- |
| 15 | Nenhum candidato | Interpretou “Viela Projetada 3” como rua “Viela Projetada”, número 3; confidence/street 0,90, building ausente, `inner_part`. Também sugeriu outros números. | Confirmar manualmente: nome do logradouro divergente; não assumir que 3 seja número de imóvel. |
| 34 | Nenhum candidato | “Rua A 68”, bairro Bonsucesso; confidence/street/building 1, `full_match`. Bairro solicitado: Ponte Alta. | Confirmar manualmente: rua genérica e bairro incompatível, apesar dos scores altos. |
| 58 | Nenhum candidato | Dois candidatos “Rua Arthur De Azevedo 6”, ambos em Vila Gopoúva, CEPs 07194-190 e 07194-090; scores 1, `full_match`. Bairro solicitado: Jardim Bela Vista. | Rua aproximada; confirmar manualmente o número/local e a divergência de bairro. |
| 77 | Nenhum candidato | “Rua Palmira D’Oeste 5”, bairro Jacana; confidence 0,6939, street/building 1, `full_match`, além de outros números. Bairro solicitado: Jardim Betel. | Rua aproximada; confirmar manualmente por baixa confiança geral e bairro divergente. |
| 81 | Nenhum candidato | Avenida em São Paulo, bairro Jacana, números 1307/1301 e outros; primeiro confidence 0,0278, street 0,4499 e building 0,0026. Solicitado: 275, Guarulhos/Jardim Joamar. | Confirmar manualmente; município e números incompatíveis. |

**Localizados automaticamente: nenhum. Confirmação manual pendente: IDs 15, 34, 58, 77 e 81.** As coordenadas no JSON são sugestões retornadas pelos provedores, não destinos aprovados. Não foram aplicadas aos cadastros.

Reprodução explícita, com arquivo de saída novo e sem banco de produção:

```powershell
cd backend
./.venv/Scripts/python.exe -m app.audit_geocoding --input ../storage/backups/validacao-coletas-2026-11-09.csv --output ../docs/nova-auditoria.json --live
```

O comando recusa sobrescrever relatório existente para evitar repetição acidental. A rotina usa banco SQLite em memória apenas para quotas e arquivos locais para entrada/saída.

## Validação final

- `npm run build`: passou, incluindo TypeScript e Vite. A interface não foi exercitada em navegador nesta sessão.
- Suíte completa: **139 passaram, 3 falharam**, em 246,77 s. Comando: `./.venv/Scripts/python.exe -m pytest -q --tb=short --basetemp=.pytest-tmp-dual-final-20261109`.
- Os 12 testes novos de `test_dual_geocoding.py` passaram: fallback, dispensa do secundário, confiança baixa/ausente, centros administrativos, número incorreto, conflitos, quota compartilhada, indisponibilidade, cache negativo, preservação manual e corrida com consulta automática, autenticação/validação da confirmação, bairro divergente, reprodução offline dos cinco endereços e transporte HTTP/timeout/429 sem chave na resposta. Os testes de cache existentes foram adaptados ao cache negativo temporário.
- Também passaram os testes existentes de Sankhya, rastreamento, rotas, entregas e migrations. Migrations foram exercitadas exclusivamente em bancos de teste; instalação nova e preservação de registros foram verificadas.
- Falhas restantes: `test_master_full_panel_access_and_user_management`, `test_purchasing_permissions` e `test_role_changes_apply_to_existing_sessions`. Os testes esperam criação de usuários por `ADMIN`, enquanto `backend/app/api/users.py` exige `MASTER`. A API de usuários e esses testes são idênticos aos arquivos em `HEAD`, sem alterações nesta entrega. A regra existente não foi relaxada para fazer os testes passarem.
- `git diff --check`: passou. Varredura da implementação, testes e relatórios não encontrou a chave fornecida. Arquivos de ambiente permanecem ignorados pelo Git.
