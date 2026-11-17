import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from database import store

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.patch = patch.object(store, "DB_PATH", self.db)
        self.patch.start()
        store.initialize()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_initializes_six_agents(self):
        agents = store.get_agents()
        self.assertEqual(len(agents), 6)
        self.assertEqual(
            [agent["name"] for agent in agents],
            [name for name, _, _ in store.AGENTS],
        )

    def test_new_local_workspaces_are_created_idempotently(self):
        store.initialize()
        counts = store.counts()
        self.assertEqual(counts["agents"], 6)
        self.assertEqual(counts["documents"], 0)
        self.assertEqual(counts["agent_runs"], 0)
        with store.connect() as conn:
            names = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertTrue({"documents", "document_chunks", "agent_memories",
                         "agent_reviews", "strategies", "backtests",
                         "paper_operations", "connections", "knowledge_items"}.issubset(names))

    def test_event_is_persisted(self):
        store.add_event("Risk Manager", "INFO", "Teste de bloqueio")
        events = store.list_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["Agente"], "Risk Manager")
        self.assertEqual(events[0]["Atividade"], "Teste de bloqueio")

    def test_initialize_migrates_legacy_agent_safety_copy(self):
        with store.connect() as conn:
            conn.execute("UPDATE agents SET status=?,responsibility=? WHERE name='Risk Manager'",
                         ("Proteções configuradas", "Valida limites de risco; bloqueia ações não autorizadas."))
            conn.execute("UPDATE agents SET status=?,responsibility=? WHERE name='Execution Agent'",
                         ("Execução desabilitada", "Executará apenas em ambiente explicitamente autorizado."))
        store.initialize()
        by_name = {item["name"]: item for item in store.get_agents()}
        self.assertEqual(by_name["Risk Manager"]["status"], "Limites pendentes de revisão")
        self.assertIn("Aguarda limites documentados", by_name["Risk Manager"]["responsibility"])
        self.assertEqual(by_name["Execution Agent"]["status"], "Simulação local apenas")
        self.assertIn("conector de negociação permanece bloqueado", by_name["Execution Agent"]["responsibility"])

    def test_events_are_newest_first_and_survive_reinitialization(self):
        store.add_event("Market Analyst", "INFO", "Primeiro evento")
        store.add_event("Risk Manager", "INFO", "Segundo evento")

        store.initialize()
        events = store.list_events()

        self.assertEqual(
            [event["Atividade"] for event in events],
            ["Segundo evento", "Primeiro evento"],
        )

    def test_memory_proposals_are_not_context_until_approved(self):
        memory_id = store.add_memory("Risk Manager", "aprendizado", "Exigir origem", "review:3")
        self.assertEqual(store.list_memories("Risk Manager", include_pending=False), [])
        store.review_memory(memory_id, True)
        approved = store.list_memories("Risk Manager", include_pending=False)
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0]["content"], "Exigir origem")

    def test_review_promotes_learning_only_after_approval(self):
        review_id = store.add_review("Market Analyst", "Preço atrasado", "Feed inativo", "Bloquear dado obsoleto")
        store.decide_review(review_id, True)
        memories = store.list_memories("Market Analyst", include_pending=False)
        self.assertEqual([item["content"] for item in memories], ["Bloquear dado obsoleto"])

    def test_strategy_versions_are_immutable_and_increment(self):
        first = store.save_strategy("Setup de teste", {"rule": "human-supplied"}, "user")
        second = store.save_strategy("Setup de teste", {"rule": "revised"}, "user")
        rows = store.list_strategies()
        self.assertEqual({first, second}, {row["id"] for row in rows})
        self.assertEqual(sorted(row["version"] for row in rows), [1, 2])

    def test_knowledge_proposals_are_idempotent_and_require_review(self):
        args = ("concept", "Controle absoluto", "reference_docs/shared/a.pdf", "hash", 7, "evidência", {"x": 1})
        self.assertTrue(store.upsert_knowledge_item(*args))
        self.assertFalse(store.upsert_knowledge_item(*args))
        item = store.list_knowledge_items()[0]
        self.assertEqual(item["status"], "proposed")
        self.assertTrue(store.review_knowledge_item(item["id"], True))
        self.assertEqual(store.list_knowledge_items(status="approved")[0]["details"], {"x": 1})
        self.assertFalse(store.review_knowledge_item(item["id"], False))
        self.assertTrue(store.upsert_knowledge_item(
            "concept", "Controle absoluto", "reference_docs/shared/a.pdf", "new-hash", 7,
            "nova evidência", {"x": 2}))
        versions = store.list_knowledge_items(kind="concept")
        self.assertEqual(sorted(row["version"] for row in versions), [1, 2])

