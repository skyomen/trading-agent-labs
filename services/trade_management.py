"""Trade Management service (Entrega 8 / Fase 2).

Reproduces, for an already-open simulated position, the exact same conduction logic the
backtest engine (`services/setup_backtest.py`) already uses — stop/target/trailing — instead
of a second, independently-written implementation. Runs strictly on demand, recomputing from
scratch every time (DEC-2026-11-16-escopo-entrega-8-trade-management.md, item 1): there is no
background process here, mirroring the rest of the project except the market-data collector.

The trailing rule is replicated bit-for-bit, hardcode by setup name included (DEC item 2):
`rules_json.management` is read here ONLY for audit (to expose, not to fix, the known
inconsistency between the declared field and the real behaviour) and is never passed to the
shared engine, which still decides trailing by `rules["setup_name"] in {"VBS", "VSS"}`.

The price and stop/target used to manage the position are the ones already FROZEN in the
pipeline run's `report_json["execution"]` (and the operation's own `entry_price`, which is
what the human actually confirmed) — never recomputed from `strategies.rules_json`, which
could have changed since the position was opened (same "frozen price" principle as Entrega 7).
"""

import json
from datetime import datetime, timedelta, timezone

from database import store
from services import market_data, setup_backtest

CONDUCTION_VERSION = "trade_management_v1"
# Same cost assumptions as the backtest (DEC item 7 of Entrega 8 — explicit user decision:
# use the backtest's assumptions, not zero cost).
FEE_BPS = 10.0
SLIPPAGE_BPS = 5.0
CONDUCTION_STAGE_INDEX = 8


