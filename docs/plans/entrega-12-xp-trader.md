# Entrega 12 — investigação do XP Trader 5.0.4.34

Estado: aprovado pelo usuário e executado em 17/11/2026. Investigação documental, sem conexão XP, SDK ou ordem.

## Diagnóstico verificado

- O commit `b0d31db` concluiu localmente a Entrega 11; o workspace está limpo. `python main.py test` passou com 150 testes antes desta entrega.
- `AGENTS.md` exige confirmação específica de licença, documentação e SDK para XP Trader 5.0.4.34. O projeto não contém DLL, SDK, credenciais, adaptador XP nem evidência de conta de simulação XP vinculada a API.
- O portal e o Laboratório já mostram XP Trader desconectado e ordens reais bloqueadas. O adaptador Binance Spot Testnet é isolado e não comprova compatibilidade com a XP.
- A [Nelogica classifica XP Trader como plataforma White Label](https://ajuda.nelogica.com.br/hc/pt-br/articles/360061369691-Como-realizar-o-download-do-Profit), cujo download exige a área logada; isso não comprova que a licença XP Trader 5.0.4.34 habilite integração por API.
- A [ProfitDLL requer contratação e acesso próprios](https://ajuda.nelogica.com.br/hc/pt-br/articles/51583791325211-Como-obter-acesso-%C3%A0-ProfitDLL). O pacote da licença DLL inclui binários e manual, inacessíveis neste workspace. A [introdução oficial da DLL](https://ajuda.nelogica.com.br/hc/pt-br/articles/11166353435035-Introdu%C3%A7%C3%A3o-ao-Produto-DLL-Real-Time) menciona dados, histórico tick a tick, roteamento e cobertura BM&F/Bovespa, além de ativação válida; não afirma cobertura de BTCUSDT/ETHUSDT ou AAPL/MSFT.
- O [guia oficial do ecossistema ProfitDLL](https://ajuda.nelogica.com.br/hc/pt-br/articles/22396517026203-Ecossistema-ProfitDLL-e-primeiros-passos) distingue inicialização apenas para dados e inicialização com roteamento. O [guia oficial de ordens](https://ajuda.nelogica.com.br/hc/pt-br/articles/13312468554651-Como-rotear-ordens-com-a-ProfitDLL) exige permissão de trading e conta ativa; retorno síncrono não confirma execução, que depende de callbacks. Não há confirmação pública de que a conta simulada do XP Trader 5.0.4.34 seja roteável pela ProfitDLL.
- O [Replay de Mercado em versões White Label](https://ajuda.nelogica.com.br/hc/pt-br/articles/360043469772-Replay-de-Mercado) pode exigir módulo de simulação; isso é recurso da plataforma e não prova acesso de um aplicativo externo ao simulador.
- A busca pública por `XP Trader 5.0.4.34` não encontrou manual oficial da versão, contrato de API próprio ou matriz oficial de compatibilidade com ProfitDLL. Ausência em busca pública não prova inexistência: a confirmação deve vir da Nelogica/XP e dos arquivos da licença aplicável.

## Plano de execução

1. Criar `docs/integrations/xp-trader-5.0.4.34.md` com matriz de evidências para dados, API, SDK, simulação, execução, mercados cobertos e limitações. Separar fatos da plataforma XP Trader, capacidades genéricas da ProfitDLL e pontos ainda não confirmados para a licença e versão do usuário. Registrar fontes oficiais e data de consulta.
2. Registrar o roteiro de validação específica junto à Nelogica/XP: identificação exata da licença, existência de SDK/API para 5.0.4.34, direito de uso de dados, módulo de simulação, possibilidade de ligar a ProfitDLL à conta simulada, mercados e símbolos permitidos, mecanismo de consulta/reconciliação, arquitetura e termos. Não coletar senhas, chaves ou números de conta na documentação.
3. Manter o estado da conexão XP como `desconectado` e sem método de envio de ordem. Atualizar `AGENTS.md`, `PROJECT_DOCUMENTATION.md` e a seção 54 do roadmap com o resultado da investigação e o portão de decisão para uma integração futura. Ajustar a UI apenas se alguma frase atual induzir compatibilidade que não foi demonstrada.
4. Testar que a documentação/estado não alteraram o fluxo de simulação: `python main.py test`, `python main.py status` e inspeção de diff. Se houver ajuste de UI, validar as larguras 1440×1000, 390×844 e 320×740.
5. Apresentar a matriz e as lacunas, sem chamar DLL, sem login e sem ordem. Parar antes da Entrega 13.

## Critérios de aceite

- Dados, APIs, SDK, simulação e execução aparecem com evidência e limite claros para XP Trader 5.0.4.34; capacidade genérica da ProfitDLL não é apresentada como direito da licença XP.
- BTCUSDT, ETHUSDT, AAPL e MSFT permanecem fora de qualquer cobertura XP presumida.
- O produto permanece desconectado, sem credenciais em SQLite, sem DLL carregada e sem rota para ordem real ou simulada via XP.
- A suíte obrigatória passa e a documentação permite uma decisão humana sobre o próximo passo técnico.

## Fora do escopo

- Contratar licença ou módulo, baixar SDK, usar conta pessoal, integrar ProfitDLL, implementar feed B3 ou enviar ordens.
