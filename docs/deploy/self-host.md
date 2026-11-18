# Publicar o portal em servidor próprio

Esta configuração usa um processo Streamlit persistente, volumes Docker para SQLite/PDFs e Caddy como proxy HTTPS. O projeto continua **somente em simulação**. Não inclua banco, PDFs, credenciais ou backup no repositório.

## Pré-requisitos

- Servidor Linux com Docker Compose, domínio apontando para o servidor e portas 80/443 acessíveis.
- Acesso privado ao console do servidor para criar o primeiro administrador e fazer backups.
- Definir quem pode acessar o portal e quais PDFs/dados locais podem ser transferidos. O banco legado do proprietário é opcional; se for transferido, faça backup verificado antes.

## Preparar e iniciar

Crie `.env.production` no diretório do projeto no servidor; esse nome já está coberto por `.gitignore`:

```text
TRADING_LAB_DOMAIN=lab.seudominio.com
TRADING_LAB_TLS_EMAIL=voce@seudominio.com
```

Execute no diretório do projeto no servidor:

```sh
docker compose --env-file .env.production build
docker compose --env-file .env.production run --rm --no-deps app python -m scripts.bootstrap_owner
docker compose --env-file .env.production up -d
docker compose --env-file .env.production ps
```

O cadastro principal é feito somente no console. Se `identity.db` estiver vazio, o modo online bloqueia o cadastro pelo navegador. Outros usuários são criados pelo proprietário após login. A porta 8501 fica apenas na rede interna do Compose; Caddy publica 80/443 e obtém TLS para o domínio. O app não usa API keys do processo para usuários autenticados.

## Backup e prova de restauração

Crie a pasta `backups/` no host e proteja seu acesso. O arquivo `.tlab` é cifrado com uma senha independente; guarde senha e arquivo em locais separados. O script nunca substitui um backup existente.

```sh
docker compose --env-file .env.production stop app
docker compose --env-file .env.production run --rm --no-deps -v "$(pwd)/backups:/backups" app python -m scripts.backup_online --create /backups/portal-AAAA-MM-DD.tlab
docker compose --env-file .env.production start app
docker compose --env-file .env.production run --rm --no-deps -v "$(pwd)/backups:/backups:ro" app python -m scripts.backup_online --verify /backups/portal-AAAA-MM-DD.tlab
```

Para ensaiar restauração, execute o mesmo script com `--restore /backups/portal-AAAA-MM-DD.tlab --to /tmp/restored` em um container temporário. Ele só escreve em um destino vazio, verifica senha e hashes, e não altera o volume ativo. A restauração real deve ocorrer com o app parado, após revisão do conteúdo e cópia para os volumes corretos. Faça backup antes de cada atualização e teste a restauração periodicamente.

## Limites atuais

O portal não está publicado por este repositório: faltam servidor, domínio e decisão sobre transferência dos dados locais. O login local não oferece recuperação de senha. Não há configuração de OIDC ou operação multi-instância. A integração XP Trader continua desconectada e nenhuma ordem real é preparada ou enviada.
