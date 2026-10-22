# Rastreamento

O item fica entre Viagens e Ocorrências. `/rastreamento` redireciona para `/admin/rastreamento`, protegido para gestores. A tela consulta o backend a cada 30 segundos, apresenta todos os veículos cadastrados, filtros, mapa Leaflet/OpenStreetMap, detalhes e rota das últimas 24 horas. Atualização da consulta não significa atualização do GPS; cada posição exibe sua data própria. O mapa requer acesso à internet para carregar os tiles.

No cadastro de Veículos, abra **Editar veículo** para salvar separadamente o vínculo com o ID do rastreador Pósitron. Para um veículo novo, salve o cadastro antes de vincular. IDs são únicos. Trocar o ID remove posições anteriores daquele veículo para evitar misturar equipamentos.

Migration: `20261009_0007`, tabelas `vehicle_tracking` e `tracking_positions`. Execute `alembic upgrade head` no backend antes de iniciar a nova versão. Nenhum banco de produção foi alterado durante o desenvolvimento.

API interna, somente gestores:

- `GET /api/tracking`: frota, posição mais recente e viagem/motorista atuais.
- `PUT /api/tracking/{vehicle_id}/link`: `provider: POSITRON`, `tracker_id`, `active`.
- `GET /api/tracking/{vehicle_id}/history?hours=24`: histórico ordenado, até 168 horas e 10.000 pontos.

Sem posição: aguardando primeira posição. Posição com mais de cinco minutos: sem comunicação. Sem velocidade: velocidade indisponível, sem inferir veículo parado. Não há posições demonstrativas ou endpoint público para inserir localizações. Origem/destino não existem no modelo atual de viagem e não são inventados.

## Positron Sync

Contrato validado em 14/10/2026: [Swagger oficial](https://webservices.positronrt.com.br/srb-external-ws/swagger-ui/index.html), OpenAPI 1.0.10. O perfil LOGISTICS atende ao rastreamento. Teste real: login aceito, ambiente DEVELOPMENT, cinco veiculos e cinco posicoes. Esses dados pertencem ao fornecedor, e nao a frota Modial.

Configure `POSITRON_LOGIN` e `POSITRON_PASSWORD` exclusivamente no backend com as credenciais proprias. Os arquivos Compose encaminham essas variaveis. No Azure, configure as variaveis do servico. As credenciais de teste nao foram gravadas nem ativadas automaticamente.

Endpoints usados: POST /api/v1/auth/token (login/password e token Bearer, renovado apos HTTP 401), GET /api/v1/vehicle/list, GET /api/v1/position/latest?withAddress=true e POST /api/v1/position/history (idVehicle, start, end, withDetailedAddress).

Gestores podem consultar `GET /api/tracking/provider/vehicles` para obter placas e idVehicle autorizados. No cadastro, o campo existente tracker_id deve receber o **idVehicle**, e nao o PIN/serial do rastreador. Confira os vinculos anteriores. Nunca vincule veiculos de teste aos caminhoes reais.

Com a tela aberta, a consulta da frota sincroniza e persiste as ultimas posicoes, no maximo uma vez a cada 30 segundos por processo. Nao ha coletor continuo com a tela fechada. O botao de rota recupera o historico remoto das ultimas 24 horas. O endpoint realtime nao e utilizado: ele consome os eventos ao ler.

A data GPS e moduleDatetime, interpretada como UTC quando nao tem offset, conforme o padrao de datas documentado. Posicoes explicitamente sem GPS ou estimadas sao ignoradas. Falhas preservam as posicoes existentes e exibem aviso; erros no historico sao apresentados ao gestor. A persistencia evita duplicacao por veiculo/data. Tokens e senhas permanecem no backend.

Antes de producao, confirmar com a Positron: acesso a frota Modial, limites de consulta, UTC para moduleDatetime sem offset, unidade da velocidade e eventual liberacao de IP.

Resposta sugerida ao fornecedor:

> Bom dia! Avaliamos a documentacao Sync e validamos o login e as consultas de veiculos e ultimas posicoes com o usuario de teste LOGISTICS. Precisamos consultar posicoes e historico dos caminhoes Modial. Solicitamos credenciais proprias no perfil LOGISTICS, com acesso a nossa frota, e a relacao de placas com seus idVehicle. Poderiam confirmar os limites de consulta, o fuso de moduleDatetime sem offset, a unidade da velocidade e eventual necessidade de liberacao de IP? Obrigado!


## Validacao com credenciais Modial em 22/10/2026

Login real aceito com perfil LOGISTICS. A resposta de autenticacao identifica o ambiente como DEVELOPMENT; confirmar com a Positron a liberacao para uso em producao. A consulta de veiculos e de ultimas posicoes retornou quatro registros. Credenciais configuradas somente no .env local, ignorado pelo Git; nao foram aplicadas ao servidor de producao.

O teste real de historico revelou HTTP 400 (JSON invalido) quando as datas possuem microssegundos. O cliente agora envia UTC no formato YYYY-MM-DDTHH:MM:SSZ, validado com retorno de historico real. Ha teste de regressao para conversao de fuso e remocao de microssegundos.

Publicacao pendente: configurar POSITRON_LOGIN e POSITRON_PASSWORD no .env do servidor, publicar a versao corrigida e vincular cada veiculo pelo idVehicle correspondente a placa. O GitHub CLI local apresentou autenticacao invalida durante esta validacao. Nao houve alteracao no banco de producao.
