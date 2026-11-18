"""Synthetic fixtures for the Agent Orchestration pipeline (Entrega 7 / Fase 2).

Never market observations: bars are flat and deterministic, and `signal_at`
is always mocked (pipeline.run_pipeline calls it exactly once per
evaluation, at a single predetermined bar, so there is no need to replicate
the real setup-pattern arithmetic here — only `services/setup_signals.py`'s
and `services/setup_backtest.py`'s own test suites do that).
"""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from database import store
from services import decision, execution, market_data, pipeline, risk

ORIGIN = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_rules(setup_name="VBS", side="buy", setup_id="SETUP_01"):
    return {
        "engine": "setup_pattern_v1", "setup_id": setup_id, "setup_name": setup_name,
        "side": side, "timeframes": ["2m", "5m"],
        "source": [{"path": "source.pdf", "sha256": "approved", "pages": [1, 2]}],
        "pattern": {"kind": "three_countertrend_bars", "trend_ma": 20, "trend_slope_bars": 3},
        "entry": {"kind": "next_bar_stop"}, "stop": {"kind": "known_before_entry"},
        "target": {"kind": "half_retracement"},
        "management": {"trailing_after_favorable_closes": 2,
                       "trailing_reference": "previous_bar_extreme"},
        "filters": {"session_hours": "pending_market_selection", "tick_size": "required_from_dataset"},
        "costs": {"fees_spread_slippage": "required_per_backtest"},
        "intrabar_conflict": "stop_first",
        "approval": "rules_human_approved",
    }


def raw_minute_bars(count=70, start=None, price=100.0):
    start = start or ORIGIN
    return [{"timestamp": (start + timedelta(minutes=i)).isoformat(),
             "open": price, "high": price + 1, "low": price - 1, "close": price,
             "volume": 10.0} for i in range(count)]


def signal_mock(entry, stop, target, side="buy", setup_id="SETUP_01", conflict="stop_first"):
    """A `signal_at` replacement that always finds a signal at whatever bar it is asked about."""
    def _mock(bars, index, rules, tick):
        return {"setup_id": setup_id, "side": side, "signal_bar": bars[index]["timestamp"],
                "valid_on_next_bar": True, "entry": entry, "stop": stop, "target": target,
                "intrabar_conflict": conflict}
    return _mock


def no_signal_mock(bars, index, rules, tick):
    return None


class PipelineTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.db_patch = patch.object(store, "DB_PATH", self.db)
        self.db_patch.start()
        store.initialize()
        self.docs_patch = patch(
            "services.setup_backtest.documents.library_status",
            return_value=[{"path": "source.pdf", "status": "indexed",
                          "record": {"sha256": "approved"}}])
        self.docs_patch.start()

    def tearDown(self):
        self.docs_patch.stop()
        self.db_patch.stop()
        self.tmp.cleanup()

    def approved_strategy(self, rules=None):
        rules = rules if rules is not None else make_rules()
        strategy_id = store.save_strategy("VBS · teste", rules, "user")
        store.approve_strategy(strategy_id)
        return {"id": strategy_id, "status": "approved", "rules_json": json.dumps(rules)}

    def seed_feed(self, symbol="BTCUSDT", count=70, start=None):
        store.upsert_market_bars(market_data.PROVIDER, symbol, "1m", raw_minute_bars(count, start))


