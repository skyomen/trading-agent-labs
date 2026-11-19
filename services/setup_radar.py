"""Read-only setup observations for additional Binance Spot assets.

The radar records confirmed setup triggers for study. Its rows are deliberately
separate from pipeline_runs, Risk commitments, and paper_operations.
"""

import json
from datetime import datetime, timezone

from database import store
from services import market_data
from services.setup_backtest import WARMUP_BARS, aggregate_minutes, verify_approved_rules, verify_source_documents
from services.setup_signals import signal_at

_METADATA_RETRY_AFTER = {}


def _fresh_feed(symbol, now):
    feed = next((item for item in store.list_market_feeds()
                 if item["provider"] == market_data.PROVIDER and item["symbol"] == symbol
                 and item["timeframe"] == "1m"), None)
    if not feed or feed["status"] != "connected" or not feed["last_bar_at"]:
        return False
    stamp = datetime.fromisoformat(feed["last_bar_at"].replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    age = (now - stamp.astimezone(timezone.utc)).total_seconds()
    return 0 <= age <= 180


def scan_observation_watchlist(strategies=None, now=None):
    """Store only actual setup/trigger observations; never evaluate or reserve Risk."""
    now = now or datetime.now(timezone.utc)
    if strategies is None:
        strategies = [row for row in store.list_strategies()
                      if row["status"] == "approved"
                      and (rules := json.loads(row["rules_json"])).get("engine") == "setup_pattern_v1"
                      and rules.get("approval") == "rules_human_approved"]
    created = []
    errors = []
    for symbol in market_data.OBSERVATION_ONLY_SYMBOLS:
        if not _fresh_feed(symbol, now):
            continue
        if now.timestamp() < _METADATA_RETRY_AFTER.get(symbol, 0):
            continue
        try:
            metadata = market_data.symbol_metadata(symbol)
            _METADATA_RETRY_AFTER.pop(symbol, None)
            bars = store.get_market_bars(market_data.PROVIDER, symbol, "1m", limit=600)
            for strategy in strategies:
                rules = json.loads(strategy["rules_json"])
                for timeframe in rules.get("timeframes", []):
                    try:
                        rules = verify_approved_rules(strategy, timeframe)
                        verify_source_documents(rules)
                        aggregated, coverage = aggregate_minutes(bars, int(timeframe[:-1]))
                        if len(aggregated) < WARMUP_BARS + 1:
                            continue
                        index = len(aggregated) - 2
                        raw = signal_at(aggregated, index, rules, metadata["tick_size"])
                        if raw is None:
                            continue
                        trigger_bar = aggregated[index + 1]
                        direction = 1 if rules["side"] == "buy" else -1
                        triggered = (trigger_bar["high"] >= raw["entry"] if direction == 1
                                     else trigger_bar["low"] <= raw["entry"])
                        entry = (max(trigger_bar["open"], raw["entry"]) if direction == 1
                                 else min(trigger_bar["open"], raw["entry"])) if triggered else raw["entry"]
                        state = "gatilho_observado" if triggered else "aguardando_gatilho"
                        report = {
                            "mode": "observation_only",
                            "source": market_data.PROVIDER,
                            "strategy_version_id": strategy["id"],
                            "strategy_version": strategy["version"],
                            "rules": {key: rules.get(key) for key in
                                      ("pattern", "entry", "stop", "target", "filters", "source")},
                            "signal": raw,
                            "entry_reference": entry,
                            "trigger_bar_utc": trigger_bar["timestamp"],
                            "triggered": triggered,
                            "tick_size": metadata["tick_size"],
                            "tick_size_source": metadata["tick_size_source"],
                            "min_notional_source_value": metadata["min_notional"],
                            "coverage": coverage,
                            "backtest_status": "sem_validacao_historica_para_este_ativo",
                            "risk_status": "nao_avaliado; observacao nao consome limite diario",
                            "execution_status": "bloqueada; este ativo nao esta habilitado para paper",
                        }
                        inserted = store.save_setup_observation(
                            strategy["id"], rules["setup_id"], rules["setup_name"],
                            symbol, timeframe, raw["signal_bar"], state, report)
                        if inserted:
                            created.append({"setup": rules["setup_name"], "symbol": symbol,
                                            "timeframe": timeframe, "state": state,
                                            "signal_bar_utc": raw["signal_bar"]})
                    except (ValueError, RuntimeError) as exc:
                        errors.append(f"{rules.get('setup_name', 'setup')} {symbol} {timeframe}: {exc}")
        except (ValueError, RuntimeError, OSError) as exc:
            _METADATA_RETRY_AFTER[symbol] = now.timestamp() + 60
            errors.append(f"{symbol}: {exc}")
    return {"created": created, "errors": errors,
            "symbols": list(market_data.OBSERVATION_ONLY_SYMBOLS)}
