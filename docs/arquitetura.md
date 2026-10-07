# Arquitetura

O sistema é um monólito modular independente. Não compartilha código, banco ou regras com o FreteWay.

## Componentes

- React + TypeScript entrega as interfaces de motorista e gestor.
- FastAPI expõe a API REST e concentra autorização e regras críticas.
- SQLAlchemy gerencia persistência; Alembic controla a evolução do schema.
- PostgreSQL armazena a operação.
- `UploadService` grava imagens em volume local. O contrato isolado permite implementar S3 depois.
- Nginx serve o frontend e encaminha `/api` e `/uploads` no Compose.

## Organização backend

- `api`: rotas, dependências de autenticação e serialização HTTP.
- `core`: configuração, conexão e segurança.
- `models`: entidades e enums.
- `schemas`: entrada e saída com validação.
- `services`: transações e regras de negócio.
- `repositories`: consultas reutilizáveis, como paginação.

## Decisões importantes

- JWT com expiração e hash Argon2.
- Índices únicos parciais impedem viagens simultâneas por motorista e veículo, além das validações de serviço.
- Viagem é a entidade central. Checklist e ocorrência carregam as chaves de viagem, motorista e veículo para consultas gerenciais eficientes.
- Dashboard usa agregações SQL e subconsultas; não carrega registros completos para calcular indicadores.
- Desativação lógica preserva históricos de veículos e motoristas.
- Auditoria simples registra as mutações operacionais relevantes.

