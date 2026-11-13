# Geoapify — diagnóstico, configuração e validação

Branch de implementação: `feat/geoapify-platform`, a partir do commit original `3126adc`. A tentativa anterior de Google está preservada separadamente em `feat/google-maps-platform` (`6a192f3`) e não faz parte desta implementação. Nenhuma alteração direta na main, deploy ou migração de banco foi realizada.

## Diagnóstico dos provedores

| Área | Código original | Configuração atual |
| --- | --- | --- |
| Endereços | Nominatim; adaptador Photon disponível | Geoapify Geocoding API |
| Trajetos, distâncias e duração | OSRM `/route` | Geoapify Routing API |
| Matrizes usadas pelo roteirizador existente | OSRM `/table` | Geoapify Route Matrix API |
| Interface dos mapas e marcadores | Leaflet + tiles OpenStreetMap | Mantidos; apenas créditos Geoapify acrescentados |
| Notas fiscais | Sankhya | Preservado |
| Posições e histórico dos veículos | Positron | Preservado |

Geoapify é o único provedor ativo de geocodificação e roteirização. Não existe fallback automático para Nominatim, Photon ou OSRM. Os adaptadores legados continuam disponíveis no código para compatibilidade e testes existentes, mas não são chamados na configuração Geoapify. Esta branch não inclui adaptadores, dependências ou configuração de Google Maps.

## Arquivos afetados

- `backend/app/services/geoapify.py`: HTTP autenticado exclusivamente no servidor; geocodificação, trajetos e matrizes; validação, timeout, limites e mensagens sem segredos.
- `backend/app/core/config.py`: `GEOAPIFY_API_KEY` como `SecretStr`, seleção de provedores e defaults Geoapify.
- `backend/app/services/route_planning.py`: despacho aos novos adaptadores, mantendo os contratos e o algoritmo local existente.
- `backend/app/services/dual_geocoding.py`: reserva compartilhada da cota de consultas e atribuição do provedor; mesma classificação conservadora de resultados.
- `backend/app/services/geocoding_cache.py`: separação do cache automático por provedor; confirmações manuais continuam sendo reutilizadas.
- `backend/app/api/route_plans.py` e `route_templates.py`: identificação correta do provedor nas respostas; estruturas e endpoints preservados.
- `frontend/src/components/AddressPicker.tsx`, `LocationEditor.tsx`, `RouteMap.tsx`: créditos Geoapify; sem substituição de Leaflet, tiles, marcadores ou interações.
- `frontend/src/pages/admin/RoutesPage.tsx` e `EstablishedRoutes.tsx`: mesmo aviso de limitações de caminhões, com texto independente de OSRM.
- `.env.example`, `docker-compose.yml`, `docker-compose.oracle.yml`: configuração segura do backend. Nenhuma chave no frontend ou em argumentos de build.
- `backend/tests/conftest.py`, `backend/tests/test_geoapify.py`: isolamento das credenciais reais e testes offline.
- `backend/app/check_geoapify.py` e `docs/geoapify-validation-2026-11-13.json`: diagnóstico real reproduzível e evidência sanitizada.

## Comportamento preservado

Os contratos internos continuam usando `latitude` e `longitude`, GeoJSON `LineString` em ordem `[longitude, latitude]`, distâncias em metros e durações em segundos. A resposta Geoapify `MultiLineString` é convertida para o formato existente, sem inventar trechos ou estimativas.

No cálculo manual (`optimize: false`), as paradas são enviadas na sequência recebida. A chamada Geoapify envia explicitamente `optimize_stops=false`. Origem, entregas e retorno mantêm sua ordem. Não é utilizada Route Optimization API, Google Maps ou Geoapify Route Planner API.

O botão de otimização já existente continua executando o algoritmo local anterior, sobre a matriz viária Geoapify. Não houve reconstrução do roteirizador nem alteração das regras dos botões ou do valor padrão do contrato `CalculateInput`.

