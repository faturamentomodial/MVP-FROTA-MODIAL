# Sistema completo na Render

O `render.yaml` cria um Web Service Docker com frontend React e API Python no mesmo endereço HTTPS e um PostgreSQL gerenciado. Não há armazenamento de fotos. Não depende da Vercel. O `docker-compose.yml` continua disponível para desenvolvimento local.

## Publicar

1. Entre na [Render](https://dashboard.render.com/) e conecte a conta GitHub com acesso a `faturamentomodial/MVP-FROTA-MODIAL`.
2. Escolha **New > Blueprint**, selecione esse repositório e a branch `main`. O arquivo é `render.yaml`, na raiz.
3. Revise os recursos e os valores apresentados pela Render antes de criar: Web Service `starter`, PostgreSQL `0.1c-256mb` com 1 GB. São recursos pagos. A aplicação não precisa de disco persistente. O banco gratuito tem prazo de expiração.
4. Aplique o Blueprint e acompanhe o build. As migrations executam na inicialização, antes de o servidor começar a atender.
5. Quando o serviço estiver disponível, abra a URL HTTPS informada pela Render, por exemplo `https://modial-frota.onrender.com` (o endereço final pode ser diferente).

Não configure Root Directory como `frontend` ou `backend`: o Dockerfile completo fica na **raiz**. Não é necessário configurar `VITE_API_URL` na Render. O container usa `/api` no mesmo domínio. A Render fornece a variável `PORT`, a URL interna do banco e gera `SECRET_KEY` pelo Blueprint. O backend converte a URL do banco para o driver psycopg instalado.

O banco bloqueia acesso externo e se comunica pela rede privada. O TLS é fornecido pela Render. Como a interface e a API compartilham o domínio, não é necessário liberar CORS.

## Primeiro acesso

No painel do Web Service, abra **Shell** e execute:

```sh
python -m app.create_admin
```

Informe nome, email e senha nas perguntas do terminal. A senha não aparece na tela. Esse comando só cria o primeiro gestor e não insere dados fictícios. Se já houver um gestor, o comando se recusa a criar outro; use o painel de configurações do sistema para os próximos gestores.

Entre na aplicação e cadastre os itens de checklist, os motoristas e os veículos antes da primeira viagem. Não execute o seed de desenvolvimento na implantação.

## Verificação após publicar

- Abra `/health` e confirme `{"status":"ok"}`.
- Faça login e cadastre um veículo e um motorista para validar o acesso ao banco.
- Atualize uma página interna, como `/admin/viagens`, diretamente no navegador.
- Complete uma viagem de teste, com checklist e ocorrência por escrito; confira a descrição e o tratamento no painel do gestor.
- Reinicie o serviço e confira que os registros permanecem disponíveis.

O health check confirma que o servidor subiu, mas não substitui os testes de login e banco. Não exclua o banco ao atualizar o código. Planeje backups do PostgreSQL antes de usar dados reais.

Se o deploy falhar, confira os logs: erros de migration ou conexão com o banco impedem a inicialização.

Referências: [Blueprint](https://render.com/docs/blueprint-spec), [Docker](https://render.com/docs/docker) e [limitações do plano gratuito](https://render.com/docs/free).

## Atualização de instalações anteriores

Os endpoints de upload foram removidos. Checklists e ocorrências não aceitam nem exibem fotos. Não é necessária migration para esta mudança: tabelas e colunas antigas podem permanecer no banco sem serem usadas, preservando dados já existentes. Arquivos antigos não são apagados automaticamente. Para instalações que já tinham um disco de fotos na Render, retirar o disco do YAML não confirma sua remoção nem o fim da cobrança; confira esse recurso no painel antes de excluí-lo.