class RunPipelineTests(PipelineTestBase):
    def test_happy_path_records_full_trail_and_awaits_quantity(self):
        strategy = self.approved_strategy()
        self.seed_feed()
        with patch("services.pipeline.signal_at", side_effect=signal_mock(100.5, 98.0, 103.0)):
            result = pipeline.run_pipeline(strategy, "BTCUSDT", "2m")
        self.assertEqual(result["estado"], "ok")
        run = store.get_pipeline_run(result["run_id"])
        self.assertEqual(len(run["stages"]), 7)
        self.assertEqual(run["decision"], "trade_candidate")
        self.assertEqual(run["risk_verdict"], "autorizado")
        self.assertEqual(run["status"], "aguardando_quantidade")
        self.assertIsNotNone(run["pending_since"])
        self.assertEqual({stage["stage"] for stage in run["stages"]},
                         {key for key, _ in pipeline.STAGES})

    def test_no_bars_returns_sem_feed_without_writing(self):
        strategy = self.approved_strategy()
        result = pipeline.run_pipeline(strategy, "BTCUSDT", "2m")
        self.assertEqual(result, {"estado": "sem_feed"})
        self.assertEqual(store.counts()["pipeline_runs"], 0)

    def test_insufficient_aggregated_history_returns_without_writing(self):
        strategy = self.approved_strategy()
        self.seed_feed(count=40)  # 40 raw 1m bars -> ~19-20 aggregated 2m blocks, < 30 required
        result = pipeline.run_pipeline(strategy, "BTCUSDT", "2m")
        self.assertEqual(result["estado"], "historico_insuficiente")
        self.assertIn("faltam", result)
        self.assertEqual(store.counts()["pipeline_runs"], 0)

    def test_same_signal_bar_does_not_duplicate_the_trail(self):
        strategy = self.approved_strategy()
        self.seed_feed()
        with patch("services.pipeline.signal_at", side_effect=signal_mock(100.5, 98.0, 103.0)):
            first = pipeline.run_pipeline(strategy, "BTCUSDT", "2m")
            second = pipeline.run_pipeline(strategy, "BTCUSDT", "2m")
        self.assertEqual(first["estado"], "ok")
        self.assertEqual(second, {"estado": "sem_barra_nova"})
        self.assertEqual(store.counts()["pipeline_runs"], 1)

    def test_no_signal_records_sem_oportunidade_with_all_stages(self):
        strategy = self.approved_strategy()
        self.seed_feed()
        with patch("services.pipeline.signal_at", side_effect=no_signal_mock):
            result = pipeline.run_pipeline(strategy, "BTCUSDT", "2m")
        run = store.get_pipeline_run(result["run_id"])
        self.assertEqual(run["status"], "sem_oportunidade")
        self.assertEqual(run["decision"], "no_trade")
        self.assertEqual(run["risk_verdict"], "nao_avaliado")
        self.assertEqual(len(run["stages"]), 7)
        by_stage = {stage["stage"]: stage["status"] for stage in run["stages"]}
        self.assertEqual(by_stage["risk"], "nao_executado")
        self.assertEqual(by_stage["execution"], "nao_executado")

    def test_signal_without_trigger_records_entrada_nao_acionada(self):
        strategy = self.approved_strategy()
        self.seed_feed()
        # entry far above anything the flat synthetic bars reach: never triggers.
        with patch("services.pipeline.signal_at", side_effect=signal_mock(1000.0, 900.0, 1100.0)):
            result = pipeline.run_pipeline(strategy, "BTCUSDT", "2m")
        run = store.get_pipeline_run(result["run_id"])
        self.assertEqual(run["status"], "entrada_nao_acionada")
        self.assertEqual(run["decision"], "no_trade")
        self.assertEqual(run["risk_verdict"], "nao_avaliado")

    def test_changed_source_pdf_propagates_before_any_write(self):
        strategy = self.approved_strategy()
        self.seed_feed()
        with patch("services.setup_backtest.documents.library_status",
                   return_value=[{"path": "source.pdf", "status": "stale",
                                 "record": {"sha256": "changed"}}]):
            with self.assertRaisesRegex(ValueError, "alterad|ausente"):
                pipeline.run_pipeline(strategy, "BTCUSDT", "2m")
        self.assertEqual(store.counts()["pipeline_runs"], 0)

    def test_exposure_limit_denies_a_third_candidate(self):
        strategy = self.approved_strategy()
        self.seed_feed()
        other_run = store.save_pipeline_run(
            pipeline.PIPELINE_VERSION, strategy["id"], "SEED-1", "VBS", "ETHUSDT", "2m",
            "2026-01-01T00:00:00+00:00", "trade_candidate", risk_verdict="autorizado",
            status="posicao_aberta")
        store.open_paper_operation("ETHUSDT", "buy", 1.0, 3000.0, "seed", pipeline_run_id=other_run)
        store.save_pipeline_run(
            pipeline.PIPELINE_VERSION, strategy["id"], "SEED-2", "VBS", "ETHUSDT", "5m",
            "2026-01-01T00:05:00+00:00", "trade_candidate", risk_verdict="autorizado",
            status="aguardando_quantidade")
        with patch("services.pipeline.signal_at", side_effect=signal_mock(100.5, 98.0, 103.0)):
            result = pipeline.run_pipeline(strategy, "BTCUSDT", "2m")
        run = store.get_pipeline_run(result["run_id"])
        self.assertEqual(run["risk_verdict"], "negado")
        self.assertIn("exposicao_excedida", json.loads(run["denial_reasons_json"]))
        self.assertEqual(run["status"], "avaliado")
        self.assertNotIn("mercado_fora_das_regras", json.loads(run["denial_reasons_json"]))


