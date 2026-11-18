# Alternativa gerenciada: Render

O `render.yaml` prepara um serviço Streamlit com 2 GB de RAM, um disco persistente de 10 GB, HTTPS e subdomínio `onrender.com`. O plano permanece em manutenção até o proprietário ser criado no console privado. Não há domínio próprio obrigatório. A configuração escolhe Virgínia e impede deploy automático por commit.

Na tabela atual da Render, o serviço de 2 GB custa **US$ 25/mês** e o disco custa **US$ 0,25 por GB/mês** (10 GB ≈ US$ 2,50/mês), além de eventual tráfego extra. Preços podem mudar; confira o valor exibido antes de aceitar a cobrança. O plano gratuito não oferece disco persistente nem shell, portanto não atende a este projeto.

## Antes de criar o serviço

1. Conectar uma conta Render ao repositório GitHub do projeto.
2. Revisar o que será enviado: imagem sem bancos, PDFs, `.env`, cofres ou backups. O código e o `render.yaml` ficam no repositório.
3. Decidir se o banco legado e PDFs locais serão transferidos. Se sim, criar e verificar backup cifrado antes de enviar qualquer arquivo ao serviço.
4. Confirmar o custo e criar uma instância de Blueprint a partir de `render.yaml`.

## Primeiro acesso

O serviço inicia em modo manutenção. No Shell privado da Render, execute `python -m scripts.bootstrap_owner` antes de desativar a manutenção. Depois confira o health check, desative o modo manutenção no Dashboard e entre na URL HTTPS da Render. O formulário público nunca cria o primeiro proprietário no modo online.

O disco fica em `/data`; bancos, cofre e PDFs privados/comuns usam esse mesmo volume. O aplicativo continua em uma instância. O processo coletor de mercado não é iniciado automaticamente; sua operação contínua exige plano próprio, e dados ausentes permanecem identificados como ausentes.

## Backup

Render cria snapshots diários de disco, mas eles não substituem o backup lógico cifrado do projeto. Para backup próprio, coloque o serviço em manutenção e gere um arquivo com `python -m scripts.backup_online --create /tmp/backup.tlab` no Shell privado. Transfira o arquivo cifrado para local seguro e remova a cópia temporária. Verifique com `--verify` e ensaie `--restore ... --to /tmp/restored`. Guarde a senha fora da Render. A restauração do banco ativo exige janela de manutenção e validação específica.

## Pendências de aceite

Nenhuma conta Render foi conectada, nenhum serviço foi criado, nenhum dado foi transferido e nenhuma cobrança foi autorizada. Antes de liberar usuários, testar no destino: escrita no disco como usuário não root, reinício preservando registros, HTTPS, login, isolamento, backup e restauração. A possibilidade de operações reais continua apenas em avaliação; o código bloqueia ordens reais.
