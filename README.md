# Trading Agent Lab

Portal local com a estrutura visual de `referencia.html`, em português brasileiro e alimentada pelos registros locais do SQLite. O modo de laboratório Streamlit anterior, com as telas de trabalho completas, continua disponível em `?lab=1`.

## Windows 11: instalação

Requisitos: Python 3.11 ou superior e Streamlit 1.49 ou superior (instalado pelo `requirements.txt`).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Se o PowerShell bloquear a ativação do ambiente:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Comandos

```powershell
python main.py status
python main.py test
python main.py dashboard
```

O portal abre em `http://localhost:8501`. O modo padrão preserva `referencia.html` como referência visual, mas monta uma versão localizada da interface usando agentes, documentos, eventos e contagens do banco local.

## Cópia da referência

- O arquivo de referência permanece intacto. O portal adapta seus rótulos para pt-BR e usa os seis agentes persistidos no SQLite.
- A página padrão não consulta o GitHub nem a Kraken e não cria agentes, cotações, capital, operações ou resultados de demonstração.
- Mercado e XP Trader aparecem como desconectados. Nenhuma ordem é preparada ou enviada.
- A página mantém uma única rolagem vertical; no celular, a sala pode ser deslocada na horizontal para mostrar todas as mesas.
- Para voltar à experiência local de seis agentes e aos registros SQLite, abra `http://localhost:8501/?lab=1`.

## Laboratório local

Neste modo, agentes, tarefas, documentos indexados, memória, eventos e demais registros usam `database\trading.db` e sobrevivem a reinicializações. A tela padrão também lê esses dados quando o portal é carregado.

- **Sala de análise** — seis mesas locais; sala de execução isolada; contexto, conhecimento, memória, revisão e tarefas no perfil do agente.
- **Mercado** — sem feed conectado.
- **Operações** — eventos de sistema separados de operações simuladas conciliadas.
- **Informe** — resumo do estado local e resultados persistidos.
- **Controle** — bloqueios, biblioteca local, provedor de IA e conexões ainda pendentes.
- **Laboratório** — importa CSV OHLCV e executa backtests após aprovação explícita.
- **Evolução do capital** — usa somente operações simuladas encerradas; não infere saldo inicial.

## Biblioteca de PDFs

Coloque documentos comuns em `reference_docs\shared\` e documentos específicos em `reference_docs\agents\<slug>\`. Slugs: `research-agent`, `market-analyst`, `fundamental-analyst`, `strategy-backtest`, `risk-manager` e `execution-agent`.

No modo `?lab=1`, em **Controle**, use **Indexar PDFs locais**. A extração acontece no computador e registra hash, páginas e trechos no SQLite. Arquivos sem texto extraível ou com erro ficam identificados. A reindexação não duplica conteúdo se o hash não mudou.

Por padrão, documentos não saem do computador. Uma tarefa só inclui trechos indexados quando isso é marcado no formulário e o envio ao provedor é confirmado.

## Provedor de IA

O conector aceita uma API compatível com OpenAI Chat Completions. Nenhuma conexão é iniciada automaticamente. Configure as variáveis no ambiente do processo que inicia o portal:

- `TRADING_LAB_LLM_BASE_URL` — URL base do provedor.
- `TRADING_LAB_LLM_MODEL` — identificador do modelo.
- `TRADING_LAB_LLM_API_KEY` — chave do provedor externo; para endpoint local pode ficar vazia.

Exemplo de endpoint local: `http://localhost:11434/v1`. Para provedores externos, use HTTPS. O valor da chave não aparece na interface nem é armazenado no banco. A chamada ocorre somente ao executar uma tarefa.

## Aprendizado e segurança

Notas e aprendizados começam como propostas. Revisões de erro preservam observação, hipótese e mudança proposta. Só uma aprovação humana inclui o aprendizado no contexto futuro. Rejeições também ficam no histórico.

Nenhuma ordem real pode ser preparada ou enviada. A conexão com XP Trader 5.0.4.34 não está implementada nem validada; a ProfitDLL da Nelogica é um produto separado e exige confirmar licença, SDK e cobertura para a versão exata. Criptoativos e ações dos EUA também exigem fontes de dados próprias.

## Backtests com CSV

No **Laboratório** do modo `?lab=1`, importe um CSV UTF-8 com `timestamp,open,high,low,close,volume`. Informe símbolo, intervalo e origem declarada. O aplicativo valida sequência de horários, OHLC e volume; guarda barras e SHA-256 no SQLite.

O único motor atual testa cruzamento de médias simples comprado: lê o sinal no fechamento e preenche na abertura da barra seguinte. Você define as janelas, taxas e slippage. Salve a estratégia, revise-a, aprove a versão e confirme custos antes de executar. O teste não anualiza retorno e não inclui benchmark, dividendos, capital inicial ou execução intraday real.

## Verificação atual

1. `python main.py status` apresenta os seis agentes persistidos.
2. `python main.py test` cobre UI, SQLite, biblioteca local, memória e bloqueio de chamadas de IA sem configuração.
3. `python main.py dashboard` inicia o portal local.
4. Nenhum feed de mercado, conta de simulação ou ordem de corretora é presumido ativo.
