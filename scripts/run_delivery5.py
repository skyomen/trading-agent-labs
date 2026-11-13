"""Explicitly run the approved 2026-11-13 historical scenario once per combination."""

import json

from database import store
from services.setup_backtest import run_approved


def main():
    store.initialize()
    strategies = [row for row in store.list_strategies()
                  if row["status"] == "approved"
                  and json.loads(row["rules_json"]).get("setup_name") in {"VBS", "VSS", "BOP", "BDP"}]
    datasets = [row for row in store.list_historical_datasets()
                if row["symbol"] in {"BTCUSDT", "ETHUSDT"} and row["timeframe"] == "1m"]
    if len(strategies) != 4 or len(datasets) != 2:
        raise ValueError("A demonstração exige quatro regras aprovadas e dois snapshots cripto de 1m.")
    existing = [json.loads(row["metrics_json"]) for row in store.list_backtests()]
    for strategy in sorted(strategies, key=lambda row: row["id"]):
        name = json.loads(strategy["rules_json"])["setup_name"]
        for dataset in sorted(datasets, key=lambda row: row["symbol"]):
            for timeframe in ("2m", "5m"):
                report = run_approved(strategy, dataset["id"], timeframe, 10.0, 5.0)
                matching = [item for item in existing
                            if item.get("kind") == "historical_simulation"
                            and item.get("strategy_id") == strategy["id"]
                            and item.get("dataset_id") == dataset["id"]
                            and item.get("timeframe") == timeframe
                            and item.get("fee_bps_per_side") == 10.0
                            and item.get("slippage_bps_per_side") == 5.0]
                if matching and matching[0] != report:
                    raise ValueError(f"Reprodução divergente: {name} {dataset['symbol']} {timeframe}")
                if not matching:
                    result_id = store.save_backtest(strategy["id"], dataset["symbol"], timeframe,
                                                    dataset["source"], dataset["sha256"], report)
                    store.add_event("Strategy & Backtest", "INFO",
                                    f"Simulação histórica #{result_id}: {name} {dataset['symbol']} {timeframe}; "
                                    f"{report['signal_count']} sinais, {report['trade_count']} operações")
                print(f"{name} {dataset['symbol']} {timeframe}: "
                      f"{report['signal_count']} sinais, {report['trade_count']} operações, "
                      f"{report['expired_entries']} entradas expiradas")


if __name__ == "__main__":
    main()
