# TRADING AGENT LAB — PLANO MESTRE ATÉ A ENTREGA FINAL

**Documento de controle do projeto para o Codex e para o responsável pelo Trading Agent Lab.**

> Este documento complementa `AGENTS.md` e `PROJECT_DOCUMENTATION.md`. Ele define o plano funcional e estratégico de evolução a partir do estado atual, com prioridade para a inteligência dos agentes, sincronização entre conhecimento → backtest → decisão → execução, aprendizagem controlada e futura utilização por outras pessoas.
>
> **Regra central:** nenhuma etapa futura deve ser marcada como concluída apenas porque o código foi escrito. Cada etapa precisa produzir uma capacidade verificável no portal, testes automatizados e evidência de funcionamento.

---

# 1. ESTADO REAL DO PROJETO

O projeto já possui uma base local em Python/Streamlit com:

- portal visual baseado na referência HTML;
- laboratório em `?lab=1`;
- seis agentes persistidos;
- SQLite;
- eventos;
- indexação local de PDFs;
- memória/revisão humana;
- cadastro versionado de estratégias;
- importação de CSV OHLCV;
- motor de backtest SMA básico;
- estrutura de operações simuladas;
- estrutura de conexões;
- bloqueio de ordens reais.

O modo atual é **local e simulado**.

Ainda não há:

- feed de mercado conectado;
- execução real;
- setups do método formalizados e aprovados;
- backtests reais desses setups;
- paper trading conectado a mercado;
- integração validada com XP Trader 5.0.4.34;
- ciclo de aprendizagem validado.

A referência técnica informa que já existem **dois PDFs indexados** na biblioteca, mas o estado persistido do Research Agent ainda aparece como “Aguardando documentos”. Essa divergência deve ser corrigida de forma explícita, sem mascarar o estado do banco. fileciteturn1file1L1-L15

---

# 2. VISÃO DO SISTEMA FINAL

O Trading Agent Lab não deve ser apenas um chatbot com vários agentes.

Ele deve funcionar como um **laboratório de trading orientado por conhecimento, evidência, validação e feedback controlado**.

Fluxo:

```text
KNOWLEDGE
   ↓
SETUP LIBRARY
   ↓
BACKTEST
   ↓
VALIDATION
   ↓
MARKET CONTEXT
   ↓
FUNDAMENTAL / EVENTS
   ↓
DECISION
   ↓
RISK
   ↓
EXECUTION
   ↓
TRADE MANAGEMENT
   ↓
TRADE JOURNAL
   ↓
LEARNING REVIEW
   ↓
NOVA HIPÓTESE
   ↓
NOVO BACKTEST
```

O sistema deve possuir feedback loop, mas **não deve permitir que a IA altere automaticamente uma estratégia de produção sem aprovação e sem nova validação**.

---

# 3. PRINCÍPIO CENTRAL: CONHECIMENTO ≠ ESTRATÉGIA

Os PDFs são a fonte intelectual do sistema.

Mas:

```text
PDF
≠
estratégia pronta
```

O Knowledge Agent deve transformar o conhecimento em especificações estruturadas.

Exemplo:

```text
PDF
 ↓
conceito
 ↓
setup
 ↓
contexto
 ↓
entrada
 ↓
confirmação
 ↓
stop
 ↓
alvo
 ↓
condução
 ↓
invalidação
 ↓
regras testáveis
```

Se o backtest for ruim, o sistema não deve simplesmente alterar a regra para procurar lucro.

Qualquer alteração experimental deve virar uma nova versão:

```text
SETUP ORIGINAL v1.0
SETUP v1.1
SETUP v2.0
```

O original permanece preservado.

---

# 4. AGENTES PRINCIPAIS

Os seis agentes existentes continuam sendo a base. Suas responsabilidades, porém, devem evoluir.

Não criar dezenas de agentes sem necessidade.

## 4.1 Knowledge Agent — Mestre do método

É um dos agentes centrais.

### Responsabilidade

Ser a memória estruturada do método fornecido pelo usuário.

Deve conhecer:

- conceitos;
- setups;
- filtros;
- contexto;
- entradas;
- stops;
- alvos;
- condução;
- saídas;
- gestão;
- exceções;
- contraindicações;
- exemplos;
- contraexemplos;
- condições de mercado;
- horários;
- observações dos autores.

### Deve responder

> O que o método diz sobre esta situação?

e:

> Quais setups do método são compatíveis com este contexto?

### Deve manter rastreabilidade

```text
autor
documento
página
trecho
conceito
setup
versão
status
```

### Não deve

- operar;
- alterar estratégia aprovada sozinho;
- declarar que uma técnica é lucrativa apenas porque aparece em um PDF.

---

# 5. SETUP LIBRARY — CORAÇÃO DO MÉTODO

A biblioteca de setups deve ser um componente estruturado.

Cada setup precisa possuir:

```text
setup_id
nome
autor
fonte
mercados
timeframes
contexto
entrada
confirmação
stop
alvo
condução
saída
invalidação
filtros
contraindicações
horários
evidências
versão
status
```

Estados:

```text
DISCOVERED
→ DRAFT
→ REVIEW
→ APPROVED_FOR_BACKTEST
→ TESTED
→ APPROVED_FOR_PAPER
→ PAPER_VALIDATED
→ LIVE_ELIGIBLE
```

---

# 6. CONDUÇÃO DO TRADE É PARTE DO SETUP

Não reduzir um setup a:

```text
entrada + stop + alvo
```

Se o método ensina diferentes formas de condução, isso precisa ser modelado.

Exemplos conceituais:

```text
Management A
stop fixo + alvo fixo

Management B
stop inicial + proteção progressiva

Management C
parcial + restante

Management D
condução barra a barra

Management E
saída por mudança estrutural
```

