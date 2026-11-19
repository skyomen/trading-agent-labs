# Trading Agent Lab

Laboratório local de seis agentes para pesquisa intraday, documentos, estratégias, backtests e operações **simuladas**. O painel Streamlit mostra somente dados persistidos. Nenhuma ordem real é preparada ou enviada.

## Abrir o aplicativo

No Windows, com Python 3.11 ou superior:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py dashboard
```

Abra **http://127.0.0.1:8501**. O servidor escuta apenas no próprio computador e a página local abre diretamente, sem pedir usuário ou senha. Os registros de `database/trading.db` continuam no workspace do proprietário.

A única página é **Operações**. Ela mostra posições paper abertas e encerradas; selecione uma operação para ver gráfico, candles, setup, intervalo, passo a passo, razão da entrada, saída, custos e resultado. O tema escuro é o padrão; **Aparência** no topo troca para claro. As próximas páginas serão construídas uma a uma.

## O que aparece em cada workspace

- O modo local abre o histórico do proprietário. Os serviços e bancos isolados de contas adicionais permanecem no projeto, mas a página local atual não oferece troca de usuário.
- Os PDFs comuns permanecem em `reference_docs/shared/` e `reference_docs/agents/<slug>/`. Os serviços de indexação local permanecem no projeto; a interface de documentos será redesenhada em uma página futura.
- Conhecimento extraído começa como proposta. Somente itens comuns aprovados e promovidos explicitamente podem ser compartilhados. A interface de revisão será redesenhada em uma página futura.
- O cofre de credenciais permanece no projeto para o modo online. A página local Operações não carrega chaves privadas nem chama provedores privados ao abrir.

O portal online é uma entrega futura e mantém autenticação separada; a dispensa de login vale para o servidor local em `127.0.0.1`.

Há um [pacote de preparação para servidor com HTTPS](docs/deploy/self-host.md). Ele ainda não está publicado: exige servidor, domínio e decisão sobre quais dados locais serão transferidos.
Também há uma [alternativa gerenciada na Render](docs/deploy/render.md), com subdomínio HTTPS e disco pago. Nenhuma conta ou cobrança foi criada.
**Vercel não executa o aplicativo Streamlit completo como está.** Veja a [avaliação de compatibilidade e caminhos de migração](docs/deploy/vercel.md) antes de tentar configurar um deploy.

## Fluxos disponíveis

- **Agentes e documentos:** tarefas de IA só ocorrem ao clicar para executá-las; incluir trechos de PDF em contexto externo exige autorização explícita por tarefa.
- **Mercado:** snapshots e candles persistidos têm fonte e horário. Histórico não é cotação atual nem preço executável. Binance Spot público fornece dados cripto; Alpaca IEX opcional fornece apenas histórico de ações.
- **Estratégias e backtests:** regras versionadas exigem aprovação humana; resultados são históricos/simulados, com custos e limitações identificados.
- **Paper local:** oportunidades passam por risco, entrada de 2 USDT por padrão (faixa manual de 1 a 10 USDT), condução e diário. Não há capital inicial presumido.
- **Binance Spot Testnet:** ordens virtuais externas têm confirmação humana específica, consulta e cancelamento. O estado é separado do paper local; compras preenchidas não recebem stop automático. Sem credenciais Testnet do usuário, o conector fica desconectado.
- **XP Trader 5.0.4.34:** desconectado. A [investigação](docs/integrations/xp-trader-5.0.4.34.md) ainda depende de confirmação da licença, do SDK e da conta exclusivamente simulada.

## Testar com candles ao vivo e resultados simulados

Em um terminal, mantenha o coletor público ativo:

```powershell
python -m services.market_data stream
```

Em outro terminal, abra o painel com `python main.py dashboard`. O dock fixo inferior alterna entre **Operações** e **Mercado**. Em Operações, selecione uma operação para ver candles locais fechados Binance Spot no mesmo par e intervalo; a tabela OHLCV permite conferir os candles marcados. Triângulos preenchidos apontados para a direita indicam a entrada e a saída paper no preço e candle da trilha. Linhas âmbar e azul mostram STOP e ALVO planejados; uma guia vertical marca o horário da saída. O passo a passo só mostra fatos registrados e informa quando não houve parcial.

Para abrir e acompanhar automaticamente posições **somente paper local** sem manter a tela aberta, inicie um terceiro processo:

```powershell
python -m scripts.run_paper_auto
```

Ele verifica o feed a cada 10 segundos, abre apenas candidatos recentes aprovados pelo risco com **2 USDT por entrada**, limita a duas posições e conduz posições abertas. Pare com `Ctrl+C` no terminal. O coletor e o computador precisam continuar ligados. Binance Spot Testnet e ordens reais não fazem parte da automação. O valor é em **USDT**, não em USD de uma conta. Operações paper encerradas mostram o P&L líquido em USDT, custos e resultado em R quando registrados. Esses valores são de simulação e não constituem saldo de corretora.

## Comandos e provas

```powershell
python main.py status
python main.py test
python -m scripts.run_delivery13 --prova
python scripts/check_operations_ui.py
```

`status` mostra os seis agentes do workspace principal. `test` é a suíte obrigatória. A prova visual usa banco temporário e credenciais sintéticas, sem ordens externas.

Em **Mercado**, o widget Advanced Chart do TradingView oferece busca de ativos, intervalos, indicadores e ferramentas de desenho. Ele usa sua própria conexão e seus dados; não substitui os candles Binance Spot persistidos que aparecem nos detalhes em **Operações**. Os dois gráficos podem ser comparados pelo mesmo ativo, intervalo e fuso UTC. O widget requer internet, pode exibir cobertura e atualização diferentes do feed local, não aceita scripts Pine personalizados e não envia ordens.

O [MetaTrader 5](docs/integrations/metatrader5-research.md) está registrado como pesquisa futura para B3 e ações americanas. A conta Binance própria também não está conectada; uma integração futura poderá consultar dados com permissão somente leitura, separada das operações paper.

Para a prova visual, instale o navegador de teste uma vez com `python -m playwright install chromium`.

Detalhes de arquitetura, tabelas, proveniência e limitações estão em [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md). O [roadmap](TRADING_AGENT_LAB_MASTER_ROADMAP.md) separa a próxima etapa de portal online deste laboratório local.
