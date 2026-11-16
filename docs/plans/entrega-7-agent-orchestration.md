# Entrega 7 — plano de orquestração de agentes (Agent Orchestration)

Estado: decisão aprovada pelo usuário em `DEC-2026-11-16-escopo-entrega-7-orquestracao.md`
(`_capsule/decisoes/`); implementação dividida em 4 fases. Este documento é a referência que
as fases 2, 3 e 4 devem ler antes de tocar em código — resume fielmente o DEC e a arquitetura
combinada, sem reabrir nenhuma decisão nele registrada. Qualquer dúvida de leitura deve ser
resolvida relendo o DEC, não reinterpretando este resumo.

## Base observada em 16/11/2026

- Diagnóstico mostrou que hoje não há encadeamento entre agentes: cada chamada de LLM é
  isolada; "Decision" e "Knowledge", citados no roadmap (seção 49), não existem como
  entidades no código.
- Duas investigações nos PDFs do método (chunks indexados; depois leitura exaustiva das
  311+9 páginas) confirmaram ausência de qualquer camada de money management, position
  sizing, R múltiplo numérico, drawdown ou exposição de portfólio no método Oliver Velez —
  ele trata risco só geometricamente (tamanho do stop por setup).
- `services/setup_signals.py` e `services/setup_backtest.py` (Entrega 5) e o Validation
  Engine (Entrega 6, `services/validation.py`) já existem e são reaproveitados por esta
  entrega, não recriados.

## 1. Decisão (resumo fiel do DEC)

Fonte de verdade completa: `_capsule/decisoes/DEC-2026-11-16-escopo-entrega-7-orquestracao.md`.
Os pontos abaixo recapitulam os 13 itens da seção "Decisão" desse arquivo — em caso de
qualquer divergência, o DEC prevalece sobre este resumo.

1. **Disparo automático**: uma oportunidade simulada dispara a sequência completa
   `Market → Knowledge → Backtest Evidence → Fundamental → Decision → Risk → Execution`
   sem exigir clique por etapa.
2. **Decision e Knowledge são serviço, não agente novo**: função/serviço determinístico (ou
   LLM orquestrado internamente), sem registro próprio em `agents`/tela Sala. O Research
   Agent continua sendo a fonte de "Knowledge".
3. **Risk Manager com proveniência explícita por campo**, combinando:
   - **Do método** (PDFs indexados + `rules_json` de `services/setup_specs.py`): stop, alvo
     e trailing por setup; status de estratégia aprovada (`strategies.status`/`approval`).
   - **Parâmetro de projeto** (não extraído do método, ausência confirmada por duas
     investigações): risco por trade = **1R** (R = distância entrada→stop do próprio setup,
     já definida em `setup_specs.py`); perda diária máxima = **3R**; exposição máxima =
     **2 posições simultâneas**. Unidade R escolhida em vez de % de capital para não
     contradizer a decisão de design vigente de não presumir saldo inicial/curva de capital.
4. Dos 7 motivos de bloqueio do Risk Manager previstos no roadmap (seção 14), **"mercado
   fora das regras"** (`filters.session_hours`, ainda `pending_market_selection`) permanece
   sem fonte definida: marcado como `não aplicável/pendente` na trilha auditável, nunca
   bloqueia nem libera nada até ganhar definição própria.
5. **Perda diária (3R) vale já, por comprometido**: cada autorização do dia soma 1R ao
   orçamento diário, mesmo sem desfecho real conhecido; 3 autorizações no mesmo dia UTC já
   esgotam o limite. Quando existir `realized_r` (entregas futuras), ele se soma ao
   comprometido.
6. **Amostra insuficiente da Validation Engine não bloqueia o candidato**: as 16 combinações
   aprovadas hoje estão rotuladas `insuficiente` (Entrega 6); a Decision continua podendo
   gerar `Trade Candidate`, sempre citando a adequação de amostra como fator contrário
   obrigatório. Informativo, não é motivo de negação do Risk Manager.
7. **Fonte do sinal é o feed ao vivo** (`market_bars`/coletor Binance), não o snapshot
   histórico verificado por hash. Aceita-se a barra mais recente do coletor como está, sem
   checagem adicional de integridade (sem verificação de lacuna/atraso) — se o coletor cair
   ou atrasar, a trilha fica sem sinal novo até ele voltar.
