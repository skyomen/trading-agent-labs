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

- **TRD-01** — Interface Streamlit; persistência SQLite acessada somente por `database/store.py`. `database/trading.db` permanece como workspace legado do proprietário; contas adicionais usam bancos isolados em `database/workspaces/`.
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

## Entrega 6 — Validation Engine

- **REQ-21** — Nenhuma estratégia é promovida por resultado bruto. Toda validação declara a adequação da amostra antes de qualquer número e nunca afirma robustez: menos de 10 operações no pior lado do corte é `insuficiente` e não gera leitura; de 10 a 29 é `limitrofe`, leitura apenas indicativa; a partir de 30 é `adequada`, o que apenas habilita a leitura. Os limiares 10/30 são decisão de projeto aprovada em 13/11/2026 e ficam registrados em cada execução. Retorno líquido não aparece isolado como veredito em nenhuma tela. Amostra insuficiente é resultado legítimo do histórico curto, não defeito a mascarar.
- **TRD-10** — `services/validation.py` corta a série uma vez em ordem cronológica, alinhando o corte a bloco UTC completo e cobrando de cada lado o próprio aquecimento de 29 barras, sem compartilhar barra entre treino e out-of-sample. Roda a grade fixa de custo (0/0, 5/2, 10/5 e 20/10 bps por lado) nos dois lados, marcando o custo zero como baseline de sensibilidade, e mede concentração removendo a operação de maior retorno individual. Reaproveita `verify_approved_rules`/`prepare_verified_run` de `services/setup_backtest.py` sem duplicar a verificação de proveniência. Persiste em `validation_runs` por `database/store.py`, com migração aditiva e idempotente. "Comparar períodos" e "procurar degradação" ficam fora deste escopo por falta de janelas longas independentes, e a pendência é registrada em cada execução.

## Entrega 7 — Agent Orchestration

- **REQ-22** — Uma oportunidade simulada dispara automaticamente, sem clique por etapa, a sequência completa `Market → Knowledge → Backtest Evidence → Fundamental → Decision → Risk → Execution`, com trilha auditável de 7 estágios persistida mesmo quando um estágio não roda (ex.: "não aplicável" ou "não executado"). Decision e Knowledge são serviço/função, não ganham registro novo em `agents`/tela Sala — o Research Agent continua sendo a fonte de "Knowledge". Os parâmetros de risco (1R por trade, 3R de perda diária, 2 posições simultâneas) são parâmetro de projeto explícito — não extraídos do método Oliver Velez, cuja ausência de qualquer camada de money management/position sizing foi confirmada por escavação completa dos PDFs — sujeitos a revisão humana futura. A fonte do sinal é o feed ao vivo (`market_bars`), não um snapshot com hash; a execução abre posição real em `paper_operations` com quantidade informada pelo usuário na tela, nunca presumida; fechamento e cálculo de P&L ficam fora do escopo desta entrega. Decisão completa: `../_capsule/decisoes/DEC-2026-11-16-escopo-entrega-7-orquestracao.md`.
- **TRD-11** — `services/pipeline.py` orquestra os 7 estágios sobre o feed ao vivo, reaproveitando `services/setup_signals.py`, `services/setup_backtest.py` (incl. `verify_source_documents`, extraída de `prepare_verified_run` sem mudar comportamento) e `services/validation.py`; `services/decision.py` e `services/risk.py` são serviço determinístico, não agente; `services/execution.py` monta o plano só quando o Risk autoriza e expõe o portão humano (`confirm_open`/`discard`). Duas tabelas novas em `database/store.py`: `pipeline_runs` (uma linha por barra avaliada, `UNIQUE(strategy_id, symbol, timeframe, signal_bar_utc)` garante idempotência por barra) e `pipeline_stages` (um registro por estágio por run, com entrada/saída/limitações). `paper_operations` ganha a coluna aditiva `pipeline_run_id`. `python -m scripts.run_delivery7` demonstra a trilha completa em modo avaliação (padrão) e o portão humano em modo confirmação (`--abrir`/`--quantidade`, `--descartar`).

## Entrega 8 — Trade Management

- **REQ-23** — A condução (fechamento de posição simulada por stop/alvo/trailing) roda sob demanda, recalculando do zero a cada abertura da tela correspondente — sem processo novo em background, mesmo padrão sob demanda já usado pelo pipeline da Entrega 7. A lógica de trailing é replicada tal como está no motor do backtest, hardcode por nome de setup incluído (`rules["setup_name"] in {"VBS", "VSS"}`); `rules_json.management` não é lido para decidir condução nesta entrega — é inconsistência conhecida e registrada, não corrigida, e passa a existir em dois motores (backtest e paper) em vez de um. O custo no fechamento usa as mesmas premissas do backtest (10 bps de taxa, 5 bps de slippage por lado), não custo zero. Decisão completa: `../_capsule/decisoes/DEC-2026-11-16-escopo-entrega-8-trade-management.md`.
- **TRD-12** — `services/trade_management.py` reconduz uma `paper_operation` aberta chamando o motor compartilhado de `services/setup_backtest.py` (`replay_open_position`, extraída de dentro de `simulate` sem mudar seu comportamento) a partir da barra de entrada congelada na trilha (`report_json["execution"]`), nunca recomputando a partir de `strategies.rules_json`. `database/store.py` ganhou três funções: `get_strategy` (uma versão por id, só para auditoria do `management` declarado), `get_market_bars_since` (janela de barras 1m desde um instante, ordem ascendente, tolerante às duas convenções de sufixo de fuso do projeto) e `close_paper_operation` (fechamento condicional idempotente que também estampa `pipeline_runs.realized_r` na mesma transação); `paper_operations` ganhou a coluna aditiva `exit_reason`. `python -m scripts.run_delivery8` demonstra a condução em modo padrão (contra o banco real) e, em `--prova`, a paridade de motor entre `simulate()`/`replay_open_position()` sobre cenários sintéticos e o fluxo completo com persistência num banco temporário.

