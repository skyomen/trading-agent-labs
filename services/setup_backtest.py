"""Deterministic, historical-only execution of approved setup signals."""

import hashlib
import json
import math
from datetime import datetime, timezone

from database import store
from services import datasets, documents
from services.setup_signals import signal_at

ENGINE_VERSION = "setup_backtest_v1"
# Bars consumed before the first possible signal: `signal_at` only reads a
# completed window from index 28 onwards and the order lives on the next bar.
WARMUP_BARS = 29


def aggregate_minutes(bars, minutes):
    """Build complete UTC blocks; never bridge a missing minute."""
    if minutes not in (2, 5):
        raise ValueError("Intervalo agregado deve ser 2m ou 5m.")
    groups = {}
    for bar in bars:
        stamp = datetime.fromisoformat(bar["timestamp"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0 or stamp.second or stamp.microsecond:
            raise ValueError("As barras de origem devem iniciar em minutos inteiros UTC.")
        minute = int(stamp.timestamp() // 60)
        groups.setdefault(minute - minute % minutes, []).append((minute, bar))
    result, dropped = [], []
    for start, group in sorted(groups.items()):
        group.sort(key=lambda item: item[0])
        if [item[0] for item in group] != list(range(start, start + minutes)):
            dropped.append({"start_utc": datetime.fromtimestamp(start * 60, timezone.utc).isoformat(),
                            "minutes_present": len(group)})
            continue
        rows = [item[1] for item in group]
        result.append({"timestamp": datetime.fromtimestamp(start * 60, timezone.utc).isoformat(),
                       "open": rows[0]["open"], "high": max(row["high"] for row in rows),
                       "low": min(row["low"] for row in rows), "close": rows[-1]["close"],
                       "volume": sum(row["volume"] for row in rows)})
    gaps = sum((datetime.fromisoformat(b["timestamp"]) - datetime.fromisoformat(a["timestamp"])).total_seconds()
               != minutes * 60 for a, b in zip(result, result[1:]))
    return result, {"discarded_blocks": len(dropped), "discarded_examples": dropped[:20],
                    "gaps_between_complete_blocks": gaps}


def _segment_gap(bars, index, minutes):
    """True when bars[index] does not continue bars[index - 1] (same arithmetic the main
    loop already uses to detect the start of a new segment)."""
    return index > 0 and (datetime.fromisoformat(bars[index]["timestamp"]) -
                          datetime.fromisoformat(bars[index - 1]["timestamp"])).total_seconds() != minutes * 60


def advance_position(position, bars, index, rules, direction, minutes):
    """One bar of managing an already-open position. Mutates `position` in place
    (favorable_closes, stop, trailing_updates) and returns None (position stays open) or a
    dict {"index": i, "price": ..., "reason": ..., "conflict": bool} when the bar closes it.

    Checked in this exact order (copied from the former inline loop, do not reorder):
    1. A segment gap closes the position at the PREVIOUS bar's close, before this bar's
       stop/target are even considered (replicates the former behaviour where a gap bar
       never runs the normal management step).
    2. Stop/target on the current bar, stop-first on an intrabar conflict.
    3. Otherwise: favorable_closes compares this bar's close against the entry price (not the
       previous close), and the VBS/VSS trailing hardcode (intentional, DEC item 2 of
       Entrega 8 — do not generalize to rules["management"]).
    """
    if _segment_gap(bars, index, minutes):
        return {"index": index - 1, "price": bars[index - 1]["close"],
                "reason": "gap_boundary", "conflict": False}
    bar = bars[index]
    stop_hit = bar["low"] <= position["stop"] if direction == 1 else bar["high"] >= position["stop"]
    target_hit = bar["high"] >= position["target"] if direction == 1 else bar["low"] <= position["target"]
    if stop_hit or target_hit:
        return {"index": index, "price": position["stop"] if stop_hit else position["target"],
                "reason": "stop" if stop_hit else "target", "conflict": stop_hit and target_hit}
    if direction * (bar["close"] - position["entry_price"]) > 0:
        position["favorable_closes"] += 1
    if position["favorable_closes"] >= 2 and rules["setup_name"] in {"VBS", "VSS"} and index > 0:
        candidate = bars[index - 1]["low"] if direction == 1 else bars[index - 1]["high"]
        if direction * (candidate - position["stop"]) > 0:
            position["stop"] = candidate
            position["trailing_updates"] += 1
    return None


def closed_trade(position, side, exit_index, exit_price, reason, conflict, direction,
                 fee_bps, slippage_bps):
    """Build the trade dict with adverse slippage and round-trip fee (same arithmetic
    close_position used to do inline). `exit_index` travels back as "exit_index" because this
    function never sees `bars`; the caller (which does) replaces it with the real "exit_time"
    before persisting or returning the trade."""
    adverse = exit_price * (1 - direction * slippage_bps / 10000)
    gross = direction * (adverse - position["entry_price"]) / position["entry_price"]
    fee = 2 * fee_bps / 10000
    net = gross - fee
    return {"side": side, "signal_time": position["signal_time"],
            "entry_time": position["entry_time"], "exit_index": exit_index,
            "entry_price": position["entry_price"], "exit_price": adverse,
            "initial_stop": position["initial_stop"], "final_stop": position["stop"],
            "target": position["target"], "exit_reason": reason,
            "intrabar_conflict": conflict, "trailing_updates": position["trailing_updates"],
            "gross_return_pct": gross * 100, "net_return_pct": net * 100}


def replay_open_position(bars, position, rules, direction, minutes, fee_bps, slippage_bps,
                         start_index=0, check_entry_bar=True, close_on_end_of_data=False):
    """Manage an already-open position over `bars`, where bars[start_index] is the ENTRY bar
    (the position already exists at that index, exactly as simulate() creates it at the end of
    the entry bar's iteration).

    1. If check_entry_bar: applies the same ambiguity rule simulate() applies on the entry bar
       itself today — closes immediately as "entry_bar_ambiguous_stop" (conflict=True) when the
       stop OR the target was already touched on the entry bar.
    2. Otherwise, walks index = start_index + 1 .. len(bars) - 1, calling advance_position on
       each bar; a closing result from advance_position ends the replay.
    3. If the loop ends without closing: close_on_end_of_data=True closes at bars[-1]["close"]
       with reason "end_of_data" (the same rule simulate() uses when bars run out);
       close_on_end_of_data=False (the mode used live, DEC item 5) returns the still-open
       position instead.
    """
    def _closed(exit_index, exit_price, reason, conflict):
        trade = closed_trade(position, rules["side"], exit_index, exit_price, reason, conflict,
                             direction, fee_bps, slippage_bps)
        trade["exit_time"] = bars[trade.pop("exit_index")]["timestamp"]
        return {"estado": "fechada", "trade": trade}

    if check_entry_bar:
        entry_bar = bars[start_index]
        stop_hit = entry_bar["low"] <= position["stop"] if direction == 1 else entry_bar["high"] >= position["stop"]
        target_hit = entry_bar["high"] >= position["target"] if direction == 1 else entry_bar["low"] <= position["target"]
        if stop_hit or target_hit:
            return _closed(start_index, position["stop"], "entry_bar_ambiguous_stop", True)

    for index in range(start_index + 1, len(bars)):
        closing = advance_position(position, bars, index, rules, direction, minutes)
        if closing:
            return _closed(closing["index"], closing["price"], closing["reason"], closing["conflict"])

    if close_on_end_of_data:
        return _closed(len(bars) - 1, bars[-1]["close"], "end_of_data", False)
    return {"estado": "aberta", "position": position,
            "barras_avaliadas": len(bars) - start_index - 1}


def simulate(bars, rules, tick_size, fee_bps, slippage_bps):
    """Signal at a close, fill only the next bar, and resolve ambiguous paths against the trade."""
    if any(not math.isfinite(float(value)) or float(value) < 0 for value in (fee_bps, slippage_bps)):
        raise ValueError("Custos devem ser finitos e não negativos.")
    if not bars:
        raise ValueError("Não há barras completas para o backtest.")
    direction = 1 if rules["side"] == "buy" else -1
    trades, signals, expired, conflicts = [], 0, 0, 0
    position = None
    equity, peak, drawdown = 1.0, 1.0, 0.0
    trailing_updates = 0
    minutes = int(rules["tested_timeframe"][:-1])
    segment_start = 0

    def close_position(index, price, reason, conflict=False):
        nonlocal position, equity, peak, drawdown, conflicts
        trade = closed_trade(position, rules["side"], index, price, reason, conflict,
                             direction, fee_bps, slippage_bps)
        trade["exit_time"] = bars[trade.pop("exit_index")]["timestamp"]
        equity *= 1 + trade["net_return_pct"] / 100
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak)
        conflicts += int(conflict)
        trades.append(trade)
        position = None

    for i, bar in enumerate(bars):
        occupied_at_open = position is not None
        if _segment_gap(bars, i, minutes):
            segment_start = i
        if position:
            trailing_before = position["trailing_updates"]
            closing = advance_position(position, bars, i, rules, direction, minutes)
            if closing:
                close_position(closing["index"], closing["price"], closing["reason"], closing["conflict"])
            else:
                trailing_updates += position["trailing_updates"] - trailing_before
        if occupied_at_open or position or i - segment_start < WARMUP_BARS or i == len(bars) - 1:
            continue
        # The signal is evaluated on i-1; order lives only on i. No prior signal
        # is evaluated across an absent aggregate bar.
        if i == 0 or (datetime.fromisoformat(bar["timestamp"]) -
                      datetime.fromisoformat(bars[i - 1]["timestamp"])).total_seconds() != minutes * 60:
            continue
        signal = signal_at(bars, i - 1, rules, tick_size)
        if signal is None:
            continue
        signals += 1
        triggered = bar["high"] >= signal["entry"] if direction == 1 else bar["low"] <= signal["entry"]
        if not triggered:
            expired += 1
            continue
        raw_entry = max(bar["open"], signal["entry"]) if direction == 1 else min(bar["open"], signal["entry"])
        entry = raw_entry * (1 + direction * slippage_bps / 10000)
        position = {"entry_price": entry, "entry_time": bar["timestamp"],
                    "signal_time": signal["signal_bar"], "initial_stop": signal["stop"],
                    "stop": signal["stop"], "target": signal["target"],
                    "favorable_closes": 0, "trailing_updates": 0}
        stop_hit = bar["low"] <= signal["stop"] if direction == 1 else bar["high"] >= signal["stop"]
        target_hit = bar["high"] >= signal["target"] if direction == 1 else bar["low"] <= signal["target"]
        if stop_hit or target_hit:
            # With no intrabar sequence, even target-only on the entry bar is ambiguous.
            close_position(i, signal["stop"], "entry_bar_ambiguous_stop", True)
    if position:
        close_position(len(bars) - 1, bars[-1]["close"], "end_of_data")
    wins = sum(trade["net_return_pct"] > 0 for trade in trades)
    return {"signal_count": signals, "expired_entries": expired, "trade_count": len(trades),
            "win_rate_pct": 100 * wins / len(trades) if trades else 0.0,
            "net_return_pct": 100 * (equity - 1), "equity_index": equity,
            "max_drawdown_pct": 100 * drawdown, "estimated_fees_pct_of_notional":
            len(trades) * 2 * fee_bps / 100,
            "estimated_slippage_bps_round_trip": 2 * slippage_bps,
            "intrabar_conflicts": conflicts,
            "trailing_updates": trailing_updates, "trades": trades}


def verify_approved_rules(strategy, timeframe):
    """Refuse anything but a human-approved setup version on a supported interval."""
    if strategy["status"] != "approved":
        raise ValueError("A estratégia precisa estar aprovada.")
    rules = json.loads(strategy["rules_json"])
    if rules.get("engine") != "setup_pattern_v1" or rules.get("approval") != "rules_human_approved":
        raise ValueError("A versão não contém regras de setup aprovadas.")
    if timeframe not in rules["timeframes"] or timeframe not in {"2m", "5m"}:
        raise ValueError("Intervalo incompatível com as regras aprovadas.")
    return {**rules, "tested_timeframe": timeframe}


def verify_source_documents(rules):
    """Raise if any source PDF behind `rules` is no longer indexed with the approved hash.

    Shared provenance gate: checks every entry in `rules["source"]` against the
    current library status (`documents.library_status()`), refusing anything
    that is missing, stale or indexed under a different hash. Pure verification,
    no side effect — reused by `prepare_verified_run` here and, from Phase 2
    onward, by `services/pipeline.py` (which has no dataset hash to check, only
    the live feed, but still needs this same PDF-provenance check).
    """
    current = {item["path"]: item for item in documents.library_status()}
    for source in rules["source"]:
        entry = current.get(source["path"], {})
        if entry.get("status") != "indexed" or entry.get("record", {}).get("sha256") != source["sha256"]:
            raise ValueError("PDF de origem ausente, alterado ou sem índice atual: " + source["path"])


def prepare_verified_run(strategy, dataset_id, timeframe, rules=None, allowed_symbols=None):
    """Single provenance gate shared by every engine that reads approved setups.

    Confirms the source PDFs are still indexed with the approved hash, restores
    the dataset through its canonical hash and rejects anything that is not a
    verified Binance Spot 1m crypto snapshot. Returns the source 1m bars so the
    caller decides how to aggregate or split them; no simulation happens here.
    """
    rules = rules or verify_approved_rules(strategy, timeframe)
    verify_source_documents(rules)
    restored = datasets.load_verified(dataset_id)
    row, metadata = restored["dataset"], restored["metadata"]
    if not row["canonical_sha256"] or metadata.get("market") != "crypto" or row["timeframe"] != "1m":
        raise ValueError("Exige snapshot cripto de 1m com hash canônico; ações horárias são inelegíveis.")
    # The default remains the original, paper-eligible backtest universe.
    # Watchlist analysis must opt into an explicit allowlist at the call site.
    eligible_symbols = set(allowed_symbols if allowed_symbols is not None else {"BTCUSDT", "ETHUSDT"})
    if (row["symbol"] not in eligible_symbols or metadata.get("quote_currency") != "USDT"
            or metadata.get("provider") != "Binance Spot public"):
        raise ValueError("Fonte/símbolo incompatível com esta execução de setup.")
    rule_hash = hashlib.sha256(strategy["rules_json"].encode("utf-8")).hexdigest()
    prepared = {
        "rules": rules, "tick_size": float(metadata["tick_size"]),
        "source_bars": restored["bars"],
        "provenance": {
            "strategy_id": strategy["id"], "strategy_version": strategy["version"],
            "rule_sha256": rule_hash, "source_pdfs": rules["source"],
            "dataset_id": dataset_id, "file_sha256": row["sha256"],
            "canonical_sha256": row["canonical_sha256"], "source": row["source"],
            "symbol": row["symbol"], "market": metadata["market"],
            "source_timeframe": "1m", "timeframe": timeframe,
            "source_bar_count": len(restored["bars"]),
            "filters": {"market": "crypto", "provider": "Binance Spot public",
                        "source_timeframe": "1m", "complete_utc_blocks_only": True},
        },
    }
    if allowed_symbols is not None and row["symbol"] not in {"BTCUSDT", "ETHUSDT"}:
        prepared["provenance"]["analysis_only"] = True
        prepared["provenance"]["paper_eligible"] = False
    return prepared


def run_approved(strategy, dataset_id, timeframe, fee_bps=10.0, slippage_bps=5.0,
                 confirm_zero_costs=False, allowed_symbols=None):
    rules = verify_approved_rules(strategy, timeframe)
    if (fee_bps == 0 or slippage_bps == 0) and not confirm_zero_costs:
        raise ValueError("Custo zero exige confirmação explícita.")
    prepared = prepare_verified_run(strategy, dataset_id, timeframe, rules, allowed_symbols)
    bars, coverage = aggregate_minutes(prepared["source_bars"], int(timeframe[:-1]))
    if not bars:
        raise ValueError("Nenhuma barra agregada completa.")
    metrics = simulate(bars, prepared["rules"], prepared["tick_size"], fee_bps, slippage_bps)
    return {"kind": "historical_simulation", "engine_version": ENGINE_VERSION,
            **prepared["provenance"],
            "start_utc": bars[0]["timestamp"], "end_utc": bars[-1]["timestamp"],
            "aggregated_bar_count": len(bars),
            "coverage": coverage, "fee_bps_per_side": fee_bps,
            "slippage_bps_per_side": slippage_bps,
            "cost_scenario": "zero_confirmed" if fee_bps == slippage_bps == 0 else "user_supplied_assumption",
            **metrics}
