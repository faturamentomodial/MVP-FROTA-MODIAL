# Revisão das cinco coletas para o Mapa rotas

**Atualização posterior:** os quatro endereços corrigidos pelo usuário foram aplicados; Vilma está confirmada e as outras três referências estão sinalizadas como aproximadas. Veja o [resultado final da aplicação](coletas-localizacoes-aplicadas-2026-11-09.md). O texto de pesquisa abaixo registra o estado anterior, não o status atual.

Pesquisa complementar em 09/11/2026. Foram usados os resultados anteriores, referências públicas e cinco consultas individuais adicionais ao Geoapify com CEP/localidade mais específicos. Não houve consultas adicionais ao Nominatim público, conexão ao banco configurado, deploy ou alteração dos cadastros. Nenhum ponto abaixo está confirmado manualmente.

As consultas são hipóteses de pesquisa; não corrigem automaticamente o endereço original. Respostas completas: [JSON de pesquisa](pickup-location-review-2026-11-09.json). Dados: Geoapify, © OpenStreetMap contributors e © OpenAddresses contributors; licenças de origem preservadas no JSON.

| Coleta | Referência encontrada | Ponto para revisão | Pendência antes de salvar |
| --- | --- | --- | --- |
| M. AUXILIADORA — ID 34 | Rua A, Jardim Ponte Alta I, CEP 07179-065, conforme [consulta de CEP](https://www.busquecep.com.br/endereco/07179-065/). | Sem coordenada confiável para o endereço solicitado. | Mesmo com o CEP, Geoapify retorna Rua A 68 em Bonsucesso, CEP 07170-550, e até outras ruas com confidence 1. Não aceitar apenas o score. Solicitar localização compartilhada ou referência do nº 68. |
| M. FERREIRA — ID 58 | Rua Arthur de Azevedo, Jardim América, CEP 07194-090. O [anuário da Diocese](https://diocesedeguarulhos.org.br/wp-content/uploads/2024/01/Anuario-Diocesano-2024-WEB.pdf) informa a paróquia no nº 24 dessa rua. | [Candidato ao nº 6: -23.442225, -46.513113](https://www.google.com/maps/search/?api=1&query=-23.442225%2C-46.513113). Geoapify retornou confidence/street/building 1. | Confirmar se a coleta fica nessa rua do Jardim América; o cadastro informa Jardim Bela Vista e o provedor usa a área Vila Gopoúva. A referência da paróquia confirma a rua, não o imóvel da coleta. |
| MERCIA — ID 81 | Há [parada de ônibus no nº 275](https://busmaps.com/pt-BR/brazil/public_transit-stop-Av-Josino-Vieira-De-G%C3%B3es-275-2085314725904031323), São Paulo, CEP 02319-000. | [Candidato ao nº 275: -23.450899, -46.597046](https://www.google.com/maps/search/?api=1&query=-23.450899%2C-46.597046). Geoapify retornou confidence/street/building 1. | Confirmar município: a pesquisa aponta São Paulo/Bortolândia, mas o cadastro informa Guarulhos/Jardim Joamar. Não trocar município sem confirmação. |
| SUELY LIMA — ID 77 | Rua Palmira D'Oeste consta em Jardim Betel, CEP 07083-340, inclusive no [Diário Oficial municipal, nº 8](https://diariooficial.guarulhos.sp.gov.br/uploads/pdf/1958373357.pdf). | [Candidato ao nº 5: -23.435209, -46.548549](https://www.google.com/maps/search/?api=1&query=-23.435209%2C-46.548549). Geoapify retornou confidence 0,8333, street/building 1 e bairro Jacana. | Referências externas sustentam Jardim Betel, mas não confirmam o nº 5 da coleta. Rever o ponto no mapa com o gestor antes de confirmar. |
| VILMA — ID 15 | [Viela Projetada, Recreio São Jorge, CEP 07144-546](https://codigo-postal.org/pt-br/brasil/sp/guarulhos/logradouro/viela-projetada/). | Nenhum ponto novo confiável. A busca sem o “3” trouxe ruas sem relação com o endereço; foram rejeitadas. | Confirmar se “3” é o número do imóvel ou parte do nome “Viela Projetada 3”. Enviar localização compartilhada ou ponto de referência. |

Os três links de coordenadas são **candidatos para conferência**, não comprovação da localização dessas pessoas. Não usar centros de bairro, o ponto de uma igreja, uma parada de ônibus ou o número de outro imóvel para substituir o destino da coleta.

## Esclarecimento de Vilma

O usuário confirmou: **Viela Projetada, 3 — Recreio São Jorge**. O “3” é número do imóvel. A nova consulta com endereço separado e CEP trouxe apenas vias incompatíveis e foi rejeitada. A auditoria inicial já havia retornado um candidato com rua `Viela Projetada`, número `3` e CEP `07144-546`: **-23.402618, -46.517677**, [abrir candidato no mapa](https://www.google.com/maps/search/?api=1&query=-23.402618%2C-46.517677). Entretanto, confidence/street são 0,90, building está ausente e match_type é `inner_part`. O esclarecimento resolve a interpretação do endereço, mas não confirma a coordenada. O candidato permanece pendente de conferência visual pelo gestor; nenhum cadastro foi alterado.

Para aplicar os pontos: confirmar os candidatos com o responsável, manter a indicação de precisão real e usar a confirmação persistente do sistema. Até lá, os cadastros e suas coordenadas permanecem intactos.

## Confirmação do ponto de Vilma

O usuário respondeu **“Sim”** à pergunta sobre a coordenada **-23.402618, -46.517677**. Portanto, o ponto da coleta **VILMA, ID 15**, está confirmado pelo usuário, independentemente da confiança automática do provedor.

Payload preparado em [vilma-confirmed-location.json](vilma-confirmed-location.json), preservando a chave exata do endereço originalmente cadastrado para que o mapa associe a confirmação à coleta. Não foi fabricado um identificador de usuário do sistema; a aplicação autenticada registrará o gestor responsável. Não foram modificados o endereço cadastrado, outras coletas, o banco de produção ou o deploy. A aplicação em produção permanece pendente por causa da restrição inicial explícita de não modificar produção.
