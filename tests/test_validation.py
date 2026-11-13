"""Synthetic fixtures for the validation engine; never market observations."""

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from services.validation import (ADEQUACY_GOOD_TRADES, ADEQUACY_MIN_TRADES,
                                 DEFAULT_COST_GRID, REFERENCE_COST,
                                 concentration, evaluate_validation,
                                 run_cost_grid, sample_adequacy,
                                 split_bars_temporal, summarize_cost_grid,
                                 worst_adequacy)

ORIGIN = datetime(2026, 1, 1, tzinfo=timezone.utc)


def minute_bars(count, start=ORIGIN):
    return [{"timestamp": (start + timedelta(minutes=i)).isoformat(),
             "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0}
            for i in range(count)]


def aggregated_bars(count=35, start=ORIGIN):
    return [{"timestamp": (start + timedelta(minutes=2 * i)).isoformat(),
             "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0}
            for i in range(count)]


def rules(side="buy", name="BOP"):
    return {"side": side, "setup_name": name, "tested_timeframe": "2m"}


def winning_signal(data, index, rule, tick):
    """One deterministic long order at the first bar the engine may read."""
    if index != 29:
        return None
    # A thin edge on purpose: it survives cheap costs and dies at the expensive corner.
    return {"entry": 101.5, "stop": 99.0, "target": 102.0,
            "signal_bar": data[index]["timestamp"]}


def trade(net_return_pct, label="t"):
    return {"side": "buy", "signal_time": label, "entry_time": label, "exit_time": label,
            "exit_reason": "target", "net_return_pct": net_return_pct}


class SplitTests(unittest.TestCase):
    def test_holdout_lies_entirely_after_training_and_nothing_is_shuffled(self):
        bars = minute_bars(100)
        split = split_bars_temporal(bars, 0.3)
        self.assertEqual(split["train_bar_count"] + split["holdout_bar_count"], len(bars))
        self.assertEqual(split["train_bars"], bars[:split["train_bar_count"]])
        self.assertEqual(split["holdout_bars"], bars[split["train_bar_count"]:])
        self.assertLess(split["train_end_utc"], split["holdout_start_utc"])
        self.assertEqual(split["cut_utc"], split["holdout_start_utc"])
        self.assertEqual(split["order"], "chronological_no_shuffle")
        for bar in split["holdout_bars"]:
            self.assertGreater(bar["timestamp"], split["train_end_utc"])

    def test_cut_snaps_back_to_a_complete_utc_block(self):
        bars = minute_bars(100, ORIGIN + timedelta(minutes=1))
        for block in (2, 5):
            split = split_bars_temporal(bars, 0.3, block_minutes=block)
            cut = datetime.fromisoformat(split["cut_utc"])
            self.assertEqual(int(cut.timestamp() // 60) % block, 0)
            self.assertLess(split["train_end_utc"], split["holdout_start_utc"])

    def test_degenerate_fractions_and_unordered_bars_are_refused(self):
        bars = minute_bars(20)
        for fraction in (0, 1, 1.5, -0.2, float("nan")):
            with self.assertRaisesRegex(ValueError, "fração out-of-sample"):
                split_bars_temporal(bars, fraction)
        shuffled = [bars[5]] + bars[:5] + bars[6:]
        with self.assertRaisesRegex(ValueError, "cronológica"):
            split_bars_temporal(shuffled, 0.3)


class CostGridTests(unittest.TestCase):
    def grid_on_one_trade(self):
        fixture = aggregated_bars()
        fixture[30].update(open=101.0, high=101.8, low=100.5, close=101.7)
        fixture[31].update(open=101.7, high=103.5, low=101.0, close=103.0)
        with patch("services.setup_backtest.signal_at", side_effect=winning_signal):
            return run_cost_grid(fixture, rules(), 0.01, DEFAULT_COST_GRID)

    def test_return_never_improves_as_cost_rises_over_the_same_bars(self):
        summary = summarize_cost_grid(self.grid_on_one_trade())
        returns = [row["net_return_pct"] for row in summary["scenarios"]]
        self.assertEqual({row["trade_count"] for row in summary["scenarios"]}, {1})
        self.assertEqual(returns, sorted(returns, reverse=True))
        self.assertTrue(summary["monotonic_in_cost"])
        self.assertGreater(summary["cheapest"]["net_return_pct"],
                           summary["most_expensive"]["net_return_pct"])

    def test_sign_change_between_cheapest_and_dearest_is_reported(self):
        summary = summarize_cost_grid(self.grid_on_one_trade())
        self.assertGreater(summary["cheapest"]["net_return_pct"], 0)
        self.assertLess(summary["most_expensive"]["net_return_pct"], 0)
        self.assertTrue(summary["sign_flips_with_cost"])
        self.assertEqual(summary["scenarios"][0]["cost_scenario"], "sensitivity_baseline_zero")

    def test_reference_cost_belongs_to_the_default_grid(self):
        self.assertIn(REFERENCE_COST, DEFAULT_COST_GRID)


class ConcentrationTests(unittest.TestCase):
    def test_one_dominant_trade_is_measured_and_flips_the_sign(self):
        metrics = {"trades": [trade(12.0, "best"), trade(-1.0), trade(-1.0), trade(-1.0)]}
        result = concentration(metrics)
        self.assertEqual(result["best_trade"]["net_return_pct"], 12.0)
        self.assertGreater(result["aggregate_net_return_pct"], 0)
        self.assertLess(result["net_return_pct_without_best"], 0)
        self.assertTrue(result["sign_flips_without_best"])
        self.assertGreater(result["contribution_share_pct"], 100)
        self.assertFalse(result["single_trade_explains_result"])

    def test_a_spread_result_does_not_flip_when_the_best_trade_is_removed(self):
        metrics = {"trades": [trade(2.0, "best"), trade(1.5), trade(1.0), trade(1.0)]}
        result = concentration(metrics)
        self.assertFalse(result["sign_flips_without_best"])
        self.assertGreater(result["net_return_pct_without_best"], 0)

    def test_single_trade_and_empty_series_are_labelled_not_hidden(self):
        single = concentration({"trades": [trade(3.0)]})
        self.assertTrue(single["single_trade_explains_result"])
        self.assertTrue(single["sign_flips_without_best"])
        self.assertAlmostEqual(single["net_return_pct_without_best"], 0.0)
        empty = concentration({"trades": []})
        self.assertFalse(empty["evaluated"])
        self.assertEqual(empty["trade_count"], 0)


class AdequacyTests(unittest.TestCase):
    def test_thresholds_change_exactly_at_ten_and_thirty(self):
        self.assertEqual(sample_adequacy(0), "insuficiente")
        self.assertEqual(sample_adequacy(ADEQUACY_MIN_TRADES - 1), "insuficiente")
        self.assertEqual(sample_adequacy(ADEQUACY_MIN_TRADES), "limitrofe")
        self.assertEqual(sample_adequacy(ADEQUACY_GOOD_TRADES - 1), "limitrofe")
        self.assertEqual(sample_adequacy(ADEQUACY_GOOD_TRADES), "adequada")
        self.assertEqual(sample_adequacy(ADEQUACY_GOOD_TRADES + 1), "adequada")

    def test_the_weaker_side_decides_the_label(self):
        self.assertEqual(worst_adequacy(["adequada", "insuficiente"]), "insuficiente")
        self.assertEqual(worst_adequacy(["adequada", "limitrofe"]), "limitrofe")
        self.assertEqual(worst_adequacy(["adequada", "adequada"]), "adequada")


class ProvenanceTests(unittest.TestCase):
    def test_validation_reuses_the_backtest_provenance_gate(self):
        draft = {"status": "draft", "rules_json": json.dumps({"engine": "setup_pattern_v1"})}
        with self.assertRaisesRegex(ValueError, "aprovada"):
            evaluate_validation(draft, 1, "2m")
        changed = {"id": 1, "version": 2, "status": "approved", "rules_json": json.dumps({
            "engine": "setup_pattern_v1", "approval": "rules_human_approved",
            "timeframes": ["2m"], "source": [{"path": "source.pdf", "sha256": "approved"}]})}
        with patch("services.setup_backtest.documents.library_status", return_value=[
                {"path": "source.pdf", "status": "stale", "record": {"sha256": "changed"}}]):
            with self.assertRaisesRegex(ValueError, "alterado"):
                evaluate_validation(changed, 1, "2m")


if __name__ == "__main__":
    unittest.main()