8. **Execução abre posição real em `paper_operations`, com quantidade informada pelo usuário
   na tela** (não presumida pelo sistema): quando o Risk autoriza um candidato, a UI
   apresenta o plano (ativo, lado, entrada, stop, alvo, 1R) e pede a quantidade; só então a
   posição simulada é aberta de verdade (linha em `paper_operations`, estado aberto). **O
   fechamento (sair no stop/alvo, calcular P&L) fica fora do escopo desta entrega** — é
   trabalho de entrega futura. O app só funciona como trader de ponta a ponta quando essa
   cadeia de entregas futuras também estiver concluída.
9. **Pendência de risco reserva vaga e consome orçamento**: enquanto uma autorização aguarda
   a quantidade do usuário, ela ocupa uma das 2 vagas de exposição e já gasta 1R do
   orçamento diário de 3R — do contrário o limite de exposição seria contornável deixando
   várias autorizações pendentes ao mesmo tempo. A pendência expira sozinha em ~15 minutos
   (preço de entrada de barra fechada ficaria obsoleto depois disso).
10. **Custo de abertura é zero, com confirmação explícita**: a posição abre ao preço cru
    apurado na barra (sem os 5 bps hipotéticos do backtest), rotulado na trilha como "custos
    serão registrados no fechamento".
11. **Sem limite de candidatos pendentes simultâneos**: o pipeline avalia as 16 combinações
    (4 setups × 2 pares × 2 intervalos) e pode gerar vários candidatos aguardando quantidade
    ao mesmo tempo; o usuário decide a ordem de confirmar ou descartar cada um.
12. **Disparo automático ao abrir a aba de Orquestração**: a avaliação roda sozinha quando o
    usuário abre essa vista, protegida contra duplicar (mesma barra nunca gera uma segunda
    trilha). Um botão "Avaliar agora" força uma nova checagem.
