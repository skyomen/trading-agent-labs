"""Run the Validation Engine once per approved combination and persist the reading.

Mirrors `scripts.run_delivery5`: the same four approved setups, the same two
verified crypto snapshots and the same two aggregation intervals, now split
into training and out-of-sample. A combination already persisted with the same
engine version and holdout fraction is reported, not repeated.
"""

import json

from database import store
from services.validation import ENGINE_VERSION, evaluate_validation

HOLDOUT_FRACTION = 0.3


def main():
    store.initialize()
    strategies = [row for row in store.list_strategies()
                  if row["status"] == "approved"
                  and json.loads(row["rules_json"]).get("setup_name") in {"VBS", "VSS", "BOP", "BDP"}]
    datasets = [row for row in store.list_historical_datasets()
                if row["symbol"] in {"BTCUSDT", "ETHUSDT"} and row["timeframe"] == "1m"]
    if len(strategies) != 4 or len(datasets) != 2:
        raise ValueError("A validação exige quatro regras aprovadas e dois snapshots cripto de 1m.")
    existing = store.list_validation_runs(limit=1000)
    for strategy in sorted(strategies, key=lambda row: row["id"]):
        name = json.loads(strategy["rules_json"])["setup_name"]
        for dataset in sorted(datasets, key=lambda row: row["symbol"]):
            for timeframe in ("2m", "5m"):
                already = [row for row in existing
                           if row["strategy_id"] == strategy["id"]
                           and row["dataset_id"] == dataset["id"]
                           and row["timeframe"] == timeframe
                           and row["engine_version"] == ENGINE_VERSION
                           and abs(row["holdout_fraction"] - HOLDOUT_FRACTION) < 1e-9]
                report = evaluate_validation(strategy, dataset["id"], timeframe, HOLDOUT_FRACTION)
                if already:
                    print(f"{name} {dataset['symbol']} {timeframe}: já persistido como #{already[0]['id']}")
                    continue
                run_id = store.save_validation_run(strategy["id"], dataset["symbol"], timeframe,
                                                   dataset["id"], dataset["sha256"], report)
                store.add_event("Strategy & Backtest", "INFO",
                                f"Validação #{run_id}: {name} {dataset['symbol']} {timeframe}; "
                                f"amostra {report['sample_adequacy']}; "
                                f"{report['split']['train']['reference_trade_count']} operações no treino e "
                                f"{report['split']['holdout']['reference_trade_count']} out-of-sample")
                print(f"{name} {dataset['symbol']} {timeframe}: amostra {report['sample_adequacy']}; "
                      f"treino {report['split']['train']['reference_trade_count']} operações, "
                      f"out-of-sample {report['split']['holdout']['reference_trade_count']}; "
                      f"{len(report['fragility_flags'])} sinais de fragilidade")


if __name__ == "__main__":
    main()
