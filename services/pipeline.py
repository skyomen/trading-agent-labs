"""Agent Orchestration pipeline (Entrega 7 / Fase 2).

`run_pipeline` evaluates ONE approved strategy over the live feed
(`market_bars`, DEC-2026-11-16 item 7) and writes the full 7-stage audit
trail — `Market → Knowledge → Backtest Evidence → Fundamental → Decision →
Risk → Execution` — in one shot (DEC item 1: automatic trigger, no
per-stage click). Decision and Knowledge stay services, not new agents
(DEC item 2): Decision is reported under the existing "Trading Lab" system
label, Knowledge under "Research Agent".

Idempotency is by signal bar: the same `(strategy, symbol, timeframe,
signal_bar_utc)` never produces a second trail (DEC item 12). `database.
store.save_pipeline_run` already enforces this with
`ON CONFLICT ... DO NOTHING`; this module detects whether its own call was
the one that actually inserted (by comparing against the table's maximum id
before calling) so it never writes a second set of stages for a bar already
recorded.
"""

import json
from datetime import datetime, timezone

from database import store
from services import market_data
from services.decision import build_decision
from services.execution import build_execution_plan
from services.risk import evaluate_risk
from services.setup_backtest import (WARMUP_BARS, aggregate_minutes,
                                     verify_approved_rules, verify_source_documents)
from services.setup_signals import _mean, _sma, signal_at

PIPELINE_VERSION = "agent_pipeline_v1"
# Parâmetro de projeto (DEC-2026-11-16, item 13), não lido de manifesto algum.
TICK_SIZE = 0.01

STAGES = (("market", "Market Analyst"), ("knowledge", "Research Agent"),
          ("backtest_evidence", "Strategy & Backtest"), ("fundamental", "Fundamental Analyst"),
          ("decision", "Trading Lab"), ("risk", "Risk Manager"), ("execution", "Execution Agent"))

_STAGE_LIMITATIONS = {
    "market": ["feed ao vivo sem hash canônico; sem checagem de integridade adicional "
              "sobre lacuna/atraso (DEC-2026-11-16, item 7)."],
    "knowledge": [],
    "backtest_evidence": ["amostra de validação rotulada insuficiente/limítrofe não bloqueia "
                         "o candidato (DEC item 6)."],
    "fundamental": ["nenhuma fonte de notícias/eventos integrada ao projeto."],
    "decision": [],
    "risk": ["mercado_fora_das_regras permanece não aplicável até filters.session_hours "
            "ganhar fonte própria (DEC item 4)."],
    "execution": ["fechamento (stop/alvo/P&L) é escopo de entrega futura (DEC item 8)."],
}


def _atr20(bars, index):
    window = bars[index - 20:index + 1]
    if len(window) < 21:
        return None
    true_ranges = []
    for i in range(1, len(window)):
        bar, prev = window[i], window[i - 1]
        true_ranges.append(max(bar["high"] - bar["low"], abs(bar["high"] - prev["close"]),
                               abs(bar["low"] - prev["close"])))
    return _mean(true_ranges)


def _market_stage(symbol, timeframe, provider, aggregated, index, rules, coverage, feed_row):
    bar = aggregated[index]
    ma = rules["pattern"]["trend_ma"]
    slope_bars = rules["pattern"]["trend_slope_bars"]
    slope = _sma(aggregated, index, ma) - _sma(aggregated, index - slope_bars, ma)
    media = _sma(aggregated, index, ma)
    window20 = aggregated[index - 19:index + 1]
    avg_volume_20 = _mean([b["volume"] for b in window20])
    now = datetime.now(timezone.utc)
    bar_time = datetime.fromisoformat(bar["timestamp"].replace("Z", "+00:00"))
    return {
        "ativo": symbol, "timeframe": timeframe,
        "tendencia": {"inclinacao": slope, "media_movel_periodo": ma,
                     "periodo_inclinacao_barras": slope_bars},
        "atr20": _atr20(aggregated, index),
        "volume_vs_media_20": (bar["volume"] / avg_volume_20) if avg_volume_20 else None,
        "swing_20_barras": {"suporte": min(b["low"] for b in window20),
                            "resistencia": max(b["high"] for b in window20)},
        "momentum": {"fechamento": bar["close"], "media": media, "distancia": bar["close"] - media},
        "regime": "nao_definido_pelo_metodo",
        "eventos_proximos": "nao_definido_pelo_metodo",
        "fonte": "feed ao vivo", "provedor": provider,
        "simbolo": symbol, "timeframe_avaliado": timeframe,
        "barra_do_sinal_utc": bar["timestamp"],
        "feed_status": (feed_row or {}).get("status", "desconhecido"),
        "idade_da_barra_s": (now - bar_time).total_seconds(),
        "verificacao_de_integridade": ("não aplicável — feed ao vivo sem hash canônico "
                                       "(DEC-2026-11-16, item 7)"),
        "tick_size": {"valor": TICK_SIZE, "origem": "parâmetro declarado do projeto"},
        "cobertura_agregacao": coverage,
    }


