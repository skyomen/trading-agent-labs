"""Execution Agent service (Entrega 7 / Fase 2).

Execution never decides (roadmap §15): `build_execution_plan` refuses
(raises) anything the Risk Manager has not authorized — the plan is
paperwork for a decision already made elsewhere, never the decision itself.

`confirm_open` is the human gate from DEC-2026-11-16 item 8: the quantity is
always informed by the user, never presumed from capital. It re-validates
exposure right before opening (TOCTOU guard, item 9) and reads the entry
price frozen in the trail — never the live market — per item 10 (zero-cost
open, cost bookkeeping deferred to the close, which is out of this
entrega's scope).
"""

import json
import math
from datetime import datetime, timezone

from database import store
from services.risk import MAX_OPEN_POSITIONS

SIDE_LABELS = {"buy": "compra", "sell": "venda"}


def build_execution_plan(decision, risk_result, candidate_signal, rules):
    """Only ever called once Risk has authorized; raises otherwise (roadmap §15)."""
    if not risk_result or risk_result.get("verdict") != "autorizado":
        raise ValueError(
            "Plano de execução só pode ser montado quando o Risk Manager autoriza o candidato."
        )
    side = candidate_signal["side"]
    return {
        "status": "ok",
        "ativo": (decision or {}).get("ativo"),
        "side": side,
        "lado": SIDE_LABELS.get(side, side),
        "tipo_de_ordem": "stop de entrada válido somente na barra seguinte",
        "tamanho": "1R de risco; quantidade não definida — o projeto não presume capital",
        "entrada": candidate_signal["entry_price"],
        "stop": candidate_signal["stop"],
        "alvo": candidate_signal["target"],
        "barra_de_entrada_utc": candidate_signal.get("entry_bar_utc"),
        "invalidacao": ("o gatilho já foi acionado nesta barra; a invalidação por 'barra "
                       "seguinte não aciona o gatilho' não se aplica mais a este candidato"),
        "conducao": rules.get("management"),
        "saida": ("stop | alvo | fim de dados — condução sob demanda: recalculada do zero a "
                 "cada abertura da tela de Orquestração, nunca em processo contínuo; a "
                 "posição só fecha quando alguém abre essa tela, e somente enquanto o coletor "
                 "Binance estiver alimentando market_bars"),
        "aviso_preco": "o preço de entrada vem de uma barra já fechada, mesmo quando recente.",
        "custo": "custo zero na abertura; custos serão registrados no fechamento",
    }


def confirm_open(run_id, quantity):
    """Human gate: inform the quantity and really open the simulated position.

    Rereads the run, refuses anything not `aguardando_quantidade` (duplicate
    confirmation guard — roadmap R2.4), revalidates exposure excluding this
    very run (TOCTOU guard) and opens the position at the entry price frozen
    in the trail's `report_json["execution"]` — never recomputed from the
    current market.
    """
    run = store.get_pipeline_run(run_id)
    if not run or run["status"] != "aguardando_quantidade":
        raise ValueError("Esta trilha não está aguardando quantidade; confirmação recusada.")
    if store.get_broker_entry_for_run(run_id):
        raise ValueError("Esta trilha já reservou uma ordem Testnet.")
    if not math.isfinite(float(quantity)) or float(quantity) <= 0:
        raise ValueError("Quantidade deve ser um número positivo.")

    # TOCTOU guard: this very run currently counts as one reserved slot
    # (its status is still 'aguardando_quantidade'); exclude it to see what
    # else has been reserved since it was authorized.
    reserved_excluding_this = store.count_reserved_exposure() - 1
    if reserved_excluding_this >= MAX_OPEN_POSITIONS:
        store.update_pipeline_run_status(run_id, "recusado_na_confirmacao")
        raise ValueError(
            f"Exposição máxima de {MAX_OPEN_POSITIONS} posições já ocupada por outras "
            "operações desde a autorização; confirmação recusada."
        )

    report = json.loads(run["report_json"])
    execution_plan = report.get("execution") or {}
    entry_price = execution_plan.get("entrada")
    side = execution_plan.get("side")
    if entry_price is None or side is None:
        raise ValueError("Trilha sem plano de execução congelado; confirmação recusada.")

    source = f"pipeline #{run_id} · {run['setup_id']} · barra {run['signal_bar_utc']} UTC"
    kill_switch = store.get_kill_switch()
    if kill_switch["enabled"]:
        raise ValueError(f"Abertura de novas posições bloqueada: {kill_switch['reason']}")
    operation_id = store.open_paper_operation(
        run["symbol"], side, float(quantity), float(entry_price), source,
        pipeline_run_id=run_id, fees=0.0,
    )
    report["confirmacao"] = {
        "paper_operation_id": operation_id, "quantidade": float(quantity),
        "confirmado_em": datetime.now(timezone.utc).isoformat(),
        "custo": "custos serão registrados no fechamento",
    }
    store.update_pipeline_run_status(run_id, "posicao_aberta", report=report)
    return {"paper_operation_id": operation_id, "run_id": run_id}


def discard(run_id):
    """Human gate: discard a pending candidate instead of confirming it."""
    run = store.get_pipeline_run(run_id)
    if not run or run["status"] != "aguardando_quantidade":
        raise ValueError("Esta trilha não está aguardando quantidade; descarte recusado.")
    if store.get_broker_entry_for_run(run_id):
        raise ValueError("Esta trilha já reservou uma ordem Testnet.")
    store.update_pipeline_run_status(run_id, "descartado_pelo_usuario")
