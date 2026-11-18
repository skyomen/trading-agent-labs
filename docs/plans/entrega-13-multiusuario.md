# Entrega 13 — Knowledge Base Global e User Workspace

Estado: aprovado pelo usuário e implementado localmente em 17/11/2026. A prova final consta em `PROJECT_DOCUMENTATION.md`.

## Base verificada

- Commit `130110e` concluiu a investigação XP; o workspace está limpo e `python main.py test` passou com 150 testes.
- Hoje `database/store.py` abre sempre `database/trading.db`. Documentos, conhecimento, tarefas, estratégias, datasets, trilhas, operações e ordens Testnet coexistem nesse arquivo, sem proprietário. `app.py` escolhe a vista por sessão Streamlit, mas não autentica usuário. Os conectores leem credenciais do ambiente do **processo**, que também não identifica usuário.
- O roadmap exige distinguir `Knowledge Base Global` de `User Workspace` e que cada usuário configure suas próprias credenciais. A Entrega 14, portal online para usuários autorizados, é separada; portanto esta etapa permanece local.
- O [Session State do Streamlit](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state) é vinculado ao WebSocket e se perde ao recarregar a página. Ele pode guardar a identidade de uma sessão local após login, mas não substitui autenticação persistente. A [autenticação OIDC nativa do Streamlit](https://docs.streamlit.io/develop/api-reference/user/st.login) exige provedor de identidade externo, ainda não definido para este projeto.
- A [orientação OWASP para senhas](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) recomenda hash lento com salt exclusivo; nunca armazenar senha em texto puro ou SHA-256 simples.

## Decisões propostas

1. **Identidade local, sem exposição em rede.** Criar contas locais com senha, hash Argon2id e verificação com limitação de tentativas. `python main.py dashboard` escuta somente `127.0.0.1`. O primeiro cadastro do proprietário ocorre apenas no bootstrap local, uma vez; contas adicionais são criadas pelo proprietário. Sem login, nenhuma página ou snapshot lê dados do workspace. Logout limpa identidade, prévias e chaves da sessão. Recarregar a página pede novo login. Isso não declara o portal pronto para internet.
2. **Isolamento por arquivo.** Preservar `database/trading.db` como workspace do proprietário, sem mover ou apagar o legado. Cada conta nova recebe `database/workspaces/<id>.db`, criada com o esquema vigente e seis agentes iniciais. Uma pequena base `database/identity.db` mantém IDs, usuário, papel, hash de senha e vínculo de arquivo. `database/store.py` recebe contexto de usuário explícito e resolve somente o banco desse usuário; caminhos vêm do registro interno, nunca de entrada do navegador. Serviços e scripts não podem usar o banco de outro usuário por ID de registro. Comandos CLI locais continuam funcionando com contexto administrativo explícito.
3. **Conhecimento global curado.** `database/global_knowledge.db` e o acervo `reference_docs/shared/`/`reference_docs/agents/<slug>/` formam a biblioteca comum. Somente itens aprovados, com hash de PDF atual e promovidos pelo proprietário, compõem o contexto global. Propostas e rejeições não são globais. PDF, trecho, memória, revisão e proposta adicionados por um usuário ficam em seu workspace e só compõem o próprio contexto após aprovação. Documentos particulares vão para um diretório por ID de usuário; caminho livre não pode escapar desse diretório. O legado não é publicado automaticamente como conhecimento global: revisão explícita identifica os itens elegíveis.
4. **Credenciais por usuário.** Substituir leituras diretas de `.env`/variáveis de processo nas ações de IA, Alpaca e Binance Spot Testnet por um `CredentialProvider` do workspace. O usuário configura suas próprias chaves pela UI, sem exibição posterior. Segredos ficam cifrados fora de SQLite com chave derivada da senha de login e salt próprio; a chave só vive na sessão. Sem credencial daquele usuário, o conector fica desconectado. Não há fallback para a chave global antiga em modo multiusuário. O proprietário precisa cadastrar novamente suas chaves no cofre pessoal antes de usar conectores.
5. **Separação em todas as superfícies.** Portal, Laboratório, arquivos, exports, eventos, métricas, feed persistido, estratégias, backtests, pipeline, diário paper, aprendizado e ordens Testnet consultam exclusivamente o workspace autenticado. O catálogo comum aparece com fonte global. Idempotência de barra e limites de risco operam por workspace. Os fluxos de envio à Testnet mantêm o portão humano e não usam credenciais de outro usuário.

## Implementação proposta

1. Introduzir `services/auth.py` e `services/credential_vault.py`; adicionar dependências de hash/criptografia em `requirements.txt`. Verificar suporte e parâmetros no ambiente Windows atual. Senhas são verificadores no `identity.db`, chaves de API permanecem fora de SQLite.
2. Refatorar `database/store.py` para receber contexto de workspace em cada conexão, com caminho resolvido internamente e migração aditiva/idempotente. Criar camada separada para a base global sem abrir SQLite diretamente na UI. Fazer bootstrap do proprietário sem alterar `database/trading.db` até o login ser concluído; manter backup operacional antes da migração.
3. Separar indexação e contexto global/privado em `services/documents.py` e `services/knowledge.py`, preservando citações e hashes. Promover conhecimento global apenas por ação do proprietário, com trilha de origem e revisão.
4. Proteger as duas apresentações do `app.py` com login antes de qualquer consulta ao workspace, página de contas para o proprietário e configuração de credenciais por usuário. Injetar credenciais nos serviços externos; nenhuma consulta privada durante renderização.
5. Cobrir em testes: bootstrap, login/logout, senha inválida, limitação de tentativas, dois usuários com IDs iguais em bancos distintos, ausência de vazamento entre portal/Laboratório/exports/serviços, contexto global aprovado versus privado, hash desatualizado, segredos cifrados e não serializados, conectores sem fallback global e migração preservando histórico do proprietário.
6. Criar prova `python -m scripts.run_delivery13 --prova` com dois usuários, bancos temporários, documentos e credenciais sintéticos, sem rede. Rodar `python main.py test`, `python main.py status` e checagem de portal/Laboratório em 1440×1000, 390×844 e 320×740. Atualizar `AGENTS.md`, `PROJECT_DOCUMENTATION.md` e roadmap; demonstrar critérios e parar antes da Entrega 14.

## Portões e limites

- A interface local não permitirá alternar usuário por parâmetro de URL, nome de arquivo ou seleção sem senha.
- O primeiro usuário não ganha automaticamente permissão de publicar conhecimento privado de outros. A promoção global exige revisão explícita do proprietário e proveniência vigente.
- Nenhuma chave de API entra em SQLite, eventos, logs, snapshots HTML ou respostas de erro. Mudança de senha exige recifrar o cofre na mesma sessão; recuperação sem senha não revela segredos antigos.
- O modo local e a autenticação proposta **não** constituem autorização para publicar o portal na internet. OIDC, TLS, cookies, recuperação de conta, políticas de sessão e operação multi-instância pertencem à Entrega 14.
- Nenhum conector XP, ordem real ou nova estratégia entra neste escopo.

## Critérios de aceite

- Dois usuários autenticados veem seis agentes e somente seus próprios registros operacionais, inclusive após reiniciar o aplicativo.
- Biblioteca global mostra apenas conhecimento comum promovido, aprovado e com hash atual; workspace privado não vaza para outro usuário.
- Cada conector usa somente a credencial do usuário ativo; ausência dela mantém o conector indisponível, mesmo que exista chave de outro usuário ou no ambiente antigo.
- Histórico legado permanece no workspace do proprietário; testes obrigatórios e prova isolada passam, sem chamada externa.
