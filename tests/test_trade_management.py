"""Synthetic fixtures for Trade Management (Entrega 8 / Fase 2); never market observations.

Reuses the style of tests/test_setup_backtest.py for the candle fixtures (bars()/signal()),
and the temporary-SQLite-database pattern of tests/test_pipeline.py for the store layer.
"""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from database import store
from services import market_data, setup_backtest, trade_management

ORIGIN = datetime(2026, 1, 1, tzinfo=timezone.utc)  # UTC midnight: epoch-minute divisible
                                                     # by both 2 and 5, so 2m/5m blocks align.


def bars(count=36, start=None):
    """2-minute-spaced candles, in the exact style of tests/test_setup_backtest.py::bars()."""
    start = start or ORIGIN
    return [{"timestamp": (start + timedelta(minutes=2 * i)).isoformat(),
             "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1}
            for i in range(count)]


def make_signal(entry, stop, target):
    """A signal_at replacement that fires once, at index 29 — same convention as
    tests/test_setup_backtest.py::signal(), so WARMUP_BARS (29) is satisfied the same way."""
    def _signal(data, index, rule, tick):
        if index != 29:
            return None
        return {"entry": entry, "stop": stop, "target": target,
                "signal_bar": data[index]["timestamp"]}
    return _signal


def expand_candles_to_raw(candles, minutes, suffix="+00:00"):
    """Expand 2m/5m-looking `candles` into the raw 1-minute bars that re-aggregate (via
    setup_backtest.aggregate_minutes) into exactly the same candles — each candle's OHLC is
    duplicated across `minutes` consecutive 1-minute sub-bars (open/close survive because the
    first/last sub-bar provide them; high/low survive because they are identical across the
    duplicates). `suffix` controls the timestamp's timezone marker ("+00:00" like most of the
    codebase, or "Z" like the real collector in services/market_data.py) to exercise both
    conventions."""
    raw = []
    for candle in candles:
        start = datetime.fromisoformat(candle["timestamp"])
        for minute in range(minutes):
            stamp = (start + timedelta(minutes=minute)).isoformat().replace("+00:00", suffix)
            raw.append({"timestamp": stamp, "open": candle["open"], "high": candle["high"],
                       "low": candle["low"], "close": candle["close"], "volume": 1.0})
    return raw


class TradeManagementTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.db_patch = patch.object(store, "DB_PATH", self.db)
        self.db_patch.start()
        store.initialize()

    def tearDown(self):
        self.db_patch.stop()
        self.tmp.cleanup()

    def seed_strategy(self, setup_name="BOP", side="buy", management=None):
        rules = {"engine": "setup_pattern_v1", "setup_id": "SETUP_01", "setup_name": setup_name,
                 "side": side, "timeframes": ["2m", "5m"], "approval": "rules_human_approved",
                 "management": management if management is not None else
                              {"trailing_after_favorable_closes": 2,
                               "trailing_reference": "previous_bar_extreme"}}
        strategy_id = store.save_strategy(f"{setup_name} · teste", rules, "user")
        store.approve_strategy(strategy_id)
        return strategy_id

    def seed_run(self, strategy_id, setup_name, side, signal_bar_utc, entry_price, stop, target,
                timeframe="2m", symbol="BTCUSDT", entry_bar_utc=None):
        plan = {"status": "ok", "entrada": entry_price, "side": side, "stop": stop, "alvo": target}
        if entry_bar_utc:
            plan["barra_de_entrada_utc"] = entry_bar_utc
        return store.save_pipeline_run(
            "pipeline_v1", strategy_id, "SETUP_01", setup_name, symbol, timeframe,
            signal_bar_utc, "trade_candidate", risk_verdict="autorizado",
            status="posicao_aberta", report={"execution": plan})

    def seed_open_operation(self, run_id, side, entry_price, symbol="BTCUSDT"):
        return store.open_paper_operation(symbol, side, 1.0, entry_price, "pipeline/test",
                                          pipeline_run_id=run_id)

    def seed_feed_from_candles(self, candles, minutes, symbol="BTCUSDT", suffix="+00:00"):
        raw = expand_candles_to_raw(candles, minutes, suffix=suffix)
        store.upsert_market_bars(market_data.PROVIDER, symbol, "1m", raw)

    def run_oracle(self, candles, side, setup_name, entry, stop, target, fee_bps=None,
                  slippage_bps=None):
        """Runs setup_backtest.simulate() over the full candle set — the trusted oracle for
        "the same conduction logic the backtest uses", per the Entrega 8 DEC."""
        fee_bps = trade_management.FEE_BPS if fee_bps is None else fee_bps
        slippage_bps = trade_management.SLIPPAGE_BPS if slippage_bps is None else slippage_bps
        rules = {"side": side, "setup_name": setup_name, "tested_timeframe": "2m"}
        with patch("services.setup_backtest.signal_at", side_effect=make_signal(entry, stop, target)):
            report = setup_backtest.simulate(candles, rules, 0.01, fee_bps, slippage_bps)
        self.assertEqual(report["trade_count"], 1, "cenário mal configurado: esperava 1 trade")
        return report["trades"][0]


class ReplayOperationClosedTests(TradeManagementTestBase):
    def _build_closed_scenario(self, setup_name, side, entry, stop, target, overrides,
                               management=None):
        candles = bars(36)
        for index, fields in overrides.items():
            candles[index].update(fields)
        expected = self.run_oracle(candles, side, setup_name, entry, stop, target)

        strategy_id = self.seed_strategy(setup_name, side, management=management)
        signal_bar_utc = candles[29]["timestamp"]
        run_id = self.seed_run(strategy_id, setup_name, side, signal_bar_utc,
                               expected["entry_price"], stop, target)
        operation_id = self.seed_open_operation(run_id, side, expected["entry_price"])

        # The live feed only ever needs the entry bar onward (the warm-up candles 0..29
        # existed only so simulate() could find its signal; trade_management never reads
        # them — it starts straight from the entry bar, per the DEC).
        self.seed_feed_from_candles(candles[30:], minutes=2)

        operation = store.list_paper_operations(state="open")[0]
        self.assertEqual(operation["id"], operation_id)
        return operation, run_id, expected

    def test_closes_by_stop_with_parity_to_simulate(self):
        overrides = {30: {"open": 100, "high": 102, "low": 99.5, "close": 101},
                    31: {"open": 101, "high": 101, "low": 97, "close": 98}}
        operation, run_id, expected = self._build_closed_scenario(
            "BOP", "buy", 101.5, 99.0, 200.0, overrides)

        result = trade_management.replay_operation(operation)

        self.assertEqual(result["estado"], "fechada")
        self.assertEqual(result["exit_reason"], "stop")
        self.assertEqual(expected["exit_reason"], "stop")
        self.assertAlmostEqual(result["trade"]["exit_price"], expected["exit_price"])
        self.assertAlmostEqual(result["trade"]["net_return_pct"], expected["net_return_pct"])
        self.assertEqual(result["trade"]["trailing_updates"], 0)

        stored = store.list_paper_operations()[0]
        self.assertEqual(stored["state"], "closed")
        self.assertEqual(stored["exit_reason"], "stop")
        self.assertAlmostEqual(stored["exit_price"], expected["exit_price"])
        run = store.get_pipeline_run(run_id)
        self.assertIsNotNone(run["realized_r"])
        unidade_r = abs(expected["entry_price"] - 99.0)
        expected_r = (expected["exit_price"] - expected["entry_price"]) / unidade_r
        self.assertAlmostEqual(run["realized_r"], expected_r)
        self.assertEqual(len(run["stages"]), 1)
        self.assertEqual(run["stages"][0]["stage_index"], trade_management.CONDUCTION_STAGE_INDEX)

    def test_closes_by_target_with_parity_to_simulate_and_positive_r(self):
        overrides = {30: {"open": 100, "high": 102, "low": 99.5, "close": 101},
                    31: {"open": 102, "high": 104, "low": 101, "close": 103.5}}
        operation, run_id, expected = self._build_closed_scenario(
            "BOP", "buy", 101.5, 90.0, 103.0, overrides)

        result = trade_management.replay_operation(operation)

        self.assertEqual(result["estado"], "fechada")
        self.assertEqual(result["exit_reason"], "target")
        self.assertEqual(expected["exit_reason"], "target")
        self.assertAlmostEqual(result["trade"]["exit_price"], expected["exit_price"])
        self.assertGreater(result["realized_r"], 0)

        run = store.get_pipeline_run(run_id)
        self.assertGreater(run["realized_r"], 0)
        self.assertEqual(store.list_paper_operations()[0]["state"], "closed")

    def test_closes_by_trailing_stop_matches_backtest_trailing_fixture(self):
        # Adapted, bit-for-bit, from
        # tests/test_setup_backtest.py::test_trailing_moves_only_after_two_favorable_closes.
        overrides = {
            30: {"open": 101, "high": 102, "low": 100, "close": 101.5},
            31: {"open": 101.5, "high": 102.5, "low": 100.5, "close": 102},
            32: {"open": 102, "high": 103, "low": 101, "close": 102.5},
            33: {"open": 102.5, "high": 103, "low": 100.4, "close": 101},
        }
        operation, run_id, expected = self._build_closed_scenario(
            "VBS", "buy", 101.5, 99.0, 110.0, overrides)
        self.assertEqual(expected["trailing_updates"], 1)
        self.assertEqual(expected["exit_reason"], "stop")  # raw motor reason, per the fixture
        self.assertGreater(expected["final_stop"], 99.0)

        result = trade_management.replay_operation(operation)

        self.assertEqual(result["estado"], "fechada")
        # Persisted label differs from the motor's raw reason because the stop moved.
        self.assertEqual(result["exit_reason"], "trailing_stop")
        self.assertEqual(result["trade"]["exit_reason"], "stop")  # raw, unmodified
        self.assertEqual(result["trade"]["trailing_updates"], 1)
        self.assertAlmostEqual(result["trade"]["final_stop"], expected["final_stop"])
        self.assertAlmostEqual(result["trade"]["exit_price"], expected["exit_price"])

        stored = store.list_paper_operations()[0]
        self.assertEqual(stored["exit_reason"], "trailing_stop")
        run = store.get_pipeline_run(run_id)
        self.assertIsNotNone(run["realized_r"])


class ReplayOperationOpenTests(TradeManagementTestBase):
    def test_em_curso_when_bars_are_insufficient_to_close_and_nothing_is_written(self):
        candles = bars(4)  # candle[0] is the entry bar; none of them ever hit stop/target.
        strategy_id = self.seed_strategy("BOP", "buy")
        signal_bar_utc = (ORIGIN - timedelta(minutes=2)).isoformat()
        run_id = self.seed_run(strategy_id, "BOP", "buy", signal_bar_utc,
                               101.5, 50.0, 500.0, entry_bar_utc=candles[0]["timestamp"])
        operation_id = self.seed_open_operation(run_id, "buy", 101.5)
        self.seed_feed_from_candles(candles, minutes=2)

        operation = store.list_paper_operations(state="open")[0]
        result = trade_management.replay_operation(operation)

        self.assertEqual(result["estado"], "em_curso")
        self.assertIn("barras_avaliadas", result)
        self.assertEqual(result["trailing_updates"], 0)

        self.assertEqual(store.list_paper_operations(state="open")[0]["id"], operation_id)
        self.assertIsNone(store.get_pipeline_run(run_id)["realized_r"])
        self.assertEqual(store.get_pipeline_run(run_id)["stages"], [])

    def test_trailing_does_not_generalize_to_declared_management_for_non_vbs_vss_setups(self):
        candles = bars(4)
        candles[0].update(open=100, high=101, low=99, close=100.5)   # entry bar
        candles[1].update(open=100.5, high=102, low=100, close=101.5)  # favorable close #1
        candles[2].update(open=101.5, high=103, low=101, close=102.5)  # favorable close #2
        candles[3].update(open=102.5, high=104, low=102, close=103.5)  # favorable close #3

        strategy_id = self.seed_strategy(
            "BOP", "buy",
            management={"trailing_after_favorable_closes": 2,
                        "trailing_reference": "previous_bar_extreme"})
        signal_bar_utc = (ORIGIN - timedelta(minutes=2)).isoformat()
        run_id = self.seed_run(strategy_id, "BOP", "buy", signal_bar_utc,
                               100.5, 90.0, 500.0, entry_bar_utc=candles[0]["timestamp"])
        self.seed_open_operation(run_id, "buy", 100.5)
        self.seed_feed_from_candles(candles, minutes=2)

        operation = store.list_paper_operations(state="open")[0]
        result = trade_management.replay_operation(operation)

        self.assertEqual(result["estado"], "em_curso")
        self.assertEqual(result["trailing_updates"], 0,
                         "trailing nunca deveria mexer para um setup fora de {VBS, VSS}, "
                         "mesmo com rules_json.management declarado")


class ReplayOperationDegradedTests(TradeManagementTestBase):
    def test_non_open_operation_is_not_applicable(self):
        strategy_id = self.seed_strategy()
        run_id = self.seed_run(strategy_id, "BOP", "buy", ORIGIN.isoformat(), 101.5, 99, 200)
        operation_id = self.seed_open_operation(run_id, "buy", 101.5)
        store.close_paper_operation(operation_id, 101.5, "manual", ORIGIN.isoformat())
        operation = store.list_paper_operations()[0]

        self.assertEqual(trade_management.replay_operation(operation), {"estado": "nao_aplicavel"})

    def test_operation_without_pipeline_run_id_is_sem_trilha(self):
        operation_id = store.open_paper_operation("BTCUSDT", "buy", 1.0, 101.5, "manual")
        operation = store.list_paper_operations()[0]
        self.assertIsNone(operation["pipeline_run_id"])
        self.assertEqual(operation["id"], operation_id)

        self.assertEqual(trade_management.replay_operation(operation), {"estado": "sem_trilha"})

    def test_empty_feed_is_sem_feed_without_writing(self):
        strategy_id = self.seed_strategy()
        run_id = self.seed_run(strategy_id, "BOP", "buy", ORIGIN.isoformat(), 101.5, 99, 200)
        self.seed_open_operation(run_id, "buy", 101.5)
        operation = store.list_paper_operations()[0]

        result = trade_management.replay_operation(operation)

        self.assertEqual(result, {"estado": "sem_feed"})
        self.assertEqual(store.list_paper_operations()[0]["state"], "open")
        self.assertIsNone(store.get_pipeline_run(run_id)["realized_r"])

    def test_only_the_entry_bar_in_the_feed_is_sem_barra_nova(self):
        candles = bars(1)
        strategy_id = self.seed_strategy()
        signal_bar_utc = (ORIGIN - timedelta(minutes=2)).isoformat()
        run_id = self.seed_run(strategy_id, "BOP", "buy", signal_bar_utc, 101.5, 50, 500,
                               entry_bar_utc=candles[0]["timestamp"])
        self.seed_open_operation(run_id, "buy", 101.5)
        self.seed_feed_from_candles(candles, minutes=2)
        operation = store.list_paper_operations()[0]

        result = trade_management.replay_operation(operation)

        self.assertEqual(result, {"estado": "sem_barra_nova"})
        self.assertEqual(store.list_paper_operations()[0]["state"], "open")
        self.assertIsNone(store.get_pipeline_run(run_id)["realized_r"])


class ReplayOperationIdempotencyTests(TradeManagementTestBase):
    def test_second_replay_of_an_already_closed_operation_writes_nothing_again(self):
        candles = bars(36)
        candles[30].update(open=100, high=102, low=99.5, close=101)
        candles[31].update(open=101, high=101, low=97, close=98)
        expected = self.run_oracle(candles, "buy", "BOP", 101.5, 99.0, 200.0)

        strategy_id = self.seed_strategy("BOP", "buy")
        run_id = self.seed_run(strategy_id, "BOP", "buy", candles[29]["timestamp"],
                               expected["entry_price"], 99.0, 200.0)
        self.seed_open_operation(run_id, "buy", expected["entry_price"])
        self.seed_feed_from_candles(candles[30:], minutes=2)

        first = trade_management.replay_operation(store.list_paper_operations(state="open")[0])
        self.assertEqual(first["estado"], "fechada")

        events_after_first = len(store.list_events())
        stages_after_first = len(store.get_pipeline_run(run_id)["stages"])

        closed_operation = store.list_paper_operations()[0]
        self.assertEqual(closed_operation["state"], "closed")
        second = trade_management.replay_operation(closed_operation)

        self.assertIn(second["estado"], {"ja_fechada", "nao_aplicavel"})
        self.assertEqual(len(store.list_events()), events_after_first)
        self.assertEqual(len(store.get_pipeline_run(run_id)["stages"]), stages_after_first)
        self.assertEqual(len(store.list_paper_operations()), 1)


class ReplayOperationTimestampSuffixTests(TradeManagementTestBase):
    def test_entry_bar_is_found_when_the_feed_uses_the_real_collectors_z_suffix(self):
        candles = bars(36)
        candles[30].update(open=100, high=102, low=99.5, close=101)
        candles[31].update(open=101, high=101, low=97, close=98)
        expected = self.run_oracle(candles, "buy", "BOP", 101.5, 99.0, 200.0)

        strategy_id = self.seed_strategy("BOP", "buy")
        run_id = self.seed_run(strategy_id, "BOP", "buy", candles[29]["timestamp"],
                               expected["entry_price"], 99.0, 200.0)
        self.seed_open_operation(run_id, "buy", expected["entry_price"])
        # The real collector (services/market_data.py::_stamp) writes a trailing "Z", never
        # "+00:00" — reproduce that convention for the whole window here.
        self.seed_feed_from_candles(candles[30:], minutes=2, suffix="Z")

        operation = store.list_paper_operations(state="open")[0]
        result = trade_management.replay_operation(operation)

        self.assertEqual(result["estado"], "fechada")
        self.assertEqual(result["exit_reason"], "stop")
        self.assertAlmostEqual(result["trade"]["exit_price"], expected["exit_price"])
        self.assertEqual(store.list_paper_operations()[0]["state"], "closed")


class ReplayOpenOperationsTests(TradeManagementTestBase):
    def test_replay_open_operations_tags_every_result_with_its_operation_id(self):
        strategy_id = self.seed_strategy()
        run_id = self.seed_run(strategy_id, "BOP", "buy", ORIGIN.isoformat(), 101.5, 99, 200)
        operation_id = self.seed_open_operation(run_id, "buy", 101.5)
        # No feed seeded on purpose — exercises the "sem_feed" path through the batch runner.

        results = trade_management.replay_open_operations()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["operation_id"], operation_id)
        self.assertEqual(results[0]["estado"], "sem_feed")


if __name__ == "__main__":
    unittest.main()
