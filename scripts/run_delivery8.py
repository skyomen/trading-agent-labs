"""Run/demonstrate the Entrega 8 trade-management conduction (Fase 4).

Mirrors `scripts.run_delivery7`'s structure and print style (same CLI shape, same way of
opening the database), but Entrega 8's acceptance criterion
("a lógica de condução usada no backtest pode ser reproduzida no paper engine",
roadmap seção 50) is about engine parity, not a human gate, so this script has two modes:

- **Modo condução** (default, no flags): calls `services.trade_management.replay_open_operations()`
  against the REAL database (`database/trading.db`) and prints, per currently-open
  `paper_operation`, the state `replay_operation` returned (`em_curso`/`fechada`/`sem_feed`/
  `sem_barra_de_entrada`/`sem_barra_nova`/`sem_trilha`/`ja_fechada`/`nao_aplicavel` — see
  `services/trade_management.py`'s docstring for the full table). No open position is NOT a
  failure — it just means nobody has an open `paper_operation` right now (Entrega 7's human
  gate hasn't been exercised, or every open position already closed); the script prints that
  explicitly and exits 0.
- **Modo prova** (`--prova`): demonstrates the acceptance criterion in two layers, WITHOUT ever
  touching `database/trading.db`:
  1. Engine parity, no database at all: three synthetic 2m-candle scenarios (stop, target,
     trailing — adapted bit-for-bit from `tests/test_setup_backtest.py` and
     `tests/test_trade_management.py`) run through `setup_backtest.simulate()` (the backtest's
     own oracle) and then, from the same entry bar over the exact same bars, through
     `setup_backtest.replay_open_position()` (the function `trade_management.replay_operation`
     calls live). Prints both trades field-by-field and a verdict (`IDÊNTICO`/`DIVERGE`) per
     scenario; any divergence makes the script exit non-zero — this is a real check, not a
     decorative print.
  2. End-to-end with persistence, in a TEMPORARY sqlite file (`tempfile` + an explicit swap of
     `store.DB_PATH` inside `try`/`finally` that always restores the original path — never
     `database/trading.db`): seeds 1-minute `market_bars` that aggregate into the trailing
     scenario's own candles, an approved strategy, a `pipeline_run` and an open
     `paper_operation`, then calls `trade_management.replay_open_operations()` twice to show
     the position closes with `exit_reason`/`realized_r`/the stage-8 "conduction" row on the
     first call, and that nothing changes on the second (idempotency — the operation is no
     longer `state='open'`, so `replay_open_operations()` simply does not revisit it).
"""

import argparse
import math
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from database import store
from services import market_data, setup_backtest, trade_management

# --------------------------------------------------------------------------------------------
# Modo condução — contra o banco real.
# --------------------------------------------------------------------------------------------


def _print_conduction_result(result):
    operation_id = result["operation_id"]
    estado = result["estado"]
    if estado == "em_curso":
        print(f"operação #{operation_id}: em_curso — stop corrente={result['stop_corrente']}, "
              f"trailing_updates={result['trailing_updates']}, "
              f"barras_avaliadas={result['barras_avaliadas']}.")
    elif estado == "fechada":
        print(f"operação #{operation_id}: fechada — motivo={result['exit_reason']}, "
              f"realized_r={result['realized_r']}.")
    elif estado == "sem_feed":
        print(f"operação #{operation_id}: sem_feed — o coletor Binance (services/market_data.py) "
              "não tem nenhuma barra nova desde a entrada desta posição. Estado esperado quando "
              "o coletor não está rodando; não é falha.")
    elif estado == "sem_barra_de_entrada":
        print(f"operação #{operation_id}: sem_barra_de_entrada — a barra de entrada não foi "
              "encontrada no feed agregado (pode ter sido descartada por lacuna).")
    elif estado == "sem_barra_nova":
        print(f"operação #{operation_id}: sem_barra_nova — só a barra de entrada está disponível "
              "no feed; aguardando a próxima barra fechada.")
    elif estado == "sem_trilha":
        print(f"operação #{operation_id}: sem_trilha — operação sem pipeline_run_id, ou a trilha "
              "não foi encontrada/não tem plano de execução completo.")
    elif estado == "ja_fechada":
        print(f"operação #{operation_id}: ja_fechada — já foi fechada por outra chamada entre a "
              "leitura e a tentativa de fechamento.")
    elif estado == "nao_aplicavel":
        print(f"operação #{operation_id}: nao_aplicavel — não está mais em state='open'.")
    else:
        print(f"operação #{operation_id}: {estado}")


