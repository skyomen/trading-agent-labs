# Trading Agent Lab

Laboratório local de seis agentes para pesquisa intraday, documentos, estratégias, backtests e operações **simuladas**. O portal usa a estrutura visual de `referencia.html` e mostra somente dados persistidos. Nenhuma ordem real é preparada ou enviada.

## Abrir o aplicativo

No Windows, com Python 3.11 ou superior:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py dashboard
```

Abra **http://127.0.0.1:8501**. O comando limita o servidor ao próprio computador. Na primeira abertura, crie o acesso principal com usuário e senha de pelo menos 12 caracteres. Os registros que já estavam em `database/trading.db` ficam nesse workspace principal; nada é apagado. Ao recarregar a página, entre novamente.

Depois de entrar, escolha **Portal** para a sala visual ou **Laboratório** para tarefas e controles. O endereço `http://127.0.0.1:8501/?lab=1` abre inicialmente o Laboratório, após o login. O botão **Sair** fica na barra lateral.

## O que aparece em cada workspace

- O proprietário cria outros usuários na barra lateral, em **Usuários**. Cada novo usuário recebe seus seis agentes e um banco próprio, sem histórico de operações, tarefas ou credenciais de outra pessoa.
- Os PDFs comuns permanecem em `reference_docs/shared/` e `reference_docs/agents/<slug>/`. Em **Controle**, cada usuário pode indexá-los localmente; também pode enviar um PDF privado para seu próprio workspace.
- Conhecimento extraído começa como proposta. Depois de aprová-lo, o proprietário pode **promover à biblioteca global** um item de PDF comum cujo hash ainda corresponde ao arquivo. Somente esses itens globais são compartilhados. Memórias, propostas e operações privadas não são publicadas.
- Cada usuário configura suas chaves em **Minhas credenciais**, na barra lateral. O cofre local fica cifrado fora do SQLite; as chaves não reaparecem na tela. Variáveis antigas do `.env` não são usadas por uma sessão autenticada. Sem as próprias credenciais, o serviço aparece desconectado.

Guarde sua senha: ainda não há recuperação de conta ou troca de senha pela interface. O cofre de credenciais depende dela. Este login é para uso **local**; o portal online é uma entrega futura.

## Fluxos disponíveis

- **Agentes e documentos:** tarefas de IA só ocorrem ao clicar para executá-las; incluir trechos de PDF em contexto externo exige autorização explícita por tarefa.
- **Mercado:** snapshots e candles persistidos têm fonte e horário. Histórico não é cotação atual nem preço executável. Binance Spot público fornece dados cripto; Alpaca IEX opcional fornece apenas histórico de ações.
- **Estratégias e backtests:** regras versionadas exigem aprovação humana; resultados são históricos/simulados, com custos e limitações identificados.
- **Paper local:** oportunidades passam por risco, confirmação de quantidade, condução sob demanda e diário. Não há capital inicial presumido.
- **Binance Spot Testnet:** ordens virtuais externas têm confirmação humana específica, consulta e cancelamento. O estado é separado do paper local; compras preenchidas não recebem stop automático. Sem credenciais Testnet do usuário, o conector fica desconectado.
- **XP Trader 5.0.4.34:** desconectado. A [investigação](docs/integrations/xp-trader-5.0.4.34.md) ainda depende de confirmação da licença, do SDK e da conta exclusivamente simulada.

## Comandos e provas

```powershell
python main.py status
python main.py test
python -m scripts.run_delivery13 --prova
python -m scripts.check_delivery13_ui
```

`status` mostra os seis agentes do workspace principal. `test` é a suíte obrigatória. As duas provas da Entrega 13 usam bancos temporários e credenciais sintéticas, sem chamadas externas.

Para a prova visual, instale o navegador de teste uma vez com `python -m playwright install chromium`.

Detalhes de arquitetura, tabelas, proveniência e limitações estão em [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md). O [roadmap](TRADING_AGENT_LAB_MASTER_ROADMAP.md) separa a próxima etapa de portal online deste laboratório local.
