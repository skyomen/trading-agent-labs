# Trading Agent Lab: Coluna do projeto

## Propósito e limites

Laboratório local para acompanhar seis agentes de pesquisa intraday, organizar conhecimento técnico e avaliar estratégias com dados rastreáveis. A interface deve distinguir fatos, propostas, históricos e integrações ausentes.

- Operação exclusivamente em simulação; nenhuma ordem real será preparada ou enviada.
- Não apresentar preço, saldo, sinal, retorno ou operação fictícia como resultado de mercado.
- PDFs são processados localmente por padrão. Compartilhar contexto com IA externa exige autorização explícita por tarefa.
- Aprendizado e estratégias entram como propostas; promoção exige revisão humana.
- Produto alvo informado: XP Trader 5.0.4.34 da Nelogica. Não presumir compatibilidade com Profit Pro/Ultra.
- Criptoativos e ações dos EUA exigem fontes de dados próprias; XP/ProfitDLL não será presumido como fonte universal.

## Requisitos ativos — escritório

- **REQ-01** — Implementar as oito áreas do protótipo aprovado, com sala de analistas e posto de execução separados. Referência de escopo/visual: `trading-office-preview.html`.
- **REQ-02** — Usar seis agentes e seus estados reais do SQLite. Não inventar atividade de agente, cotação, P&L, saldo ou sinal.
- **REQ-03** — Indexar PDFs de `reference_docs/shared/` e `reference_docs/agents/<slug>/` localmente, com hash, nome, página, estado e erro persistidos. O agente só recebe contexto de escopo autorizado.
- **REQ-04** — Persistir tarefas, eventos, memórias, revisões, estratégias, backtests e operações. Toda tarefa de agente grava início, resultado ou falha.
- **REQ-05** — Memória aprovada pode compor contexto; proposta/rejeitada não. Erros podem gerar revisão e aprendizado proposto, sempre com aprovação humana antes de promoção.
- **REQ-06** — Informe, Mercado, Operações e Evolução do capital refletem somente registros persistidos e identificam fonte/limite. Estados sem dados têm vazio explícito.
- **REQ-07** — Importar histórico OHLCV CSV com validação e hash. Executar apenas estratégia versionada e aprovada, com custos informados; identificar resultados como históricos/simulados.
- **REQ-08** — Conexões mostram estado e requisitos. Segredos não ficam em SQLite nem são exibidos. Provedores externos só são chamados por ação explícita.
- **REQ-09** — XP Trader 5.0.4.34 requer confirmação específica de licença, documentação e SDK antes de integração. Nenhuma ordem é encaminhada neste escopo.
- **REQ-10** — Cobrir fluxos novos com testes; `python main.py test` é a prova automatizada obrigatória.
- **REQ-11 (superado visualmente por REQ-12)** — Reorganizar visualmente o aplicativo para seguir `referencia.html`: métricas no cabeçalho, navegação e conteúdo em painel lateral, ficha do agente, vistas Sala/Laboratório/Evolução do capital, sala isométrica, resumo de agentes e quadro do diretor. Usar os seis agentes reais em sala de análise e sala de execução separada; manter os recursos locais existentes acessíveis na navegação. A instrução posterior do usuário substitui a proibição de cópia visual.
- **REQ-12 (superado por REQ-13)** — O modo padrão deveria exibir uma cópia visual e estrutural literal de `referencia.html`. A decisão posterior autoriza localizar a interface e trocar a origem dos dados, mantendo o arquivo de referência intacto.
- **REQ-13** — Preservar a estrutura visual de `referencia.html`, incluindo sala isométrica, parede de estado e ticker; traduzir todos os rótulos para pt-BR e carregar os seis agentes, estados, documentos, eventos e contagens persistidos em SQLite. Não executar carregadores GitHub/Kraken nem apresentar dados fictícios. XP permanece desconectada; Mercado mostra somente feeds locais autorizados e identifica frescor/ausência; capital, backtest e operações sem registros exibem estados vazios. Em qualquer largura, manter uma única rolagem vertical no documento, sem rolagem horizontal; adaptar a sala para manter seus elementos dentro da viewport. Validar seleção, abas e salas em 1440×1000, 390×844 e 320×740.

## Contratos técnicos

- **TRD-01** — Interface Streamlit; persistência SQLite em `database/trading.db`, acessada somente por `database/store.py`.
- **TRD-02** — Migrações aditivas e idempotentes. Preservar agentes, eventos e histórico já existentes.
- **TRD-03** — `python main.py status`, `python main.py test` e `python main.py dashboard` são os comandos CLI suportados.
- **TRD-04** — `requirements.txt` é a fonte das dependências Python.
- **TRD-05** — PDFs são extraídos por `services/documents.py`; execução de IA fica em `services/agents.py`; CSV e backtests ficam em `services/backtest.py`. UI não abre conexões de mercado diretamente.

## Referência técnica detalhada

- [`PROJECT_DOCUMENTATION.md`](PROJECT_DOCUMENTATION.md) documenta a arquitetura implementada, fluxos, esquema SQLite, estado observado, limites, provas históricas e pendências. Atualize essa referência quando o comportamento documentado mudar; `AGENTS.md` continua sendo a autoridade para requisitos e regras.

