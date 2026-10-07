# Banco de dados

## Entidades

- `users`: credenciais, perfil e estado de acesso.
- `drivers`: dados operacionais do motorista, ligados 1:1 ao usuário.
- `vehicles`: cadastro, KM atual e disponibilidade.
- `trips`: saída, retorno, KM e estado da viagem.
- `trip_invoices`: notas fiscais e volumes carregados por viagem.
- `checklist_items`: configuração ordenada dos itens.
- `checklists` e `checklist_answers`: inspeção por viagem e respostas.
- `occurrences` e `occurrence_attachments`: fatos de rota e imagens.
- `audit_logs`: trilha simples de mutações.

## Invariantes

- Uma viagem ativa (`ABERTA` ou `EM_ANDAMENTO`) por motorista.
- Uma viagem ativa por veículo.
- `km_final >= km_inicial`, validado em serviço e por constraint.
- Um checklist por viagem e uma resposta por item em cada checklist.
- Cada nota é única dentro da viagem e deve possuir ao menos um volume.
- Finalizar viagem atualiza `vehicle.km_atual` e libera o veículo na mesma transação.

## Migrações

```bash
cd backend
alembic upgrade head
alembic current
```

Para criar uma nova migração durante o desenvolvimento:

```bash
alembic revision --autogenerate -m "descricao"
```

Revise sempre o arquivo gerado antes de aplicá-lo.
