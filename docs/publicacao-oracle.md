# Publicacao na Oracle com GitHub Actions

O workflow `Deploy Oracle` compila o Dockerfile da raiz no GitHub, transfere a imagem por SSH e executa a aplicacao e PostgreSQL na VM. Executa em pushes na main e manualmente. A porta 80 serve interface e API; o banco nao publica portas. Configure HTTPS antes de usar credenciais e dados reais pela internet.

## Preparacao da VM

Instale Docker e Compose, mantenha swap para a VM de 1 GB e crie `~/modial-frota/.env` com permissoes 600:

```dotenv
POSTGRES_PASSWORD=senha_aleatoria_hexadecimal
SECRET_KEY=segredo_aleatorio_com_pelo_menos_32_caracteres
CORS_ORIGINS=http://168.75.67.111
```

Gere os segredos no servidor com `openssl rand -hex 32`. Use senha hexadecimal para evitar caracteres especiais na URL do PostgreSQL. Nunca versione esse arquivo. O usuario SSH precisa executar `sudo docker` sem senha, como o usuario ubuntu padrao da imagem Oracle. Libere TCP 80 na lista de seguranca ou NSG da Oracle e no firewall da VM; mantenha acesso SSH TCP 22 para os runners GitHub.

## Secrets do GitHub

Em Settings > Secrets and variables > Actions configure `ORACLE_HOST`, `ORACLE_USER`, `ORACLE_SSH_KEY` e `ORACLE_KNOWN_HOSTS`. O ultimo deve conter a chave publica do host obtida na sessao SSH ja autenticada, por exemplo com:

```bash
printf '168.75.67.111 '
cat /etc/ssh/ssh_host_ed25519_key.pub
```

Salve a linha inteira com IP, tipo e chave. O workflow valida a identidade do host e nunca usa a chave privada do host.

## Primeiro acesso e operacao

Apos o deploy, na VM:

```bash
cd ~/modial-frota
export $(cat .release.env)
sudo env APP_IMAGE="$APP_IMAGE" docker compose -f docker-compose.oracle.yml exec app python -m app.create_admin
```

Informe os dados do primeiro gestor no terminal. Nao rode o seed de desenvolvimento. Confira `http://168.75.67.111/health` e a interface na raiz.

O volume `modial-frota_postgres_data` preserva o banco entre deploys. Nunca use `down -v` em producao. Migrations executam ao iniciar a aplicacao. Faca backup do banco antes de mudancas de schema; o workflow nao implementa rollback de migrations nem backups automaticos. As imagens de releases anteriores permanecem na VM; monitore o espaco em disco e remova imagens antigas quando necessario.
