"""Run/demonstrate the Entrega 7 agent-orchestration pipeline (Fase 4).

Mirrors `scripts.run_delivery5`/`run_delivery6`'s structure and print style
(same CLI shape, same way of opening the database, same "evaluate every
approved combination" loop), but Entrega 7 has a human gate in the middle
(DEC-2026-11-16 item 8), so this script has two modes:

- **Modo avaliação** (default, no flags): calls `services.pipeline.run_pipeline`
  for every approved strategy × eligible symbol (BTCUSDT/ETHUSDT) × the
  setup's own timeframes (`rules_json["timeframes"]`), exactly like `app.py`'s
  `_run_pipeline_for_all_approved`. Prints, per combination, the state
  (`sem_feed`/`historico_insuficiente`/`sem_barra_nova`/`sem_oportunidade`/
  `entrada_nao_acionada`/`aguardando_quantidade`/other), the decision, the
  risk verdict and any denial reasons. `sem_feed`/`historico_insuficiente`
  are the expected state when `database/trading.db` has no live feed running
  right now (`services/market_data.py`'s collector) — this is NOT a failure
  and the script still exits 0.
- **Modo confirmação**: `--abrir <run_id> --quantidade <X>` calls
  `services.execution.confirm_open`; `--descartar <run_id>` calls
  `services.execution.discard`.

Idempotent: `run_pipeline` never duplicates a trail for a bar already
recorded (`sem_barra_nova`), so running the evaluation mode twice in a row
is safe.
"""

import argparse
import json

from database import store
from services import execution, pipeline
from services.market_data import SYMBOLS


def _approved_strategies():
    return [row for row in store.list_strategies()
            if row["status"] == "approved"
            and json.loads(row["rules_json"]).get("engine") == "setup_pattern_v1"
            and json.loads(row["rules_json"]).get("approval") == "rules_human_approved"]


def run_evaluation():
    strategies = _approved_strategies()
    if not strategies:
        print("Nenhuma estratégia aprovada com regras human-approved encontrada; nada a avaliar.")
        return

    print(f"{len(strategies)} estratégia(s) aprovada(s). Avaliando cada uma × "
          f"{'/'.join(SYMBOLS)} × seus próprios timeframes (rules_json['timeframes'])...\n")

    any_trail = False
    for strategy in sorted(strategies, key=lambda row: row["id"]):
        rules = json.loads(strategy["rules_json"])
        name = rules.get("setup_name", strategy["name"])
        for symbol in SYMBOLS:
            for timeframe in rules.get("timeframes", []):
                label = f"{name} · {symbol} · {timeframe}"
                outcome = pipeline.run_pipeline(strategy, symbol, timeframe)
                estado = outcome.get("estado")

                if estado == "sem_feed":
                    print(f"{label}: sem_feed — o coletor Binance (services/market_data.py) não "
                          "tem nenhuma barra em market_bars no momento. Estado esperado quando o "
                          "coletor não está rodando; não é falha do pipeline.")
                    continue
                if estado == "historico_insuficiente":
                    print(f"{label}: historico_insuficiente — faltam "
                          f"{outcome.get('faltam')} barra(s) agregada(s) para completar o "
                          "aquecimento (WARMUP_BARS). Estado esperado com feed recém-iniciado.")
                    continue
                if estado == "sem_barra_nova":
                    print(f"{label}: sem_barra_nova — a barra mais recente já tinha gerado trilha "
                          "nesta mesma combinação (idempotência por barra, DEC item 12). Não é "
                          "duplicata nem erro.")
                    continue

                any_trail = True
                run_id = outcome["run_id"]
                status = outcome["status"]
                run = store.get_pipeline_run(run_id)
                report = json.loads(run["report_json"])
                decisao = (report.get("decision") or {}).get("decisao", "—")
                risk_payload = report.get("risk") or {}
                risk_verdict = risk_payload.get("verdict", risk_payload.get("status", "—"))
                denial_reasons = json.loads(run["denial_reasons_json"])
                line = (f"{label}: run #{run_id} · estado={estado} · status={status} · "
                        f"decisão={decisao} · risco={risk_verdict}")
                if denial_reasons:
                    line += f" · motivos de negação: {'; '.join(denial_reasons)}"
                print(line)

    pending = store.list_pending_pipeline_runs()
    print()
    if pending:
        print(f"{len(pending)} trilha(s) aguardando quantidade (status='aguardando_quantidade'):")
        for run in pending:
            print(f"  run #{run['id']} · {run['setup_name']} · {run['symbol']} · "
                  f"{run['timeframe']} · barra do sinal {run['signal_bar_utc']} UTC")
        print("\nPara abrir a posição: python -m scripts.run_delivery7 --abrir <run_id> "
              "--quantidade <X>")
        print("Para descartar: python -m scripts.run_delivery7 --descartar <run_id>")
    else:
        print("Nenhuma trilha aguardando quantidade no momento.")

    if not any_trail:
        print("\nNenhuma combinação produziu uma trilha nova nesta rodada — todas retornaram "
              "sem_feed/historico_insuficiente/sem_barra_nova. Isto não é uma falha do script: é "
              "o estado esperado quando `database/trading.db` não tem o coletor Binance "
              "(services/market_data.py) rodando com barras suficientes no momento em que este "
              "script roda. Rode o coletor e execute este script novamente para ver uma trilha "
              "completa (Market -> Knowledge -> Backtest Evidence -> Fundamental -> Decision -> "
              "Risk -> Execution).")


def run_confirm(run_id, quantity):
    try:
        result = execution.confirm_open(run_id, quantity)
        print(f"Posição aberta: paper_operation #{result['paper_operation_id']} "
              f"(pipeline run #{result['run_id']}).")
    except ValueError as exc:
        print(f"Confirmação recusada: {exc}")


def run_discard(run_id):
    try:
        execution.discard(run_id)
        print(f"Run #{run_id}: candidato descartado pelo usuário.")
    except ValueError as exc:
        print(f"Descarte recusado: {exc}")


def main():
    parser = argparse.ArgumentParser(
        description="Entrega 7 — avalia/demonstra a trilha de orquestração de agentes "
                    "(pipeline Market->Knowledge->Backtest Evidence->Fundamental->Decision->Risk->Execution).")
    parser.add_argument("--abrir", type=int, metavar="RUN_ID",
                        help="Confirma a quantidade e abre a posição simulada desta run "
                             "(aguardando_quantidade).")
    parser.add_argument("--quantidade", type=float, metavar="X",
                        help="Quantidade do ativo; obrigatório junto com --abrir.")
    parser.add_argument("--descartar", type=int, metavar="RUN_ID",
                        help="Descarta o candidato pendente desta run.")
    args = parser.parse_args()

    store.initialize()

    if args.abrir is not None:
        if args.quantidade is None:
            raise SystemExit("--abrir exige --quantidade.")
        run_confirm(args.abrir, args.quantidade)
    elif args.descartar is not None:
        run_discard(args.descartar)
    else:
        run_evaluation()


if __name__ == "__main__":
    main()