Para preservar o limite existente de até 100 paradas, trajetos extensos são divididos em grupos de até 20 pontos para limitar o tamanho das URLs, com extremidade compartilhada. Matrizes são divididas em blocos de até 31 × 31 células, abaixo do limite documentado de 1.000 células por chamada. Todas as chamadas de roteirização continuam no Geoapify. Matrizes completas consomem mais créditos, especialmente em rotas grandes; planejamentos mantêm a geração de matriz já prevista no contrato original.

O perfil continua `drive`, com trânsito `free_flow`. Não foram introduzidas regras novas de peso, altura, eixos ou restrições legais de caminhões. O aviso de revisão humana continua visível.

## Variáveis no servidor

Configure no `.env` utilizado pelo Docker Compose no servidor:

```dotenv
GEOAPIFY_API_KEY=<chave-do-projeto-geoapify>
ROUTES_GEOCODER_PROVIDER=geoapify
ROUTES_ROUTER_PROVIDER=geoapify
ROUTES_TIMEOUT_SECONDS=15
ROUTES_MIN_INTERVAL_SECONDS=1
```

As três primeiras variáveis definem a integração. Timeout e intervalo já têm os valores acima como padrão. Sobrescreva também os seletores de provedor se o `.env` do servidor ainda contiver `nominatim`, `photon` ou `osrm`.

As variáveis existentes continuam válidas:

```dotenv
GEOCODING_PRIMARY_ENABLED=true
GEOCODING_REQUIRE_NEIGHBORHOOD_MATCH=true
GEOCODING_CONFLICT_METERS=200
GEOCODING_CACHE_SECONDS=2592000
GEOCODING_FAILURE_CACHE_SECONDS=300
```

`ROUTES_GEOCODER_URL` e `ROUTES_ROUTER_URL` são ignoradas pelos adaptadores Geoapify; não precisam apontar para endpoints autenticados. Não coloque a chave nessas URLs. Não é necessária chave `VITE_*`, chave pública de mapa, mudança no frontend ou configuração de faturamento Google.

Para execução local Python, use `backend/.env`; para Compose, use o `.env` da raiz. A chave fornecida foi configurada somente nesses dois arquivos ignorados pelo Git. Restrições por IP no painel Geoapify devem permitir o IP de saída do backend. Ajuste a cota e o limite por segundo ao plano contratado. Em múltiplos workers, mantenha o total de chamadas compatível com o plano: a reserva de geocodificação é compartilhada no banco, e a limitação HTTP de rotas é por processo.

As variáveis de Sankhya e Positron permanecem com suas configurações anteriores. Não foi executado deploy; aplicar as variáveis no servidor e reiniciar o serviço é uma etapa futura, fora desta execução.

## Cache, erros e atribuição

Confirmações manuais existentes continuam prevalecendo e não são invalidadas pela troca de provedor. Resultados automáticos Geoapify são reutilizados durante `GEOCODING_CACHE_SECONDS`. Resultados automáticos de outros provedores são consultados novamente em Geoapify; nenhum endereço ou histórico foi apagado.