Cada condução deve ser uma regra testável.

O Backtest Agent deve conseguir comparar:

```text
mesma entrada
+
diferentes conduções
```

---

# 7. BACKTEST AGENT — INVESTIGADOR DA ESTRATÉGIA

O Backtest Agent não deve ser apenas um calculador de win rate.

Ele deve investigar a estratégia.

## Performance

- número de trades;
- win rate;
- loss rate;
- payoff;
- expectativa;
- profit factor;
- retorno;
- drawdown;
- sequência de perdas;
- sequência de ganhos;
- custos;
- slippage.

## Contexto

- tendência;
- lateralização;
- volatilidade;
- volume;
- estrutura;
- timeframe superior;
- contexto anterior;
- comportamento recente.

## Horário

Descobrir:

- melhores horários;
- piores horários;
- expectativa por faixa horária;
- quantidade de trades por faixa.

## Ativo

Comparar:

- BTC;
- ETH;
- ações americanas líquidas;
- outros ativos posteriormente.

## Timeframe

Comparar, quando houver dados adequados:

- 1m;
- 5m;
- 15m;
- 1h.

## Condução

Comparar as diferentes formas de gerenciamento previstas pelo método.

---

# 8. SINCRONIZAÇÃO KNOWLEDGE ↔ BACKTEST

Este é um requisito central.

O Knowledge Agent e o Backtest Agent devem trabalhar em ciclo.

```text
Knowledge Agent
      ↓
ensina regras
      ↓
Backtest Agent
      ↓
testa
      ↓
resultados
      ↓
Knowledge Agent
      ↓
confere se a interpretação
está fiel ao método
      ↓
Validation
```

## Exemplo

O Knowledge Agent encontra quatro setups:

```text
Setup A
Setup B
Setup C
Setup D
```

O Backtest Agent recebe exatamente essas quatro especificações.

Depois dos testes:

```text
A → expectativa X
B → expectativa Y
C → drawdown elevado
D → melhor desempenho em determinado contexto
```

O Knowledge Agent deve revisar:

- se a regra foi interpretada corretamente;
- se alguma condição foi omitida;
- se a condução foi implementada corretamente;
- se o teste respeitou o método.

Se houver erro de interpretação:

```text
BACKTEST INVALIDADO
```

e o teste deve ser refeito.

---

# 9. APRENDIZADO CONTÍNUO, MAS CONTROLADO

O sistema deve aprender continuamente.

Porém, “aprender” não significa alterar sozinho a estratégia que será usada.

O ciclo deve ser:

```text
Observação
↓
Hipótese
↓
Teste
↓
Evidência
↓
Revisão
↓
Aprovação
↓
Nova versão
```

Nunca:

```text
perdeu dinheiro
↓
IA muda regra
↓
regra nova vira oficial
```

## Tipos de memória

### Memória factual

O que aconteceu.

### Memória do método

O que os autores ensinam.

### Memória experimental

O que os backtests descobriram.

### Memória operacional

O que aconteceu no paper trading.

### Memória de erro

O que falhou e por quê.

Esses tipos não devem ser misturados.

---

# 10. VALIDATION ENGINE

Deve existir uma camada dedicada à validação.

Responsabilidades:

- detectar overfitting;
- separar treino/validação/out-of-sample;
- testar sensibilidade;
- variar custos;
- variar slippage;
- comparar períodos;
- comparar ativos;
- verificar se poucas operações explicam o resultado;
- procurar degradação.

Pergunta central:

> O resultado parece robusto ou depende de uma combinação favorável do histórico?

---

# 11. MARKET ANALYST

O Market Analyst deve produzir uma ficha estruturada do mercado atual.

```text
ATIVO
TIMEFRAME
REGIME
TENDÊNCIA
VOLATILIDADE
VOLUME
ESTRUTURA
SUPORTE
RESISTÊNCIA
MOMENTUM
TIMEFRAME SUPERIOR
CONTEXTO RECENTE
EVENTOS PRÓXIMOS
SETUPS COMPATÍVEIS
SETUPS INCOMPATÍVEIS
```

Depois consulta o Knowledge Agent:

> Quais setups do método são adequados a este contexto?

---

# 12. FUNDAMENTAL / EVENT AGENT

Para ações americanas, este agente deve avaliar:

- earnings;
- resultados;
- guidance;
- eventos corporativos;
- notícias;
- eventos macro;
- calendário econômico;
- catalisadores;
- riscos.

Para cripto:

- notícias relevantes;
- eventos do setor;
- decisões regulatórias;
- eventos de protocolo;
- catalisadores.

Ele não decide sozinho comprar/vender.

Sua saída é:

```text
CONTEXTO
RISCOS
CATALISADORES
EVENTOS
```

---

# 13. DECISION AGENT

Precisamos de uma etapa explícita de síntese.

Ele recebe:

```text
Market Analysis
+
Knowledge Evidence
+
Backtest Evidence
+
Fundamental/Event Analysis
+
Risk Constraints
```

e produz:

```text
TRADE CANDIDATE
```

ou:

```text
NO TRADE
```

Formato:

```text
Ativo:
Direção:
Setup:
Evidência do método:
Contexto atual:
Evidência histórica:
Condução:
Risco:
Fatores contrários:
Decisão:
```

Não usar um “confidence score” como se fosse probabilidade real de lucro.

---

# 14. RISK MANAGER

O Risk Manager é a barreira entre inteligência e execução.

A IA pode dizer:

```text
Entraria.
```

Mas o Risk Manager pode responder:

```text
NEGADO
```

por motivos como:

- risco excedido;
- stop ausente;
- exposição excedida;
- perda diária atingida;
- mercado fora das regras;
- estratégia não aprovada;
- paper/live gate não aprovado.