def _knowledge_stage(rules):
    approved_items = store.list_knowledge_items(status="approved")
    return {
        "itens_aprovados": [{"id": item["id"], "kind": item["kind"], "title": item["title"]}
                            for item in approved_items],
        "itens_aprovados_count": len(approved_items),
        "fonte_pdf_regras": rules["source"],
        "aprovacao_humana_referencia": "DEC-2026-11-13-primeiros-quatro-setups.md",
    }


def _backtest_evidence_stage(strategy_id, symbol, timeframe):
    backtest = next((row for row in store.list_backtests()
                     if row["strategy_id"] == strategy_id and row["symbol"] == symbol
                     and row["timeframe"] == timeframe), None)
    validation = next((row for row in store.list_validation_runs(limit=100000)
                       if row["strategy_id"] == strategy_id and row["symbol"] == symbol
                       and row["timeframe"] == timeframe), None)
    if backtest is None and validation is None:
        return {"status": "sem_fonte", "promotes_strategy": False}
    payload = {"status": "ok", "promotes_strategy": False}
    if backtest is not None:
        metrics = json.loads(backtest["metrics_json"])
        payload["backtest"] = {"id": backtest["id"], "signal_count": metrics.get("signal_count"),
                               "trade_count": metrics.get("trade_count"),
                               "created_at": backtest["created_at"]}
    if validation is not None:
        report = json.loads(validation["report_json"])
        payload["validation"] = {"id": validation["id"], "sample_adequacy": validation["sample_adequacy"],
                                 "verdict": report.get("verdict"),
                                 "fragility_flags": report.get("fragility_flags", []),
                                 "created_at": validation["created_at"]}
    return payload


def _execution_not_run_motive(candidate_signal, risk_result):
    if candidate_signal is None:
        return "no_trade: sem candidato de entrada (sem sinal ou entrada não acionada)."
    if risk_result and risk_result["verdict"] == "negado":
        return "risco negado: " + ", ".join(risk_result["denial_reasons"])
    return "não avaliado."