Geoapify permite armazenar resultados, preservando os créditos da fonte. O adaptador mantém `datasource`, atribuição e identificação do provedor nos dados armazenados. Os mapas mantêm os créditos OpenStreetMap e a consulta de endereços inclui link para Geoapify. Veja a [política publicada sobre armazenamento](https://www.geoapify.com/geocoding-api/).

Sem resultados: `candidates: []`, sem escolher um centro de cidade como imóvel. Resultados parciais ou divergentes mantêm a necessidade de revisão. Coordenadas, geometria e métricas inválidas são rejeitadas; matrizes incompletas não recebem valores inventados. HTTP 429 é tratado com `Retry-After`; falhas de autenticação, rede, timeout e JSON inválido retornam mensagens controladas. Não há log de URLs autenticadas nem exposição da resposta bruta de erro do provedor. Falhas de geocodificação mantêm o cache negativo curto já existente.

## Validação real em 13/11/2026

As oito consultas responderam com a chave fornecida. O resultado **não equivale à confirmação do imóvel**: bairros divergentes, ruas genéricas ou múltiplos pontos exigem a revisão que já existe no sistema.

| Consulta em Guarulhos | Resultado classificado pelo sistema |
| --- | --- |
| Rua Carinas, 76, Jardim Santa Inês | Aproximado: rua/número encontrados, mas Geoapify retornou bairro Taboão |
| Avenida Paulo Faccini, Macedo | Conflito: vários segmentos da mesma avenida |
| Rua Dom Pedro II, Centro | Conflito: dois candidatos elegíveis em Guarulhos; municípios diferentes classificados como não verificados |
| Viela Projetada 3, Recreio São Jorge | Exige confirmação; nenhum candidato elegível pela correspondência atual |
| Rua A, 68, Ponte Alta | Exige confirmação; rua genérica sem evidência suficiente |
| Rua Arthur de Azevedo, 6, Jardim Bela Vista | Aproximado; dois candidatos elegíveis |
| Rua Palmira D'Oeste, 5, Jardim Betel | Aproximado; quatro candidatos elegíveis |
| Avenida Josino Vieira de Goes, 275, Jardim Joamar | Exige confirmação; nenhum candidato elegível pela correspondência atual |

Para validar o transporte, foram escolhidos explicitamente candidatos das três primeiras consultas, sem gravar confirmações no banco. Sequência: Rua Carinas → Avenida Paulo Faccini → Rua Dom Pedro II → Rua Carinas. Geoapify calculou **19.536 metros**, **1.509,487 segundos** (aproximadamente 25,2 minutos), com geometria de 663 pontos. A matriz 3 × 3 também foi calculada. Essa seleção de teste não homologa os endereços operacionais nem substitui a validação do gestor.

Os detalhes de candidatos, coordenadas, classificação, ordem de teste, geometria, métricas e atribuições estão em [geoapify-validation-2026-11-13.json](geoapify-validation-2026-11-13.json), sem credenciais. Não foi gravado nenhum dado operacional por esse diagnóstico.

## Testes e reprodução

- 29 novos testes Geoapify aprovados: endereços brasileiros, correspondência conservadora, coordenadas inválidas, vazios, HTTP/JSON, cotas, segredo ausente, cache, matriz, rotas extensas e sequência manual nos dois endpoints.
- 8 testes existentes do frontend aprovados; TypeScript e build aprovados. Vite mantém um aviso de bundle acima de 500 kB.
- Verificação Chromium/Playwright dos componentes reais: quatro marcadores, percurso, popup, seleção no mapa, arraste e confirmação manual passaram; confirmação HTTP simulada, nenhuma chamada Google Maps e nenhum erro JavaScript.
- Suíte completa: **207 aprovados e 4 falhas preexistentes**, sem erros de preparação ou diretórios temporários. Todas as regressões de rotas, templates, geocodificação, Sankhya e Positron passaram, além dos 29 testes novos.
- As quatro falhas são as mesmas reproduzidas no commit original `3126adc`: `test_master_full_panel_access_and_user_management`, `test_purchasing_permissions` e `test_role_changes_apply_to_existing_sessions` esperam criação de usuários por ADMIN, mas recebem 403; `test_purchasing_can_read_map_without_management_access` usa um mock que não aceita o argumento existente `fetch`. Não foram alteradas permissões ou regras de negócio para contornar esses testes.
- `git diff --check` aprovado. A chave Geoapify não foi encontrada nos arquivos versionáveis nem no bundle do frontend.

Testes offline (nunca execute duas suítes pytest simultaneamente, pois usam o mesmo SQLite):

```powershell
cd backend
.venv/Scripts/python.exe -m pytest -q --tb=short --basetemp=.pytest-tmp-geoapify-tests
cd ../frontend
npm test
npm run build
```

Diagnóstico real explícito, que consome créditos Geoapify:

```powershell
cd backend
.venv/Scripts/python.exe -m app.check_geoapify --output ../docs/geoapify-validation-2026-11-13.json
```

Referências: [Geocoding](https://apidocs.geoapify.com/docs/geocoding/forward-geocoding/), [Routing](https://apidocs.geoapify.com/docs/routing/) e [Route Matrix](https://apidocs.geoapify.com/docs/route-matrix/).