As regras críticas devem ser determinísticas.

---

# 15. EXECUTION AGENT

O Execution Agent não deve decidir livremente se deve operar.

Ele recebe uma decisão autorizada e executa o plano.

Deve receber:

- entrada;
- tipo de ordem;
- tamanho;
- stop;
- alvo;
- invalidação;
- condução;
- saída.

---

# 16. TRADE MANAGEMENT ENGINE

A condução durante o trade deve ser uma máquina de estados.

Exemplo:

```text
PENDING
↓
ENTERED
↓
INITIAL_PROTECTION
↓
PROFIT_ZONE
↓
MANAGEMENT
↓
PARTIAL / TRAILING / BAR-BY-BAR
↓
EXIT
↓
CLOSED
```

A condução não deve ser improvisada.

Ela deve seguir o playbook aprovado do setup.

---

# 17. COMUNICAÇÃO ENTRE AGENTES

Não queremos uma conversa livre e desorganizada.

Não:

```text
"acho que vai subir"
"concordo"
"talvez compre"
```

Queremos mensagens estruturadas.

Exemplo:

```json
{
  "asset": "BTCUSDT",
  "timeframe": "15m",
  "setup_id": "SETUP_04",
  "market_context": {},
  "method_evidence": [],
  "backtest_evidence": {},
  "event_context": {},
  "risk": {},
  "decision": "candidate"
}
```

Isso permite auditoria.

---

# 18. TRADE JOURNAL

Cada operação deve registrar muito mais que P&L.

```text
Setup
Contexto
Horário
Timeframe
Entrada
Stop
Plano de condução
Condução realizada
Saída
Resultado
Desvio do plano
Erro
Acerto
Lição proposta
```

Isso será a base do aprendizado operacional.

---

# 19. LEARNING REVIEW

Após um conjunto de operações, o sistema procura padrões.

Exemplo:

```text
100 operações do Setup 04.

Resultado:

Horário X:
expectativa negativa.

Timeframe superior alinhado:
resultado superior.

Volume abaixo da média:
resultado inferior.

Hipótese:
filtrar condição Y.
```

Isso gera:

```text
LEARNING PROPOSAL
```

e não alteração automática.

---

# 20. EXPERIMENTOS

Toda melhoria deve ser um experimento versionado.

```text
Hipótese:
Evitar Setup 04 no horário X.

Versão:
Setup 04 V2

Teste:
período A
período B
out-of-sample

Resultado:
...

Conclusão:
...

Status:
REVIEW
```

Somente aprovação humana promove a versão.

---

# 21. OS PRIMEIROS QUATRO SETUPS

O primeiro grande trabalho do Knowledge Agent deve ser selecionar quatro setups do método.

Não escolher apenas por fama.

Priorizar setups que:

- tenham regras claras;
- tenham entrada;
- tenham saída;
- tenham condução;
- sejam operacionalizáveis;
- tenham ocorrências suficientes;
- permitam comparação objetiva.

O Knowledge Agent propõe.

O usuário aprova.

O Backtest Agent testa.

---

# 22. MATRIZ DOS QUATRO SETUPS

Para cada setup:

```text
ATIVO
TIMEFRAME
PERÍODO
HORÁRIO
CONTEXTO
ENTRADA
CONDUÇÃO
CUSTOS
SLIPPAGE
```

Comparar BTC, ETH e universo inicial de ações líquidas conforme disponibilidade dos dados.

Não forçar todos os ativos/timeframes quando os dados não forem adequados.

---

# 23. CONTEXTO ANTERIOR À ENTRADA

O Backtest Agent não deve avaliar somente a barra do gatilho.

Quando a estratégia permitir, analisar janelas anteriores.

Exemplos de experimento:

```text
20 barras
50 barras
100 barras
```

para investigar:

- tendência;
- compressão;
- expansão;
- rompimento;
- pullback;
- volume;
- volatilidade;
- estrutura;
- distância de médias.

A janela deve ser documentada.

---

# 24. HORÁRIO

O sistema deve analisar horário explicitamente.

Para ações americanas, utilizar o timezone correto do mercado.

Para cripto, considerar o mercado 24h.

Não aplicar automaticamente as mesmas janelas de ações a cripto.

---

# 25. BACKTEST SEM LOOK-AHEAD

O motor deve impedir uso de informação futura.

Exemplo:

Se o sinal é confirmado no fechamento da barra `T`, uma regra explícita deve definir a execução, como:

```text
abertura de T+1
```

ou outra regra do setup.

Nunca utilizar informação futura para decidir a entrada.

---

# 26. CUSTOS E EXECUÇÃO

Os backtests devem permitir:

- comissão;
- spread;
- slippage;
- atraso;
- tamanho de posição;
- capital.

Separar:

```text
resultado bruto
resultado após custos
```

---

# 27. BACKTEST → PAPER TRADING

Uma estratégia não vai diretamente para operação.

Pipeline:

```text
DRAFT
↓
BACKTEST
↓
VALIDATION
↓
OUT-OF-SAMPLE
↓
PAPER APPROVED
↓
PAPER TRADING
↓
REVIEW
↓
LIVE ELIGIBLE
```

---

# 28. MARKET DATA ENGINE

Os agentes não devem consultar fornecedores diretamente.

Arquitetura:

```text
Provider
↓
Market Data Adapter
↓
Normalizer
↓
Validator
↓
Storage
↓
Market Service
↓
Agents
```

Isso permite trocar fontes sem reescrever os agentes.

---

# 29. AÇÕES AMERICANAS

O universo inicial deve ser limitado a ativos líquidos.

Considerar:

