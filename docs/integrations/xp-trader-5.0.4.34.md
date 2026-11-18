# XP Trader 5.0.4.34 — investigação de integração

Consulta pública: 17/11/2026. Produto alvo informado pelo usuário: **XP Trader 5.0.4.34**, versão White Label da Nelogica. Este documento registra evidências públicas e as confirmações que ainda dependem da licença e do SDK aplicáveis. O projeto permanece em simulação e **XP Trader desconectado**.

## Matriz de evidências

| Tema | Evidência pública | Situação para XP Trader 5.0.4.34 |
| --- | --- | --- |
| Identidade da plataforma | A Nelogica [classifica XP Trader como White Label](https://ajuda.nelogica.com.br/hc/pt-br/articles/360061369691-Como-realizar-o-download-do-Profit) e orienta o download pela área logada. | A classificação é confirmada. A versão exata, licença e módulos da instalação do usuário não foram inspecionados. |
| Dados de mercado | A [ProfitDLL](https://ajuda.nelogica.com.br/hc/pt-br/articles/11166353435035-Introdu%C3%A7%C3%A3o-ao-Produto-DLL-Real-Time) descreve cotações, livro, negócios e histórico tick a tick, com cobertura BM&F/Bovespa. O [guia de tempo real](https://ajuda.nelogica.com.br/hc/pt-br/articles/11168755650459-Fun%C3%A7%C3%B5es-Real-Time-DLL) detalha assinaturas e callbacks. | Não há confirmação de que a licença XP Trader do usuário inclua ProfitDLL, direitos de dados ou acesso externo. BTCUSDT, ETHUSDT, AAPL e MSFT não estão cobertos pelas fontes consultadas. |
| API externa | O [ecossistema ProfitDLL](https://ajuda.nelogica.com.br/hc/pt-br/articles/22396517026203-Ecossistema-ProfitDLL-e-primeiros-passos) descreve uma DLL Windows para aplicações externas, com modos distintos de inicialização de dados e roteamento. | É uma capacidade documentada **da ProfitDLL**, não um contrato de API confirmado para XP Trader 5.0.4.34. Nenhuma API própria da versão foi identificada nas fontes públicas consultadas. |
| SDK | A Nelogica informa que o [pacote ProfitDLL.zip e o manual](https://ajuda.nelogica.com.br/hc/pt-br/articles/51583791325211-Como-obter-acesso-%C3%A0-ProfitDLL) são acessados mediante contratação e login. | Nenhum SDK, cabeçalho, manual da licença ou DLL foi fornecido ao projeto. Não se conhecem ABI, versão, funções habilitadas e termos aplicáveis ao usuário. |
| Simulação | O [Replay de Mercado](https://ajuda.nelogica.com.br/hc/pt-br/articles/360043469772-Replay-de-Mercado) menciona versões White Label e pode exigir Módulo de Simulação. A Nelogica informa que [contas de simulação podem depender de liberação adicional](https://ajuda.nelogica.com.br/hc/pt-br/articles/50936749743515-Como-cadastrar-novas-contas-de-roteamento). | Replay e conta simulada da plataforma não comprovam que a ProfitDLL consiga rotear para a conta simulada específica do XP Trader. Essa vinculação precisa de confirmação expressa. |
| Execução e reconciliação | O [guia de roteamento ProfitDLL](https://ajuda.nelogica.com.br/hc/pt-br/articles/13312468554651-Como-rotear-ordens-com-a-ProfitDLL) descreve envio, consulta e cancelamento para B3, condicionados a inicialização, licença, conexão e conta habilitada. A aceitação síncrona não é preenchimento: a confirmação final vem por callbacks. | Nenhum roteamento XP está habilitado no laboratório. Não foi verificada conta simulada exposta à DLL, permissão de ordens ou mecanismo de reconciliação para a versão e licença do usuário. |
| Limitações | A introdução oficial da DLL cita cobertura BM&F/Bovespa; XP Trader é White Label e ProfitDLL é produto contratado separadamente. | Não presumir compatibilidade com Profit Pro/Ultra, nem cobertura de criptoativos ou ações dos EUA. Nenhuma ordem será preparada ou enviada via XP neste escopo. |

**Leitura correta:** a existência de recursos no Profit ou na ProfitDLL não demonstra que estejam presentes na licença XP Trader 5.0.4.34. A busca pública não encontrou uma matriz oficial da versão exata com ProfitDLL; isso indica falta de evidência disponível aqui, não inexistência do recurso.

## Confirmações necessárias antes de desenhar um adaptador

Solicitar à Nelogica/XP, sem enviar senhas ou dados de conta ao projeto:

1. Identificador comercial e módulos da licença **XP Trader 5.0.4.34**; confirmação por escrito de API/SDK externo disponível para essa licença.
2. Se a ProfitDLL exige licença adicional, qual edição/versão, pacote oficial, manual, cabeçalhos, arquitetura, termos de uso e direitos de redistribuição de dados.
3. Mercados, classes, símbolos, horários, histórico, profundidade e permissões de dados acessíveis à instalação e à conta de simulação.
4. Se uma conta **exclusivamente simulada** da XP é visível e roteável pelo SDK; como distingui-la inequivocamente de conta real antes da inicialização, do envio e da reconciliação.
5. Quais callbacks/consultas confirmam aceitação, preenchimento parcial, cancelamento e falha; comportamento após desconexão, reinício e resposta desconhecida.
6. Requisitos de ambiente e testes autorizados: Windows/arquitetura, ativação, processo separado, limites de conexão e ambiente de homologação sem rota para conta real.

Se essas respostas forem obtidas, registrar o documento/versão e seu hash localmente, revisar as permissões e elaborar **novo plano** para um adaptador estritamente de simulação. A presente investigação não autoriza carregar a DLL nem testar login/ordem.

## Estado do laboratório em 17/11/2026

- Não há SDK, DLL, credenciais XP ou adaptador XP no repositório.
- `app.py` apresenta XP Trader 5.0.4.34 como desconectado. Não há função de envio XP.
- O feed cripto Binance e os históricos de ações dos EUA usam fontes próprias; nenhum deles é apresentado como dado XP.
- A Binance Spot Testnet da Entrega 11 é um adaptador virtual separado e não serve como prova de integração XP.
