# Entrega 11 — Broker Paper: plano para aprovação

Estado: aprovado pelo usuário e implementado localmente em 17/11/2026. Aceite externo da Testnet pendente de credenciais exclusivas e ação explícita; nenhuma ordem externa foi enviada pela prova.

## Base verificada

- Commit `ef5a911` contém as Entregas 9 e 10; workspace limpo, `main` um commit à frente de `origin/main`. `python main.py test` passou com 142 testes.
- Hoje não há Broker Interface nem adaptador de ordens. `services/execution.py` abre somente `paper_operations` locais; `services/market_data.py` acessa Binance pública apenas para dados e Alpaca IEX apenas para históricos. Não existem ordens ou conta de corretora integradas.
- O produto alvo XP Trader 5.0.4.34 depende de investigação específica da Entrega 12 e permanece excluído desta conexão.
- [Binance Spot Testnet oficial](https://github.com/binance/binance-spot-api-docs/blob/master/testnet/general-info.md) usa `https://testnet.binance.vision/api`, fundos virtuais e apenas endpoints `/api/*`; seu estado é apagado periodicamente. [A documentação da API Spot](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md) descreve consulta, criação e cancelamento de ordens assinadas. A disponibilidade de cada par, tipo de ordem e filtros será consultada em `exchangeInfo`, nunca presumida.
- [Alpaca Paper](https://docs.alpaca.markets/us/docs/paper-trading) requer credenciais próprias, diferentes das chaves de dados IEX já usadas localmente. Não oferece continuidade direta para BTCUSDT/ETHUSDT do feed atual; por isso, este plano propõe Binance Spot Testnet como primeiro adaptador.

## Decisões propostas

1. **Interface e adaptador isolados.** `services/brokers/base.py` define capacidades, estado de conexão, envio, consulta e cancelamento; `services/brokers/binance_spot_testnet.py` implementa apenas a URL fixa da Testnet. Nenhum host de produção configurável, fallback para produção ou chave de produção. O Execution Agent chama a interface, nunca monta HTTP ou assinatura de fornecedor.
2. **Credenciais exclusivas.** `BINANCE_SPOT_TESTNET_API_KEY` e `BINANCE_SPOT_TESTNET_API_SECRET` ficam só no ambiente ou `.env` local ignorado. Chaves Alpaca IEX não são reutilizadas. SQLite e logs guardam somente estado, IDs de ordem e respostas sem segredos. Sem chaves, a interface mostra desconectado e testes com adaptador falso continuam executáveis. Não pedir chaves por chat.
3. **Escopo inicial de ordens:** apenas candidatos **comprados** BTCUSDT/ETHUSDT aprovados pelo Risk Manager, ainda dentro do prazo de confirmação, com quantidade informada pelo usuário. VSS/BDP vendidos ficam inelegíveis para Spot Testnet; `SELL` não abre short nessa modalidade. Antes do envio, o adaptador verifica `exchangeInfo`, filtros de símbolo/quantidade/preço e cotação recente **da Testnet**. O preço da Binance pública não é apresentado como preço executável da Testnet.
4. **Portão humano e preço.** A UI oferece escolha explícita entre a simulação local atual e a execução na Testnet. Para Testnet, mostra ambiente, símbolo, quantidade, tipo de ordem, limite informado pelo usuário, cotação/frescor da Testnet e divergência do preço do sinal. Exige confirmação específica da ordem virtual. O pedido será `LIMIT` com preço do usuário e prazo/cancelamento explícitos; nenhum envio automático ao abrir a tela ou ao gerar sinal. Sem cotação fresca ou filtro validado, bloqueia.
5. **Persistência e reconciliação.** Uma tabela `broker_paper_orders` guarda pedido, `clientOrderId` determinístico, run de origem, estado, IDs/resposta da Testnet, horários e erros sanitizados. A intenção é persistida antes do POST; timeout fica `unknown` e exige consulta por `clientOrderId` antes de qualquer reenvio. Consultas posteriores atualizam `NEW`/`PARTIALLY_FILLED`/`FILLED`/`CANCELED`/`REJECTED` sem inventar preenchimento. Idempotência impede segunda ordem para a mesma confirmação. Ordens e saldo virtuais da Testnet ficam separados de `paper_operations` e do P&L local até haver reconciliação validada; não somar os dois regimes.
6. **Saída e limites.** A Entrega 11 não transforma automaticamente stop/alvo do feed público em ordens de saída da Testnet. O adaptador oferece cancelamento da compra ainda aberta e, após preencher, uma ação humana separada de venda `LIMIT` restrita à quantidade comprada e reconciliada, com preço de saída informado pelo usuário e filtros da Testnet verificados. A tela destaca que a posição virtual externa fica **sem stop automático** até a venda preencher. O envio de compra permanece bloqueado se a consulta/cancelamento/saída não estiverem operacionais. A decisão de ampliar para OCO/stop exigirá confirmação dos tipos e filtros do símbolo e prova de reconciliação.

## Implementação e provas propostas

1. Criar interface, adaptador, configuração e testes de assinatura, URL fixa, filtros, ausência de chaves, rejeição de venda/ativo não elegível, sanitização e falha de rede. Nenhuma dependência nova se `urllib`/biblioteca padrão bastarem.
2. Persistir e exibir ciclo de ordem virtual separadamente do diário local. O portal mostra estado da conexão e da ordem com fonte e horário; o Laboratório oferece conexão/consulta e o portão humano. Nenhum carregamento de página chama endpoint privado automaticamente.
3. Criar prova `python -m scripts.run_delivery11 --prova` com adaptador falso e banco temporário: autorização → confirmação humana → intenção → resposta/timeout → consulta → cancelamento ou venda de saída, com idempotência. A prova não envia ordem à Testnet.
4. Com credenciais de **Testnet** configuradas pelo usuário e nova ação explícita, verificar conexão e um ciclo real de ordem virtual em símbolo permitido. A parte externa do aceite depende desse acesso; sem ele, relatar a conexão como não validada, sem simular sucesso.
5. Rodar `python main.py test`, checar portal/Laboratório em 1440×1000, 390×844 e 320×740, atualizar `AGENTS.md`, `PROJECT_DOCUMENTATION.md` e roadmap, demonstrar limites e parar antes da Entrega 12.

## Critérios de aceite

- A API de produção nunca é alcançável pelo adaptador, mesmo com entrada inválida ou variável de ambiente equivocada.
- Nenhuma chamada privada acontece por renderização de tela; envio virtual exige o portão humano completo. Ordens vendidas que implicariam short são bloqueadas.
- Uma falha ou timeout nunca vira preenchimento presumido nem dispara reenvio cego. Consulta e cancelamento usam IDs persistidos e mantêm trilha auditável.
- Ordens virtuais Testnet e operações simuladas locais aparecem separadas, com fonte, estado e frescor. Nenhum saldo virtual é tratado como saldo real.
- Prova local com falso adaptador e suíte obrigatória passam. Conexão e ordem reais da Testnet só contam como verificadas quando efetivamente observadas com credenciais específicas.

## Fora do escopo

- XP Trader/ProfitDLL, Alpaca Trading, mercado real, short/margem/futuros, ordem automática por sinal, equivalência de preço entre feed público e Testnet e promoção automática de estratégia.
