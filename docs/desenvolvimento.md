# Desenvolvimento

## Variáveis

Copie `.env.example` para `.env`. Defina uma `SECRET_KEY` longa e aleatória. A aplicação aceita ainda `DATABASE_URL`, `CORS_ORIGINS` e `ACCESS_TOKEN_EXPIRE_MINUTES`.

## Banco e usuário inicial

Execute `alembic upgrade head`. Em desenvolvimento, `python -m app.seed` cria 3 motoristas, 5 veículos, os 15 itens padrão e registros históricos. O comando é idempotente para banco já preenchido e bloqueado em produção.

Usuários reais devem ser criados pelo gestor na tela Motoristas. Esse fluxo cria, na mesma transação, a conta de acesso e o cadastro operacional.

## Testes

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```

Os testes usam SQLite isolado para velocidade; a validação do Compose aplica a migração em PostgreSQL. Para validar o frontend:

```bash
cd frontend
npm run build
```

## Produção

- configure segredos fortes fora do repositório;
- use HTTPS no proxy de borda;
- mantenha `ENVIRONMENT=production`;
- faça backup do PostgreSQL;
- restrinja `CORS_ORIGINS` ao domínio real;
- execute migrações antes de subir a nova versão.