- preço;
- volume;
- spread;
- horário;
- earnings;
- corporate events;
- notícias;
- contexto de mercado.

Não começar com milhares de ativos.

---

# 30. CRIPTO

Começar por:

```text
BTC
ETH
```

Depois ampliar.

A seleção deve considerar:

- liquidez;
- volume;
- spread;
- qualidade do histórico;
- disponibilidade da API.

---

# 31. XP TRADER 5.0.4.34

A plataforma do usuário é:

```text
XP Trader 5.0.4.34
```

Não assumir recursos do Profit Pro/Ultra.

Antes de qualquer execução:

1. identificar recursos disponíveis;
2. verificar interfaces;
3. verificar documentação;
4. verificar SDK/API;
5. verificar conta de simulação;
6. verificar leitura de dados;
7. verificar execução.

Prioridade:

```text
API oficial
>
interface documentada
>
integração de dados
>
automação de tela como último recurso
```

---

# 32. ARQUITETURA DE BROKERS

Quando chegarmos à execução:

```text
Execution Agent
↓
Broker Interface
↓
Broker Adapter
```

Possíveis adaptadores futuros:

```text
Alpaca
Crypto Exchange
XP
```

O Execution Agent não deve conhecer detalhes de uma corretora específica.

---

# 33. COMPARTILHAMENTO COM OUTRAS PESSOAS

A expertise deve ser compartilhável.

Regra:

```text
EXPERTISE
=
CENTRALIZADA

CREDENCIAIS
=
INDIVIDUAIS
```

Outra pessoa deve conseguir configurar sua própria conta sem receber API keys do proprietário da expertise.

---

# 34. CONFIGURAÇÃO DE PROVEDORES

Criar no portal:

```text
Configurações
→ Provedores
```

Exemplo:

```text
LLM Provider
Base URL
Model
API Key
[Validar conexão]
```

Broker:

```text
Broker
API Key
Secret
Ambiente
[Validar]
```

As chaves não devem aparecer completas depois de configuradas.

---

# 35. SEGURANÇA DE CREDENCIAIS

Não armazenar chaves em:

- SQLite;
- Markdown;
- Git;
- prompts;
- logs;
- memória dos agentes.

Para instalação local:

```text
.env
```

Para uma aplicação compartilhada/publicada:

```text
secret store
```

com isolamento por usuário.

---

# 36. SEPARAÇÃO DE DADOS

A arquitetura final deve separar:

```text
GLOBAL KNOWLEDGE
```

de:

```text
USER WORKSPACE
```

### Global

- PDFs;
- setups;
- regras;
- experimentos aprovados;
- conhecimento;
- playbooks;
- resultados publicados.

### Usuário

- API keys;
- broker;
- capital;
- risco;
- timezone;
- preferências;
- operações;
- histórico privado.

---

# 37. VISUAL DO PORTAL

A referência HTML fornecida pelo usuário deve continuar sendo a direção visual.

O projeto atual já preserva:

- tema escuro;
- sala de agentes;
- mesas;
- painel lateral;
- Mercado;
- Operações;
- Informe;
- Controle;
- Laboratório;
- Evolução do capital.

A evolução deve mostrar dados reais do sistema, nunca números decorativos. O projeto atual explicitamente evita fabricar cotações, P&L ou atividade quando os dados não existem. fileciteturn1file1L1-L15

---

# 38. LIVE DECISION TRACE

Adicionar uma visão no portal mostrando a cadeia da decisão.

Exemplo:

```text
08:42:11
MARKET ANALYST

Estrutura compatível com Setup 04.

↓

08:42:13
KNOWLEDGE AGENT

Setup 04 requer:
...

Fonte:
documento / página

↓

08:42:14
BACKTEST AGENT

Contexto semelhante:
...

Expectancy:
...

↓

08:42:16
EVENT AGENT

Nenhum evento crítico.

↓

08:42:17
DECISION AGENT

Trade Candidate.

↓

08:42:18
RISK MANAGER

Aprovado para paper.

↓

08:42:19
EXECUTION AGENT

Ordem simulada enviada.
```

Isso é uma das principais funcionalidades para que o usuário acompanhe o raciocínio do ecossistema.

---

# 39. EXPLICABILIDADE

Todo sinal deve responder:

## Por quê?

### Método

Qual regra veio do conhecimento.

### Histórico

Qual evidência do backtest existe.

### Mercado

O que está acontecendo agora.

### Eventos

Quais riscos existem.

### Risco

Por que o tamanho/stop foi aprovado.

### Decisão

Por que operar ou não operar.

---

# 40. MÉTRICAS DOS PRÓPRIOS AGENTES

O sistema deve avaliar os agentes.

## Knowledge Agent

- precisão de recuperação;
- citações;
- regras inventadas;
- consistência.

## Backtest Agent

- reprodutibilidade;
- look-ahead;
- custos;
- integridade dos dados.

## Market Analyst

- qualidade do contexto;
- falsos sinais;
- aderência ao setup.

## Decision Agent

- coerência;
- decisões;
- rejeições;
- resultado posterior.

## Execution Agent

- falhas;
- latência;
- ordens duplicadas;
- divergência de execução.

---

# 41. VERSIONAMENTO

Versionar:

```text
setup
prompt
agent
backtest engine
dataset
parameters
management rules
```

Um resultado antigo precisa continuar reproduzível.

---

# 42. REPRODUTIBILIDADE

Um backtest importante deve poder ser reproduzido com:

```text
strategy_version
+
dataset_hash
+
parameters
+
costs
+
slippage
+
engine_version
```

O sistema deve conseguir responder:

> Como este resultado foi obtido?

---

# 43. TESTES OBRIGATÓRIOS

Além de testes unitários:

## Integração

