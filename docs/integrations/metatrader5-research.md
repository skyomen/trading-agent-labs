# MetaTrader 5 como fonte futura de dados

Pesquisa inicial de 18/11/2026. Nenhum terminal ou conta foi conectado nesta entrega.

## O que a documentação confirma

- A [integração oficial Python do MetaTrader 5](https://www.mql5.com/en/docs/python_metatrader5) permite consultar símbolos, propriedades, candles, ticks, posições e histórico por meio de um terminal MT5 instalado e conectado. O mesmo pacote também expõe `order_send`; uma integração deste laboratório deverá excluir completamente essa função.
- A [janela Market Watch](https://www.metatrader5.com/en/terminal/help/trading/market_watch) mostra os instrumentos disponibilizados pelo servidor da corretora. Os dados históricos são baixados do servidor da corretora, e as propriedades do instrumento variam conforme a oferta dela. Ver um nome parecido com IBOV, dólar ou ação americana não prova que seja contrato negociado na B3 ou ação à vista na bolsa americana.
- A [B3 identifica WIN e WDO](https://b3.com.br/data/files/D5/90/57/D2/C793F8100E866AE8AC094EA8/B3%20Trading%20Procedures%20Manual.pdf) como contratos futuros mini de Ibovespa e dólar. O índice IBOV, WIN, dólar à vista, DOL e WDO são instrumentos distintos; o mapeamento terá de ser confirmado por contrato e vencimento.
- A [MetaQuotes lista gateways para NASDAQ e NYSE](https://www.metatrader5.com/en/stocks-ecns), mas essa capacidade da plataforma não garante que a conta ou corretora do usuário forneça ações americanas de bolsa, nem que os dados tenham o direito de uso exigido.

## Pendências para uma prova local somente leitura

1. Identificar corretora, servidor e tipo de conta MT5 que o usuário pretende utilizar; verificar se há conta demo e quais símbolos estão visíveis.
2. Confirmar para cada símbolo se é contrato B3/ação negociada em bolsa ou derivativo/CFD, além de fuso, moeda, tamanho de contrato, incremento, vencimento, horário e custo de dados.
3. Confirmar direito de acesso e retenção dos candles e validar amostra OHLCV contra a fonte oficial do instrumento.
4. Construir coletor somente leitura separado da interface, sem importação de `order_send`, sem abrir ordens e sem usar credenciais de conta real na interface.

Até essa verificação, BTCUSDT/ETHUSDT continuam na fonte pública Binance Spot e AAPL/MSFT continuam identificados como snapshots históricos Market History/Alpaca IEX quando disponíveis. A primeira página Operações lê apenas operações paper locais já persistidas.
