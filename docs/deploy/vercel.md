# Avaliação de compatibilidade com Vercel

**Estado em 19/11/2026: não implantar o aplicativo completo atual na Vercel.** O projeto não contém `vercel.json`, integração `.vercel/` nem handler de função Vercel. O CLI não está instalado/configurado neste ambiente. O repositório aponta para GitHub, mas isso não torna um app Streamlit implantável na Vercel automaticamente.

## Por que não funciona como está

- O aplicativo é um servidor Streamlit contínuo (`python main.py dashboard`), e não uma função HTTP Python com handler por rota. O runtime Python documentado pela Vercel empacota funções serverless, com limites de duração; não há configuração de runtime que converta `streamlit run app.py` num serviço web persistente.
- O dashboard e o coletor usam SQLite/arquivos locais e precisam de armazenamento persistente. O filesystem de Vercel Functions é somente leitura, exceto `/tmp`, que é temporário; isso não atende aos bancos SQLite, documentos e cofres do projeto.
- `scripts/run_paper_auto.py` e `services.market_data stream` são processos contínuos iniciados separadamente. Funções Vercel têm duração limitada e não são supervisores de worker permanente.
- Mesmo com suporte recente a WebSocket para Vercel Functions, isso não resolve a necessidade de processo Streamlit contínuo, workspace persistente e coletor/automações long-lived.

Fontes oficiais consultadas:

- [Runtime Python da Vercel](https://vercel.com/docs/functions/runtimes/python) — runtime para funções HTTP Python e empacotamento da função.
- [Runtimes e sistema de arquivos](https://vercel.com/docs/functions/runtimes) — filesystem somente leitura com `/tmp` temporário e limite de duração.
- [Limites de duração das funções](https://vercel.com/docs/functions/limitations) — funções terminam ao exceder a duração máxima configurada.
- [WebSocket nas Functions](https://vercel.com/kb/guide/do-vercel-serverless-functions-support-websocket-connections) — suporte WebSocket não é armazenamento durável nem worker contínuo.

## Destinos já preparados

- **Servidor próprio:** `Dockerfile`, `compose.yaml` e `docs/deploy/self-host.md` descrevem Streamlit persistente, volume, HTTPS e backup.
- **Render:** `render.yaml` e `docs/deploy/render.md` descrevem disco persistente e serviço Docker de instância única; há custo e configuração de proprietário/backup pendentes.

## Se Vercel for requisito futuro

Tratar como migração de arquitetura, não como configuração de deploy: separar frontend de API persistente; migrar SQLite para banco gerenciado; colocar documentos/cofres em armazenamento seguro; executar coleta e paper automation em worker gerenciado próprio; implementar autenticação online e autorização; verificar backup/restore, segredos e políticas de rede. Manter simulação e proibição de ordens reais. Um eventual frontend estático independente pode ser hospedado na Vercel, mas não substitui nem publica o backend atual.

Não criar projeto Vercel ou enviar dados do workspace como parte desta avaliação. Nenhum deploy foi iniciado.
