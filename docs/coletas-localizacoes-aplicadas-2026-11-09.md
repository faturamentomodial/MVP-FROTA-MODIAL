# Quatro coletas incluídas no Mapa rotas

Em 09/11/2026, após o usuário fornecer os quatro endereços corrigidos e solicitar sua inclusão no mapa, foram atualizados exclusivamente os IDs **34, 58, 77 e 15** no servidor existente. Não houve deploy, reinício da aplicação, migration ou alterações em motoristas, veículos, viagens, rotas salvas ou Mercia (ID 81).

| ID | Coleta | Endereço salvo | Latitude | Longitude | Precisão |
| --- | --- | --- | --- | --- | --- |
| 34 | M. AUXILIADORA | Rua José Damiani Filho, 68 - Jardim Pres. Dutra, Guarulhos - SP | -23.421109 | -46.4226017 | Referência aproximada do logradouro; nº 68 não confirmado |
| 58 | M. FERREIRA | Rua Arthur de Azevedo, 6 - Jardim America, Guarulhos - SP, 07194-090 | -23.442225 | -46.513113 | Ponto aproximado; sem confirmação manual do imóvel |
| 77 | SUELY LIMA | R. Palmira D'oeste, 5 - Jardim Betel, Guarulhos - SP, 07083-340 | -23.435209 | -46.548549 | Ponto aproximado; sem confirmação manual do imóvel |
| 15 | VILMA | Viela Projetada, 3 - Recreio São Jorge, Guarulhos - SP, 07144-546 | -23.402618 | -46.517677 | Confirmado manualmente pelo usuário no chat |

**Os quatro registros retornam `location` preenchida na função do endpoint `/api/pickups` da versão em execução.** Também foi conferido que o frontend publicado usa `item.location` para substituir o cache do navegador antes de desenhar os marcadores. Basta atualizar o Mapa rotas para carregar os dados salvos. Não foram executadas consultas externas de geocodificação na validação posterior à gravação.

## Origem dos pontos e limitações

- Auxiliadora: a pesquisa pelo novo nome retornou “Rua José Damiani”, sem “Filho”, em outra região. Foi rejeitada. O [Decreto municipal 34746/2018](https://diariooficial.guarulhos.sp.gov.br/uploads/pdf/1784655049.pdf) esclarece que José Damiani Filho é a antiga Rua A do Residencial Parque Cumbica, iniciando na Rua Altemar Dutra. Outra Rua A, anteriormente sugerida, tem conexões diferentes no OpenStreetMap e também foi rejeitada. Foi adotada somente a [referência de coordenadas do logradouro/CEP 07174-330](https://cepdarua.net/cep/07174330), mantendo **precisão aproximada**, sem atribuir a ela exatidão do imóvel nº 68.
- Ferreira: reaproveitada a resposta Geoapify específica ao CEP 07194-090. A rua no Jardim América também consta no [anuário diocesano](https://diocesedeguarulhos.org.br/wp-content/uploads/2024/01/Anuario-Diocesano-2024-WEB.pdf). O provedor usa o bairro amplo Vila Gopoúva, por isso o ponto não foi promovido a confirmação manual.
- Suely: reaproveitada a resposta Geoapify para rua, nº 5 e CEP 07083-340. O logradouro no Jardim Betel consta no [Diário Oficial municipal](https://diariooficial.guarulhos.sp.gov.br/uploads/pdf/1958373357.pdf). Confidence geral de 0,8333 e bairro amplo “Jacana” no provedor permanecem registrados; não foi declarada precisão automática alta.
- Vilma: coordenada explicitamente conferida e aprovada pelo usuário. A interpretação do nº 3 e o endereço completo foram corrigidos sem novas buscas.

As referências aproximadas ficam visíveis no mapa, mas têm `selected=null`, `selection_required=true` e `manual_confirmed=false`: **não passam a ser destinos automaticamente confirmados para roteirização**. Vilma mantém prioridade manual. O campo `map_point`, acompanhado de `map_reviewed=true`, permite que a versão mais nova preserve a visualização dessas referências sem aprovar silenciosamente seus imóveis. A versão já publicada lê o primeiro candidato, que foi salvo com o mesmo ponto e precisão explícita.

## Aplicação, backup e verificação

- Manifesto: [coletas-localizacoes-aplicar-2026-11-09.json](coletas-localizacoes-aplicar-2026-11-09.json).
- Resultado verificado no servidor: [coletas-aplicadas-20261109.json](coletas-aplicadas-20261109.json).
- Aplicação por `app.apply_pickup_locations`, primeiro em prévia, depois em uma transação com validação de IDs, nomes e endereços anteriores, proteção de confirmações manuais, backup antes da gravação e quatro registros de auditoria com origem da solicitação. Reexecução é idempotente.
- Backup durável no servidor: `/home/ubuntu/modial-frota/backups/coletas-before-correction-20261109.json`, com permissão 600. Cópia local em `storage/backups/coletas-before-correction-20261109.json`, ignorada pelo Git. Nenhum backup foi incluído no commit.
- CSV atualizado salvo separadamente em `storage/backups/validacao-coletas-corrigidas-20261109.csv`. O arquivo original aberto no IDE não pôde ser sobrescrito por permissão do sistema e foi preservado.
- **22 testes passaram**, incluindo os quatro novos testes de correção, visualização de referências sem aprovação automática, idempotência, preservação dos outros cadastros, identidade/endereço alterados e proteção de ponto manual conflitante. Também passaram os testes de cache e dos dois provedores. Healthcheck do servidor: `{"status":"ok"}`.
- Push com `[skip ci]` para não disparar o workflow de deploy. Esta operação é uma correção de quatro registros no serviço já publicado, e não uma publicação de uma nova versão.

Este relatório substitui o status pendente dos quatro registros nos relatórios de pesquisa anteriores. As respostas originais permanecem como histórico; resultados rejeitados não foram aplicados.
