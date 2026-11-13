---
run_id: 2026-11-13-entrega-5-backtest-quatro-setups
provider: Codex
modelo: GPT-6
iniciado_em: 2026-11-13T10:43
encerrado_em: 2026-11-13T11:00
objetivo: Implementar e demonstrar backtest histórico dos quatro setups aprovados.
estado_final: succeeded
checkpoint: 16 relatórios locais persistidos e reprodução sem duplicatas; suíte e navegador verificados.
artifacts: [services/setup_backtest.py, scripts/run_delivery5.py, scripts/check_delivery5_ui.py, tests/test_setup_backtest.py, database/trading.db]
memory_disposition: sem_memoria
propostas: []
pendencias: [Amostra cripto curta; nenhum resultado valida desempenho futuro. Ações horárias inelegíveis para 2m/5m.]
proxima_acao: Planejar Entrega 6 separadamente, com aprovação própria.
---
# O que foi feito

- Motor histórico causal para VBS, VSS, BOP e BDP, restrito a regras aprovadas, PDFs atuais e snapshots Binance Spot BTCUSDT/ETHUSDT de 1m com hash canônico.
- Agregação UTC 2m/5m com descarte explícito de blocos incompletos e gaps; entrada na barra seguinte, expiração, gap adverso, conflito intrabar pelo stop, trailing protetivo e saída no fim dos dados.
- Formulário e relatórios no laboratório Streamlit, com custos hipotéticos explícitos, 10 bps de taxa e 5 bps de slippage por lado na demonstração. Zero exige confirmação.
- Dezesseis relatórios persistidos no SQLite local; segunda execução comparou os relatórios e não duplicou registros. Contagens de sinais/operações:

| Setup | BTC 2m | BTC 5m | ETH 2m | ETH 5m |
|---|---:|---:|---:|---:|
| VBS | 4/1 | 1/1 | 6/1 | 2/2 |
| VSS | 12/4 | 2/0 | 5/1 | 3/1 |
| BOP | 51/14 | 21/5 | 57/15 | 21/6 |
| BDP | 46/15 | 15/5 | 50/14 | 12/5 |

- `python main.py test`: 53 testes, OK.
- Playwright: quatro formulários, resultados persistidos e nenhuma rolagem horizontal em 1440×1000, 390×844 e 320×740.

# O que NÃO foi feito e por quê

- Nenhuma ordem real ou integração XP; fora do escopo de simulação.
- Nenhuma execução em AAPL/MSFT; snapshots de 1h incompatíveis com os intervalos aprovados.
- Nenhuma inferência de lucratividade futura; período histórico local é curto.
