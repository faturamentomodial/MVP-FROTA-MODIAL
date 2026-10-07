# Docker no Microsoft Azure

O projeto não depende de uma plataforma específica. O Dockerfile na raiz compila o frontend React e o inclui no servidor Python. A interface e a API usam o mesmo domínio. Checklists e ocorrências são registrados por texto, sem uploads ou disco de fotos.

## Opção recomendada

Use Azure Container Apps para o container da aplicação, Azure Container Registry para a imagem e Azure Database for PostgreSQL Flexible Server para o banco persistente. O `docker-compose.yml` continua disponível para desenvolvimento local e também pode ser executado em uma máquina virtual Linux com Docker instalado.

O Container Apps recebe uma imagem Docker e configurações de execução; não executa diretamente o Compose local com seus três serviços. Para essa opção, use a imagem completa gerada pelo Dockerfile na raiz, com PostgreSQL separado.

## Configurações da aplicação

- Container Linux, construído a partir de `./Dockerfile` com contexto na raiz.
- Entrada HTTP externa com porta de destino **8080**. O processo escuta em `0.0.0.0`; `PORT` permite alterar a porta quando necessário.
- `DATABASE_URL`: URL do PostgreSQL com driver psycopg, por exemplo `postgresql+psycopg://USUARIO:SENHA@HOST:5432/BANCO?sslmode=require`. Codifique caracteres especiais do usuário e da senha na URL e configure a rede para permitir a conexão.
- `SECRET_KEY`: chave aleatória de pelo menos 32 caracteres, configurada como segredo.
- `ENVIRONMENT=production`.
- `CORS_ORIGINS`: pode ficar vazio quando a interface e a API usam o mesmo domínio.
- Endpoint de saúde: `/health`.

O Dockerfile já define `FRONTEND_DIST` e `VITE_API_URL=/api`. Não envie `.env` para a imagem nem salve credenciais no repositório.

As migrations executam na inicialização, antes de a API começar a atender. Para a implantação inicial, use uma única réplica e evite inicializações simultâneas executando migrations. Se for aumentar réplicas ou usar revisões concorrentes, separe as migrations em uma etapa única da implantação. Configure tempo de inicialização suficiente para as migrations concluírem antes de considerar o container indisponível.

## Primeiro acesso e validação

Em um terminal interativo do container conectado ao banco, execute `python -m app.create_admin`. Informe nome, email e senha para criar o primeiro gestor. Não use o seed de desenvolvimento em produção.

Valide `/health`, login, cadastro de motorista e veículo, checklist, ocorrência por escrito e finalização de viagem. Atualize uma página interna no navegador e confirme que ela continua abrindo. Os dados devem permanecer no PostgreSQL após reiniciar ou substituir o container.

Este guia descreve a configuração necessária; nenhum recurso foi criado no Azure. O sistema requer o provisionamento do banco, a publicação da imagem e a configuração do serviço antes de ficar online.

Referências: [Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/overview) e [aplicação Python com PostgreSQL](https://learn.microsoft.com/en-us/azure/developer/python/tutorial-deploy-python-web-app-azure-container-apps-01).
