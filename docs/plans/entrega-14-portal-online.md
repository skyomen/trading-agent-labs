# Entrega 14 — Portal online autorizado

Estado: pacote local de servidor, bootstrap e backup implementado em 17/11/2026. A entrega continua aberta; publicação depende de conta de hospedagem paga e autorização final para transferir dados locais. A alternativa Render dispensa domínio próprio.

## Base

- Entrega 13 concluiu login local, workspaces isolados, credenciais cifradas e 157 testes. O servidor ainda escuta apenas `127.0.0.1`.
- Streamlit exige um processo Python persistente e WebSocket. SQLite, PDFs e cofre exigem armazenamento persistente. Um servidor/container com volume atende à arquitetura atual; Vercel Functions exigiria reescrever a persistência e a sessão. Render, com serviço pago e disco, fornece alternativa gerenciada com subdomínio e TLS próprios.
- A documentação oficial do Streamlit recomenda TLS no proxy reverso para produção. A autenticação OIDC nativa exige provedor e configuração ainda não escolhidos.
- O contrato vigente mantém somente simulação. Nenhuma ordem real entra nesta entrega.

## Implementação local preparatória

1. Empacotar o app para servidor com armazenamento persistente e proxy HTTPS; nunca publicar a porta Streamlit diretamente.
2. Bloquear cadastro inicial pelo navegador no modo online. Criar o proprietário por comando interativo no servidor antes de expor o domínio.
3. Manter login e autorização por workspace; limitar sessão e tentativas, preservar XSRF/CORS e impedir retorno a credenciais globais do processo.
4. Preparar backup consistente dos bancos SQLite, vault e PDFs, com verificação de restauração isolada e health check. Revisar logs do ambiente de destino antes de liberar usuários.
5. Testar dois usuários, acesso sem login, bootstrap, isolamento, integridade de backup e reversão. Rodar `python main.py test` e prova visual.

## Publicação

1. Escolher provedor/servidor, endereço HTTPS, destino de backup e quem administrará as contas. Confirmar direitos de uso e transferência dos PDFs/dados persistidos.
2. Montar volumes persistentes; configurar DNS, HTTPS, segredos e backup fora do repositório.
3. Fazer cópia verificada dos dados locais. Criar o proprietário por console; publicar somente depois de testar autenticação, isolamento e restauração no ambiente de destino.
4. Registrar URL, teste de acesso, recuperação operacional, limites e responsável. Não ligar corretora real nem credenciais antigas por padrão.

## Critério de aceite

Usuários autorizados entram via HTTPS, cada um vê somente seu workspace, dados persistem após reinício, backup restaura em ambiente isolado e o portal não permite cadastro público inicial. Sem hospedagem configurada, a entrega fica preparada mas não publicada.
