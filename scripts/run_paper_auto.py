"""Supervise local paper entries at a fixed 2 USDT per approved candidate.

This process never calls a broker. It must be started explicitly and only acts
on the owner's local workspace. It accepts fresh, already triggered pipeline
candidates, then replays open paper positions as closed candles arrive.
"""

import argparse
import json
import time
from datetime import datetime, timedelta, timezone

from database import store
from services import execution, pipeline, setup_radar, trade_management
from services.market_data import PROVIDER, SYMBOLS

POLL_SECONDS = 10
MAX_CONFIRM_DELAY_SECONDS = 45


def _utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _feed_is_fresh(symbol, now):
    feed = next((row for row in store.list_market_feeds()
                 if row["provider"] == PROVIDER and row["symbol"] == symbol
                 and row["timeframe"] == "1m"), None)
    if not feed or feed["status"] != "connected" or not feed["last_bar_at"]:
        return False
    age = (now - _utc(feed["last_bar_at"])).total_seconds()
    return 0 <= age <= 180


def _fresh_pending(run, now):
    if run["symbol"] not in SYMBOLS or not run["pending_since"]:
        return False
    age = (now - _utc(run["pending_since"])).total_seconds()
    if not 0 <= age <= MAX_CONFIRM_DELAY_SECONDS:
        return False
    plan = json.loads(run["report_json"]).get("execution") or {}
    entry_bar = plan.get("barra_de_entrada_utc")
    if not entry_bar:
        return False
    bar_end = _utc(entry_bar) + timedelta(minutes=int(run["timeframe"][:-1]))
    bar_age = (now - bar_end).total_seconds()
    return 0 <= bar_age <= MAX_CONFIRM_DELAY_SECONDS


def run_once():
    """Evaluate every approved setup and open only fresh local paper candidates."""
    now = datetime.now(timezone.utc)
    store.expire_stale_pipeline_runs(max_age_seconds=900)
    managed = trade_management.replay_open_operations()
    approved = [row for row in store.list_strategies()
                if row["status"] == "approved"
                and (rules := json.loads(row["rules_json"])).get("engine") == "setup_pattern_v1"
                and rules.get("approval") == "rules_human_approved"]
    for strategy in approved:
        rules = json.loads(strategy["rules_json"])
        for symbol in SYMBOLS:
            if not _feed_is_fresh(symbol, now):
                continue
            for timeframe in rules.get("timeframes", []):
                try:
                    pipeline.run_pipeline(strategy, symbol, timeframe)
                except (ValueError, RuntimeError) as exc:
                    print(f"Avaliação ignorada: {rules['setup_name']} {symbol} {timeframe}: {exc}", flush=True)
    radar = setup_radar.scan_observation_watchlist(approved, now=datetime.now(timezone.utc))
    opened = []
    if store.get_kill_switch()["enabled"]:
        return {"opened": opened, "managed": managed, "blocked": True, "radar": radar}
    for run in store.list_pending_pipeline_runs():
        check_time = datetime.now(timezone.utc)
        if not _feed_is_fresh(run["symbol"], check_time) or not _fresh_pending(run, check_time):
            continue
        try:
            result = execution.confirm_open_usdt(run["id"], execution.DEFAULT_ENTRY_USDT)
        except ValueError as exc:
            print(f"Entrada paper recusada: trilha #{run['id']}: {exc}", flush=True)
            continue
        store.add_event("Execution Agent", "INFO",
                        f"Abertura paper automática #{result['paper_operation_id']}: "
                        f"{run['setup_name']} {run['symbol']} {execution.DEFAULT_ENTRY_USDT:.2f} USDT")
        opened.append(result)
    return {"opened": opened, "managed": managed, "blocked": False, "radar": radar}


def main():
    parser = argparse.ArgumentParser(description="Abertura paper local automática de 2 USDT por entrada")
    parser.add_argument("--once", action="store_true", help="Executa uma rodada e sai")
    parser.add_argument("--interval", type=int, default=POLL_SECONDS,
                        help="Segundos entre rodadas (padrão: 10)")
    args = parser.parse_args()
    if args.interval < 2:
        parser.error("--interval deve ser de pelo menos 2 segundos")
    owner = next((user for user in store.list_identity_users() if user["role"] == "owner"), None)
    if owner is None:
        parser.error("Crie o proprietário local antes de iniciar a automação")
    with store.user_workspace(owner["id"]):
        store.initialize()
        try:
            while True:
                try:
                    result = run_once()
                    store.record_heartbeat("paper-auto", "running")
                    if (result["opened"] or result["radar"]["created"] or
                            any(item["estado"] == "fechada" for item in result["managed"])):
                        print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
                except Exception as exc:
                    store.record_heartbeat("paper-auto", "error")
                    print(f"Falha na rodada paper automática: {exc}", flush=True)
                if args.once:
                    break
                time.sleep(args.interval)
        finally:
            store.record_heartbeat("paper-auto", "stopped")


if __name__ == "__main__":
    main()
