# Entrega 5 — plano de backtest dos quatro setups

Estado: aprovado pelo usuário em 13/11/2026; implementação e demonstração registradas na run da Entrega 5.

## Base observada em 13/11/2026

- Código em `main` no commit `21b8435`, worktree limpo.
- `python main.py test`: 46 testes, OK.
- Estratégias aprovadas v2 no SQLite: VBS #5, VSS #6, BOP #7 e BDP #8. Rascunhos v1 preservados. Regras têm páginas e SHA-256 dos PDFs.
- Datasets reais: BTCUSDT #2 e ETHUSDT #1, 999 barras de 1 minuto cada; AAPL #3 e MSFT #4, 100 barras horárias cada. Todos têm SHA-256 canônico verificável. Os números de ID são locais.
- Conferência somente de cobertura: cada snapshot cripto permite 499 barras completas de 2 minutos (1 bloco parcial descartado) ou 199 barras completas de 5 minutos (2 blocos parciais descartados), entre 12/11/2026 20:07 e 13/11/2026 12:45 UTC. A janela curta limita qualquer inferência estatística; nenhum backtest foi feito nesta conferência.
- `services/setup_signals.py` emite ordem hipotética válida apenas na barra seguinte; não preenche ordens. `services/backtest.py` só calcula SMA. A UI bloqueia a execução dos quatro setups nesta versão.

## Escopo e dados elegíveis

1. Construir motor determinístico em `services/backtest.py` (ou módulo subordinado desse serviço), separado do SMA e de conectores de negociação.
2. Aceitar apenas estratégia `setup_pattern_v1` **aprovada**, `approval=rules_human_approved`, fontes PDF com hash ainda atual, dataset recuperado por `load_verified`, `market=crypto` e par compatível com a fonte.
3. Agregar candles fechados de 1 minuto em barras de 2 e 5 minutos alinhadas a UTC. Cada bloco exige 2/5 minutos contíguos e completos; bloco incompleto e intervalo com gap são descartados e reportados. Nenhuma barra será inventada. O timestamp da barra agregada é o início do bloco.
4. AAPL e MSFT de 1 hora são incompatíveis com os timeframes 2m/5m aprovados: relatório de inelegibilidade, sem resultado numérico. Uma fonte de minuto para ações exigirá etapa própria.

## Simulação de ordens e gestão proposta

- Avaliar o sinal somente ao fechamento da barra `i`. A ordem stop de entrada existe somente na barra `i+1`; se não for acionada, expira. No lado buy, tocar a máxima no preço de entrada aciona a compra; no lado sell, tocar a mínima aciona a venda.
- Se a barra abrir além do gatilho, usar a abertura como preço de execução (gap desfavorável), nunca um preço melhor que o gatilho. Aplicar slippage adverso informado ao preço de entrada e saída.
- Só uma posição por ativo/setup por vez. Não abrir outra enquanto houver posição. Início do dataset e períodos anteriores à janela mínima são aquecimento, sem operação.
- Stop e alvo são conhecidos no momento da entrada. Se ambos ocorrerem na mesma barra, stop vence. Se entrada e saída ocorrerem na mesma barra sem sequência intrabar observável, resolver de forma conservadora: entrada e stop; registrar conflito.
- Para VBS/VSS, após dois fechamentos favoráveis desde a entrada, ajustar stop no fechamento para a extremidade da barra anterior na direção protetiva, sem afrouxar stop; novo stop só vale na barra seguinte. BOP/BDP não têm trailing.
- Ao fim do dataset, liquidar posição aberta no último fechamento, identificando `end_of_data` em vez de afirmar execução de mercado. A barra final não gera nova entrada.
- Cobrar taxa por lado e slippage por lado em bps, informados no momento da execução; preservar os valores no relatório. Não inferir tarifa da corretora nem spread observado a partir de OHLCV. A primeira demonstração propõe **10 bps de taxa por lado e 5 bps de slippage por lado**, rotulados como hipótese de cenário, não como custo real de conta. Zero só será aceito com confirmação explícita e rotulado como cenário sem custos.
- P&L em retornos percentuais por operação, sem tamanho monetário presumido, alavancagem ou capital inicial fictício. Série de capital unitário (base 1) e drawdown são índices simulados, não saldo.

## Relatório e reprodutibilidade

Cada execução persistirá: ID/versão e hash das regras, hashes dos PDFs atuais, dataset ID, SHA-256 de arquivo e canônico, origem, símbolo, mercado, timeframe original/agregado, período UTC, filtros e gaps, custos, slippage, código/versão do motor, instante da execução e parâmetros. Resultados: contagem de sinais, entradas expiradas, operações, taxa de acerto, retorno líquido, drawdown máximo, custos estimados, horários, lado, entrada/saída, motivo de saída, conflitos intrabar e condução/trailing. Execuções sem sinais mostrarão `0` e causa/cobertura, sem inventar operações.

O relatório ficará disponível na UI do laboratório e em formato estruturado no SQLite, com comparação de hash ao reproduzir. Reexecutar com mesmas regras, dataset e custos deve produzir métricas idênticas (desconsiderado ID e horário de execução). Snapshot histórico não será substituído por barras posteriores do feed em tempo real.

## Provas e aceite

- Testes causais com barras sintéticas rotuladas como fixtures: long/short, entrada no candle seguinte, expiração, gap, stop/alvo simultâneos, trailing, custos, período incompleto, gaps, aprovação/hash, idempotência de reprodução.
- `python main.py test` obrigatório e inspeção no navegador do formulário/relatórios em desktop e celular.
- Executar VBS, VSS, BOP e BDP nos datasets BTCUSDT/ETHUSDT nos intervalos 2m/5m, com o cenário de custos aprovado. Publicar número de sinais e trades inclusive se for zero. Não reivindicar validação estatística, lucratividade futura ou recomendação.
- Atualizar `AGENTS.md`, `PROJECT_DOCUMENTATION.md` e run da cápsula; um único commit exclusivo da Entrega 5, seguido de `git push origin main`.

## Gate

O §60 do roadmap exige aprovar este plano antes da implementação e parar após demonstrar o critério de aceite. A Entrega 6 terá plano e aprovação próprios.