## Entrega 2 — Conhecimento Real

- **REQ-14 (derivado do roadmap)** — Estruturar conceitos e setups extraídos localmente com citação de arquivo/página/hash, estado de proposta e revisão humana. Apenas conhecimento aprovado e com hash de origem atual pode compor contexto de agente. Descoberta de setup não equivale a regra formal, estratégia aprovada ou autorização de backtest/operação.
- **TRD-06** — Persistir conhecimento em `knowledge_items`, com versões por origem/página/hash e estados `proposed`, `approved` e `rejected`; a extração é determinística e local em `services/knowledge.py`.

## Entrega 3 — quatro setups

- **REQ-15** — VBS, VSS, BOP e BDP foram selecionados pelo usuário. As regras v1 têm parâmetros operacionais aprovados em 13/11/2026, versões imutáveis e fontes PDF com hash. O motor de sinais usa apenas barras já fechadas. O backtest dos quatro padrões pertence à Entrega 5.
- **TRD-07** — `services/setup_specs.py` define e registra versões; `services/setup_signals.py` detecta sinais sem executar operações. O SQLite preserva rascunhos v1 e versões aprovadas v2. Incremento mínimo, custos e horário dependem dos metadados do histórico da Entrega 4.

## Entrega 4 — dados históricos e atualização contínua

- **REQ-16** — Importações OHLCV possuem manifesto de mercado, fonte, símbolo, intervalo, fuso UTC, moeda, incremento mínimo, unidade de volume e direito de uso declarado; hash do arquivo e hash canônico das barras permitem reprodução. Histórico importado é um snapshot imutável. Lacunas ficam explícitas.
- **REQ-17** — BTCUSDT e ETHUSDT usam dados públicos Binance Spot para snapshots e candles fechados em WebSocket, com reconexão e backfill. O processo coletor deve ser iniciado explicitamente e supervisionado para operação contínua. A interface mostra estado/idade persistidos; não confunde histórico com cotação atual.
- **REQ-18** — AAPL e MSFT possuem amostras horárias históricas públicas Market History, sem conta; são fonte histórica, não feed em tempo real. O conector opcional Alpaca IEX exige credenciais de dados no ambiente local e ação explícita. IEX não representa o mercado consolidado. Sem credenciais, manter a Alpaca desconectada; nenhuma chave em SQLite/logs. Streaming de ações depende de implementação e validação posteriores.
- **TRD-08** — `services/datasets.py` valida manifesto e integridade; `services/market_data.py` acessa fontes externas mediante ação explícita. `database/store.py` é o único acesso a SQLite. O coletor é separado da interface e não possui função de negociação.

## Entrega 5 — backtest dos quatro setups

- **REQ-19** — Executar VBS, VSS, BOP e BDP aprovados apenas sobre snapshots BTCUSDT/ETHUSDT Binance Spot de 1m com hash canônico verificado. Agregar blocos UTC completos de 2m/5m, descartar e reportar blocos parciais e gaps. AAPL/MSFT horários são inelegíveis.
- **REQ-20** — Simular ordem stop somente na barra seguinte ao sinal, expiração se não acionada, gap adverso, stop prioritário em conflito intrabar, trailing protetivo em VBS/VSS e liquidação identificada no fim dos dados. Custos por lado são hipóteses explícitas; zero requer confirmação. Resultados são históricos/simulados, sem saldo monetário ou ordem real.
- **TRD-09** — `services/setup_backtest.py` valida aprovação, PDFs atuais, fonte e integridade; persiste relatório estruturado em `backtests` via `database/store.py`. `python -m scripts.run_delivery5` reproduz o cenário aprovado de 10 bps de taxa e 5 bps de slippage por lado, sem duplicar execuções idênticas.

## Contrato visual e rastreabilidade

- Para REQ-13, `referencia.html` continua como autoridade estrutural e visual; o portal gera uma versão pt-BR ligada ao SQLite, conforme `DEC-2026-11-12-portal-localizado-dados-locais`. O antigo `trading-office-preview.html` continua como referência funcional do portal local.
- Preservar responsividade, foco por teclado, alvos de toque adequados e conteúdo real do histórico. A troca para tema escuro fixo é específica da referência aprovada.
- Manter a sala de execução isolada, bloqueio de ordens reais visível e ausência de feed identificada.
- Decisão geral vigente: `../_capsule/decisoes/DEC-2026-11-12-reference-layout.md`. A composição restaurada da sala segue `../_capsule/decisoes/DEC-2026-11-12-restaurar-reference-html.md`.

## Biblioteca de documentos

- Conteúdo comum: `reference_docs/shared/`.
- Conteúdo específico: `reference_docs/agents/<slug>/`, com `research-agent`, `market-analyst`, `fundamental-analyst`, `strategy-backtest`, `risk-manager` e `execution-agent`.
- Os originais permanecem nesses diretórios. O índice local guarda trechos e referências de página no SQLite; reindexar por hash quando o conteúdo mudar.
- Não adicionar credenciais, extratos ou dados pessoais. Não enviar PDFs a serviço externo sem autorização explícita.
