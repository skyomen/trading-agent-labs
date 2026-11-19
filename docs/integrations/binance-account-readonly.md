# Consulta futura da conta Binance Spot

Pesquisa de 18/11/2026. Nenhuma conta pessoal foi conectada e nenhuma chave foi solicitada nesta entrega.

A [documentação oficial da Binance Spot](https://developers.binance.com/en/docs/products/spot/rest-api) distingue `USER_DATA`, para informações privadas como saldo, estado de ordens e histórico de trades, de `TRADE`, para enviar ou cancelar ordens. A futura integração deverá aceitar somente chave com leitura habilitada e negociação/saque desabilitados; as credenciais ficam no cofre por usuário, fora do SQLite.

Uma página futura poderá importar saldos e trades Spot já executados como registros de **conta Binance**, com origem e horário próprios. Esses registros ficarão separados de `paper_operations`, do resultado em USDT simulado e das ordens virtuais da Spot Testnet. Não haverá cópia automática de operação paper para a conta nem preparação de ordem real.

Antes de implementar, confirmar com o usuário o escopo da conta (Spot, margem ou futuros), permissões da chave, limites de consulta, símbolos desejados e período histórico. A página Operações atual mostra apenas paper local.
