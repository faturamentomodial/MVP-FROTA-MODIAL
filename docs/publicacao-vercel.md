# Publicação para testes na Vercel

A Vercel publica o frontend React/Vite. A API Python e o PostgreSQL devem estar em um servidor externo. O `docker-compose.yml` atual continua sendo a opção para testes locais.

## 1. Preparar a API

Publique `backend/Dockerfile` em um servidor que execute containers, com HTTPS e acesso a um PostgreSQL persistente. O container executa as migrations ao iniciar e escuta na porta 8000. Configure no serviço do backend:

- `DATABASE_URL`: conexão `postgresql+psycopg://usuario:senha@host:5432/banco` (configure TLS conforme o provedor).
- `SECRET_KEY`: chave aleatória de pelo menos 32 caracteres.
- `ENVIRONMENT=production`.
- `CORS_ORIGINS=https://seu-projeto.vercel.app`: endereço exato do frontend, sem barra final. Para outros domínios, separe por vírgula.

Confirme que `https://ENDERECO-DA-API/health` retorna `{"status":"ok"}`. O health check só confirma a API; login e cadastros também precisam ser testados para validar o banco. Cadastre os usuários de teste pelo procedimento de administração do projeto. O seed de desenvolvimento não executa com `ENVIRONMENT=production`; nunca use o banco de operação para dados fictícios.

## 2. Publicar a interface

Pelo painel da Vercel, importe o repositório e configure:

| Campo | Valor |
| --- | --- |
| Root Directory | `frontend` |
| Framework Preset | `Vite` |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Environment Variable | `VITE_API_URL=https://ENDERECO-DA-API/api` |

Configure a variável nos ambientes Production e Preview usados nos testes. O build na Vercel exige uma URL pública HTTPS terminando em `/api`. Após mudar a variável, faça um novo deploy: o Vite inclui o valor no build.

O projeto está vinculado ao [repositório MVP-FROTA-MODIAL](https://github.com/faturamentomodial/MVP-FROTA-MODIAL). Importe esse repositório no painel da Vercel. Como alternativa, publique pelo terminal, dentro de `frontend`, usando `npx vercel login` e `npx vercel`. No vínculo com o projeto, mantenha a raiz como a pasta atual (`./`). Configure `VITE_API_URL` nas configurações do projeto antes do build e repita `npx vercel` para Preview ou `npx vercel --prod` para Production.

As variáveis `VITE_` ficam públicas no navegador. `SECRET_KEY`, senhas e `DATABASE_URL` pertencem somente ao backend. `.env` e `.vercel` estão ignorados no Git.

O `frontend/vercel.json` configura o build e o fallback para `index.html`, permitindo atualizar páginas internas. As chamadas à API vão diretamente ao endereço configurado. O proxy local do Vite não existe na Vercel.

Para previews com URLs diferentes, inclua o endereço exato autorizado em `CORS_ORIGINS` e reinicie o backend. Use uma API e um banco exclusivos para testes.

## 3. Validar no computador e no celular

1. Abra `/login`, faça login e confirme o perfil e os cadastros.
2. Atualize uma página interna diretamente e confirme que ela abre.
3. Inicie uma viagem, preencha o checklist.
4. Registre uma ocorrência por escrito e confira a descrição no painel do gestor.
5. Finalize o fluxo e confirme os dados após sair e entrar novamente.
6. Reinicie o backend e confirme que os registros permanecem disponíveis.

Se o navegador indicar erro de CORS, confira o domínio do frontend na API. Se uma chamada de API retornar HTML, confira `VITE_API_URL` e refaça o deploy.

Referência: [Vite na Vercel](https://vercel.com/docs/frameworks/frontend/vite).
