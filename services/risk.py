"""Risk Manager service (Entrega 7 / Fase 2): deterministic authorization gate.

Per DEC-2026-11-16 item 3, every check states its own provenance: "método"
(stop/target/trailing come from the setup's own `rules_json`, derived from
the approved PDFs) or "parâmetro de projeto" (risk-per-trade, daily loss and
exposure limits, approved by the user on 16/11/2026 precisely because the
method has no money-management layer of its own). The two are never blended
silently.

Evaluates the 7 fixed motives of the roadmap (§14), in this fixed order.
Only motives 1 (`estrategia_nao_aprovada`), 3 (`risco_excedido`),
4 (`exposicao_excedida`), 5 (`perda_diaria_atingida`) and
6 (`paper_live_gate`) can deny — motive 2 (`stop_ausente`) is always
satisfied by construction for an approved setup (every setup defines its
stop before the entry), and motive 7 (`mercado_fora_das_regras`) is always
"não aplicável" until `filters.session_hours` gains its own source (DEC
item 4).
"""

import math

from database import store

RISK_ENGINE_VERSION = "risk_manager_v1"
RISK_PER_TRADE_R = 1.0
MAX_DAILY_LOSS_R = 3.0
MAX_OPEN_POSITIONS = 2
PARAMETER_SOURCE = "parametro_de_projeto:DEC-2026-11-16-escopo-entrega-7-orquestracao"
METHOD_SOURCE = "metodo_pdf:rules_json(setup_specs)"

_TOL = 1e-9
# Only these motives can flip the verdict to "negado" (DEC item 3/4; roadmap §14).
_VERDICT_MOTIVES = {"estrategia_nao_aprovada", "risco_excedido", "exposicao_excedida",
                    "perda_diaria_atingida", "paper_live_gate"}


def evaluate_risk(strategy, rules, candidate_signal, mode="paper"):
    """Evaluate one triggered candidate against the 7 fixed risk motives.

    `candidate_signal` must already carry `entry_price` (the real fill,
    computed by `services/pipeline.py` the same way `setup_backtest.simulate`
    does), `stop`, `target` and `signal_bar` (ISO UTC timestamp of the
    evaluated signal bar) — this function is only ever called once a
    candidate has actually formed.
    """
    checks = []

    def add(motivo, fonte, estado, detalhe):
        checks.append({"motivo": motivo, "fonte": fonte, "estado": estado, "detalhe": detalhe})

    # 1. estrategia_nao_aprovada — same gate as services.setup_backtest.verify_approved_rules;
    # if the candidate already passed through it, this check is "ok" by reuse, not re-derivation.
    approved = strategy.get("status") == "approved" and rules.get("approval") == "rules_human_approved"
    add("estrategia_nao_aprovada", "metodo",
        "ok" if approved else "negado",
        "Estratégia aprovada (strategies.status='approved') e regras com aprovação humana "
        "(rules_json.approval='rules_human_approved')." if approved else
        "Estratégia ou regras ainda sem aprovação humana registrada.")

    # 2. stop_ausente — never denies in practice for an approved setup.
    entrada = float(candidate_signal["entry_price"])
    stop = float(candidate_signal["stop"])
    stop_presente = math.isfinite(entrada) and math.isfinite(stop) and abs(entrada - stop) > _TOL
    add("stop_ausente", "metodo",
        "satisfeito_por_construcao" if stop_presente else "negado",
        "Todo setup aprovado define o stop antes da entrada; a distância entrada→stop é "
        "garantida pela regra do método (rules_json).")

    # 3. risco_excedido — by construction, 1R = abs(entrada-stop), então risco_r = 1.0 sempre
    # que o stop existir; a checagem continua explícita por auditoria.
    unidade_r = abs(entrada - stop)
    risco_r = (unidade_r / unidade_r) if unidade_r > _TOL else float("nan")
    risco_ok = math.isfinite(risco_r) and risco_r > 0 and risco_r <= RISK_PER_TRADE_R + _TOL
    add("risco_excedido", "parametro_de_projeto",
        "ok" if risco_ok else "negado",
        f"Risco do candidato = {risco_r if math.isfinite(risco_r) else 'indefinido'}R "
        f"(distância entrada→stop do método, fonte={METHOD_SOURCE}); "
        f"limite de projeto = {RISK_PER_TRADE_R}R.")

    # 4. exposicao_excedida
    reserved = store.count_reserved_exposure()
    exposicao_ok = reserved < MAX_OPEN_POSITIONS
    add("exposicao_excedida", "parametro_de_projeto",
        "ok" if exposicao_ok else "negado",
        f"Exposição reservada atual: {reserved} de {MAX_OPEN_POSITIONS} vagas (posições abertas "
        "+ autorizações aguardando quantidade, parâmetro de projeto).")

    # 5. perda_diaria_atingida — "hoje UTC" é a data da barra do sinal, não a data de agora
    # (isola a checagem do relógio da máquina e a torna determinística em teste).
    date_utc = str(candidate_signal["signal_bar"])[:10]
    committed = store.count_committed_risk_r(date_utc)
    perda_ok = committed + RISK_PER_TRADE_R <= MAX_DAILY_LOSS_R + _TOL
    add("perda_diaria_atingida", "parametro_de_projeto",
        "ok" if perda_ok else "negado",
        f"Orçamento diário comprometido em {date_utc} (UTC): {committed}R + {RISK_PER_TRADE_R}R "
        f"desta autorização; limite de projeto = {MAX_DAILY_LOSS_R}R.")

    # 6. paper_live_gate
    modo_ok = mode == "paper"
    add("paper_live_gate", "invariante_de_codigo",
        "ok" if modo_ok else "negado",
        "Modo paper confirmado; execução real está bloqueada no projeto." if modo_ok else
        "Execução real bloqueada no projeto; apenas o modo paper é autorizável.")

    # 7. mercado_fora_das_regras — nunca bloqueia nem libera (DEC item 4).
    add("mercado_fora_das_regras", "sem_fonte", "nao_aplicavel",
        "Sem definição de mercado/fuso (filters.session_hours ainda pending_market_selection); "
        "não bloqueia nem libera nada até ganhar fonte própria.")

    denial_reasons = [check["motivo"] for check in checks
                      if check["motivo"] in _VERDICT_MOTIVES and check["estado"] == "negado"]
    verdict = "negado" if denial_reasons else "autorizado"

    parametros_de_risco = {
        "risco_por_trade_r": RISK_PER_TRADE_R,
        "perda_diaria_maxima_r": MAX_DAILY_LOSS_R,
        "exposicao_maxima_posicoes": MAX_OPEN_POSITIONS,
        "unidade": "R (distância entrada→stop do próprio setup)",
        "fonte": PARAMETER_SOURCE,
        "referencia": "DEC-2026-11-16-escopo-entrega-7-orquestracao",
    }

    return {
        "engine_version": RISK_ENGINE_VERSION,
        "verdict": verdict,
        "checks": checks,
        "denial_reasons": denial_reasons,
        "parametros_de_risco": parametros_de_risco,
        "nota_quantidade": ("O valor monetário de 1R depende da quantidade informada pelo "
                            "humano e não é avaliado por este sistema, que não presume capital."),
        "mode": mode,
        "risk_committed_r": RISK_PER_TRADE_R if verdict == "autorizado" else 0.0,
    }
