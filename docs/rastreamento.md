# Rastreamento

O item fica entre Viagens e Ocorrências. `/rastreamento` redireciona para `/admin/rastreamento`, protegido para gestores. A tela consulta o backend a cada 30 segundos, apresenta todos os veículos cadastrados, filtros, mapa Leaflet/OpenStreetMap, detalhes e rota das últimas 24 horas. Atualização da consulta não significa atualização do GPS; cada posição exibe sua data própria. O mapa requer acesso à internet para carregar os tiles.

No cadastro de Veículos, abra **Editar veículo** para salvar separadamente o vínculo com o ID do rastreador Pósitron. Para um veículo novo, salve o cadastro antes de vincular. IDs são únicos. Trocar o ID remove posições anteriores daquele veículo para evitar misturar equipamentos.

Migration: `20261009_0007`, tabelas `vehicle_tracking` e `tracking_positions`. Execute `alembic upgrade head` no backend antes de iniciar a nova versão. Nenhum banco de produção foi alterado durante o desenvolvimento.

API interna, somente gestores:

- `GET /api/tracking`: frota, posição mais recente e viagem/motorista atuais.
- `PUT /api/tracking/{vehicle_id}/link`: `provider: POSITRON`, `tracker_id`, `active`.
- `GET /api/tracking/{vehicle_id}/history?hours=24`: histórico ordenado, até 168 horas e 10.000 pontos.

Sem posição: aguardando primeira posição. Posição com mais de cinco minutos: sem comunicação. Sem velocidade: velocidade indisponível, sem inferir veículo parado. Não há posições demonstrativas ou endpoint público para inserir localizações. Origem/destino não existem no modelo atual de viagem e não são inventados.

## Dependência para integração real

Consulta pública em 09/10/2026: a [página oficial de soluções para frotas](https://conteudos.positron.com.br/para-sua-empresa-e-frota) menciona integração WebService, mas não publica contrato de autenticação, métodos e respostas. As [perguntas frequentes](https://positron.com.br/suporte/duvidas-frequentes) explicam como consultar o ID do rastreador no portal e indicam suporte pelo WhatsApp (11) 96399-0556. Não foi encontrada especificação técnica pública oficial suficiente para conectar este contrato.

Solicite à Pósitron:

- Liberação de leitura das posições e histórico da frota Modial no contrato empresarial.
- Manual técnico vigente, URL oficial do serviço e WSDL, se SOAP, ou especificação equivalente, se REST.
- Credenciais próprias da integração e método de autenticação. Pode exigir usuário/senha ou chave/token; a forma exata precisa ser confirmada no manual.
- Identificador de cliente/contrato, se exigido, e relação de placas com IDs de rastreadores.
- Regras de liberação de IP do backend, se houver, limites de consulta, fuso horário e unidades de velocidade.

`TrackingProvider` e `PositronTrackingProvider` ficam em `app/services/tracking.py`. A implementação Pósitron lança `ProviderNotConfigured`; não acessa URLs presumidas nem usa a senha do portal. A integração deve implementar coleta, autenticação, renovação, normalização e persistência apenas após receber a documentação. Credenciais devem ficar exclusivamente no backend.

Referência do mapa: [Leaflet](https://leafletjs.com/reference-1.9.4.html).
