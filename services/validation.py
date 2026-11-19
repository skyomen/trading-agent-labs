"""Validation of approved setups: causal split, cost grid and concentration.

This module never promotes a strategy and never produces a verdict of
robustness. It produces a labelled reading of an historical simulation and
says plainly when the sample cannot support any reading at all.

Three deliberate choices govern the whole module:

1. **The split is causal.** The series is cut once, in chronological order;
   the earlier fraction is development/training and the later fraction is
   out-of-sample. Bars are never shuffled, never resampled and never shared
   between the two sides. Each side independently pays the ``WARMUP_BARS``
   warm-up of the signal engine, so no training bar is ever read while an
   out-of-sample signal is being formed. The cost is a smaller sample; the
   gain is that look-ahead is structurally impossible rather than merely
   unlikely.
2. **Costs are a grid, not an assumption.** The same bars run under four
   fixed (fee, slippage) scenarios. The zero-cost corner is a sensitivity
   baseline and is labelled as such; it is never shown alone as a result.
   What matters is whether the sign of the return survives the expensive
   corner.
3. **Sample adequacy is declared before any number is read.** Fewer than
   ``ADEQUACY_MIN_TRADES`` trades on the worse side is ``insuficiente`` and
   carries no verdict at all. These thresholds are a project decision
   approved by the user on 13/11/2026, not a statistical derivation; they
   are stated here so they can be argued with instead of hidden.
"""

import math
from datetime import datetime

from services.setup_backtest import (WARMUP_BARS, aggregate_minutes,
                                     prepare_verified_run, simulate)

ENGINE_VERSION = "validation_engine_v1"

# (fee_bps_per_side, slippage_bps_per_side), ordered from cheapest to most expensive.
DEFAULT_COST_GRID = ((0.0, 0.0), (5.0, 2.0), (10.0, 5.0), (20.0, 10.0))
# The cost assumption approved for the Entrega 5 scenario; trade counts,
# adequacy and concentration are read at this point of the grid.
REFERENCE_COST = (10.0, 5.0)

# Project decision, approved by the user: thresholds on the trade count of the
# worse of the two sides. They are reported with every run so the reader can
# see the rule being applied instead of inferring it from a number.
ADEQUACY_MIN_TRADES = 10
ADEQUACY_GOOD_TRADES = 30
ADEQUACY_ORDER = ("insuficiente", "limitrofe", "adequada")
VERDICTS = {
    "insuficiente": "sem_veredito_amostra_insuficiente",
    "limitrofe": "leitura_indicativa_amostra_limitrofe",
    "adequada": "leitura_possivel_sujeita_aos_sinais_de_fragilidade",
}

# Roadmap items that this engine deliberately does not implement, with the
# reason. They are persisted with every run so the gap stays visible.
OUT_OF_SCOPE = [
    {"item": "comparar_periodos",
     "reason": "exige várias janelas longas e independentes; o histórico local tem cerca de 16h38 por par, "
               "o que não permite separar período de ruído."},
    {"item": "procurar_degradacao",
     "reason": "degradação só é mensurável ao longo de janelas sucessivas; uma única janela curta não a mede."},
    {"item": "comparar_ativos_estatisticamente",
     "reason": "cada execução cobre um par; comparar BTCUSDT e ETHUSDT lado a lado é leitura visual, "
               "sem teste estatístico possível com esta amostra."},
]

_ZERO = 1e-9


def _sign(value):
    if value > _ZERO:
        return 1
    if value < -_ZERO:
        return -1
    return 0