def run_conduction():
    results = trade_management.replay_open_operations()
    if not results:
        print("Nenhuma posição simulada aberta no momento.")
        return
    print(f"{len(results)} posição(ões) simulada(s) aberta(s). Reconduzindo cada uma do zero "
          "(services/trade_management.replay_open_operations)...\n")
    for result in results:
        _print_conduction_result(result)


# --------------------------------------------------------------------------------------------
# Modo prova — camada 1: paridade de motor, sem banco.
# --------------------------------------------------------------------------------------------

# Candle fixtures in the exact style of tests/test_setup_backtest.py::bars() /
# tests/test_trade_management.py::bars() — synthetic only, never market observations.
_ORIGIN = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _bars(count=36, start=None):
    start = start or _ORIGIN
    return [{"timestamp": (start + timedelta(minutes=2 * i)).isoformat(),
             "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1}
            for i in range(count)]


def _make_signal(entry, stop, target):
    """A signal_at replacement that fires once, at index 29 — same convention as
    tests/test_setup_backtest.py::signal(), so WARMUP_BARS (29) is satisfied the same way."""
    def _signal(data, index, rule, tick):
        if index != 29:
            return None
        return {"entry": entry, "stop": stop, "target": target,
                "signal_bar": data[index]["timestamp"]}
    return _signal


def _expand_candles_to_raw(candles, minutes):
    """Expand 2m-looking `candles` into the raw 1-minute bars that re-aggregate (via
    setup_backtest.aggregate_minutes) into exactly the same candles — adapted from
    tests/test_trade_management.py::expand_candles_to_raw()."""
    raw = []
    for candle in candles:
        start = datetime.fromisoformat(candle["timestamp"])
        for minute in range(minutes):
            stamp = (start + timedelta(minutes=minute)).isoformat()
            raw.append({"timestamp": stamp, "open": candle["open"], "high": candle["high"],
                       "low": candle["low"], "close": candle["close"], "volume": 1.0})
    return raw


# Three scenarios — stop, target, trailing — adapted bit-for-bit from
# tests/test_trade_management.py::ReplayOperationClosedTests (the trailing one from
# tests/test_setup_backtest.py::test_trailing_moves_only_after_two_favorable_closes).
_SCENARIOS = [
    {"name": "fechamento por stop", "setup_name": "BOP", "side": "buy",
     "entry": 101.5, "stop": 99.0, "target": 200.0,
     "overrides": {30: {"open": 100, "high": 102, "low": 99.5, "close": 101},
                   31: {"open": 101, "high": 101, "low": 97, "close": 98}}},
    {"name": "fechamento por alvo", "setup_name": "BOP", "side": "buy",
     "entry": 101.5, "stop": 90.0, "target": 103.0,
     "overrides": {30: {"open": 100, "high": 102, "low": 99.5, "close": 101},
                   31: {"open": 102, "high": 104, "low": 101, "close": 103.5}}},
    {"name": "fechamento por trailing stop (VBS)", "setup_name": "VBS", "side": "buy",
     "entry": 101.5, "stop": 99.0, "target": 110.0,
     "overrides": {30: {"open": 101, "high": 102, "low": 100, "close": 101.5},
                   31: {"open": 101.5, "high": 102.5, "low": 100.5, "close": 102},
                   32: {"open": 102, "high": 103, "low": 101, "close": 102.5},
                   33: {"open": 102.5, "high": 103, "low": 100.4, "close": 101}}},
]

_COMPARE_FIELDS = ["exit_time", "exit_reason", "exit_price", "final_stop", "trailing_updates",
                   "net_return_pct"]


def _values_equal(a, b):
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)
    return a == b