```text
Knowledge
→ Strategy
→ Backtest
```

## Segurança

```text
API ausente
API inválida
ordem real bloqueada
risco excedido
```

## Dados

```text
timestamp
gaps
duplicidade
OHLC inválido
timezone
```

## Trading

```text
entrada
stop
target
parcial
trailing
saída
```

---

# 44. ENTREGA 2 — CONHECIMENTO REAL

1. confirmar PDFs existentes;
2. corrigir a divergência de estado do Research Agent;
3. processar os PDFs;
4. estruturar conceitos;
5. estruturar setups;
6. adicionar citações por página;
7. permitir revisão humana.

### Critério de aceite

O usuário consegue abrir a biblioteca e visualizar os conhecimentos/setups extraídos com fonte rastreável.

### Registro de execução em 13/11/2026

Entrega concluída no código. A biblioteca contém 6 conceitos e 23 setups descobertos como propostas, com trecho de evidência, página e SHA-256 da fonte. A revisão humana registra aprovação ou rejeição; propostas e fontes desatualizadas ficam fora do contexto aprovado. O Research Agent acompanha o estado da biblioteca local.

Provas: `python -m py_compile app.py database/store.py services/documents.py services/knowledge.py services/agents.py` passou; `python main.py test` passou com 34 testes; Playwright mostrou citação, revisão e ausência de rolagem horizontal em 1440×1000, 390×844 e 320×740. O commit desta entrega registra os artefatos e o código.

---

# 45. ENTREGA 3 — QUATRO SETUPS

O Knowledge Agent propõe quatro setups.

O usuário aprova.

**Estado em 13/11/2026:** o usuário selecionou VBS, VSS, BOP e BDP e aprovou os parâmetros v1. O SQLite preserva quatro rascunhos v1 e quatro versões v2 aprovadas para backtest. A especificação de origem e as decisões de implementação estão em `PROJECT_DOCUMENTATION.md`; o detector de sinais está em `services/setup_signals.py`. Ainda não há dataset nem backtest desses setups.

**Prova:** `python main.py test` passou com 40 casos. O detector produziu ordens hipotéticas reproduzíveis para os quatro padrões sobre barras sintéticas. Playwright confirmou as versões aprovadas e a ausência de execução SMA indevida em 1440×1000, 390×844 e 320×740.

Cada um recebe:

```text
setup_id
version
source
rules
management
filters
```

### Critério de aceite

Existem quatro setups aprovados para backtest e suas regras são operacionalizáveis.

---

# 46. ENTREGA 4 — DADOS HISTÓRICOS

Construir pipeline de dados.

Começar pequeno:

```text
BTC
ETH
ações líquidas
```

### Critério de aceite

Dados podem ser importados, validados, armazenados e reproduzidos.

---

# 47. ENTREGA 5 — BACKTEST DOS QUATRO SETUPS

Para cada setup:

```text
performance
horário
contexto
ativo
timeframe
condução
drawdown
custos
slippage
```

### Critério de aceite

Cada setup possui relatório reproduzível.

---

# 48. ENTREGA 6 — VALIDATION ENGINE

Separar:

```text
desenvolvimento
validação
out-of-sample
```

Executar stress tests.

### Critério de aceite

Nenhuma estratégia é promovida apenas por resultado bruto.

### Registro de execução em 13/11/2026

Entrega concluída no código. `services/validation.py` separa desenvolvimento e out-of-sample por corte temporal causal, roda uma grade fixa de custo nos dois lados, mede concentração removendo a melhor operação e rotula a adequação da amostra. O portão de proveniência do backtest foi extraído para `verify_approved_rules` e `prepare_verified_run` em `services/setup_backtest.py` e é reaproveitado sem duplicação: versão não aprovada, PDF alterado ou dataset fora do padrão cripto 1m verificado são recusados na validação como no backtest. A série nunca é embaralhada, o corte recua até um bloco UTC completo e cada lado paga seu próprio aquecimento de 29 barras, de modo que nenhuma barra de treino alimenta um sinal out-of-sample.

O critério de aceite é cumprido pela via do rótulo, não da promoção: o resultado traz `promotes_strategy: false` e um veredito que nunca afirma robustez. Menos de 10 operações no pior lado é `insuficiente` e não gera leitura alguma; de 10 a 29 é `limitrofe` e gera leitura apenas indicativa; a partir de 30 é `adequada` e apenas habilita a leitura, sujeita aos sinais de fragilidade. Os dois limiares são decisão de projeto aprovada pelo usuário, registrada em cada execução ao lado do resultado. `validation_runs` guarda as projeções consultáveis e o registro completo com hashes e janela de datas; os dois modos de portal mostram contagem, rótulo e sinais de fragilidade, com o retorno líquido nunca isolado como veredito.

Provas: `python main.py test` passou com 70 testes, incluindo `tests/test_validation.py` (corte sem vazamento do futuro, monotonicidade da grade de custo, detecção de trade dominante, limiares em 10 e 30) e os novos casos `AppTest`. `python -m scripts.run_delivery6` executou as 16 combinações de quatro setups, dois pares e dois intervalos com fração out-of-sample de 0,30; a segunda execução não duplicou registros. `python -m scripts.run_delivery5` recomparou os 16 backtests da Entrega 5 com os relatórios persistidos e não acusou divergência, provando que o refactor preservou o histórico. `python scripts/check_portal_state.py` confirmou a seção de validação nos dois modos de portal em 1440×1000, 390×844 e 320×740, sem erro de JavaScript e sem rolagem horizontal.