def _epoch_minute(stamp):
    return int(stamp.timestamp() // 60)


def split_bars_temporal(bars, holdout_fraction=0.3, block_minutes=None):
    """Cut one chronological series once: earlier bars train, later bars hold out.

    The series is never shuffled. ``block_minutes`` snaps the cut backwards to
    the start of a complete UTC aggregation block, so neither side loses a
    block to a partial boundary; moving the cut earlier only enlarges the
    out-of-sample side, so causality is preserved.
    """
    if not isinstance(holdout_fraction, (int, float)) or not math.isfinite(holdout_fraction) \
            or not 0 < holdout_fraction < 1:
        raise ValueError("A fração out-of-sample deve ser um número entre 0 e 1, exclusive.")
    if len(bars) < 2:
        raise ValueError("São necessárias ao menos duas barras para separar treino e out-of-sample.")
    stamps = [datetime.fromisoformat(bar["timestamp"].replace("Z", "+00:00")) for bar in bars]
    if any(stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0 for stamp in stamps):
        raise ValueError("As barras precisam trazer timestamp UTC explícito.")
    if any(later <= earlier for earlier, later in zip(stamps, stamps[1:])):
        raise ValueError("As barras precisam estar em ordem cronológica estrita; o corte nunca reordena a série.")
    cut = len(bars) - int(round(len(bars) * holdout_fraction))
    cut = min(max(cut, 1), len(bars) - 1)
    if block_minutes:
        aligned = cut
        while aligned > 1 and _epoch_minute(stamps[aligned]) % block_minutes:
            aligned -= 1
        if _epoch_minute(stamps[aligned]) % block_minutes:
            raise ValueError("Não há início de bloco UTC completo próximo ao corte solicitado.")
        cut = aligned
    train, holdout = bars[:cut], bars[cut:]
    if not train or not holdout:
        raise ValueError("O corte deixou um dos lados vazio; ajuste a fração out-of-sample.")
    if stamps[cut - 1] >= stamps[cut]:  # structural guard against look-ahead
        raise ValueError("O out-of-sample precisa começar depois do fim do treino.")
    return {
        "train_bars": train, "holdout_bars": holdout,
        "cut_utc": holdout[0]["timestamp"],
        "train_bar_count": len(train), "holdout_bar_count": len(holdout),
        "train_start_utc": train[0]["timestamp"], "train_end_utc": train[-1]["timestamp"],
        "holdout_start_utc": holdout[0]["timestamp"], "holdout_end_utc": holdout[-1]["timestamp"],
        "holdout_fraction_requested": holdout_fraction,
        "holdout_fraction_effective": len(holdout) / len(bars),
        "block_minutes": block_minutes,
        "order": "chronological_no_shuffle",
    }


def sample_adequacy(trade_count):
    """Label one side's sample by its trade count, never by its return."""
    if trade_count < ADEQUACY_MIN_TRADES:
        return "insuficiente"
    if trade_count < ADEQUACY_GOOD_TRADES:
        return "limitrofe"
    return "adequada"


def worst_adequacy(labels):
    """A validation is only as good as its weaker side."""
    return min(labels, key=ADEQUACY_ORDER.index)


def run_cost_grid(bars, rules, tick_size, cost_grid=DEFAULT_COST_GRID):
    """Run the same bars under each cost scenario and keep the full metrics."""
    if not cost_grid:
        raise ValueError("A grade de custo não pode ser vazia.")
    results = []
    for fee_bps, slippage_bps in cost_grid:
        metrics = simulate(bars, rules, tick_size, float(fee_bps), float(slippage_bps))
        results.append({"fee_bps_per_side": float(fee_bps),
                        "slippage_bps_per_side": float(slippage_bps),
                        "metrics": metrics})
    return results


def summarize_cost_grid(results):
    """Persistable view of the grid plus the two flags that matter."""
    scenarios = []
    for item in results:
        metrics = item["metrics"]
        zero = item["fee_bps_per_side"] == item["slippage_bps_per_side"] == 0
        scenarios.append({
            "fee_bps_per_side": item["fee_bps_per_side"],
            "slippage_bps_per_side": item["slippage_bps_per_side"],
            "cost_scenario": "sensitivity_baseline_zero" if zero else "cost_sensitivity_scenario",
            "signal_count": metrics["signal_count"],
            "expired_entries": metrics["expired_entries"],
            "trade_count": metrics["trade_count"],
            "win_rate_pct": metrics["win_rate_pct"],
            "net_return_pct": metrics["net_return_pct"],
            "max_drawdown_pct": metrics["max_drawdown_pct"],
        })
    ordered = sorted(scenarios, key=lambda row: (row["fee_bps_per_side"] + row["slippage_bps_per_side"]))
    cheapest, dearest = ordered[0], ordered[-1]
    returns = [row["net_return_pct"] for row in ordered]
    return {
        "scenarios": scenarios,
        "cheapest": {key: cheapest[key] for key in
                     ("fee_bps_per_side", "slippage_bps_per_side", "net_return_pct", "trade_count", "win_rate_pct")},
        "most_expensive": {key: dearest[key] for key in
                           ("fee_bps_per_side", "slippage_bps_per_side", "net_return_pct", "trade_count", "win_rate_pct")},
        "net_return_pct_spread": cheapest["net_return_pct"] - dearest["net_return_pct"],
        "sign_flips_with_cost": _sign(cheapest["net_return_pct"]) != _sign(dearest["net_return_pct"]),
        "trade_count_changes_with_cost": len({row["trade_count"] for row in ordered}) > 1,
        # Costs normally only subtract, but protective trailing reads the entry
        # price, so slippage can change the path. A False here is a finding.
        "monotonic_in_cost": all(later <= earlier + _ZERO for earlier, later in zip(returns, returns[1:])),
    }


def concentration(metrics):
    """Remove the single best trade and report what is left of the result."""
    trades = metrics.get("trades", [])
    if not trades:
        return {"evaluated": False, "trade_count": 0,
                "note": "Sem operações simuladas; não há concentração a medir."}
    best = max(trades, key=lambda trade: trade["net_return_pct"])
    equity_all, equity_without = 1.0, 1.0
    removed = False
    for trade in trades:
        equity_all *= 1 + trade["net_return_pct"] / 100
        if not removed and trade is best:
            removed = True
            continue
        equity_without *= 1 + trade["net_return_pct"] / 100
    aggregate = 100 * (equity_all - 1)
    without = 100 * (equity_without - 1)
    share = None if abs(aggregate) <= _ZERO else 100 * (aggregate - without) / abs(aggregate)
    return {
        "evaluated": True, "trade_count": len(trades),
        "best_trade": {key: best[key] for key in
                       ("signal_time", "entry_time", "exit_time", "exit_reason", "net_return_pct")},
        "aggregate_net_return_pct": aggregate,
        "net_return_pct_without_best": without,
        "contribution_pct_points": aggregate - without,
        "contribution_share_pct": share,
        "sign_flips_without_best": _sign(aggregate) != _sign(without),
        "single_trade_explains_result": len(trades) == 1,
    }


def _evaluate_side(name, bars_1m, rules, tick_size, minutes, cost_grid):
    bars, coverage = aggregate_minutes(bars_1m, minutes)
    if not bars:
        raise ValueError(f"O lado {name} não produziu nenhum bloco UTC completo de {minutes}m.")
    results = run_cost_grid(bars, rules, tick_size, cost_grid)
    reference = next((item for item in results
                      if (item["fee_bps_per_side"], item["slippage_bps_per_side"]) == REFERENCE_COST),
                     results[-1])
    trade_count = reference["metrics"]["trade_count"]
    return {
        "summary": {
            "source_bar_count": len(bars_1m), "aggregated_bar_count": len(bars),
            "start_utc": bars[0]["timestamp"], "end_utc": bars[-1]["timestamp"],
            "coverage": coverage, "warmup_bars_required": WARMUP_BARS,
            "bars_available_for_signals": max(0, len(bars) - WARMUP_BARS - 1),
            "reference_trade_count": trade_count,
            "reference_signal_count": reference["metrics"]["signal_count"],
            "sample_adequacy": sample_adequacy(trade_count),
        },
        "cost_grid": summarize_cost_grid(results),
        "concentration": concentration(reference["metrics"]),
        "reference_cost": {"fee_bps_per_side": reference["fee_bps_per_side"],
                           "slippage_bps_per_side": reference["slippage_bps_per_side"]},
    }


def _fragility_flags(sides):
    flags = []
    for name, label in (("train", "treino"), ("holdout", "out-of-sample")):
        side = sides[name]
        if side["cost_grid"]["sign_flips_with_cost"]:
            flags.append(f"O sinal do retorno muda entre o cenário mais barato e o mais caro ({label}).")
        if not side["cost_grid"]["monotonic_in_cost"]:
            flags.append(f"O retorno não cai de forma monótona com o custo ({label}); "
                         "o caminho das operações mudou com o slippage.")
        if side["concentration"].get("single_trade_explains_result"):
            flags.append(f"Uma única operação explica todo o resultado ({label}).")
        elif side["concentration"].get("sign_flips_without_best"):
            flags.append(f"Remover a melhor operação inverte o sinal do resultado ({label}).")
        if side["summary"]["sample_adequacy"] == "insuficiente":
            flags.append(f"Amostra insuficiente: {side['summary']['reference_trade_count']} operações ({label}).")
    return flags


def evaluate_validation(strategy, dataset_id, timeframe, holdout_fraction=0.3,
                        cost_grid=DEFAULT_COST_GRID, allowed_symbols=None):
    """Validate one approved setup over one verified snapshot and label the sample.

    Reuses the provenance gate of ``services.setup_backtest`` unchanged, so an
    unapproved version, a changed source PDF or a non-verified dataset is
    refused here exactly as it is for a backtest.
    """
    prepared = prepare_verified_run(strategy, dataset_id, timeframe,
                                    allowed_symbols=allowed_symbols)
    minutes = int(timeframe[:-1])
    split = split_bars_temporal(prepared["source_bars"], holdout_fraction, block_minutes=minutes)
    sides = {name: _evaluate_side(name, split[f"{name}_bars"], prepared["rules"],
                                  prepared["tick_size"], minutes, cost_grid)
             for name in ("train", "holdout")}
    by_side = {name: sides[name]["summary"]["sample_adequacy"] for name in sides}
    adequacy = worst_adequacy(list(by_side.values()))
    split_block = {key: value for key, value in split.items()
                   if key not in {"train_bars", "holdout_bars"}}
    split_block.update({
        "train": sides["train"]["summary"], "holdout": sides["holdout"]["summary"],
        "look_ahead_guard": "o out-of-sample começa depois do fim do treino; nenhuma barra é compartilhada",
        "warmup_policy": f"cada lado paga seu próprio aquecimento de {WARMUP_BARS} barras agregadas; "
                         "o treino nunca alimenta um sinal out-of-sample",
    })
    cost_block = {
        "grid": [[float(fee), float(slippage)] for fee, slippage in cost_grid],
        "reference_cost": {"fee_bps_per_side": REFERENCE_COST[0],
                           "slippage_bps_per_side": REFERENCE_COST[1]},
        "train": sides["train"]["cost_grid"], "holdout": sides["holdout"]["cost_grid"],
    }
    concentration_block = {
        "reference_cost": cost_block["reference_cost"],
        "train": sides["train"]["concentration"], "holdout": sides["holdout"]["concentration"],
    }
    return {
        "kind": "validation_run", "engine_version": ENGINE_VERSION,
        **prepared["provenance"],
        "start_utc": sides["train"]["summary"]["start_utc"],
        "end_utc": sides["holdout"]["summary"]["end_utc"],
        "holdout_fraction": holdout_fraction,
        "split": split_block, "cost_grid": cost_block,
        "concentration": concentration_block,
        "sample_adequacy": adequacy, "sample_adequacy_by_side": by_side,
        "adequacy_thresholds": {"insuficiente_abaixo_de": ADEQUACY_MIN_TRADES,
                                "adequada_a_partir_de": ADEQUACY_GOOD_TRADES,
                                "medida": "operações simuladas no pior dos dois lados",
                                "origem": "decisão de projeto aprovada pelo usuário, não derivação estatística"},
        "verdict": VERDICTS[adequacy],
        "fragility_flags": _fragility_flags(sides),
        "promotes_strategy": False,
        "out_of_scope": OUT_OF_SCOPE,
    }
