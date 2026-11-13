"""Synthetic fixtures for historical execution rules; never market observations."""

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from services.setup_backtest import aggregate_minutes, simulate, run_approved


def bars(count=35, start=None):
    start = start or datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [{"timestamp": (start + timedelta(minutes=2 * i)).isoformat(),
             "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1}
            for i in range(count)]


def rules(side="buy", name="BOP"):
    return {"side": side, "setup_name": name, "tested_timeframe": "2m"}


def signal(data, index, rule, tick):
    if index != 29:
        return None
    return {"entry": 101.5, "stop": 99, "target": 103,
            "signal_bar": data[index]["timestamp"]}


class AggregationTests(unittest.TestCase):
    def test_incomplete_and_gap_blocks_are_reported(self):
        origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
        raw = [{"timestamp": (origin + timedelta(minutes=i)).isoformat(),
                "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1}
               for i in (0, 1, 4, 5, 6)]
        result, coverage = aggregate_minutes(raw, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(coverage["discarded_blocks"], 1)
        self.assertEqual(coverage["gaps_between_complete_blocks"], 1)


class ExecutionTests(unittest.TestCase):
    def test_next_bar_expiration_and_conflict(self):
        fixture = bars()
        with patch("services.setup_backtest.signal_at", side_effect=signal):
            expired = simulate(fixture, rules(), .01, 10, 5)
        self.assertEqual((expired["signal_count"], expired["expired_entries"]), (1, 1))
        fixture[30]["high"] = 102
        with patch("services.setup_backtest.signal_at", side_effect=signal):
            filled = simulate(fixture, rules(), .01, 10, 5)
        self.assertEqual(filled["trade_count"], 1)
        self.assertEqual(filled["trades"][0]["exit_reason"], "entry_bar_ambiguous_stop")
        self.assertEqual(filled["intrabar_conflicts"], 1)
        self.assertEqual(filled["trades"][0]["entry_time"], fixture[30]["timestamp"])

    def test_gap_open_and_costs_are_adverse_for_short(self):
        fixture = bars()
        fixture[30].update(open=98, high=101, low=97, close=98)
        def short_signal(data, index, rule, tick):
            if index == 29:
                return {"entry": 99, "stop": 101, "target": 95,
                        "signal_bar": data[index]["timestamp"]}
        with patch("services.setup_backtest.signal_at", side_effect=short_signal):
            report = simulate(fixture, rules("sell", "BDP"), .01, 10, 5)
        self.assertEqual(report["trade_count"], 1)
        self.assertLess(report["trades"][0]["entry_price"], 98)
        self.assertLess(report["trades"][0]["net_return_pct"],
                        report["trades"][0]["gross_return_pct"])

    def test_approval_required(self):
        strategy = {"status": "draft", "rules_json": json.dumps({"engine": "setup_pattern_v1"})}
        with self.assertRaisesRegex(ValueError, "aprovada"):
            run_approved(strategy, 1, "2m")

    def test_changed_pdf_blocks_execution_before_loading_data(self):
        strategy = {"status": "approved", "rules_json": json.dumps({
            "engine": "setup_pattern_v1", "approval": "rules_human_approved",
            "timeframes": ["2m"], "source": [{"path": "source.pdf", "sha256": "approved"}]})}
        with patch("services.setup_backtest.documents.library_status", return_value=[
            {"path": "source.pdf", "status": "stale", "record": {"sha256": "changed"}}]):
            with self.assertRaisesRegex(ValueError, "alterado"):
                run_approved(strategy, 1, "2m")

    def test_trailing_moves_only_after_two_favorable_closes(self):
        fixture = bars(36)
        fixture[30].update(open=101, high=102, low=100, close=101.5)
        fixture[31].update(open=101.5, high=102.5, low=100.5, close=102)
        fixture[32].update(open=102, high=103, low=101, close=102.5)
        fixture[33].update(open=102.5, high=103, low=100.4, close=101)
        def distant_target(data, index, rule, tick):
            item = signal(data, index, rule, tick)
            return {**item, "target": 110} if item else None
        with patch("services.setup_backtest.signal_at", side_effect=distant_target):
            report = simulate(fixture, rules("buy", "VBS"), .01, 10, 5)
        self.assertEqual(report["trailing_updates"], 1)
        self.assertEqual(report["trades"][0]["exit_reason"], "stop")
        self.assertGreater(report["trades"][0]["final_stop"], 99)


if __name__ == "__main__":
    unittest.main()
