"""Deterministic local hypotheses from completed, traceable paper operations.

Eligibility is a project parameter, not a statistical claim. No rule is promoted here.
"""

import hashlib
import json
import math
from collections import Counter

from database import store

ANALYZER_VERSION = "paper_learning_v1"
MIN_CLOSED_TRADES = 30
MIN_UTC_DAYS = 2
EDITABLE_RULE_FIELDS = {"pattern", "entry", "stop", "target", "management", "filters"}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _verified_rows():
    """Discard incomplete or inconsistent legacy rows; never infer missing evidence."""
    valid = []
    for row in store.list_paper_learning_source_rows():
        details = json.loads(row["details_json"])
        report = json.loads(row["report_json"])
        plan = report.get("execution") or {}
        if (row["risk_verdict"] != "autorizado" or row["run_status"] != "posicao_aberta"
                or row["pipeline_run_id"] != row["operation_pipeline_run_id"]
                or row["conduction_stage_id"] is None
                or details.get("kind") != "paper_simulation"
                or not details.get("signal_bar_utc") or not details.get("exit_time")
                or not details.get("conduction") or not plan.get("barra_de_entrada_utc")
                or plan.get("entrada") != row["entry_price"]
                or plan.get("side") != row["side"]
                or row["realized_r"] is None or not math.isfinite(row["realized_r"])
                or details.get("quote_currency") != "USDT"
                or details.get("entry_price") != row["entry_price"]
                or details.get("exit_price") != row["exit_price"]
                or details.get("fees") != row["fees"]
                or details.get("realized_r") != row["realized_r"]
                or details.get("signal_bar_utc") != row["signal_bar_utc"]
                or details.get("net_pnl") is None
                or not math.isclose(details["net_pnl"],
                    (row["exit_price"] - row["entry_price"]) * row["quantity"] *
                    (1 if row["side"] == "buy" else -1) - row["fees"],
                    rel_tol=1e-9, abs_tol=1e-8)):
            continue
        valid.append(row)
    return valid


def cohort_status(strategy_id, symbol, timeframe):
    rows = [row for row in _verified_rows()
            if (row["strategy_id"], row["symbol"], row["timeframe"])
            == (strategy_id, symbol, timeframe)]
    days = sorted({row["signal_bar_utc"][:10] for row in rows})
    return {"strategy_id": strategy_id, "symbol": symbol, "timeframe": timeframe,
            "closed_count": len(rows), "utc_days": len(days), "days": days,
            "eligible": len(rows) >= MIN_CLOSED_TRADES and len(days) >= MIN_UTC_DAYS,
            "minimum_closed": MIN_CLOSED_TRADES, "minimum_days": MIN_UTC_DAYS}


def _evidence_row(row):
    details = json.loads(row["details_json"])
    report = json.loads(row["report_json"])
    market = report.get("market") or {}
    return {
        "operation_id": row["operation_id"], "pipeline_run_id": row["pipeline_run_id"],
        "strategy_id": row["strategy_id"], "symbol": row["symbol"],
        "timeframe": row["timeframe"], "setup_name": row["setup_name"],
        "signal_bar_utc": row["signal_bar_utc"], "exit_time": details["exit_time"],
        "side": row["side"], "quantity": row["quantity"],
        "entry_price": row["entry_price"], "exit_price": row["exit_price"],
        "fees": row["fees"], "exit_reason": row["exit_reason"] or "não informado",
        "realized_r": row["realized_r"], "closed_at": row["closed_at"],
        "conduction": details["conduction"],
        "market_context": {key: market[key] for key in
                           ("tendencia", "atr20", "volume_vs_media_20", "regime",
                            "provedor", "feed_status", "idade_da_barra_s") if key in market},
    }