def _parse_utc(value):
    """Parse a stored timestamp ("...Z", "...+00:00" or no suffix) into an aware UTC
    datetime, so entry-bar matching compares real instants, never raw strings."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def replay_operation(operation):
    """Reconduct ONE paper_operation. Never raises for a data condition — only for a
    programming error. Always returns a dict carrying an "estado" key; see the module's
    DEC/task description for the full state table (nao_aplicavel, sem_trilha, sem_feed,
    sem_barra_de_entrada, sem_barra_nova, em_curso, fechada, ja_fechada).
    """
    if operation["state"] != "open":
        return {"estado": "nao_aplicavel"}

    pipeline_run_id = operation["pipeline_run_id"]
    if pipeline_run_id is None:
        return {"estado": "sem_trilha"}
    run = store.get_pipeline_run(pipeline_run_id)
    if run is None:
        return {"estado": "sem_trilha"}

    report = json.loads(run["report_json"])
    plan = report.get("execution") or {}
    if plan.get("entrada") is None or plan.get("stop") is None or plan.get("alvo") is None:
        return {"estado": "sem_trilha"}

    # Regras passadas ao motor compartilhado: apenas o necessário para decidir a condução,
    # nunca a estratégia inteira (DEC: preço e regra de trailing já estão congelados na
    # trilha; reabrir strategies.rules_json mudaria o resultado de uma posição já aberta se
    # a regra tivesse mudado desde então).
    rules = {"setup_name": run["setup_name"], "side": plan["side"],
             "tested_timeframe": run["timeframe"]}

    # Auditoria apenas (DEC item 2) — nunca usado para decidir a condução.
    strategy = store.get_strategy(run["strategy_id"])
    management_declarado_nao_aplicado = None
    if strategy is not None:
        management_declarado_nao_aplicado = json.loads(strategy["rules_json"]).get("management")

    entry_price = operation["entry_price"]
    stop = plan["stop"]
    target = plan["alvo"]
    direction = 1 if plan["side"] == "buy" else -1
    minutes = int(run["timeframe"][:-1])

    entry_bar_utc = plan.get("barra_de_entrada_utc")
    if entry_bar_utc:
        entry_dt = _parse_utc(entry_bar_utc)
    else:
        # Fallback determinístico: o campo barra_de_entrada_utc ainda não existe nesta fase
        # da Entrega 8. A barra de entrada é sempre a barra seguinte à barra do sinal
        # (signal_bar_utc), um timeframe inteiro à frente — mesma relação sinal/entrada já
        # usada por services/pipeline.py (signal_bar vs trigger_bar).
        entry_dt = _parse_utc(run["signal_bar_utc"]) + timedelta(minutes=minutes)

    # since_timestamp SEM sufixo de fuso — ver database.store.get_market_bars_since.
    since_param = entry_dt.strftime("%Y-%m-%dT%H:%M:%S")
    raw = store.get_market_bars_since(market_data.PROVIDER, run["symbol"], "1m", since_param)
    if not raw:
        return {"estado": "sem_feed"}

    aggregated, coverage = setup_backtest.aggregate_minutes(raw, minutes)
    entry_index = next((i for i, bar in enumerate(aggregated)
                        if _parse_utc(bar["timestamp"]) == entry_dt), None)
    if entry_index is None:
        return {"estado": "sem_barra_de_entrada"}
    if entry_index == len(aggregated) - 1:
        return {"estado": "sem_barra_nova"}

    # Mesmas chaves exatas que simulate() cria para uma posição recém-aberta.
    position = {"entry_price": entry_price, "entry_time": aggregated[entry_index]["timestamp"],
                "signal_time": run["signal_bar_utc"], "initial_stop": stop, "stop": stop,
                "target": target, "favorable_closes": 0, "trailing_updates": 0}

    result = setup_backtest.replay_open_position(
        aggregated, position, rules, direction, minutes, FEE_BPS, SLIPPAGE_BPS,
        start_index=entry_index, check_entry_bar=True, close_on_end_of_data=False)

    if result["estado"] == "aberta":
        return {"estado": "em_curso", "stop_corrente": position["stop"],
                "trailing_updates": position["trailing_updates"],
                "barras_avaliadas": result["barras_avaliadas"]}

    trade = result["trade"]
    unidade_r = abs(entry_price - stop)
    quantity = operation["quantity"]
    entry_fee = entry_price * quantity * FEE_BPS / 10000
    exit_fee = trade["exit_price"] * quantity * FEE_BPS / 10000
    fees = entry_fee + exit_fee
    gross_pnl = direction * (trade["exit_price"] - entry_price) * quantity
    net_pnl = gross_pnl - fees
    realized_r = None if unidade_r <= 1e-9 else net_pnl / (unidade_r * quantity)

    motivo_do_motor = trade["exit_reason"]
    if motivo_do_motor == "stop" and trade["final_stop"] != trade["initial_stop"]:
        exit_reason_persistido = "trailing_stop"
    else:
        exit_reason_persistido = motivo_do_motor

    summary = (f"{run['symbol']} {run['timeframe']}: operação #{operation['id']} fechada por "
              f"{exit_reason_persistido} em {trade['exit_time']}; realized_r="
              f"{realized_r if realized_r is not None else 'indefinido'}.")
    limitations = ["Trailing decidido por nome de setup; rules_json.management é dado "
                   "declarado e não aplicado (DEC-2026-11-16 Entrega 8)."]
    stage = {
        "stage_index": CONDUCTION_STAGE_INDEX, "stage": "conduction",
        "agent": "Execution Agent", "status": "ok", "summary": summary,
        "input": {"operation_id": operation["id"], "entry_time": position["entry_time"],
                  "janela_desde": since_param, "barras_agregadas": len(aggregated),
                  "indice_entrada": entry_index, "cobertura_agregacao": coverage},
        "output": {**trade, "exit_reason_persistido": exit_reason_persistido,
                   "motivo_do_motor": motivo_do_motor, "realized_r": realized_r,
                   "management_declarado_nao_aplicado": management_declarado_nao_aplicado,
                   "entry_fee": entry_fee, "exit_fee": exit_fee, "net_pnl": net_pnl},
        "limitations": limitations,
    }
    closed = store.close_paper_operation(
        operation["id"], trade["exit_price"], exit_reason_persistido,
        datetime.now(timezone.utc).isoformat(), fees=fees, realized_r=realized_r,
        journal_details={"entry_time": position["entry_time"], "exit_time": trade["exit_time"],
                         "conduction": stage["output"], "fee_bps_per_side": FEE_BPS,
                         "slippage_bps_per_side": SLIPPAGE_BPS,
                         "entry_fee": entry_fee, "exit_fee": exit_fee,
                         "gross_pnl": gross_pnl, "net_pnl": net_pnl,
                         "quote_currency": "USDT" if run["symbol"] in {"BTCUSDT", "ETHUSDT"} else None,
                         "limitations": limitations},
        conduction_stage=stage)
    if not closed:
        return {"estado": "ja_fechada"}
    store.add_event("Execution Agent", "INFO", summary)

    return {"estado": "fechada", "exit_reason": exit_reason_persistido,
            "realized_r": realized_r, "trade": trade}


def replay_open_operations():
    """Replays every currently open paper_operation; returns the list of results, each
    carrying its own "operation_id" alongside whatever `replay_operation` returned."""
    resultados = []
    for operation in store.list_paper_operations(state="open"):
        resultados.append({**replay_operation(operation), "operation_id": operation["id"]})
    return resultados