## Entrega 9 — Paper Trading

- **REQ-24** — Completar o ciclo simulado `signal → risk → entry → management → exit → journal` sem dinheiro ou ordem real. Quantidade continua informada pelo usuário. O diário mostra proveniência e limitações da trilha, estados abertos/fechados e custos por lado; legados não recebem fatos reconstruídos. P&L em USDT e resultado em R usam os mesmos preços e taxas da operação paper, com slippage adverso já embutido no preço de saída.
- **TRD-13** — `paper_journal` guarda uma ficha por `paper_operation`, criada na abertura e concluída no fechamento. `database/store.py` fecha operação, `pipeline_runs.realized_r`, diário e estágio de condução em uma transação idempotente. `python -m scripts.run_delivery9 --prova` demonstra o ciclo em banco temporário e com dados sintéticos. A condução permanece sob demanda e o coletor Binance continua separado.

## Entrega 10 — Aprendizado Controlado

- **REQ-25** — Hipóteses paper são geradas localmente e de modo determinístico somente após 30 operações encerradas e íntegras da mesma estratégia, símbolo e intervalo em pelo menos dois dias UTC. Os limiares são parâmetro de projeto, não prova de robustez. Observação, hipótese, evidência e limitações permanecem distintas. Aprovação/rejeição é humana; aprovar uma hipótese não altera regra, memória de método ou operação. Nova versão nasce apenas como rascunho após edição manual e mantém a versão aprovada de origem intacta.
- **TRD-14** — `services/paper_learning.py` calcula coortes e digest canônico de operações/trilhas/diários; `database/store.py` persiste em `paper_learning_proposals` com unicidade por coorte, versão do analisador e digest. A criação de rascunho revalida a integridade da evidência, só permite alterar campos operacionais e marca `rules_json.approval` como pendente de revisão, impedindo backtest/pipeline até aprovação específica futura. `python -m scripts.run_delivery10 --prova` usa somente banco temporário e dados sintéticos.

## Entrega 11 — Broker Paper

- **REQ-26** — Binance Spot Testnet é o único adaptador de ordens virtuais externas, com host fixo e credenciais exclusivas locais. Somente candidatos BUY BTCUSDT/ETHUSDT autorizados pelo Risk podem virar compra LIMIT, após quantidade, preço, cotação/filtros Testnet e confirmação humana explícitos. VSS/BDP vendidos não abrem short. A venda de saída é manual e limitada à quantidade comprada reconciliada; não há stop automático. Ordens Testnet ficam separadas de `paper_operations`, P&L e saldo local. Nenhuma chamada privada ocorre ao renderizar a tela, e nenhuma ordem real é preparada ou enviada.
- **TRD-15** — `services/brokers/base.py` define a interface e `services/brokers/binance_spot_testnet.py` implementa HTTP assinado apenas em `https://testnet.binance.vision/api/v3/`. `services/broker_paper.py` governa o portão humano, persistência de intenção antes de POST, consulta, cancelamento e venda; `database/store.py` persiste em `broker_paper_orders` com client ID único. Timeout fica `unknown` e não reenvia automaticamente. `python -m scripts.run_delivery11 --prova` demonstra o fluxo em banco temporário com adaptador falso.

## Entrega 12 — Investigação XP Trader

- **REQ-27** — A investigação do XP Trader 5.0.4.34 separa capacidades genéricas da ProfitDLL de direitos da licença XP. Dados, API, SDK, simulação, execução e limitações têm evidência e lacunas registradas em `docs/integrations/xp-trader-5.0.4.34.md`. Sem confirmação específica de licença, SDK e conta exclusivamente simulada roteável, XP permanece desconectado; nenhum adaptador XP, login ou ordem será implementado nesta entrega. BTCUSDT, ETHUSDT, AAPL e MSFT continuam em fontes próprias.
- **TRD-16** — Uma integração XP futura exige nova decisão e plano, manual/SDK oficial versionado com hash, direitos de dados e prova de separação inequívoca entre conta simulada e real. A documentação pública da ProfitDLL não substitui essa confirmação.

## Entrega 13 — Multiusuário local

- **REQ-28** — Exigir login local antes de mostrar Portal ou Laboratório. O primeiro cadastro cria o proprietário, cujo histórico permanece em `database/trading.db`; somente ele cria outras contas. Cada conta adicional tem workspace SQLite próprio e vê somente seus registros. Conhecimento comum só aparece globalmente após aprovação, promoção explícita do proprietário e confirmação do hash atual da fonte. PDFs particulares permanecem no diretório do usuário. Cada usuário configura suas credenciais; a interface autenticada não utiliza chaves do ambiente do processo como fallback. O app local escuta em `127.0.0.1`; publicação na internet pertence à Entrega 14.
- **TRD-17** — `database/store.py` concentra o acesso aos bancos de identidade, conhecimento global e workspaces; `services/auth.py` verifica senhas Argon2id e limita tentativas; `services/credential_vault.py` cifra segredos por usuário fora do SQLite. `services/global_knowledge.py` valida aprovação e proveniência na promoção. `python -m scripts.run_delivery13 --prova` demonstra isolamento e credenciais sem rede.

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
