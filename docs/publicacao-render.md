# Sistema completo na Render

O `render.yaml` cria um Web Service Docker com frontend React e API Python no mesmo endereço HTTPS, um PostgreSQL gerenciado e um disco persistente de 1 GB para fotos. Não depende da Vercel. O `docker-compose.yml` continua disponível para desenvolvimento local.

## Publicar

1. Entre na [Render](https://dashboard.render.com/) e conecte a conta GitHub com acesso a `faturamentomodial/MVP-FROTA-MODIAL`.
2. Escolha **New > Blueprint**, selecione esse repositório e a branch `main`. O arquivo é `render.yaml`, na raiz.
3. Revise os recursos e os valores apresentados pela Render antes de criar: Web Service `starter`, PostgreSQL `0.1c-256mb` com 1 GB e disco de uploads de 1 GB. São recursos pagos. O plano gratuito não aceita disco persistente e o banco gratuito tem prazo de expiração.
4. Aplique o Blueprint e acompanhe o build. As migrations executam na inicialização, antes de o servidor começar a atender.
5. Quando o serviço estiver disponível, abra a URL HTTPS informada pela Render, por exemplo `https://modial-frota.onrender.com` (o endereço final pode ser diferente).

Não configure Root Directory como `frontend` ou `backend`: o Dockerfile completo fica na **raiz**. Não é necessário configurar `VITE_API_URL` na Render. O container usa `/api` no mesmo domínio. A Render fornece a variável `PORT`, a URL interna do banco e gera `SECRET_KEY` pelo Blueprint. O backend converte a URL do banco para o driver psycopg instalado.

O banco bloqueia acesso externo e se comunica pela rede privada. As fotos ficam em `/data/uploads`, no volume persistente. O TLS é fornecido pela Render. Como a interface e a API compartilham o domínio, não é necessário liberar CORS.

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
- Complete uma viagem de teste, com checklist e ocorrência com foto; confira o anexo no painel do gestor.
- Reinicie o serviço e confira que os registros e as fotos permanecem disponíveis.

O health check confirma que o servidor subiu, mas não substitui os testes de login, banco e uploads. O disco exige uma única instância do serviço e os deploys podem interromper o atendimento brevemente. Não exclua o banco nem o disco ao atualizar o código. Planeje backups separados do PostgreSQL e das fotos antes de usar dados reais.

Se o deploy falhar, confira os logs: erros de migration ou conexão com o banco impedem a inicialização. Confira também se o disco está montado em `/data/uploads`.

Referências: [Blueprint](https://render.com/docs/blueprint-spec), [Docker](https://render.com/docs/docker), [discos persistentes](https://render.com/docs/disks) e [limitações do plano gratuito](https://render.com/docs/free).