Limitação conhecida: com cerca de 16h38 de candles por par, as 16 combinações ficaram todas rotuladas como `insuficiente`. Esse é o resultado correto e esperado desta amostra, não uma falha do motor. "Comparar períodos" e "procurar degradação", desta seção e da seção 10, ficaram explicitamente fora do escopo por exigirem várias janelas longas e independentes que o histórico atual não oferece; a pendência está registrada em cada execução no campo `out_of_scope` e em `PROJECT_DOCUMENTATION.md`.

---

# 49. ENTREGA 7 — AGENT ORCHESTRATION

Implementar o fluxo:

```text
Market
→ Knowledge
→ Backtest Evidence
→ Fundamental
→ Decision
→ Risk
→ Execution
```

### Critério de aceite

Uma oportunidade simulada gera uma trilha completa e auditável.

### Registro de execução em 16/11/2026

Entrega concluída no código, em 4 fases, com decisão aprovada previamente pelo usuário em `DEC-2026-11-16-escopo-entrega-7-orquestracao.md`. `database/store.py` ganhou as tabelas `pipeline_runs` (uma linha por barra de sinal avaliada, `UNIQUE(strategy_id, symbol, timeframe, signal_bar_utc)` garantindo que a mesma barra nunca gera uma segunda trilha) e `pipeline_stages` (um registro por estágio por run, mesmo quando o estágio não roda), além da coluna `pipeline_run_id` em `paper_operations` — tudo por migração aditiva e idempotente. Quatro módulos novos de serviço implementam o encadeamento: `services/pipeline.py` orquestra os 7 estágios sobre o feed ao vivo; `services/decision.py` e `services/risk.py` são serviço determinístico, nunca agente novo na tabela `agents`; `services/execution.py` só monta o plano quando o Risk autoriza e expõe o portão humano (`confirm_open`/`discard`).

Duas decisões do usuário definiram o desenho: a fonte do sinal é o feed ao vivo (`market_bars`/coletor Binance), não o snapshot histórico verificado por hash que era a opção recomendada — aceita-se a barra mais recente do coletor sem checagem adicional de integridade, e o pipeline retorna `sem_feed`/`historico_insuficiente` em vez de trilha quando o coletor não tem barras suficientes; e a Execution abre posição real em `paper_operations`, com a quantidade sempre informada pelo usuário na tela no momento da autorização, nunca presumida do sistema — mais concreto do que a alternativa inicialmente recomendada de registrar só a intenção. Os parâmetros de risco (1R por trade, 3R de perda diária, 2 posições simultâneas) são parâmetro de projeto explícito, não extraídos do método: duas investigações nos PDFs (chunks indexados; depois leitura exaustiva das 311+9 páginas) confirmaram que o método Oliver Velez não tem nenhuma camada de money management, position sizing, R múltiplo ou exposição de portfólio.

Limitações conhecidas, registradas também em `PROJECT_DOCUMENTATION.md`: `filters.session_hours` (motivo `mercado_fora_das_regras`) segue sem definição de mercado/fuso, herdada de `DEC-2026-11-13-primeiros-quatro-setups.md`, e fica `nao_aplicavel` na trilha, nunca bloqueando nem liberando. O estágio Fundamental está sempre `sem_fonte`: nenhuma fonte de notícias/eventos foi integrada ao projeto. Fechamento de posição, acompanhamento de stop/alvo e cálculo de P&L ficam fora do escopo desta entrega — são trabalho de entregas futuras (Entrega 8). A amostra insuficiente apontada pela Validation Engine (Entrega 6, as 16 combinações aprovadas) não bloqueia o candidato: é aviso obrigatório na Decision, não motivo de negação do Risk Manager.

Provas: `python main.py test` passou com a suíte completa (contagem na run desta entrega). `python -m scripts.run_delivery7` demonstrou o critério de aceite avaliando cada estratégia aprovada × símbolo elegível (BTCUSDT/ETHUSDT) × timeframe do próprio setup sobre o feed ao vivo real, produzindo 16 trilhas completas e auditáveis (uma por combinação); rodar a avaliação uma segunda vez não duplicou nenhuma trilha (idempotência por barra confirmada). O modo de confirmação do script (`--abrir`/`--quantidade`, `--descartar`) exercitou o portão humano e o caminho de recusa (run não `aguardando_quantidade`) sem quebrar.

---

# 50. ENTREGA 8 — TRADE MANAGEMENT

Implementar condução.

O Executor recebe:

```text
Entry Plan
+
Initial Stop
+
Management Plan
+
Exit Plan
```

### Critério de aceite

A lógica de condução usada no backtest pode ser reproduzida no paper engine.

### Registro de execução em 16/11/2026

Entrega concluída no código, em 4 fases, com decisão aprovada previamente pelo usuário em `DEC-2026-11-16-escopo-entrega-8-trade-management.md`. `services/setup_backtest.py::simulate` foi extraída, sem mudar nenhum comportamento existente, numa função nova `replay_open_position` que gerencia uma posição já aberta sobre uma sequência de barras a partir de um índice — o mesmo mecanismo que `simulate` já usava internamente para stop/alvo/trailing, agora reutilizável fora de um backtest completo. `database/store.py` ganhou a coluna aditiva `exit_reason` em `paper_operations` e três funções novas: `get_strategy` (uma versão por id), `get_market_bars_since` (janela ascendente de barras desde um instante, tolerante às duas convenções de sufixo de fuso do projeto) e `close_paper_operation` (fechamento condicional idempotente que também estampa `pipeline_runs.realized_r` na mesma transação). `services/trade_management.py` é o serviço de condução sob demanda: para cada `paper_operation` aberta, reconstrói a posição a partir da barra de entrada congelada na trilha (`pipeline_runs.report_json["execution"]`) e chama `replay_open_position` sobre as barras do feed ao vivo, nunca reabrindo `strategies.rules_json`. A integração em `services/pipeline.py`/`services/execution.py` (barra de entrada congelada) e `app.py` (disparo automático do replay a cada abertura de tela, nos dois modos de portal, mais a UI de condução) foi feita nas Fases 1–3 e verificada antes desta fase.