def run_engine_parity():
    print("=== Camada 1: paridade de motor — simulate() vs replay_open_position(), SEM banco ===\n")
    all_ok = True
    for scenario in _SCENARIOS:
        candles = _bars(36)
        for index, fields in scenario["overrides"].items():
            candles[index].update(fields)
        rules = {"side": scenario["side"], "setup_name": scenario["setup_name"],
                 "tested_timeframe": "2m"}
        direction = 1 if scenario["side"] == "buy" else -1

        with patch("services.setup_backtest.signal_at",
                  side_effect=_make_signal(scenario["entry"], scenario["stop"], scenario["target"])):
            report = setup_backtest.simulate(candles, rules, 0.01, trade_management.FEE_BPS,
                                             trade_management.SLIPPAGE_BPS)
        if report["trade_count"] != 1:
            print(f"[{scenario['name']}] cenário mal configurado: simulate() produziu "
                  f"{report['trade_count']} trade(s), esperava 1. Pulando.\n")
            all_ok = False
            continue
        trade_sim = report["trades"][0]

        entry_index = next(i for i, bar in enumerate(candles) if bar["timestamp"] == trade_sim["entry_time"])
        position = {"entry_price": trade_sim["entry_price"], "entry_time": trade_sim["entry_time"],
                    "signal_time": trade_sim["signal_time"], "initial_stop": trade_sim["initial_stop"],
                    "stop": trade_sim["initial_stop"], "target": trade_sim["target"],
                    "favorable_closes": 0, "trailing_updates": 0}
        replay_result = setup_backtest.replay_open_position(
            candles, position, rules, direction, 2, trade_management.FEE_BPS,
            trade_management.SLIPPAGE_BPS, start_index=entry_index, check_entry_bar=True,
            close_on_end_of_data=False)

        print(f"Cenário: {scenario['name']} ({scenario['setup_name']} {scenario['side']})")
        if replay_result["estado"] != "fechada":
            print(f"  DIVERGE: replay_open_position() não fechou a posição "
                  f"(estado={replay_result['estado']}) enquanto simulate() fechou por "
                  f"{trade_sim['exit_reason']}.\n")
            all_ok = False
            continue
        trade_replay = replay_result["trade"]

        print(f"  {'campo':<16}{'simulate()':<28}{'replay_open_position()':<28}")
        diffs = []
        for field in _COMPARE_FIELDS:
            a, b = trade_sim[field], trade_replay[field]
            same = _values_equal(a, b)
            if not same:
                diffs.append(field)
            marca = "" if same else "  <-- DIVERGE"
            print(f"  {field:<16}{str(a):<28}{str(b):<28}{marca}")
        if diffs:
            print(f"  Veredito: DIVERGE ({', '.join(diffs)})\n")
            all_ok = False
        else:
            print("  Veredito: IDÊNTICO\n")
    return all_ok


# --------------------------------------------------------------------------------------------
# Modo prova — camada 2: ponta a ponta com persistência, em banco TEMPORÁRIO.
# --------------------------------------------------------------------------------------------


