"""Deterministic Decision service (Entrega 7 / Fase 2).

Per DEC-2026-11-16 item 2, Decision is a function/service, never a new agent:
it combines the Market, Knowledge, Backtest Evidence and Fundamental stages
into one decision dict. Reported under the system label "Trading Lab"
(already used for system-level events in `database/store.py`), not a row in
`agents`.

No confidence score, probability or any other numeric "certainty" field is
ever produced here. The decision is a label (`trade_candidate`|`no_trade`)
plus explicit, source-labelled evidence and contrary factors — never a
number that could be read as odds.
"""

SIDE_LABELS = {"buy": "compra", "sell": "venda"}


def build_decision(market, knowledge, backtest_evidence, fundamental, candidate_signal, rules):
    """Combine the four upstream stages into one decision dict.

    `candidate_signal` is the dict pipeline.py builds only once the setup's
    signal exists AND the next bar actually triggered the entry (it carries
    `entry_price`, `stop`, `target`, `side`, `signal_bar`, ...); `None`
    whenever there is no signal at all or the signal's entry never
    triggered. Per DEC item 6, a signal that triggers is always
    `trade_candidate` — insufficient validation sample never blocks it, it
    only ever appears in `fatores_contrarios`.
    """
    decisao = "trade_candidate" if candidate_signal is not None else "no_trade"

    fatores_contrarios = []
    validation = (backtest_evidence or {}).get("validation") or {}
    sample_adequacy = validation.get("sample_adequacy")
    if (backtest_evidence or {}).get("status") == "sem_fonte" or sample_adequacy != "adequada":
        fatores_contrarios.append(
            "amostra de validação insuficiente ou limítrofe para este par/intervalo "
            f"(adequação: {sample_adequacy or 'sem registro de validação'})."
        )
    if (fundamental or {}).get("status") == "sem_fonte":
        fatores_contrarios.append(
            "ausência de fonte fundamentalista: " + (fundamental or {}).get("motivo", "")
        )
    if (rules.get("filters") or {}).get("session_hours") == "pending_market_selection":
        fatores_contrarios.append(
            "filters.session_hours pendente de definição de mercado/fuso (não bloqueia nem libera)."
        )
    if (knowledge or {}).get("itens_aprovados_count", 0) == 0:
        fatores_contrarios.append("zero itens de conhecimento aprovados em knowledge_items.")

    if candidate_signal is not None:
        entrada = candidate_signal["entry_price"]
        stop = candidate_signal["stop"]
        alvo = candidate_signal["target"]
        risco = {
            "entrada": entrada, "stop": stop, "alvo": alvo,
            "unidade_r": abs(entrada - stop),
            "unidade_r_origem": "parâmetro de projeto: 1R = distância entrada→stop do setup",
        }
    else:
        risco = {
            "entrada": None, "stop": None, "alvo": None, "unidade_r": None,
            "motivo": "sem candidato de entrada (sem sinal ou entrada não acionada)",
        }

    return {
        "ativo": (market or {}).get("ativo"),
        "direcao": SIDE_LABELS.get(rules.get("side"), rules.get("side")),
        "setup": {"id": rules.get("setup_id"), "nome": rules.get("setup_name")},
        "evidencia_do_metodo": knowledge,
        "contexto_atual": market,
        "evidencia_historica": backtest_evidence,
        "conducao": rules.get("management"),
        "risco": risco,
        "fatores_contrarios": fatores_contrarios,
        "decisao": decisao,
    }