Quatro decisões do usuário definiram o desenho, documentadas na DEC: a condução roda sob demanda, recalculando do zero a cada abertura de tela — sem processo novo em background, mesmo padrão já usado pelo pipeline da Entrega 7 (opção recomendada); a lógica de trailing é replicada tal como está no backtest, hardcode por nome de setup incluído, em vez de generalizar a leitura de `rules_json.management` (não é a opção recomendada — o usuário priorizou reproduzir fielmente o comportamento existente, inconsistência incluída, a corrigir numa entrega futura dedicada); o custo no fechamento usa as mesmas premissas do backtest, 10 bps de taxa e 5 bps de slippage por lado, não custo zero (não é a opção recomendada); e a tela "Evolução do capital" pode passar a mostrar P&L monetário automaticamente assim que a primeira posição fechar, com legenda nova deixando claro que o resultado oficial continua em R (opção recomendada). O fechamento por lacuna no feed (`gap_boundary`) foi aceito tal como o backtest trata, fiel ao backtest.

Limitações conhecidas, registradas também em `PROJECT_DOCUMENTATION.md`: uma posição `open` que já deveria ter fechado só fecha quando alguém abre a tela de condução — se ninguém abrir, ela continua `open` mesmo tendo batido o stop há horas, o que é esperado, não bug. A condução depende do coletor Binance estar rodando para ter barra nova para avaliar, mesma dependência já aceita para gerar sinal na Entrega 7. A inconsistência entre `rules_json.management` (dado declarado) e o comportamento real de trailing (hardcode por nome de setup) passa a existir em DOIS motores — backtest e paper engine — em vez de um, não corrigida nesta entrega.

Provas: `python main.py test` passou com 132 testes (rodado duas vezes, sem flakiness). `python -m scripts.run_delivery8` demonstrou o critério de aceite em duas camadas, sem nunca tocar `database/trading.db`: paridade de motor sem banco (três cenários sintéticos de barras 2m — fechamento por stop, por alvo e por trailing, este último adaptado do fixture de trailing dos testes — com `simulate()` e `replay_open_position()` rodando lado a lado sobre as mesmas barras, veredito `IDÊNTICO` campo a campo nos três); e um fluxo ponta a ponta com persistência num banco temporário (semeadura de `market_bars`/estratégia/`pipeline_run`/`paper_operation` aberta, fechamento com `exit_reason`/`realized_r`/estágio 8 "conduction" gravado na primeira chamada de `replay_open_operations()`, e confirmação de que a segunda chamada não muda nada — idempotência). Em modo condução, contra o banco real, não havia nenhuma posição simulada aberta no momento da execução.

---

# 51. ENTREGA 9 — PAPER TRADING

Executar mercado atual em simulação.

Fluxo:

```text
signal
→ risk
→ entry
→ management
→ exit
→ journal
```

### Critério de aceite

Ciclo completo sem dinheiro real.

### Registro de execução em 17/11/2026

Plano `docs/plans/entrega-9-paper-trading.md` aprovado pelo usuário. A entrega fecha o ciclo local já iniciado nas Entregas 7 e 8: abertura com quantidade humana, condução sob demanda, saída por stop/alvo/trailing e diário em `paper_journal` com uma ficha por operação. A ficha é criada na abertura e completada no fechamento; a migração identifica operações legadas sem inventar sinal ou condução. `close_paper_operation` grava posição, resultado líquido em R, diário e estágio 8 na mesma transação condicional. Taxas de 10 bps por lado usam o nocional de cada lado; slippage de 5 bps adverso já está no preço de saída, sem desconto duplo. Evolução do capital identifica P&L em USDT apenas para BTCUSDT/ETHUSDT.

Provas: `python main.py test` passou com a suíte completa; `python -m scripts.run_delivery9 --prova` demonstrou o ciclo e o bloqueio por exposição usando somente banco temporário/candles sintéticos, conferindo diário único e reconciliação de custos/R. `scripts/check_delivery9_ui.py` verificou portal e Laboratório nas três larguras contratadas (1440×1000, 390×844, 320×740), sem erro de JavaScript nem rolagem horizontal. Limitações: coletor Binance separado, condução sob demanda, amostra de validação insuficiente e inconsistência conhecida do trailing por nome de setup.

---

# 52. ENTREGA 10 — APRENDIZADO CONTROLADO

Após volume suficiente de paper trades:

```text
o que funcionou
o que falhou
qual contexto
qual horário
qual setup
qual condução
```

O sistema gera hipóteses.

### Critério de aceite

O usuário consegue aprovar/rejeitar propostas de aprendizado e criar novas versões.

### Registro de execução em 17/11/2026

Plano `docs/plans/entrega-10-aprendizado-controlado.md` aprovado pelo usuário. `services/paper_learning.py` gera hipóteses locais e determinísticas somente para uma coorte de mesma estratégia, símbolo e intervalo com 30 operações paper fechadas e íntegras em pelo menos dois dias UTC. O limiar é parâmetro de projeto, não afirmação de robustez. `paper_learning_proposals` registra versão do analisador, IDs e digest SHA-256 da evidência, observação, hipótese, limitações, revisão humana e vínculo opcional ao rascunho. Repetir a mesma análise não duplica proposta. Aprovar/rejeitar não altera estratégia ou memória; criar uma nova versão exige edição manual dos campos operacionais, reconferência da evidência e grava apenas `draft` com aprovação das regras pendente. O portal e o Laboratório apresentam contagens e estados persistidos. No banco local havia zero operações paper encerradas, logo nenhuma hipótese real foi criada.