class PipelineOrchestrationTests(unittest.TestCase):
    """Entrega 7 / Fase 1: schema and store functions, no agent/service logic yet."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.patch = patch.object(store, "DB_PATH", self.db)
        self.patch.start()
        store.initialize()
        self.strategy_id = store.save_strategy("VBS", {"rule": "test"}, "user")

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_new_tables_exist_after_initialize(self):
        with store.connect() as conn:
            names = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertIn("pipeline_runs", names)
        self.assertIn("pipeline_stages", names)

    def test_initialize_twice_does_not_duplicate_or_erase_pipeline_tables(self):
        run_id = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-BTCUSDT-2m", "VBS", "BTCUSDT", "2m",
            "2026-11-16T10:00:00+00:00", "trade_candidate")
        store.add_pipeline_stage(run_id, 1, "Market", "Market Analyst", "ok", "Barra recebida")

        store.initialize()
        store.initialize()

        counts = store.counts()
        self.assertEqual(counts["pipeline_runs"], 1)
        with store.connect() as conn:
            stage_count = conn.execute("SELECT COUNT(*) FROM pipeline_stages").fetchone()[0]
        self.assertEqual(stage_count, 1)

    def test_save_pipeline_run_is_idempotent_by_bar(self):
        first = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-BTCUSDT-2m", "VBS", "BTCUSDT", "2m",
            "2026-11-16T10:00:00+00:00", "trade_candidate")
        second = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-BTCUSDT-2m", "VBS", "BTCUSDT", "2m",
            "2026-11-16T10:00:00+00:00", "no_trade")
        self.assertEqual(first, second)
        self.assertEqual(store.counts()["pipeline_runs"], 1)
        run = store.get_pipeline_run(first)
        self.assertEqual(run["decision"], "trade_candidate")
        self.assertEqual(run["stages"], [])

    def test_open_paper_operation_rejects_invalid_values_and_accepts_valid_ones(self):
        with self.assertRaisesRegex(ValueError, "[Qq]uantidade"):
            store.open_paper_operation("BTCUSDT", "buy", 0, 100, "pipeline")
        with self.assertRaisesRegex(ValueError, "[Pp]reço"):
            store.open_paper_operation("BTCUSDT", "buy", 1, 0, "pipeline")
        with self.assertRaisesRegex(ValueError, "[Ll]ado"):
            store.open_paper_operation("BTCUSDT", "hold", 1, 100, "pipeline")

        run_id = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-BTCUSDT-2m", "VBS", "BTCUSDT", "2m",
            "2026-11-16T10:00:00+00:00", "trade_candidate")
        op_id = store.open_paper_operation("BTCUSDT", "buy", 0.5, 95000.0, "pipeline",
                                           pipeline_run_id=run_id)
        operations = store.list_paper_operations()
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["id"], op_id)
        self.assertEqual(operations[0]["pipeline_run_id"], run_id)
        self.assertEqual(operations[0]["state"], "open")
        self.assertIsNone(operations[0]["exit_price"])
        self.assertIsNone(operations[0]["closed_at"])

    def test_list_paper_operations_filters_by_state_and_preserves_default(self):
        run_id = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-BTCUSDT-2m", "VBS", "BTCUSDT", "2m",
            "2026-11-16T10:00:00+00:00", "trade_candidate")
        store.open_paper_operation("BTCUSDT", "buy", 0.5, 95000.0, "pipeline", pipeline_run_id=run_id)
        with store.connect() as conn:
            conn.execute("INSERT INTO paper_operations(symbol,side,quantity,entry_price,state,source) "
                        "VALUES('ETHUSDT','sell',1,3000,'closed','manual')")
        self.assertEqual(len(store.list_paper_operations()), 2)
        self.assertEqual(len(store.list_paper_operations(state="open")), 1)
        self.assertEqual(len(store.list_paper_operations(state="closed")), 1)

    def test_count_committed_risk_r_includes_pending_expired_and_discarded(self):
        scenarios = [
            ("VBS-A", "aguardando_quantidade", "2026-11-16T10:00:00+00:00"),
            ("VBS-B", "posicao_aberta", "2026-11-16T11:00:00+00:00"),
            ("VBS-C", "expirado", "2026-11-16T12:00:00+00:00"),
            ("VBS-D", "descartado_pelo_usuario", "2026-11-16T13:00:00+00:00"),
        ]
        for setup_id, status, signal_bar in scenarios:
            run_id = store.save_pipeline_run(
                "pipeline_v1", self.strategy_id, setup_id, "VBS", "BTCUSDT", "2m",
                signal_bar, "trade_candidate", risk_verdict="autorizado",
                risk_decided_at=signal_bar, risk_committed_r=1.0)
            store.update_pipeline_run_status(run_id, status)
        # A run never authorized must not count.
        store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-E", "VBS", "BTCUSDT", "2m",
            "2026-11-16T14:00:00+00:00", "no_trade", risk_verdict="negado")
        total = store.count_committed_risk_r("2026-11-16")
        self.assertEqual(total, 4.0)

    def test_count_reserved_exposure_counts_open_positions_and_pending_runs_only(self):
        pending_run = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-A", "VBS", "BTCUSDT", "2m",
            "2026-11-16T10:00:00+00:00", "trade_candidate", risk_verdict="autorizado",
            status="aguardando_quantidade")
        open_run = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-B", "VBS", "ETHUSDT", "2m",
            "2026-11-16T11:00:00+00:00", "trade_candidate", risk_verdict="autorizado",
            status="posicao_aberta")
        store.open_paper_operation("ETHUSDT", "buy", 1, 3000, "pipeline", pipeline_run_id=open_run)
        expired_run = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-C", "VBS", "BTCUSDT", "5m",
            "2026-11-16T12:00:00+00:00", "trade_candidate", risk_verdict="autorizado",
            status="aguardando_quantidade")
        store.update_pipeline_run_status(expired_run, "expirado")

        self.assertIsNotNone(pending_run)
        self.assertEqual(store.count_reserved_exposure(), 2)

    def test_expire_stale_pipeline_runs_uses_pending_since_not_created_at(self):
        old_pending = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        recent_pending = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        old_run = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-A", "VBS", "BTCUSDT", "2m",
            "2026-11-16T10:00:00+00:00", "trade_candidate", risk_verdict="autorizado",
            status="aguardando_quantidade", pending_since=old_pending)
        recent_run = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-B", "VBS", "ETHUSDT", "2m",
            "2026-11-16T11:00:00+00:00", "trade_candidate", risk_verdict="autorizado",
            status="aguardando_quantidade", pending_since=recent_pending)

        expired_ids = store.expire_stale_pipeline_runs(max_age_seconds=900)

        self.assertEqual(expired_ids, [old_run])
        self.assertEqual(store.get_pipeline_run(old_run)["status"], "expirado")
        self.assertEqual(store.get_pipeline_run(recent_run)["status"], "aguardando_quantidade")

    def test_list_pending_pipeline_runs_orders_oldest_first(self):
        first = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-A", "VBS", "BTCUSDT", "2m",
            "2026-11-16T10:00:00+00:00", "trade_candidate", status="aguardando_quantidade")
        second = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-B", "VBS", "ETHUSDT", "2m",
            "2026-11-16T11:00:00+00:00", "trade_candidate", status="aguardando_quantidade")
        pending = store.list_pending_pipeline_runs()
        self.assertEqual([row["id"] for row in pending], [first, second])


class TradeManagementSchemaTests(unittest.TestCase):
    """Entrega 8 / Fase 2: schema and store functions for closing a paper position."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.patch = patch.object(store, "DB_PATH", self.db)
        self.patch.start()
        store.initialize()
        self.strategy_id = store.save_strategy("VBS", {"rule": "test"}, "user")

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_exit_reason_column_exists_and_initialize_twice_is_safe(self):
        with store.connect() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(paper_operations)")}
        self.assertIn("exit_reason", columns)

        store.initialize()
        store.initialize()

        with store.connect() as conn:
            columns_again = {row[1] for row in conn.execute("PRAGMA table_info(paper_operations)")}
        self.assertIn("exit_reason", columns_again)
        self.assertEqual(store.counts()["agents"], 6)

    def test_close_paper_operation_closes_once_and_is_idempotent(self):
        run_id = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-X", "VBS", "BTCUSDT", "2m",
            "2026-11-16T10:00:00+00:00", "trade_candidate")
        op_id = store.open_paper_operation("BTCUSDT", "buy", 0.5, 100.0, "pipeline",
                                           pipeline_run_id=run_id)
        closed_at = "2026-11-16T10:10:00+00:00"

        first = store.close_paper_operation(op_id, 102.0, "target", closed_at, fees=0.5,
                                            realized_r=2.0)
        self.assertTrue(first)
        operation = store.list_paper_operations()[0]
        self.assertEqual(operation["state"], "closed")
        self.assertEqual(operation["exit_price"], 102.0)
        self.assertEqual(operation["exit_reason"], "target")
        self.assertEqual(operation["closed_at"], closed_at)
        self.assertEqual(operation["fees"], 0.5)
        self.assertEqual(store.get_pipeline_run(run_id)["realized_r"], 2.0)
        journal = store.list_paper_journal()
        self.assertEqual(len(journal), 1)
        self.assertEqual(journal[0]["state"], "closed")
        self.assertEqual(json.loads(journal[0]["details_json"])["fees"], 0.5)

        second = store.close_paper_operation(op_id, 999.0, "stop",
                                             "2026-11-16T10:20:00+00:00", realized_r=-5.0)
        self.assertFalse(second)
        operation_again = store.list_paper_operations()[0]
        self.assertEqual(operation_again["exit_price"], 102.0)
        self.assertEqual(operation_again["exit_reason"], "target")
        self.assertEqual(operation_again["closed_at"], closed_at)
        self.assertEqual(store.get_pipeline_run(run_id)["realized_r"], 2.0)
        self.assertEqual(len(store.list_paper_journal()), 1)

    def test_journal_and_conduction_stage_roll_back_with_failed_close(self):
        run_id = store.save_pipeline_run(
            "pipeline_v1", self.strategy_id, "VBS-X", "VBS", "BTCUSDT", "2m",
            "2026-11-16T10:00:00+00:00", "trade_candidate")
        op_id = store.open_paper_operation("BTCUSDT", "buy", 1, 100, "pipeline",
                                           pipeline_run_id=run_id)
        with self.assertRaises(KeyError):
            store.close_paper_operation(
                op_id, 102, "target", "2026-11-16T10:10:00+00:00", fees=0.2,
                realized_r=1.8, conduction_stage={"stage_index": 8})
        self.assertEqual(store.list_paper_operations()[0]["state"], "open")
        self.assertIsNone(store.get_pipeline_run(run_id)["realized_r"])
        self.assertEqual(store.list_paper_journal()[0]["state"], "open")

    def test_initialize_backfills_legacy_operation_without_inventing_trail(self):
        with store.connect() as conn:
            conn.execute("""INSERT INTO paper_operations
                (symbol,side,quantity,entry_price,source,state)
                VALUES('BTCUSDT','buy',1,100,'legacy','open')""")
        store.initialize()
        store.initialize()
        journal = store.list_paper_journal()
        self.assertEqual(len(journal), 1)
        details = json.loads(journal[0]["details_json"])
        self.assertIsNone(journal[0]["pipeline_run_id"])
        self.assertIn("anterior ao diário", details["limitations"][0])

    def test_get_strategy_returns_the_matching_version(self):
        first = store.save_strategy("Setup X", {"rule": "v1"}, "user")
        second = store.save_strategy("Setup X", {"rule": "v2"}, "user")
        self.assertEqual(json.loads(store.get_strategy(first)["rules_json"]), {"rule": "v1"})
        self.assertEqual(json.loads(store.get_strategy(second)["rules_json"]), {"rule": "v2"})
        self.assertIsNone(store.get_strategy(999999))

    def test_get_market_bars_since_includes_boundary_bar_with_either_timestamp_suffix(self):
        provider, symbol, timeframe = "TestProvider", "BTCUSDT", "1m"
        before = {"timestamp": "2026-11-12T20:07:00Z", "open": 1, "high": 1, "low": 1,
                 "close": 1, "volume": 1}
        boundary = {"timestamp": "2026-11-12T20:08:00+00:00", "open": 1, "high": 1, "low": 1,
                   "close": 1, "volume": 1}
        after = {"timestamp": "2026-11-12T20:09:00Z", "open": 1, "high": 1, "low": 1,
                "close": 1, "volume": 1}
        store.upsert_market_bar(provider, symbol, timeframe, before)
        store.upsert_market_bar(provider, symbol, timeframe, boundary)
        store.upsert_market_bar(provider, symbol, timeframe, after)

        # since_timestamp passed WITHOUT a timezone suffix, per the documented contract.
        bars = store.get_market_bars_since(provider, symbol, timeframe, "2026-11-12T20:08:00")
        self.assertEqual([bar["timestamp"] for bar in bars],
                         [boundary["timestamp"], after["timestamp"]])

        # A naive `WHERE timestamp >= ?` using this "...Z"-suffixed bound against a boundary
        # row stored with "+00:00" would wrongly exclude it ('+' 0x2B sorts below 'Z' 0x5A).
        # This function's second, parsed-datetime safety net must still return it.
        defensive = store.get_market_bars_since(provider, symbol, timeframe, "2026-11-12T20:08:00Z")
        self.assertEqual([bar["timestamp"] for bar in defensive],
                         [boundary["timestamp"], after["timestamp"]])


if __name__ == "__main__":
    unittest.main()
