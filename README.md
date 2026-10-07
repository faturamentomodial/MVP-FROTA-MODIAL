# Modial Controle de Frota

Para hospedar o sistema completo (interface, API e banco), consulte [publicação na Render](docs/publicacao-render.md). O repositório inclui `render.yaml` e um Dockerfile completo na raiz.

Para publicar a interface e configurar a API externa, consulte [publicação na Vercel](docs/publicacao-vercel.md).

MVP independente para checklist e controle de frota da Modial Artigos Funerários. Motoristas usam um fluxo mobile linear; gestores acompanham cadastros, viagens, checklists, ocorrências, quilometragem e indicadores em um painel responsivo.

## Início rápido com Docker

Pré-requisito: Docker Desktop em execução.

```bash
copy .env.example .env
docker compose up --build -d
```

Acesse:

- Aplicação: http://localhost:3000
- Documentação interativa da API: http://localhost:8000/docs
- Saúde da API: http://localhost:8000/health

Para carregar dados fictícios em um ambiente exclusivo de desenvolvimento, execute `docker compose exec backend python -m app.seed`. Não execute esse comando no banco destinado à operação real.

Credenciais do seed (somente desenvolvimento):

- Gestor: `admin.frota@modial.com.br` / `Admin@123`
- Motorista: `motorista1@modial.com.br` / `Motorista@123`

Troque todas as senhas e `SECRET_KEY` fora do ambiente local. O seed se recusa a executar com `ENVIRONMENT=production`.

## Comandos úteis

```bash
# migrations
docker compose exec backend alembic upgrade head

# testes automatizados
docker compose exec backend pip install -r requirements-dev.txt
docker compose exec backend pytest -q

# logs
docker compose logs -f backend frontend

# encerrar
docker compose down
```

## Desenvolvimento sem Docker

Backend (use um PostgreSQL acessível e configure `DATABASE_URL`):

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

O Vite encaminha `/api` para `localhost:8000`.

## Estrutura

- `backend/app`: API, regras, modelos, schemas, repositórios e serviços.
- `backend/migrations`: histórico Alembic.
- `backend/tests`: testes de autenticação e fluxo operacional.
- `frontend/src`: páginas separadas por perfil, componentes, layouts e serviços.
- `docs`: arquitetura, banco, API e fluxos.

Consulte [desenvolvimento](docs/desenvolvimento.md) para configuração detalhada.

O fluxo operacional por nota, a migration necessária e a validação estão descritos em [entregas operacionais](docs/entregas-operacionais.md).
