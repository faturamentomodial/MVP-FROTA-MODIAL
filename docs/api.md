# API REST

Base local: `http://localhost:8000/api`. Rotas protegidas recebem `Authorization: Bearer <token>`.

## Rotas principais

- `POST /auth/login`, `GET /auth/me`
- `GET|POST /drivers`, `GET|PUT /drivers/{id}`, `PATCH /drivers/{id}/status`
- `GET|POST /vehicles`, `GET|PUT /vehicles/{id}`, `PATCH /vehicles/{id}/status`
- `POST /trips`, `GET /trips`, `GET /trips/current`, `GET /trips/{id}`
- `PUT /trips/{id}/cargo`
- `POST /trips/{id}/start`, `POST /trips/{id}/finish`
- `GET|POST /checklist-items`, `PUT /checklist-items/{id}`
- `POST /trips/{id}/checklist`, `GET /checklists/{id}`
- `POST|GET /occurrences`, `GET|PATCH /occurrences/{id}`
- `GET /dashboard`

Listas administrativas usam `page` e `page_size`. Viagens e ocorrências aceitam filtros por período, motorista, veículo e estado. O dashboard aceita `date_from`, `date_to`, `driver_id`, `vehicle_id` e `occurrence_type`.

A especificação completa e testável fica em `/docs` (Swagger) e `/openapi.json` enquanto a API estiver executando.
