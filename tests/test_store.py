import tempfile
import unittest
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

if __name__ == "__main__":
    unittest.main()
