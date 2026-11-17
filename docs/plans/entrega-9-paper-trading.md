# Entrega 9 — Paper Trading: plano para aprovação

Estado: aprovado pelo usuário e implementado em 17/11/2026, conforme o protocolo da seção 60 do roadmap. Provas e limites observados estão em `PROJECT_DOCUMENTATION.md` e no registro da Entrega 9 do roadmap.

## Base verificada

- `python main.py test`: 132 testes, todos passaram.
- Entrega 7 já persiste sinal, decisão, risco, autorização humana de quantidade e abertura em `pipeline_runs`, `pipeline_stages` e `paper_operations`.
- Entrega 8 já reconduz posição aberta com barras persistidas, stop/alvo/trailing do motor compartilhado e fecha de modo idempotente ao abrir a tela de Orquestração.
- Ainda não existe diário estruturado da operação. O estágio de condução e o evento de fechamento registram parte da trilha, mas não compõem uma ficha fechada com proveniência e custos.
- `closed_trade()` inclui 10 bps de taxa por lado no retorno líquido e aplica 5 bps de slippage adverso no preço de saída. `trade_management.replay_operation()` grava `fees=0.0` no fechamento; assim o P&L monetário exibido em Evolução do capital não desconta as taxas simuladas.
- O feed cripto depende de coletor iniciado explicitamente; a condução permanece sob demanda. Nenhuma integração de corretora ou ordem real será incluída.

## Escopo proposto

1. **Diário persistido, ligado à operação.** Criar tabela `paper_journal` em `database/store.py`, por migração aditiva e idempotente, com `operation_id` único, `pipeline_run_id`, versão do formato, horário, resumo de sinal/risco, entrada, condução, saída, custos, resultado em R, fonte do feed e limitações em JSON. Uma operação aberta terá registro de abertura; o fechamento completará o mesmo diário, sem duplicar entradas. Operações legadas sem trilha ficam identificadas como tal, sem reconstrução fictícia.
2. **Fechamento e contabilidade coerentes.** Persistir as taxas simuladas por lado como valor na moeda de cotação, calculadas sobre a quantidade informada e preços da operação. Manter o slippage embutido no preço adverso de saída e distingui-lo da taxa para evitar desconto duplo. Registrar premissas de 10/5 bps por lado e separar retorno bruto, taxas e líquido. Reconciliar `paper_operations`, `pipeline_runs.realized_r`, diário e Evolução do capital; resultados monetários serão rotulados em USDT para BTCUSDT/ETHUSDT, sem saldo inicial presumido.
3. **Transação e idempotência.** Fechamento da operação, `realized_r`, diário e vínculo de estágio de condução serão consistentes em uma transação do store. Reabrir a tela ou repetir o replay não alterará uma operação encerrada. Falta de feed, barra de entrada ou trilha permanecerá estado explícito e não criará saída fictícia.
4. **Interface.** Adicionar diário legível à Orquestração/Laboratório e resumo no portal padrão, sempre a partir do SQLite: sinal → risco → entrada → condução → saída → diário. Mostrar estados vazios e distinguir posição aberta, fechada e operação legada. Manter aviso de simulação, limite do feed e ausência de ordens reais.
5. **Demonstração e documentação.** Criar `python -m scripts.run_delivery9 --prova` com banco temporário e barras sintéticas determinísticas para demonstrar ciclo completo, incluindo recusa pelo risco, abertura com quantidade humana, fechamento por stop/alvo, diário único e reconciliação de custos. Atualizar `PROJECT_DOCUMENTATION.md` e o registro da Entrega 9 no roadmap após a implementação.

## Critérios de aceite

- Uma oportunidade autorizada percorre sinal → risco → entrada → condução → saída → diário sem dinheiro real; a quantidade continua sendo informada pelo usuário.
- O diário referencia a barra do sinal, a trilha e a operação persistidas; registra decisões, fonte, horários, custos e limitações sem dados inventados.
- Resultado em R e P&L monetário derivam dos mesmos preços e custos simulados; a taxa não desaparece nem o slippage é descontado duas vezes.
- Repetir a avaliação, confirmação ou condução não duplica posição, fechamento ou diário.
- Sem feed suficiente, sem autorização ou sem operação fechada, a interface mostra o estado correspondente e não inventa resultado.
- `python main.py test` passa; a prova CLI usa apenas banco temporário; portal e Laboratório apresentam o ciclo sem rolagem horizontal nas larguras já contratadas (1440, 390 e 320 px).

## Fora do escopo

- Corretora paper externa, XP Trader, ordens reais, processo novo de condução em segundo plano, promoção automática de estratégia e aprendizado automático.
- Correção da inconsistência conhecida entre `rules_json.management` e trailing por nome de setup; o diário registrará o comportamento aplicado.
- Alegar validação estatística de estratégia com a amostra atual insuficiente.
