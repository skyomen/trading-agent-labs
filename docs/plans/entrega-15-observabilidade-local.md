# Entrega 15 — Observabilidade local

Estado: implementada em 17/11/2026.

## Escopo

- Saúde do servidor e persistência local: verificação de integridade SQLite e data/hora da última atividade do app e do coletor.
- Alertas determinísticos baseados em registros existentes: feed desconectado/antigo, ordem Testnet em estado `unknown` e operação paper aguardando condução sob demanda. Não inventar feed ou atividade.
- Bloqueio operacional por workspace: impedir novas aberturas paper e novas compras Testnet quando ativado. Consulta, cancelamento, descarte e saída de posição já aberta continuam possíveis.
- Reconciliação Testnet permanece ação explícita, sem consulta privada automática ao abrir a tela. Logs e erros não podem incluir credenciais.
- Backup cifrado e prova de restauração da Entrega 14 continuam disponíveis no modo local.

## Implementação

1. Migração aditiva/idempotente para estado operacional e heartbeat em `database/store.py`.
2. `services/observability.py` monta snapshot de saúde, alertas e bloqueio a partir de dados persistidos. Registrar heartbeat do app e do coletor apenas quando esses processos rodam.
3. Portão do bloqueio em `services/execution.py` e `services/broker_paper.py` imediatamente antes da reserva/abertura. Expor controles com confirmação em Controle, sem mudar o fluxo de saída.
4. Testes de ausência de dados, feed antigo, ordem incerta, bloqueio nas duas aberturas, saídas permitidas, isolamento entre workspaces e migração idempotente. Prova CLI com banco temporário.
5. Rodar `python main.py test`, prova visual e atualizar documentação. Parar antes da Entrega 16.

## Limites

Não há monitor de infraestrutura 24/7 enquanto o computador está desligado. Alertas são locais, sem mensagem externa. A consulta à Testnet exige credenciais e ação humana. Nenhuma ordem real é preparada ou enviada.