class RiskManagerTests(PipelineTestBase):
    def _candidate(self, **overrides):
        base = {"entry_price": 100.5, "stop": 98.0, "target": 103.0, "side": "buy",
                "signal_bar": "2026-03-01T10:00:00+00:00"}
        base.update(overrides)
        return base

    def test_denies_unapproved_strategy(self):
        strategy = self.approved_strategy()
        strategy["status"] = "draft"
        result = risk.evaluate_risk(strategy, make_rules(), self._candidate())
        self.assertEqual(result["verdict"], "negado")
        self.assertIn("estrategia_nao_aprovada", result["denial_reasons"])
        self.assertNotIn("mercado_fora_das_regras", result["denial_reasons"])

    def test_denies_when_exposure_already_full(self):
        strategy = self.approved_strategy()
        for index in range(2):
            run_id = store.save_pipeline_run(
                pipeline.PIPELINE_VERSION, strategy["id"], f"SEED-{index}", "VBS", "ETHUSDT",
                "2m", f"2026-03-01T0{index}:00:00+00:00", "trade_candidate",
                risk_verdict="autorizado", status="posicao_aberta")
            store.open_paper_operation("ETHUSDT", "buy", 1.0, 3000.0, "seed", pipeline_run_id=run_id)
        result = risk.evaluate_risk(strategy, make_rules(), self._candidate())
        self.assertEqual(result["verdict"], "negado")
        self.assertIn("exposicao_excedida", result["denial_reasons"])
        self.assertNotIn("mercado_fora_das_regras", result["denial_reasons"])

    def test_denies_when_daily_loss_budget_already_committed(self):
        strategy = self.approved_strategy()
        date_str = "2026-03-05"
        for index in range(3):
            signal_bar = f"{date_str}T0{index}:00:00+00:00"
            store.save_pipeline_run(
                pipeline.PIPELINE_VERSION, strategy["id"], f"BUDGET-{index}", "VBS", "BTCUSDT",
                "2m", signal_bar, "trade_candidate", risk_verdict="autorizado",
                risk_decided_at=signal_bar, risk_committed_r=1.0, status="aguardando_quantidade")
        candidate = self._candidate(signal_bar=f"{date_str}T10:00:00+00:00")
        result = risk.evaluate_risk(strategy, make_rules(), candidate)
        self.assertEqual(result["verdict"], "negado")
        self.assertIn("perda_diaria_atingida", result["denial_reasons"])
        self.assertNotIn("mercado_fora_das_regras", result["denial_reasons"])

    def test_authorized_candidate_never_lists_mercado_fora_das_regras(self):
        strategy = self.approved_strategy()
        result = risk.evaluate_risk(strategy, make_rules(), self._candidate())
        self.assertEqual(result["verdict"], "autorizado")
        self.assertNotIn("mercado_fora_das_regras", result["denial_reasons"])
        motives = {check["motivo"] for check in result["checks"]}
        self.assertIn("mercado_fora_das_regras", motives)
        nao_aplicavel = next(c for c in result["checks"] if c["motivo"] == "mercado_fora_das_regras")
        self.assertEqual(nao_aplicavel["estado"], "nao_aplicavel")


class DecisionTests(unittest.TestCase):
    def test_build_decision_is_deterministic(self):
        rules = make_rules()
        market = {"ativo": "BTCUSDT"}
        knowledge = {"itens_aprovados_count": 0}
        backtest_evidence = {"status": "sem_fonte", "promotes_strategy": False}
        fundamental = {"status": "sem_fonte", "motivo": "sem fonte integrada"}
        candidate_signal = {"entry_price": 100.5, "stop": 98.0, "target": 103.0, "side": "buy",
                            "signal_bar": "2026-03-01T10:00:00+00:00"}
        first = decision.build_decision(market, knowledge, backtest_evidence, fundamental,
                                        candidate_signal, rules)
        second = decision.build_decision(market, knowledge, backtest_evidence, fundamental,
                                         candidate_signal, rules)
        self.assertEqual(first, second)
        self.assertEqual(first["decisao"], "trade_candidate")
        for forbidden in ("confidence", "probability", "score"):
            self.assertNotIn(forbidden, json.dumps(first))

    def test_no_candidate_signal_is_always_no_trade(self):
        rules = make_rules()
        result = decision.build_decision({"ativo": "BTCUSDT"}, {"itens_aprovados_count": 0},
                                         {"status": "sem_fonte"}, {"status": "sem_fonte"},
                                         None, rules)
        self.assertEqual(result["decisao"], "no_trade")


class ExecutionPlanTests(unittest.TestCase):
    def test_refuses_to_build_plan_for_unauthorized_risk_result(self):
        candidate = {"entry_price": 100.5, "stop": 98.0, "target": 103.0, "side": "buy"}
        with self.assertRaises(ValueError):
            execution.build_execution_plan({}, {"verdict": "negado"}, candidate, make_rules())
        with self.assertRaises(ValueError):
            execution.build_execution_plan({}, None, candidate, make_rules())


