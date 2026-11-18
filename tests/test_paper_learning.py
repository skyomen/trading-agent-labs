"""Synthetic paper fixtures for the local learning gate; never market observations."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from database import store
from services import paper_learning
from tests.test_app import APP_PATH


class PaperLearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(store, "DB_PATH", Path(self.tmp.name) / "learning.db")
        self.db_patch.start()
        self.identity_patch = patch.object(store, "IDENTITY_DB_PATH", Path(self.tmp.name) / "identity.db")
        self.identity_patch.start()
        self.global_patch = patch.object(store, "GLOBAL_DB_PATH", Path(self.tmp.name) / "global.db")
        self.global_patch.start()
        store.initialize()
        self.owner_id = store.create_identity_user("test_owner", "testhash",
                                                   "dGVzdHNhbHQxMjM0NTY3OA==", "owner")
        self.rules = {"engine": "setup_pattern_v1", "setup_id": "SETUP_03",
                      "setup_name": "BOP", "side": "buy", "timeframes": ["2m"],
                      "approval": "rules_human_approved",
                      "source": [{"path": "fixture.pdf", "sha256": "fixture"}],
                      "pattern": {"kind": "compressed_base", "min_bars": 3},
                      "entry": {"kind": "next_bar_stop"}, "stop": {"ticks": 2},
                      "target": {"r": 2}, "management": {}, "filters": {}}
        self.strategy_id = store.save_strategy("BOP · fixture", self.rules, "teste")
        store.approve_strategy(self.strategy_id)

    def tearDown(self):
        self.global_patch.stop()
        self.identity_patch.stop()
        self.db_patch.stop()
        self.tmp.cleanup()

    def seed_trade(self, index, day=0, symbol="BTCUSDT", corrupt=False):
        signal_dt = datetime(2026, 1, 1 + day, 10, tzinfo=timezone.utc) + timedelta(minutes=2 * index)
        signal_at = signal_dt.isoformat()
        entry_at = (signal_dt + timedelta(minutes=2)).isoformat()
        entry, exit_price, quantity, fees = 100.0, 102.0 if index % 2 else 98.0, 2.0, 0.4
        net_pnl = (exit_price - entry) * quantity - fees
        realized_r = net_pnl / (2.0 * quantity)
        report = {"execution": {"entrada": entry, "side": "buy", "stop": 98.0,
                                "alvo": 104.0, "barra_de_entrada_utc": entry_at}}
        run_id = store.save_pipeline_run("pipeline_v1", self.strategy_id, "SETUP_03", "BOP",
                                         symbol, "2m", signal_at, "trade_candidate",
                                         risk_verdict="autorizado", status="posicao_aberta",
                                         report=report)
        op_id = store.open_paper_operation(symbol, "buy", quantity, entry, "synthetic proof",
                                           pipeline_run_id=run_id)
        stage = {"stage_index": 8, "stage": "conduction", "agent": "Execution Agent",
                 "status": "ok", "summary": "fixture", "input": {}, "output": {},
                 "limitations": []}
        store.close_paper_operation(op_id, exit_price, "target" if index % 2 else "stop",
                                    (signal_dt + timedelta(minutes=4)).isoformat(),
                                    fees=fees, realized_r=realized_r,
                                    journal_details={"exit_time": (signal_dt + timedelta(minutes=4)).isoformat(),
                                                     "conduction": {"exit_reason": "target"},
                                                     "quote_currency": "USDT", "net_pnl":
                                                     net_pnl + (1 if corrupt else 0)},
                                    conduction_stage=stage)
        return op_id

    def test_zero_and_short_cohorts_never_generate_hypothesis(self):
        empty = paper_learning.analyze_cohort(self.strategy_id, "BTCUSDT", "2m")
        self.assertEqual(empty["state"], "insufficient")
        for index in range(29):
            self.seed_trade(index, day=index // 15)
        short = paper_learning.analyze_cohort(self.strategy_id, "BTCUSDT", "2m")
        self.assertEqual(short["closed_count"], 29)
        self.assertEqual(short["state"], "insufficient")
        self.assertEqual(store.list_paper_learning_proposals(), [])

    def test_two_day_gate_and_proposal_review_and_draft(self):
        for index in range(30):
            self.seed_trade(index)
        same_day = paper_learning.analyze_cohort(self.strategy_id, "BTCUSDT", "2m")
        self.assertEqual(same_day["state"], "insufficient")
        self.assertEqual(same_day["utc_days"], 1)
        # A different symbol does not make this cohort eligible.
        self.seed_trade(0, day=1, symbol="ETHUSDT")
        self.assertEqual(paper_learning.cohort_status(self.strategy_id, "BTCUSDT", "2m")["utc_days"], 1)
        self.seed_trade(0, day=1)
        first = paper_learning.analyze_cohort(self.strategy_id, "BTCUSDT", "2m")
        second = paper_learning.analyze_cohort(self.strategy_id, "BTCUSDT", "2m")
        self.assertEqual(first["proposal_id"], second["proposal_id"])
        self.assertEqual(len(store.list_paper_learning_proposals()), 1)
        proposal = store.get_paper_learning_proposal(first["proposal_id"])
        evidence = json.loads(proposal["evidence_json"])
        self.assertEqual(len(evidence["operation_ids"]), 31)
        self.assertEqual(len(set(evidence["operation_ids"])), 31)
        self.assertEqual(evidence["summary"]["trailing_count"], 0)
        self.assertEqual(evidence["summary"]["market_context_available_count"], 0)
        self.assertIn("Condução com trailing", proposal["observation"])
        self.assertIn("Investigar", proposal["hypothesis"])
        self.assertIn("não prova de robustez", proposal["limitations_json"])
        self.assertFalse(store.review_paper_learning_proposal(99999, True))
        self.assertTrue(store.review_paper_learning_proposal(proposal["id"], True))
        self.assertFalse(store.review_paper_learning_proposal(proposal["id"], False))
        self.assertEqual(store.get_paper_learning_proposal(proposal["id"])["status"], "approved")
        self.assertEqual(store.list_memories(), [])
        self.assertEqual(len(store.list_strategies()), 1)

        changed = json.loads(json.dumps(self.rules))
        changed["pattern"]["min_bars"] = 4
        draft_id = paper_learning.create_draft(proposal["id"], changed)
        draft = store.get_strategy(draft_id)
        self.assertEqual(draft["status"], "draft")
        self.assertEqual(draft["version"], 2)
        self.assertEqual(store.get_strategy(self.strategy_id)["status"], "approved")
        self.assertEqual(json.loads(draft["rules_json"])["approval"],
                         "paper_learning_draft_pending_review")
        with self.assertRaises(ValueError):
            store.approve_strategy(draft_id)
        with self.assertRaises(ValueError):
            paper_learning.create_draft(proposal["id"], changed)

    def test_corrupt_journal_and_source_edits_do_not_pass(self):
        for index in range(30):
            self.seed_trade(index, day=index // 15, corrupt=index == 0)
        status = paper_learning.analyze_cohort(self.strategy_id, "BTCUSDT", "2m")
        self.assertEqual(status["closed_count"], 29)
        self.assertEqual(status["state"], "insufficient")
        self.seed_trade(30, day=1)
        result = paper_learning.analyze_cohort(self.strategy_id, "BTCUSDT", "2m")
        self.assertEqual(result["state"], "proposed")
        store.review_paper_learning_proposal(result["proposal_id"], True)
        changed = json.loads(json.dumps(self.rules))
        changed["source"] = [{"path": "other.pdf", "sha256": "other"}]
        with self.assertRaises(ValueError):
            paper_learning.create_draft(result["proposal_id"], changed)

    def test_approved_proposal_refuses_changed_evidence_before_draft(self):
        for index in range(30):
            self.seed_trade(index, day=index // 15)
        result = paper_learning.analyze_cohort(self.strategy_id, "BTCUSDT", "2m")
        store.review_paper_learning_proposal(result["proposal_id"], True)
        with store.connect() as conn:
            row = conn.execute("SELECT id,details_json FROM paper_journal ORDER BY id LIMIT 1").fetchone()
            details = json.loads(row["details_json"])
            details["net_pnl"] += 1
            conn.execute("UPDATE paper_journal SET details_json=? WHERE id=?",
                         (json.dumps(details), row["id"]))
        changed = json.loads(json.dumps(self.rules))
        changed["pattern"]["min_bars"] = 4
        with self.assertRaisesRegex(ValueError, "Evidência paper mudou"):
            paper_learning.create_draft(result["proposal_id"], changed)

    def test_rejection_is_persisted_and_cannot_create_draft(self):
        for index in range(30):
            self.seed_trade(index, day=index // 15)
        result = paper_learning.analyze_cohort(self.strategy_id, "BTCUSDT", "2m")
        self.assertTrue(store.review_paper_learning_proposal(result["proposal_id"], False))
        self.assertFalse(store.review_paper_learning_proposal(result["proposal_id"], True))
        self.assertEqual(store.get_paper_learning_proposal(result["proposal_id"])["status"], "rejected")
        changed = json.loads(json.dumps(self.rules))
        changed["pattern"]["min_bars"] = 4
        with self.assertRaises(ValueError):
            paper_learning.create_draft(result["proposal_id"], changed)

    def test_lab_review_and_draft_actions(self):
        for index in range(30):
            self.seed_trade(index, day=index // 15)
        result = paper_learning.analyze_cohort(self.strategy_id, "BTCUSDT", "2m")
        app = AppTest.from_file(str(APP_PATH))
        app.session_state["auth-user"] = {"id": self.owner_id, "username": "test_owner", "role": "owner"}
        app.session_state["vault-key"] = bytes(32)
        app.query_params["lab"] = "1"
        app.session_state["tal-view"] = "Orquestração"
        app.run()
        self.assertFalse(app.exception)
        next(button for button in app.button if button.label == "Aprovar hipótese").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(store.get_paper_learning_proposal(result["proposal_id"])["status"], "approved")
        edited = json.loads(json.dumps(self.rules))
        edited["pattern"]["min_bars"] = 4
        next(area for area in app.text_area if area.label == "Regras editadas da nova versão (JSON)").set_value(
            json.dumps(edited, ensure_ascii=False))
        next(button for button in app.button if button.label == "Criar versão como rascunho").click().run()
        self.assertFalse(app.exception)
        proposal = store.get_paper_learning_proposal(result["proposal_id"])
        self.assertIsNotNone(proposal["draft_strategy_id"])
        self.assertEqual(store.get_strategy(proposal["draft_strategy_id"])["status"], "draft")


if __name__ == "__main__":
    unittest.main()
