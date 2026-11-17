"""Deterministic, temporary-database proof of the simulated paper cycle.

Only --prova is supported. Candles and signals here are synthetic fixtures, never market data.
"""

import argparse
import json
import math
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from database import store
from services import execution, market_data, pipeline, trade_management


ORIGIN = datetime(2026, 1, 1, tzinfo=timezone.utc)


def minute_bars(start=0, end=70, low=99.0):
    return [{"timestamp": (ORIGIN + timedelta(minutes=i)).isoformat(),
             "open": 100.0, "high": 101.0, "low": low, "close": 100.0,
             "volume": 1.0} for i in range(start, end)]


def signal(bars, index, rules, tick):
    return {"setup_id": "SETUP_DEMO", "side": "buy",
            "signal_bar": bars[index]["timestamp"], "valid_on_next_bar": True,
            "entry": 100.5, "stop": 98.0, "target": 103.0,
            "intrabar_conflict": "stop_first"}


def prove():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(store, "DB_PATH", Path(folder) / "delivery9.db"), patch(
            "services.setup_backtest.documents.library_status",
            return_value=[{"path": "synthetic-proof.pdf", "status": "indexed",
                           "record": {"sha256": "synthetic-proof"}}]):
            store.initialize()
            rules = {"engine": "setup_pattern_v1", "setup_id": "SETUP_DEMO",
                     "setup_name": "BOP", "side": "buy", "timeframes": ["2m"],
                     "approval": "rules_human_approved",
                     "source": [{"path": "synthetic-proof.pdf", "sha256": "synthetic-proof"}],
                     "pattern": {"kind": "three_countertrend_bars", "trend_ma": 20,
                                 "trend_slope_bars": 3},
                     "entry": {"kind": "next_bar_stop"}, "stop": {"kind": "known_before_entry"},
                     "target": {"kind": "half_retracement"}, "management": {},
                     "filters": {"session_hours": "pending_market_selection"}}
            strategy_id = store.save_strategy("BOP · prova sintética", rules, "user")
            store.approve_strategy(strategy_id)
            strategy = {"id": strategy_id, "status": "approved", "rules_json": json.dumps(rules)}
            for symbol in ("BTCUSDT", "ETHUSDT"):
                store.upsert_market_bars(market_data.PROVIDER, symbol, "1m", minute_bars())
            with patch("services.pipeline.signal_at", side_effect=signal):
                first = pipeline.run_pipeline(strategy, "BTCUSDT", "2m")
            assert first["estado"] == "ok" and first["status"] == "aguardando_quantidade"
            opened = execution.confirm_open(first["run_id"], 2.0)
            operation_id = opened["paper_operation_id"]
            assert len(store.list_paper_journal()) == 1
            assert store.list_paper_journal()[0]["state"] == "open"
            try:
                execution.confirm_open(first["run_id"], 2.0)
            except ValueError:
                pass
            else:
                raise AssertionError("Confirmação duplicada foi aceita")

            # The open BTC position plus a pending authorization reserve both risk slots.
            store.save_pipeline_run("pipeline_v1", strategy_id, "SETUP_RESERVA", "BOP",
                                    "ETHUSDT", "2m", "2026-01-01T00:10:00+00:00",
                                    "trade_candidate", risk_verdict="autorizado",
                                    status="aguardando_quantidade")
            with patch("services.pipeline.signal_at", side_effect=signal):
                denied = pipeline.run_pipeline(strategy, "ETHUSDT", "2m")
            denied_run = store.get_pipeline_run(denied["run_id"])
            assert denied_run["risk_verdict"] == "negado"
            assert "exposicao_excedida" in json.loads(denied_run["denial_reasons_json"])

            # A complete next block touches the stop. It is appended only after opening.
            store.upsert_market_bars(market_data.PROVIDER, "BTCUSDT", "1m",
                                     minute_bars(70, 72, low=97.0))
            replay = trade_management.replay_open_operations()
            assert len(replay) == 1 and replay[0]["estado"] == "fechada", replay
            operation = store.list_paper_operations()[0]
            journal = store.list_paper_journal()
            run = store.get_pipeline_run(first["run_id"])
            details = json.loads(journal[0]["details_json"])
            assert operation["id"] == operation_id and operation["state"] == "closed"
            assert journal[0]["state"] == "closed" and len(journal) == 1
            assert len(run["stages"]) == 8
            assert math.isclose(details["net_pnl"],
                                (operation["exit_price"] - operation["entry_price"]) * 2 - operation["fees"])
            assert math.isclose(details["realized_r"], run["realized_r"])
            assert trade_management.replay_open_operations() == []
            assert len(store.list_paper_journal()) == 1
            print("PROVA SINTETICA EM BANCO TEMPORARIO - nenhuma observacao de mercado")
            print(f"Sinal -> Risk autorizado -> entrada humana: operacao #{operation_id}, quantidade 2")
            print("Risk negou candidato concorrente: exposicao excedida")
            print(f"Conducao -> saida {operation['exit_reason']} -> diario unico #{journal[0]['id']}")
            print(f"Taxas simuladas: {operation['fees']:.6f} USDT; liquido: {details['net_pnl']:.6f} USDT; "
                  f"resultado: {run['realized_r']:.6f}R")
            print("Repeticao sem duplicacao: OK")


def main():
    parser = argparse.ArgumentParser(description="Prova da Entrega 9 em banco temporário")
    parser.add_argument("--prova", action="store_true", required=True)
    parser.parse_args()
    prove()


if __name__ == "__main__":
    main()