def run_pipeline(strategy, symbol, timeframe):
    """Evaluate one approved strategy over the live feed and persist the full trail.

    Returns `{"estado": "sem_feed"}` / `{"estado": "historico_insuficiente", ...}` /
    `{"estado": "sem_barra_nova"}` without writing anything in those three
    cases; otherwise `{"estado": "ok", "run_id": ..., "status": ...}`.
    """
    provider = market_data.PROVIDER
    bars = store.get_market_bars(provider, symbol, "1m", limit=600)
    if not bars:
        return {"estado": "sem_feed"}

    minutes = int(timeframe[:-1])
    aggregated, coverage = aggregate_minutes(bars, minutes)
    if len(aggregated) < WARMUP_BARS + 1:
        return {"estado": "historico_insuficiente", "faltam": WARMUP_BARS + 1 - len(aggregated)}

    # Candidato nunca chega a existir se a estratégia ou os PDFs de origem
    # não estiverem corretos — propaga o erro (DEC: o chamador decide log x propagação).
    rules = verify_approved_rules(strategy, timeframe)
    verify_source_documents(rules)

    index = len(aggregated) - 2
    signal_bar = aggregated[index]
    trigger_bar = aggregated[index + 1]
    signal_bar_utc = signal_bar["timestamp"]

    raw_signal = signal_at(aggregated, index, rules, TICK_SIZE)

    side = rules["side"]
    direction = 1 if side == "buy" else -1

    candidate_signal = None
    entrada_acionada = False
    if raw_signal is not None:
        triggered = (trigger_bar["high"] >= raw_signal["entry"] if direction == 1
                    else trigger_bar["low"] <= raw_signal["entry"])
        if triggered:
            entrada_acionada = True
            entry_price = (max(trigger_bar["open"], raw_signal["entry"]) if direction == 1
                          else min(trigger_bar["open"], raw_signal["entry"]))
            candidate_signal = {**raw_signal, "entry_price": entry_price}

    feed_row = next((row for row in store.list_market_feeds()
                     if row["provider"] == provider and row["symbol"] == symbol
                     and row["timeframe"] == "1m"), None)

    market = _market_stage(symbol, timeframe, provider, aggregated, index, rules, coverage, feed_row)
    knowledge = _knowledge_stage(rules)
    backtest_evidence = _backtest_evidence_stage(strategy["id"], symbol, timeframe)
    fundamental = {"status": "sem_fonte",
                   "motivo": "nenhuma fonte de notícias/eventos integrada ao projeto"}

    decision = build_decision(market, knowledge, backtest_evidence, fundamental,
                              candidate_signal, rules)

    risk_result = evaluate_risk(strategy, rules, candidate_signal, mode="paper") \
        if candidate_signal is not None else None

    execution_plan = build_execution_plan(decision, risk_result, candidate_signal, rules) \
        if risk_result is not None and risk_result["verdict"] == "autorizado" else None

    if raw_signal is None:
        status = "sem_oportunidade"
    elif not entrada_acionada:
        status = "entrada_nao_acionada"
    elif decision["decisao"] == "no_trade" or risk_result["verdict"] == "negado":
        status = "avaliado"
    else:
        status = "aguardando_quantidade"

    now_iso = datetime.now(timezone.utc).isoformat()
    pending_since = now_iso if status == "aguardando_quantidade" else None
    risk_date_utc = signal_bar_utc[:10] if candidate_signal is not None else None
    risk_decided_at = now_iso if risk_result is not None else None
    risk_verdict = risk_result["verdict"] if risk_result is not None else "nao_avaliado"
    denial_reasons = risk_result["denial_reasons"] if risk_result is not None else []
    risk_committed_r = risk_result["risk_committed_r"] if risk_result is not None else 0.0

    if risk_result is not None:
        risk_payload, risk_stage_status = risk_result, (
            "ok" if risk_result["verdict"] == "autorizado" else "bloqueado")
    else:
        risk_payload = {"status": "nao_executado",
                        "motivo": _execution_not_run_motive(candidate_signal, risk_result)}
        risk_stage_status = "nao_executado"

    if execution_plan is not None:
        execution_payload, execution_stage_status = execution_plan, "ok"
    else:
        execution_payload = {"status": "nao_executado",
                             "motivo": _execution_not_run_motive(candidate_signal, risk_result)}
        execution_stage_status = "nao_executado"

    report = {"market": market, "knowledge": knowledge, "backtest_evidence": backtest_evidence,
              "fundamental": fundamental, "decision": decision, "risk": risk_payload,
              "execution": execution_payload}

    existing = store.list_pipeline_runs(limit=1)
    max_id_before = existing[0]["id"] if existing else 0

    run_id = store.save_pipeline_run(
        PIPELINE_VERSION, strategy["id"], rules["setup_id"], rules["setup_name"], symbol,
        timeframe, signal_bar_utc, decision["decisao"], risk_verdict=risk_verdict,
        risk_date_utc=risk_date_utc, risk_decided_at=risk_decided_at,
        denial_reasons=denial_reasons, status=status, risk_committed_r=risk_committed_r,
        report=report, pending_since=pending_since)

    if run_id <= max_id_before:
        # ON CONFLICT DO NOTHING fired: this bar already had a trail recorded.
        return {"estado": "sem_barra_nova"}

    stage_status = {"market": "ok", "knowledge": "ok",
                    "backtest_evidence": "ok" if backtest_evidence["status"] == "ok" else "sem_fonte",
                    "fundamental": "sem_fonte", "decision": "ok",
                    "risk": risk_stage_status, "execution": execution_stage_status}
    stage_payload = {"market": market, "knowledge": knowledge,
                     "backtest_evidence": backtest_evidence, "fundamental": fundamental,
                     "decision": decision, "risk": risk_payload, "execution": execution_payload}
    stage_summary = {
        "market": f"{symbol} {timeframe}: barra {signal_bar_utc}; tendência "
                 f"{market['tendencia']['inclinacao']}; ATR20={market['atr20']}.",
        "knowledge": f"{knowledge['itens_aprovados_count']} item(ns) aprovado(s); "
                    f"{len(rules['source'])} PDF(s) de origem.",
        "backtest_evidence": f"status={backtest_evidence['status']}.",
        "fundamental": "sem fonte de notícias/eventos integrada.",
        "decision": f"decisão={decision['decisao']}.",
        "risk": f"veredito={risk_payload.get('verdict', risk_payload.get('status'))}.",
        "execution": f"status={execution_payload.get('status')}.",
    }

    for stage_index, (stage_key, agent) in enumerate(STAGES, start=1):
        store.add_pipeline_stage(
            run_id, stage_index, stage_key, agent, stage_status[stage_key],
            summary=stage_summary[stage_key],
            input_json={"symbol": symbol, "timeframe": timeframe,
                       "setup_id": rules["setup_id"], "signal_bar_utc": signal_bar_utc},
            output_json=stage_payload[stage_key],
            limitations_json=_STAGE_LIMITATIONS[stage_key],
        )
        store.add_event(agent, "INFO", stage_summary[stage_key])

    return {"estado": "ok", "run_id": run_id, "status": status}
