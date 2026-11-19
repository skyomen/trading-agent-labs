# Configuração de design — trading-agent-labs

Decisão de consequência (tese, autoridade visual) vive em
`_capsule/decisoes/DEC-2026-11-18-redesign-painel-funcional.md`. Este arquivo é só a
configuração de referência do protocolo (`metodo-design-de-interface.md` §2); não repita nem
contradiga o DEC.

```yaml
projeto: Trading Agent Lab
tipo: redesign
objetivo: >
  Acompanhar operações paper persistidas e abrir o Mercado para estudo visual,
  distinguindo os candles locais do widget externo.
escopo: >
  Interface Streamlit local atual: páginas Operações e Mercado, dock inferior,
  tema escuro padrão e detalhe gráfico da operação.
fora_de_escopo: >
  Nenhuma tela nova de função; mudanças visuais não alteram regra de negócio nem enviam ordens.
  Não reabre a escolha de dados reais vs. simulados já decidida em DECs anteriores.
nicho: Ferramenta local de pesquisa e acompanhamento paper
modo_de_visita: operar
tarefa_principal: comparar operação paper com candles e entender entrada, risco e saída
momento_decisivo: selecionar operação e localizar seus eventos no candle correspondente
tese: >
  Um painel opera melhor sem metáfora decorativa. Recusa: escritório/sala isométrica, mesas,
  quadro de evidências como estrutura de navegação.
original: >
  operations_page.py, market_page.py e app.py; referencia.html é histórica
referencias_esteticas: App Revolut, conforme pedido do usuário; inspiração limitada à hierarquia,
  cartões e uso de cor, sem copiar conteúdo ou identidade visual.
autoridade_visual: Impeccable
stack_e_componentes: Streamlit (Python), CSS customizado via unsafe_allow_html existente em app.py
temas_e_breakpoints: tema escuro padrão com opção clara; validado em 320/390/1440 px
dispositivos_alvo: desktop e mobile (o app já é usado nas duas larguras hoje)
orcamento_desempenho: padrão de §10 do método; sem orçamento específico do projeto além disso
acessibilidade: WCAG 2.2 AA (padrão, sem desvio)
movimento: mínimo — ferramenta de operação não usa coreografia de entrada (§11, "superfície de operação")
dados_dinamicos: SQLite via database/store.py; Advanced Chart usa feed independente do TradingView
preview: docs/design/operacoes-preview.html e capturas neste diretório
dados: registros SQLite para operações; candles fictícios só em provas com banco temporário
validacao: python main.py test e scripts/check_operations_ui.py
autorizacoes: páginas Operações/Mercado autorizadas pelo usuário; widget é visual e não executa ordens
pendencias: publicação Vercel não compatível com a arquitetura atual; ver docs/deploy/vercel.md
```
