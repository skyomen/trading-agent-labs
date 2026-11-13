import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from services.setup_signals import signal_at
from services import setup_specs
from database import store


def bar(index, price, volume=100):
    return {"timestamp": str(index), "open": price, "high": price + 1,
            "low": price - 1, "close": price + 0.2, "volume": volume}


class SetupSignalTests(unittest.TestCase):
    def rules(self, name, side):
        pullback = name in {"VBS", "VSS"}
        return {"engine": "setup_pattern_v1", "setup_name": name,
                "setup_id": name, "side": side,
                "pattern": ({"kind": "three_countertrend_bars", "trend_ma": 20,
                             "trend_slope_bars": 3} if pullback else
                            {"kind": "compressed_base", "trend_ma": 8,
                             "trend_slope_bars": 3, "min_bars": 3,
                             "max_bars": 8, "max_range_atr20": 1.5})}

    def test_pullback_pairs_emit_causal_orders(self):
        for name, side, direction in (("VBS", "buy", 1), ("VSS", "sell", -1)):
            with self.subTest(name=name):
                bars = [bar(i, 100 + direction * i * 1.1) for i in range(35)]
                last = 100 + direction * 35 * 1.1
                for step in range(3):
                    opening = last - direction * (step + 1)
                    bars.append({"timestamp": str(35 + step), "open": opening,
                                 "high": opening + 0.2, "low": opening - 1.2,
                                 "close": opening - direction * 0.8,
                                 "volume": 100})
                bars.append(bar(38, 140 if side == "buy" else 60))
                result = signal_at(bars, 37, self.rules(name, side), 0.1)
                self.assertIsNotNone(result)
                self.assertEqual(result["side"], side)
                self.assertEqual(result["signal_bar"], "37")
                self.assertGreater(direction * (result["target"] - result["entry"]), 0)

    def test_breakout_pairs_use_completed_base_and_prior_volume(self):
        for name, side, direction in (("BOP", "buy", 1), ("BDP", "sell", -1)):
            with self.subTest(name=name):
                bars = [bar(i, 100 + direction * i) for i in range(35)]
                center = 100 + direction * 34
                for i in range(35, 40):
                    bars.append({"timestamp": str(i), "open": center,
                                 "high": center + 0.3, "low": center - 0.3,
                                 "close": center, "volume": 10})
                bars.append(bar(40, center))
                result = signal_at(bars, 39, self.rules(name, side), 0.1)
                self.assertIsNotNone(result)
                self.assertEqual(result["side"], side)
                self.assertEqual(result["intrabar_conflict"], "stop_first")

    def test_invalid_tick_and_insufficient_history(self):
        rules = self.rules("BOP", "buy")
        with self.assertRaises(ValueError):
            signal_at([], 0, rules, 0)
        self.assertIsNone(signal_at([bar(i, 100 + i) for i in range(5)], 3, rules, 0.01))


class SetupApprovalTests(unittest.TestCase):
    def test_source_bound_drafts_and_human_approval_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(store, "DB_PATH", Path(tmp) / "test.db"):
            store.initialize()
            library = [{"path": path, "status": "indexed", "record": {"sha256": path[-8:]}}
                       for path in (setup_specs.SOURCE, setup_specs.SUPPLEMENT)]
            with patch.object(setup_specs.documents, "library_status", return_value=library):
                drafts = setup_specs.register_drafts()
                self.assertEqual(len(drafts), 4)
                self.assertEqual(setup_specs.register_drafts(), [])
                with self.assertRaises(ValueError):
                    store.approve_strategy(drafts[0])
                approved = setup_specs.promote_approved_rules("conversa:2026-11-13")
                self.assertEqual(len(approved), 4)
                self.assertEqual(setup_specs.promote_approved_rules("conversa:2026-11-13"), [])
                changed = [dict(item) for item in library]
                changed[0] = {**changed[0], "record": {"sha256": "changed-source"}}
                with patch.object(setup_specs.documents, "library_status", return_value=changed):
                    with self.assertRaises(ValueError):
                        setup_specs.promote_approved_rules("conversa:2026-11-13")
            rows = store.list_strategies()
            self.assertEqual(sum(row["status"] == "approved" for row in rows), 4)
            self.assertEqual(sum(row["status"] == "draft" for row in rows), 4)
            self.assertEqual({json.loads(row["rules_json"])["setup_id"] for row in rows},
                             {"SETUP_01", "SETUP_02", "SETUP_03", "SETUP_04"})