class ConfirmOpenTests(PipelineTestBase):
    def seed_pending_run(self, strategy_id, symbol="BTCUSDT", timeframe="2m",
                         signal_bar="2026-04-01T00:58:00+00:00", entry_price=100.5,
                         side="buy", stop=98.0, target=103.0, setup_id="SETUP_01"):
        return store.save_pipeline_run(
            pipeline.PIPELINE_VERSION, strategy_id, setup_id, "VBS", symbol, timeframe,
            signal_bar, "trade_candidate", risk_verdict="autorizado",
            risk_decided_at=signal_bar, risk_committed_r=1.0, status="aguardando_quantidade",
            pending_since=signal_bar,
            report={"execution": {"status": "ok", "entrada": entry_price, "side": side,
                                  "stop": stop, "alvo": target}})

    def test_confirm_open_happy_path_opens_a_real_position(self):
        strategy = self.approved_strategy()
        run_id = self.seed_pending_run(strategy["id"])
        result = execution.confirm_open(run_id, 0.5)
        operations = store.list_paper_operations()
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["id"], result["paper_operation_id"])
        self.assertEqual(operations[0]["pipeline_run_id"], run_id)
        self.assertEqual(operations[0]["entry_price"], 100.5)
        self.assertEqual(operations[0]["state"], "open")
        self.assertEqual(store.get_pipeline_run(run_id)["status"], "posicao_aberta")

    def test_confirm_open_rejects_non_positive_quantity_and_writes_nothing(self):
        strategy = self.approved_strategy()
        run_id = self.seed_pending_run(strategy["id"])
        with self.assertRaisesRegex(ValueError, "[Qq]uantidade"):
            execution.confirm_open(run_id, 0)
        self.assertEqual(store.list_paper_operations(), [])
        self.assertEqual(store.get_pipeline_run(run_id)["status"], "aguardando_quantidade")

    def test_confirm_open_rejects_a_duplicate_confirmation(self):
        strategy = self.approved_strategy()
        run_id = self.seed_pending_run(strategy["id"])
        execution.confirm_open(run_id, 0.5)
        with self.assertRaises(ValueError):
            execution.confirm_open(run_id, 0.5)
        self.assertEqual(len(store.list_paper_operations()), 1)

    def test_confirm_open_rejects_when_exposure_changed_since_authorization(self):
        strategy = self.approved_strategy()
        run_id = self.seed_pending_run(strategy["id"])
        for index in range(2):
            other_id = store.save_pipeline_run(
                pipeline.PIPELINE_VERSION, strategy["id"], f"OTHER-{index}", "VBS", "ETHUSDT",
                "2m", f"2026-04-01T0{index}:30:00+00:00", "trade_candidate",
                risk_verdict="autorizado", status="posicao_aberta")
            store.open_paper_operation("ETHUSDT", "buy", 1.0, 3000.0, "seed", pipeline_run_id=other_id)
        with self.assertRaisesRegex(ValueError, "[Ee]xposiç"):
            execution.confirm_open(run_id, 0.5)
        self.assertEqual(store.get_pipeline_run(run_id)["status"], "recusado_na_confirmacao")
        self.assertEqual(len(store.list_paper_operations()), 2)

    def test_discard_marks_run_discarded_without_opening_a_position(self):
        strategy = self.approved_strategy()
        run_id = self.seed_pending_run(strategy["id"])
        execution.discard(run_id)
        self.assertEqual(store.get_pipeline_run(run_id)["status"], "descartado_pelo_usuario")
        self.assertEqual(store.list_paper_operations(), [])

    def test_discard_refuses_a_run_not_awaiting_quantity(self):
        strategy = self.approved_strategy()
        run_id = self.seed_pending_run(strategy["id"])
        execution.discard(run_id)
        with self.assertRaises(ValueError):
            execution.discard(run_id)

    def test_confirm_open_refuses_when_kill_switch_is_active_and_writes_nothing(self):
        strategy = self.approved_strategy()
        run_id = self.seed_pending_run(strategy["id"])
        store.set_kill_switch(True, "incidente em investigação", "ana")
        with self.assertRaisesRegex(ValueError, "[Bb]loquead"):
            execution.confirm_open(run_id, 0.5)
        self.assertEqual(store.list_paper_operations(), [])
        self.assertEqual(store.get_pipeline_run(run_id)["status"], "aguardando_quantidade")

    def test_discard_still_works_while_kill_switch_is_active(self):
        strategy = self.approved_strategy()
        run_id = self.seed_pending_run(strategy["id"])
        store.set_kill_switch(True, "incidente em investigação", "ana")
        execution.discard(run_id)
        self.assertEqual(store.get_pipeline_run(run_id)["status"], "descartado_pelo_usuario")
        self.assertEqual(store.list_paper_operations(), [])


if __name__ == "__main__":
    unittest.main()