def run_persistence_round_trip():
    print("=== Camada 2: ponta a ponta com persistência — banco TEMPORÁRIO, nunca "
          "database/trading.db ===\n")
    scenario = _SCENARIOS[2]  # trailing — mesma trilha usada no teste de trailing.
    candles = _bars(36)
    for index, fields in scenario["overrides"].items():
        candles[index].update(fields)

    tmp_dir = tempfile.TemporaryDirectory()
    original_db_path = store.DB_PATH
    ok = True
    try:
        store.DB_PATH = Path(tmp_dir.name) / "prova_entrega8.db"
        store.initialize()

        strategy_id = store.save_strategy(
            f"{scenario['setup_name']} · prova entrega 8",
            {"engine": "setup_pattern_v1", "setup_id": "SETUP_01", "setup_name": scenario["setup_name"],
             "side": scenario["side"], "timeframes": ["2m", "5m"], "approval": "rules_human_approved",
             "management": {"trailing_after_favorable_closes": 2,
                            "trailing_reference": "previous_bar_extreme"}},
            "prova_entrega8")
        store.approve_strategy(strategy_id)

        entry_bar_utc = candles[30]["timestamp"]
        signal_bar_utc = candles[29]["timestamp"]
        plan = {"status": "ok", "entrada": scenario["entry"], "side": scenario["side"],
                "stop": scenario["stop"], "alvo": scenario["target"],
                "barra_de_entrada_utc": entry_bar_utc}
        run_id = store.save_pipeline_run(
            "pipeline_v1", strategy_id, "SETUP_01", scenario["setup_name"], "BTCUSDT", "2m",
            signal_bar_utc, "trade_candidate", risk_verdict="autorizado",
            status="posicao_aberta", report={"execution": plan})
        operation_id = store.open_paper_operation(
            "BTCUSDT", scenario["side"], 1.0, scenario["entry"], "prova_entrega8",
            pipeline_run_id=run_id)

        raw = _expand_candles_to_raw(candles[30:], minutes=2)
        store.upsert_market_bars(market_data.PROVIDER, "BTCUSDT", "1m", raw)

        print(f"Semeado em banco temporário ({store.DB_PATH}): strategy #{strategy_id}, "
              f"pipeline_run #{run_id}, paper_operation #{operation_id} (state='open').\n")

        first_results = trade_management.replay_open_operations()
        print(f"1ª chamada a replay_open_operations(): {first_results}")

        operation_after_first = next(op for op in store.list_paper_operations() if op["id"] == operation_id)
        run_after_first = store.get_pipeline_run(run_id)
        stages_after_first = run_after_first["stages"]

        print(f"\npaper_operations #{operation_id} após a 1ª chamada: "
              f"state={operation_after_first['state']}, "
              f"exit_reason={operation_after_first['exit_reason']}, "
              f"exit_price={operation_after_first['exit_price']}, "
              f"closed_at={operation_after_first['closed_at']}.")
        print(f"pipeline_runs #{run_id}.realized_r = {run_after_first['realized_r']}")
        print(f"pipeline_stages do run #{run_id}: {len(stages_after_first)} estágio(s) — "
              f"stage_index={[s['stage_index'] for s in stages_after_first]}.")

        if operation_after_first["state"] != "closed":
            print("FALHA: a posição não fechou na primeira chamada.")
            ok = False
        if run_after_first["realized_r"] is None:
            print("FALHA: pipeline_runs.realized_r não foi preenchido.")
            ok = False
        if trade_management.CONDUCTION_STAGE_INDEX not in [s["stage_index"] for s in stages_after_first]:
            print("FALHA: o estágio 8 (conduction) não foi gravado em pipeline_stages.")
            ok = False

        second_results = trade_management.replay_open_operations()
        operation_after_second = next(op for op in store.list_paper_operations() if op["id"] == operation_id)
        run_after_second = store.get_pipeline_run(run_id)
        stages_after_second = run_after_second["stages"]

        print(f"\n2ª chamada a replay_open_operations(): {second_results} (lista vazia esperada — "
              "replay_open_operations() só itera paper_operations com state='open', e esta já "
              "está 'closed').")
        print(f"paper_operations #{operation_id} após a 2ª chamada: "
              f"state={operation_after_second['state']}, "
              f"exit_reason={operation_after_second['exit_reason']}, "
              f"exit_price={operation_after_second['exit_price']}.")
        print(f"pipeline_runs #{run_id}.realized_r (2ª chamada) = {run_after_second['realized_r']}")
        print(f"pipeline_stages do run #{run_id} após a 2ª chamada: {len(stages_after_second)} "
              "estágio(s).")

        idempotent = (operation_after_first == operation_after_second and
                     run_after_first["realized_r"] == run_after_second["realized_r"] and
                     len(stages_after_first) == len(stages_after_second))
        if idempotent:
            print("\nIdempotência confirmada: nada mudou na segunda chamada — mesma linha de "
                  "paper_operations, mesmo realized_r, nenhum segundo estágio.")
        else:
            print("\nFALHA: a segunda chamada mudou algo (quebra de idempotência).")
            ok = False
    finally:
        store.DB_PATH = original_db_path
        tmp_dir.cleanup()
    print()
    return ok


def run_prova():
    layer1_ok = run_engine_parity()
    layer2_ok = run_persistence_round_trip()
    overall = layer1_ok and layer2_ok
    print("=== Veredito final da prova ===")
    print("Camada 1 (paridade de motor, sem banco): " + ("OK" if layer1_ok else "FALHOU"))
    print("Camada 2 (persistência/idempotência, banco temporário): " +
          ("OK" if layer2_ok else "FALHOU"))
    print("Resultado geral: " + ("OK" if overall else "FALHOU"))
    return overall


def main():
    parser = argparse.ArgumentParser(
        description="Entrega 8 — demonstra a condução sob demanda de posições simuladas "
                    "(services/trade_management.py).")
    parser.add_argument("--prova", action="store_true",
                        help="Demonstra o critério de aceite: paridade de motor "
                             "(simulate() vs replay_open_position(), sem banco) e o fluxo "
                             "completo com persistência num banco TEMPORÁRIO — nunca em "
                             "database/trading.db.")
    args = parser.parse_args()

    if args.prova:
        ok = run_prova()
        raise SystemExit(0 if ok else 1)

    store.initialize()
    run_conduction()


if __name__ == "__main__":
    main()