def analyze_cohort(strategy_id, symbol, timeframe):
    """Persist one proposed hypothesis for a sufficient, unchanged evidence snapshot."""
    status = cohort_status(strategy_id, symbol, timeframe)
    if not status["eligible"]:
        return {"state": "insufficient", **status}
    rows = [row for row in _verified_rows()
            if (row["strategy_id"], row["symbol"], row["timeframe"])
            == (strategy_id, symbol, timeframe)]
    evidence_rows = []
    reasons, hours = Counter(), Counter()
    positive = 0
    trailing_count = 0
    context_count = 0
    for row in rows:
        reason = row["exit_reason"] or "não informado"
        reasons[reason] += 1
        hours[row["signal_bar_utc"][11:13]] += 1
        positive += row["realized_r"] > 0
        evidence_row = _evidence_row(row)
        evidence_rows.append(evidence_row)
        trailing_count += (evidence_row["conduction"].get("trailing_updates") or 0) > 0
        context_count += bool(evidence_row["market_context"])
    digest = hashlib.sha256(_canonical(evidence_rows).encode("utf-8")).hexdigest()
    total = len(rows)
    most_common_reason, reason_count = reasons.most_common(1)[0]
    most_common_hour, hour_count = hours.most_common(1)[0]
    observation = (f"Coorte {symbol} {timeframe}: {total} operações paper encerradas em "
                   f"{status['utc_days']} dias UTC; {positive} com R líquido positivo e "
                   f"{total-positive} não positivas. Saída mais frequente: {most_common_reason} "
                   f"({reason_count}/{total}). Hora UTC de sinal mais frequente: "
                   f"{most_common_hour}:00 ({hour_count}/{total}). Condução com trailing "
                   f"registrado: {trailing_count}/{total}; contexto de mercado disponível: "
                   f"{context_count}/{total}.")
    hypothesis = ("Investigar em dados paper futuros e janelas independentes se a distribuição "
                  "por motivo de saída, horário e condução se repete; nenhuma alteração de regra "
                  "é indicada automaticamente por esta observação.")
    limitations = [
        "Limiar de 30 operações e dois dias UTC é parâmetro de projeto, não prova de robustez.",
        "Associações por horário, saída ou condução não demonstram causalidade.",
        "Contexto de mercado ausente em algumas trilhas não foi reconstruído.",
        "Candles do feed e fechamento sob demanda; atrasos e lacunas podem afetar o registro.",
        "Amostra paper não substitui validação histórica nem autoriza operação real.",
    ]
    evidence = {"kind": "paper_simulation", "cohort": status, "operation_ids":
                [row["operation_id"] for row in rows], "rows": evidence_rows,
                "summary": {"positive_r_count": positive, "non_positive_r_count": total-positive,
                            "trailing_count": trailing_count,
                            "market_context_available_count": context_count,
                            "exit_reasons": dict(sorted(reasons.items())),
                            "signal_hours_utc": dict(sorted(hours.items()))}}
    proposal_id = store.save_paper_learning_proposal(
        strategy_id, symbol, timeframe, ANALYZER_VERSION, digest, evidence,
        observation, hypothesis, limitations)
    return {"state": "proposed", "proposal_id": proposal_id,
            "evidence_sha256": digest, **status}


def create_draft(proposal_id, edited_rules):
    """Use human-edited rule fields to create a non-executable draft version."""
    proposal = store.get_paper_learning_proposal(proposal_id)
    if not proposal or proposal["status"] != "approved":
        raise ValueError("A proposta precisa de aprovação humana antes do rascunho.")
    parent = store.get_strategy(proposal["strategy_id"])
    if not parent or parent["status"] != "approved":
        raise ValueError("A estratégia de origem precisa continuar aprovada.")
    evidence = json.loads(proposal["evidence_json"])
    stored_rows = evidence.get("rows") or []
    if hashlib.sha256(_canonical(stored_rows).encode("utf-8")).hexdigest() != proposal["evidence_sha256"]:
        raise ValueError("Digest da evidência da proposta não confere.")
    current = {row["operation_id"]: _evidence_row(row) for row in _verified_rows()}
    if any(current.get(item["operation_id"]) != item for item in stored_rows):
        raise ValueError("Evidência paper mudou ou perdeu integridade; rascunho recusado.")
    original = json.loads(parent["rules_json"])
    if original.get("engine") != "setup_pattern_v1":
        raise ValueError("Rascunho paper requer setup versionado aprovado.")
    if not isinstance(edited_rules, dict):
        raise ValueError("As regras editadas precisam ser um objeto JSON.")
    changed = {key for key in set(original) | set(edited_rules)
               if original.get(key) != edited_rules.get(key)}
    if not changed or not changed <= EDITABLE_RULE_FIELDS or set(original) != set(edited_rules):
        raise ValueError("Altere apenas parâmetros operacionais permitidos; preserve identidade e fontes.")
    draft_rules = dict(edited_rules)
    draft_rules["approval"] = "paper_learning_draft_pending_review"
    draft_rules["paper_learning"] = {"proposal_id": proposal_id,
                                      "evidence_sha256": proposal["evidence_sha256"],
                                      "parent_strategy_id": parent["id"]}
    return store.create_paper_learning_draft(proposal_id, parent["id"], draft_rules)