Provas: `python main.py test` passou com 142 testes, incluindo revisão e criação de rascunho pela UI. `python -m scripts.run_delivery10 --prova` demonstrou limiar, revisão, versão rascunho e idempotência em banco temporário com operações sintéticas. `scripts/check_delivery9_ui.py` verificou portal e Laboratório em 1440×1000, 390×844 e 320×740, sem erro de JavaScript ou rolagem horizontal. `python main.py status` aplicou a migração ao banco local; zero diários e zero propostas paper após a prova. Limitações: condução paper sob demanda, amostra histórica de validação insuficiente, trailing ainda por nome de setup; nenhuma promoção ou otimização automática.

---

# 53. ENTREGA 11 — BROKER PAPER

Conectar uma corretora/API somente em ambiente de simulação.

A arquitetura deve usar:

```text
Broker Interface
```

para não acoplar o sistema a um fornecedor.

---

# 54. ENTREGA 12 — XP TRADER

Investigar especificamente:

```text
XP Trader 5.0.4.34
```

Documentar:

- dados;
- APIs;
- SDK;
- simulação;
- execução;
- limitações.

Não presumir compatibilidade com Profit Pro.

---

# 55. ENTREGA 13 — MULTIUSUÁRIO

Separar:

```text
Knowledge Base Global
```

de:

```text
User Workspace
```

Cada usuário configura suas próprias credenciais.

---

# 56. ENTREGA 14 — PORTAL ONLINE

Evoluir de:

```text
localhost
```

para uso por usuários autorizados.

Necessário:

- autenticação;
- autorização;
- secrets;
- HTTPS;
- isolamento de usuários;
- logs;
- backup.

A migração de SQLite para PostgreSQL deve ocorrer somente quando a concorrência/escala justificar.

---

# 57. ENTREGA 15 — OBSERVABILIDADE

Implementar:

- health checks;
- heartbeat;
- logs;
- alertas;
- kill switch;
- reconciliação;
- backup;
- monitoramento.

---

# 58. ENTREGA 16 — LIVE READINESS

Uma estratégia somente pode chegar a:

```text
LIVE_ELIGIBLE
```

depois de:

- conhecimento rastreável;
- regras claras;
- backtest;
- out-of-sample;
- stress test;
- paper trading;
- risco;
- execução;
- reconciliação;
- observabilidade;
- aprovação humana.

---

# 59. PRIMEIRA OPERAÇÃO REAL

A primeira operação real deve ser um experimento controlado.

Começar com:

```text
1 estratégia
1 mercado
1 timeframe
risco mínimo
```

Nunca ativar todas as estratégias de uma vez.

---

# 60. PROTOCOLO OBRIGATÓRIO PARA O CODEX

Para cada entrega:

```text
1. Ler AGENTS.md
2. Ler PROJECT_DOCUMENTATION.md
3. Inspecionar o código
4. Executar testes
5. Diagnosticar
6. Criar plano
7. Aguardar aprovação
8. Implementar
9. Executar testes
10. Corrigir
11. Executar novamente
12. Atualizar documentação
13. Demonstrar a funcionalidade
14. Apresentar critérios de aceite
15. Parar
```

O Codex não deve iniciar a próxima entrega automaticamente.

---

# 61. O QUE O CODEX NÃO DEVE FAZER

Não:

- recriar o projeto inteiro;
- criar dezenas de agentes sem necessidade;
- apagar decisões existentes;
- inventar dados;
- inventar backtests;
- colocar API keys no código;
- misturar conhecimento do autor com descoberta experimental;
- alterar estratégia aprovada automaticamente;
- usar resultado histórico como promessa futura;
- conectar conta real antes da autorização;
- automatizar a tela do XP Trader antes de investigar interfaces adequadas;
- avançar para a próxima entrega sem validar a atual.

---

# 62. CRITÉRIO FINAL DE CONCLUSÃO

O Trading Agent Lab estará funcional quando conseguir executar, em simulação, de ponta a ponta:

```text
PDF
 ↓
Knowledge Agent
 ↓
Setup Library
 ↓
Backtest
 ↓
Validation
 ↓
Market Context
 ↓
Fundamental Context
 ↓
Decision
 ↓
Risk
 ↓
Execution
 ↓
Trade Management
 ↓
Trade Journal
 ↓
Learning Review
 ↓
Nova hipótese
 ↓
Novo backtest
```

e tudo puder ser acompanhado no portal.

---

# 63. PRINCÍPIO FINAL

O objetivo não é construir uma IA que “adivinhe” o mercado.

O objetivo é construir um sistema que:

```text
ESTUDE
↓
FORMALIZE
↓
TESTE
↓
COMPARE
↓
REJEITE O QUE NÃO FUNCIONA
↓
APRENDA COM EVIDÊNCIA
↓
MONITORE
↓
DECIDA
↓
CONTROLE RISCO
↓
EXECUTE
↓
REGISTRE
↓
APRENDA NOVAMENTE
```

A inteligência do sistema deve vir da combinação de:

```text
CONHECIMENTO HUMANO
+
DADOS
+
BACKTEST
+
CONTEXTO
+
ANÁLISE ATUAL
+
GESTÃO
+
EXECUÇÃO
+
FEEDBACK
```

e não de uma única resposta produzida por um LLM.

**O sistema deve conseguir explicar por que uma decisão foi tomada, quais evidências sustentaram a decisão, quais evidências eram contrárias e o que aconteceu depois.**

Esse é o requisito central para transformar o Trading Agent Lab de um protótipo de agentes em um laboratório de trading verificável e, somente após validação rigorosa, em uma infraestrutura apta a suportar operações reais.
