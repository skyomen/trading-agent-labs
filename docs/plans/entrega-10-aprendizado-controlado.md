# Entrega 10 — Aprendizado Controlado: plano para aprovação

Estado: aprovado pelo usuário e implementado em 17/11/2026, conforme o protocolo da seção 60 do roadmap. Provas finais e limites observados estão em `PROJECT_DOCUMENTATION.md`.

## Base observada

- `python main.py test`: 135 testes, todos passaram.
- `paper_journal` contém zero operações no banco local, das quais zero encerradas. Nenhuma hipótese de desempenho pode ser inferida do estado atual.
- `agent_reviews` e `agent_memories` já permitem revisão humana de texto e contexto aprovado; não representam uma análise rastreável de operações paper. `strategies` já guarda versões imutáveis, mas a UI só cria rascunhos SMA; não cria uma versão de setup a partir de evidência paper.
- `validation_runs` continua rotulando as amostras históricas curtas como insuficientes. Um aprendizado paper não mudará esse rótulo nem aprovará estratégia automaticamente.
- As alterações da Entrega 9 ainda estão no workspace, sem commit. Este plano parte desse estado e não reverte essas alterações.

## Decisões propostas para esta entrega

1. **Volume mínimo:** habilitar geração de hipóteses somente para uma coorte de mesmo `strategy_id`, símbolo e timeframe com pelo menos **30 operações paper encerradas**, em **pelo menos dois dias UTC**. Este é um parâmetro novo de projeto; 30 coincide com o limiar de leitura da Validation Engine, mas não prova robustez nem validade estatística. A tela mostrará contagem e dias faltantes. Uma coorte menor não gera proposta.
2. **Análise local e determinística:** ler somente operações paper encerradas com diário e trilha íntegros. Agregar, por coorte, resultado líquido em R, motivo de saída, horário UTC, setup e condução aplicada. Separar observações de hipóteses; não usar LLM, não enviar PDFs ou dados a provedor externo. Evitar frases causais como “este horário funciona” a partir de simples associação. Registrar denominadores e contexto ausente.
3. **Proveniência e revisão:** criar `paper_learning_proposals` em migração aditiva, com versão do analisador, filtro da coorte, IDs das operações e digest canônico dos campos usados, observação, hipótese, limitações e estado `proposed/approved/rejected`. Uma mesma evidência e versão do analisador não duplica proposta. Aprovar/rejeitar exige ação humana e é idempotente; proposta rejeitada continua auditável. Aprovação classifica uma hipótese como revisada, sem colocá-la automaticamente na memória de método nem alterar regras.
4. **Nova versão somente como rascunho:** a partir de uma proposta aprovada, o usuário pode criar uma nova versão **draft** da estratégia de origem, com vínculo explícito à proposta, justificativa e alteração manual de parâmetros. A versão aprovada anterior permanece intacta e ativa; nenhuma regra executável é reescrita automaticamente. Regras de setup novas precisarão de aprovação humana específica e das mesmas verificações de fonte antes de backtest/pipeline. Uma proposta pode fundamentar um rascunho, mas não é aprovação de backtest, paper ou live.
5. **Interface e demonstração:** adicionar no Laboratório uma vista de coortes elegíveis/inelegíveis, propostas, evidências, ações de aprovar/rejeitar e criação de rascunho. O portal padrão mostra apenas contagem e estado persistidos. Criar prova `python -m scripts.run_delivery10 --prova` em banco temporário, com operações sintéticas claramente rotuladas, incluindo bloqueio abaixo do limiar, geração acima dele, revisão, rascunho vinculado e idempotência. Atualizar `PROJECT_DOCUMENTATION.md`, `AGENTS.md` e roadmap após implementação.

## Critérios de aceite

- Com o banco local atual, a interface declara zero operações encerradas e nenhuma proposta paper; não insere exemplos ou conclusões fictícias.
- Abaixo de 30 operações ou de dois dias UTC na mesma coorte, o motor retorna amostra insuficiente e não persiste hipótese.
- Uma proposta rastreia exatamente as operações e campos utilizados, explicita limites e distingue observação de hipótese. Repetir a análise não duplica registros.
- Aprovação e rejeição humanas persistem uma vez. Aprovação não altera `strategies`, `agent_memories`, backtests ou operações.
- O rascunho derivado preserva a versão anterior e não é executável até nova aprovação e validação aplicáveis.
- `python main.py test` passa; a prova usa apenas banco temporário; portal e Laboratório permanecem responsivos em 1440×1000, 390×844 e 320×740.

## Fora do escopo

- Aprendizado de regras por LLM, otimização automática de parâmetros, promoção automática, ordens reais, corretora paper externa e afirmação de robustez ou rentabilidade futura.
- Coleta de operações reais para preencher a amostra. O coletor Binance e a condução sob demanda seguem como nas Entregas 4 e 8.