13. **Defaults menores aceitos sem pergunta adicional**: `tick_size` do feed ao vivo é
    constante declarada (0,01 para BTCUSDT/ETHUSDT) rotulada como parâmetro de projeto; o
    status do Execution Agent na tela reflete o estado real (ex.: "1 posição simulada
    aberta"); a tela sempre avisa que o preço de entrada vem de uma barra já fechada, mesmo
    quando recente.

### Motivo (resumo)

O roadmap pede a Entrega 7 em três linhas, sem detalhar disparo, papel de cada etapa ou regra
de risco. O usuário optou por fluxo automático e por não inflar a lista de agentes com
registros novos para etapas que são, na prática, lógica de serviço. Como o método não fornece
nenhuma camada de money management, a unidade de risco escolhida para o parâmetro de projeto
é R (derivado do próprio stop do setup) — a que menos se afasta da linguagem do método, evitando
inventar "% de capital" sobre um saldo inicial que o projeto nunca presumiu.

### Alternativas descartadas (resumo)

Modo manual por etapa; Decision/Knowledge como agentes novos na tabela `agents`; risco como %
de capital; marcar risco/exposição/perda diária como "não implementado" sem bloquear nada;
aceitar só a primeira investigação de risco nos PDFs sem escavação completa; perda diária só
valer com desfecho real (Entrega 8); bloquear candidato por amostra insuficiente; snapshot
histórico com hash como fonte do sinal (era a recomendada); execução só como "intenção" sem
gravar em `paper_operations`; fechar a posição automaticamente já nesta entrega. Detalhe de
cada descarte: seção "Alternativas descartadas" do DEC.

### Consequências relevantes para a implementação

- `filters.session_hours` continua pendente (herdado de `DEC-2026-11-13-primeiros-quatro-setups.md`);
  a trilha expõe esse motivo como não aplicável, nunca presumindo regra de horário inexistente.
- Os valores 1R / 3R / 2 posições são parâmetro de projeto explícito, não regra extraída do
  método — devem ficar documentados como tal em `PROJECT_DOCUMENTATION.md`/`AGENTS.md`
  (fase 4), sujeitos a revisão humana futura.
- Esta decisão não libera ordens reais nem altera o bloqueio absoluto de execução real já
  vigente; aplica-se somente à trilha simulada/paper.
- `paper_operations` passa a receber escrita real nesta entrega (antes só tinha leitura); a
  quantidade é sempre informada pelo usuário, nunca calculada a partir de capital.
- A trilha fica dependente do coletor Binance (`services/market_data.py`) estar ativo; sem
  checagem de integridade adicional sobre a barra ao vivo.
- Posições abertas por esta entrega ficam sem rotina de fechamento automático: fechamento,
  cálculo de P&L e condução são escopo de entregas futuras.

## 2. Arquitetura geral

Pipeline de 7 estágios, disparado automaticamente ao abrir a aba "Orquestração" do portal
`?lab=1`:

```
Market → Knowledge → Backtest Evidence → Fundamental → Decision → Risk → Execution
```

A trilha completa (todas as 7 etapas, mesmo quando um estágio não roda — ex.: "não aplicável"
ou "não executado") fica registrada em duas tabelas novas (`pipeline_runs` + `pipeline_stages`
— seção 3). Execution para num **portão humano** (`status='aguardando_quantidade'`) até o
usuário informar a quantidade na tela — só então abre uma posição real em `paper_operations`.
Fechamento/P&L ficam fora desta entrega (DEC item 8).

### Papéis por estágio

| # | Estágio | Natureza | Fonte de dados |
|---|---|---|---|
| 1 | Market | serviço | `services/market_data.py` / `market_bars` (feed ao vivo Binance) |
| 2 | Knowledge | serviço (Research Agent é a fonte) | `knowledge_items` aprovados |
| 3 | Backtest Evidence | serviço, reaproveita Entrega 5/6 | `services/setup_backtest.py`, `services/validation.py` |
| 4 | Fundamental | agente existente (Fundamental Analyst) | contexto documental já existente |
| 5 | Decision | serviço determinístico/LLM orquestrado | combina 1-4, nunca ganha registro em `agents` |
| 6 | Risk | agente existente (Risk Manager) | parâmetros de projeto (1R/3R/2 posições) + proveniência por campo |
| 7 | Execution | agente existente (Execution Agent) | portão humano de quantidade → `paper_operations` |

Nenhum agente novo é criado na tabela `agents`/tela Sala (DEC item 2) — Decision e Knowledge
são função/serviço interno ao pipeline.

## 3. Schema e migração (`database/store.py`)

Único ponto de acesso a SQLite do projeto — nenhum outro módulo acessa SQLite diretamente.
Migração aditiva/idempotente, no mesmo padrão já usado para `validation_runs`
(`CREATE TABLE IF NOT EXISTS` + `PRAGMA table_info` + `ALTER TABLE ... ADD COLUMN` quando a
coluna não existe).

### `pipeline_runs`

Uma linha por barra de sinal avaliada (`UNIQUE(strategy_id, symbol, timeframe,
signal_bar_utc)` garante idempotência: a mesma barra nunca gera uma segunda trilha — DEC
item 12).

```sql
CREATE TABLE IF NOT EXISTS pipeline_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pipeline_version TEXT NOT NULL,
  strategy_id INTEGER REFERENCES strategies(id),
  setup_id TEXT NOT NULL, setup_name TEXT NOT NULL,
  symbol TEXT NOT NULL, timeframe TEXT NOT NULL,
  signal_bar_utc TEXT NOT NULL,
  risk_date_utc TEXT,
  decision TEXT NOT NULL CHECK(decision IN ('trade_candidate','no_trade')),
  risk_verdict TEXT NOT NULL CHECK(risk_verdict IN ('autorizado','negado','nao_avaliado')),
  risk_decided_at TEXT,
  denial_reasons_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'avaliado' CHECK(status IN (
    'sem_oportunidade','entrada_nao_acionada','avaliado',
    'aguardando_quantidade','posicao_aberta','descartado_pelo_usuario',
    'expirado','recusado_na_confirmacao')),
  risk_committed_r REAL NOT NULL DEFAULT 0,
  realized_r REAL,
  report_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(strategy_id, symbol, timeframe, signal_bar_utc)
);
```

**Detalhe de implementação definido na Fase 1** (sem especificação exata no DEC): o momento
em que uma run entra em `aguardando_quantidade` precisa de timestamp próprio para a expiração
de ~15 minutos (DEC item 9) contar a partir daí, não de `created_at`. Foi adicionada a coluna
aditiva `pending_since TEXT` em `pipeline_runs` (via `ALTER TABLE ... ADD COLUMN`,
`PRAGMA table_info` já cobre idempotência). `expire_stale_pipeline_runs` compara contra
`pending_since`, nunca contra `created_at`.

### `pipeline_stages`

Um registro por etapa por run (mesmo quando a etapa não roda — `status` cobre
`'nao_aplicavel'` e `'nao_executado'`), com entrada/saída/limitações para auditoria completa.

```sql
CREATE TABLE IF NOT EXISTS pipeline_stages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
  stage_index INTEGER NOT NULL, stage TEXT NOT NULL, agent TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('ok','sem_fonte','nao_aplicavel','bloqueado','nao_executado')),
  summary TEXT NOT NULL DEFAULT '',
  input_json TEXT NOT NULL DEFAULT '{}', output_json TEXT NOT NULL DEFAULT '{}',
  limitations_json TEXT NOT NULL DEFAULT '[]',
  produced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(run_id, stage_index)
);
```

### `paper_operations` (tabela existente, só ganha coluna nova)

```python
operation_columns = {row[1] for row in conn.execute("PRAGMA table_info(paper_operations)")}
if "pipeline_run_id" not in operation_columns:
    conn.execute("ALTER TABLE paper_operations ADD COLUMN pipeline_run_id INTEGER REFERENCES pipeline_runs(id)")
conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS paper_operations_pipeline_run
                ON paper_operations(pipeline_run_id) WHERE pipeline_run_id IS NOT NULL""")
```

`pipeline_runs` é criada antes dessa migração (a FK depende da tabela existir).

## 4. Funções novas em `database/store.py`

- `save_pipeline_run(...)` — insere em `pipeline_runs`; `INSERT ... ON CONFLICT DO NOTHING`
  sobre o `UNIQUE(strategy_id, symbol, timeframe, signal_bar_utc)`, retornando o id existente
  se já havia trilha para aquela barra (idempotência por barra).
- `update_pipeline_run_status(run_id, status, **campos)` — atualiza status e campos
  relacionados (`risk_verdict`, `denial_reasons_json`, `risk_committed_r`, `realized_r`,
  `pending_since`, etc.).
- `add_pipeline_stage(run_id, stage_index, stage, agent, status, summary, input_json,
  output_json, limitations_json)`.
- `list_pipeline_runs(limit=50)` — mais recentes primeiro.
- `get_pipeline_run(run_id)` — run + lista de estágios ordenada por `stage_index`.
- `list_pending_pipeline_runs()` — `status == 'aguardando_quantidade'`, mais antigas
  primeiro (para a fase de expiração consumir em ordem).
- `expire_stale_pipeline_runs(max_age_seconds=900)` — marca como `expirado` toda run
  `aguardando_quantidade` cujo `pending_since` passou de `max_age_seconds` (~15 min).
- `count_committed_risk_r(date_utc)` — soma `risk_committed_r` de toda run com
  `risk_verdict='autorizado'` e `date(risk_decided_at) = date_utc` (UTC), **incluindo** as
  que estão `aguardando_quantidade`, `expirado` ou `descartado_pelo_usuario` — leitura
  literal do DEC item 5 + item 9: o orçamento diário é gasto por autorização, nunca
  devolvido, mesmo que a pendência depois expire ou seja descartada.
- `count_reserved_exposure()` — conta posições abertas (`paper_operations` com
  `state='open'` e `pipeline_run_id IS NOT NULL`) **mais** runs em
  `aguardando_quantidade` (ainda não expiradas — DEC item 9: pendência reserva vaga; uma vez
  `expirado`/`descartado_pelo_usuario` a run já não está mais em `aguardando_quantidade` e
  deixa de contar aqui, embora continue contando no orçamento diário acima — essas são
  contagens independentes, com janelas diferentes por desenho do DEC).
- `open_paper_operation(symbol, side, quantity, entry_price, source, pipeline_run_id=None,
  fees=0.0)` — valida em Python (`quantity > 0`, `entry_price > 0`, `side in ('buy','sell')`,
  `fees >= 0`) com mensagem em pt-BR antes do INSERT; usa a tabela existente; retorna
  `lastrowid`; nunca preenche `exit_price`/`closed_at`.
- `list_paper_operations(state=None)` — aceita filtro opcional por `state`; sem argumento,
  comportamento idêntico ao anterior (retrocompatível com `app.py` e os testes existentes).
- `counts()` ganha a chave `pipeline_runs` — aditivo, nenhuma chave existente removida.

## 5. Refactor sem mudança de comportamento (`services/setup_backtest.py`)

`verify_source_documents(rules)` foi extraída de dentro de `prepare_verified_run`: confirma
que todo PDF em `rules["source"]` ainda está indexado (`documents.library_status()`) com o
mesmo SHA-256 aprovado, levantando `ValueError` em pt-BR caso contrário. `prepare_verified_run`
passa a chamar essa função internamente — 100% do comportamento preservado, cobertura de
testes das Entregas 5/6 inalterada. Motivo: a Fase 2 (`services/pipeline.py`) não terá hash de
dataset (só o feed ao vivo), mas ainda precisa verificar a proveniência dos PDFs — reaproveita
exatamente esta função, sem duplicar a checagem.

## 6. O que a Fase 1 explicitamente NÃO faz

Não implementa `services/pipeline.py`, `decision.py`, `risk.py`, `execution.py`; não muda
`app.py`; não cria UI da aba "Orquestração"; não dispara nada automaticamente. Fase 1 entrega
só schema + store + o refactor de proveniência + testes + este documento.

## 7. Próximas fases (visão, sem comprometer detalhe de implementação ainda)

- **Fase 2**: `services/pipeline.py` orquestrando os 7 estágios sobre o feed ao vivo
  (`market_bars`), reaproveitando `services/setup_signals.py`, `services/setup_backtest.py`
  (incl. `verify_source_documents`), `services/validation.py` e os parâmetros de risco
  (1R/3R/2 posições) via `services/risk.py`/`services/decision.py` novos (serviço, não
  agente). Grava cada run com `save_pipeline_run`/`add_pipeline_stage`.
- **Fase 3**: UI da aba "Orquestração" em `app.py` — disparo automático ao abrir a aba,
  botão "Avaliar agora", apresentação do plano (ativo, lado, entrada, stop, alvo, 1R) e
  portão humano de quantidade chamando `open_paper_operation`; rotina de expiração
  (`expire_stale_pipeline_runs`) acionada no fluxo da aba.
- **Fase 4**: atualização de `PROJECT_DOCUMENTATION.md`/`AGENTS.md` com os parâmetros de
  projeto (1R/3R/2 posições) explicitamente rotulados como tal; demonstração ponta a ponta;
  commit único da Entrega 7 seguido de `git push origin main`.

## 8. Provas e aceite desta fase

- `python main.py test` com a suíte completa (não só os testes novos).
- Testes novos em `tests/test_store.py`: as duas tabelas existem após `initialize()`;
  `initialize()` duas vezes não duplica nem apaga nada; `save_pipeline_run` idempotente por
  barra; `open_paper_operation` recusa valores inválidos e aceita valores válidos gravando
  `pipeline_run_id`; `count_committed_risk_r`/`count_reserved_exposure` corretos em cenários
  sintéticos (autorizada+pendente, autorizada+aberta, autorizada+expirada/descartada ainda
  conta no orçamento do dia mas não mais na exposição reservada).
- `tests/test_setup_backtest.py` sem nenhuma alteração de asserção — prova de que o refactor
  de `verify_source_documents` não mudou comportamento algum.
- Nenhuma tabela/coluna existente alterada ou removida; `paper_operations` ganha só a coluna
  `pipeline_run_id`.

## 9. Gate

O §60 do roadmap exige aprovar plano antes de implementar e parar após demonstrar o critério
de aceite de cada fase. Este documento cobre as 4 fases para dar contexto a quem implementa
cada uma, mas cada fase tem seu próprio critério de pronto (seção 6 e instruções de despacho
específicas) e só a Fase 4 fecha com commit/push.
