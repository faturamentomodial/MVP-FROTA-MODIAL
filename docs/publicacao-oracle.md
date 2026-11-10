# Publicacao na Oracle com GitHub Actions

O workflow `Deploy Oracle` compila o Dockerfile da raiz no GitHub, transfere a imagem por SSH e executa a aplicacao e PostgreSQL na VM. Executa em pushes na main e manualmente. O Caddy publica interface e API em HTTPS, renova certificados automaticamente e redireciona HTTP para HTTPS. A aplicacao e o banco nao publicam portas diretamente.

## Preparacao da VM

Instale Docker e Compose, mantenha swap para a VM de 1 GB e crie `~/modial-frota/.env` com permissoes 600:

```dotenv
POSTGRES_PASSWORD=senha_aleatoria_hexadecimal
SECRET_KEY=segredo_aleatorio_com_pelo_menos_32_caracteres
HTTPS_DOMAIN=modialfrotas.com.br
```

Gere os segredos no servidor com `openssl rand -hex 32`. Use senha hexadecimal para evitar caracteres especiais na URL do PostgreSQL. Nunca versione esse arquivo. O usuario SSH precisa executar `sudo docker` sem senha, como o usuario ubuntu padrao da imagem Oracle. Libere TCP 80 e 443 na lista de seguranca ou NSG da Oracle e no firewall da VM; UDP 443 e opcional para HTTP/3. Mantenha acesso SSH TCP 22 para os runners GitHub.

O registro DNS A de `modialfrotas.com.br` deve apontar para `168.75.67.111`. Se houver registro AAAA, ele tambem deve chegar a esta VM. `HTTPS_DOMAIN` deve conter somente o nome do dominio, sem protocolo ou barra. O certificado publico depende do DNS correto e das portas acessiveis. O volume `caddy_data` preserva certificados e conta ACME entre deploys; nao o apague. Consulte a [documentacao de HTTPS automatico do Caddy](https://caddyserver.com/docs/automatic-https).

O workflow transfere tambem o `Caddyfile` e verifica a saude pelo endereco HTTPS publico com validacao do certificado. Para atualizar manualmente, copie `docker-compose.oracle.yml` e `Caddyfile` para `~/modial-frota`, carregue `APP_IMAGE` de `.release.env` e execute `sudo env APP_IMAGE="$APP_IMAGE" docker compose -f docker-compose.oracle.yml up -d --wait`. Para diagnosticar a emissao, consulte `sudo env APP_IMAGE="$APP_IMAGE" docker compose -f docker-compose.oracle.yml logs caddy`.

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

Informe os dados do primeiro gestor no terminal. Nao rode o seed de desenvolvimento. Confira `https://modialfrotas.com.br/health` e a interface na raiz. O acesso HTTP ao dominio deve redirecionar para HTTPS.

O volume `modial-frota_postgres_data` preserva o banco entre deploys. Nunca use `down -v` em producao. Migrations executam ao iniciar a aplicacao. Faca backup do banco antes de mudancas de schema; o workflow nao implementa rollback de migrations nem backups automaticos. As imagens de releases anteriores permanecem na VM; monitore o espaco em disco e remova imagens antigas quando necessario.
