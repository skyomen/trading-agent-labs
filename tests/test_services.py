import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfWriter

from database import store
from services import documents
from services.backtest import parse_ohlcv_csv, run_sma_crossover
from services.agents import provider_summary, run_agent_task, _message_context
from services import knowledge


class DocumentServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.reference = self.root / "reference_docs"
        (self.reference / "shared").mkdir(parents=True)
        (self.reference / "agents" / "risk-manager").mkdir(parents=True)
        self.db_patch = patch.object(store, "DB_PATH", self.root / "test.db")
        self.root_patch = patch.object(documents, "PROJECT_ROOT", self.root)
        self.reference_patch = patch.object(documents, "REFERENCE_ROOT", self.reference)
        self.db_patch.start()
        self.root_patch.start()
        self.reference_patch.start()
        store.initialize()
        self.pdf_path = self.reference / "shared" / "method.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with self.pdf_path.open("wb") as stream:
            writer.write(stream)

    def tearDown(self):
        self.reference_patch.stop()
        self.root_patch.stop()
        self.db_patch.stop()
        self.tmp.cleanup()

    def test_pdf_is_catalogued_locally_and_reindex_is_idempotent(self):
        result = documents.index_pdf(self.pdf_path)
        repeated = documents.index_pdf(self.pdf_path)
        self.assertEqual(result["status"], "no_text")
        self.assertEqual(result["pages"], 1)
        self.assertEqual(repeated["status"], "unchanged")
        self.assertEqual(len(store.list_documents()), 1)

    def test_pdf_outside_reference_root_is_rejected(self):
        elsewhere = self.root / "outside.pdf"
        elsewhere.write_bytes(b"not a pdf")
        with self.assertRaises(ValueError):
            documents.index_pdf(elsewhere)

    def test_shared_and_agent_documents_resolve_to_page_cited_context(self):
        relative = "reference_docs/shared/method.pdf"
        store.replace_document(relative, "method.pdf", "abc", "indexed", 1,
                               [(1, 0, "regra de contexto")])
        context = store.get_document_context("Risk Manager")
        self.assertEqual(context[0]["page_number"], 1)
        self.assertEqual(context[0]["filename"], "method.pdf")

    def test_changed_source_is_marked_stale_and_excluded_from_agent_context(self):
        documents.index_pdf(self.pdf_path)
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.add_blank_page(width=612, height=792)
        with self.pdf_path.open("wb") as stream:
            writer.write(stream)
        status = documents.library_status()[0]
        context, stale = documents.agent_context("Risk Manager")
        self.assertEqual(status["status"], "stale")
        self.assertEqual(context, [])
        self.assertEqual(stale, ["reference_docs/shared/method.pdf"])

    def test_knowledge_extraction_creates_cited_proposals_idempotently(self):
        path = "reference_docs/shared/Setups Complementar Op. OV Atualizada.pdf"
        record = {"sha256": "current-hash"}
        library = [{"path": path, "filename": "Setups Complementar Op. OV Atualizada.pdf",
                    "status": "indexed", "record": record}]
        with patch.object(knowledge.documents, "library_status", return_value=library), \
             patch.object(knowledge, "_page_text", return_value="NRB Narrow Range Bar · texto de evidência"):
            first = knowledge.extract_proposals()
            second = knowledge.extract_proposals()
        items = store.list_knowledge_items()
        self.assertEqual(first["items"], 25)
        self.assertEqual(first["proposed"], 25)
        self.assertEqual(first["status"], "Revisão humana pendente")
        self.assertEqual(second["created"], 0)
        self.assertEqual(len(items), 25)
        self.assertTrue(all(item["page_number"] > 0 and item["source_sha256"] == "current-hash"
                            and item["status"] == "proposed" for item in items))

    def test_only_current_approved_knowledge_enters_agent_context(self):
        approved = store.upsert_knowledge_item("concept", "Regra aprovada",
                                               "reference_docs/shared/a.pdf", "hash", 2, "texto citado")
        store.review_knowledge_item(1, True)
        store.upsert_knowledge_item("concept", "Regra proposta",
                                    "reference_docs/shared/a.pdf", "hash", 3, "proposta")
        with patch.object(documents, "agent_context", return_value=([{"relative_path": "reference_docs/shared/a.pdf",
                                                                        "filename": "a.pdf", "page_number": 2,
                                                                        "content": "texto citado"}], [])), \
             patch.object(documents, "library_status", return_value=[{"path": "reference_docs/shared/a.pdf",
                    "record": {"sha256": "hash"}}]):
            context = _message_context("Research Agent", True)
        self.assertIn("Regra aprovada", context)
        self.assertNotIn("Regra proposta", context)

    def test_agent_context_excludes_knowledge_from_another_agents_folder(self):
        private_path = "reference_docs/agents/execution-agent/private.pdf"
        store.upsert_knowledge_item("concept", "Escopo privado", private_path,
                                    "private-hash", 1, "contexto de execução")
        store.review_knowledge_item(1, True)
        visible = {"path": "reference_docs/shared/common.pdf", "record": {"sha256": "common-hash"}}
        private = {"path": private_path, "record": {"sha256": "private-hash"}}
        with patch.object(documents, "agent_context", return_value=([], [])), \
             patch.object(documents, "library_status", return_value=[visible, private]):
            context = _message_context("Research Agent", True)
        self.assertNotIn("contexto de execução", context)


class AgentConnectorTests(unittest.TestCase):
    def test_external_provider_requires_credentials_and_model(self):
        self.assertFalse(provider_summary({"TRADING_LAB_LLM_BASE_URL": "https://example.test/v1",
                                           "TRADING_LAB_LLM_MODEL": "model"})["configured"])
        configured = provider_summary({"TRADING_LAB_LLM_BASE_URL": "https://example.test/v1",
                                      "TRADING_LAB_LLM_MODEL": "model",
                                      "TRADING_LAB_LLM_API_KEY": "present"})
        self.assertTrue(configured["configured"])
        self.assertTrue(configured["api_key_present"])
        insecure = provider_summary({"TRADING_LAB_LLM_BASE_URL": "http://provider.example/v1",
                                     "TRADING_LAB_LLM_MODEL": "model",
                                     "TRADING_LAB_LLM_API_KEY": "present"})
        self.assertFalse(insecure["configured"])

    def test_local_provider_can_be_configured_without_api_key(self):
        configured = provider_summary({"TRADING_LAB_LLM_BASE_URL": "http://localhost:11434/v1",
                                      "TRADING_LAB_LLM_MODEL": "local-model"})
        self.assertTrue(configured["configured"])
        self.assertTrue(configured["local"])

    def test_agent_task_does_not_call_provider_without_configuration(self):
        with patch.dict("os.environ", {}, clear=True), tempfile.TemporaryDirectory() as temp:
            with patch.object(store, "DB_PATH", Path(temp) / "test.db"):
                store.initialize()
                with self.assertRaisesRegex(RuntimeError, "Nenhuma chamada externa foi feita"):
                    run_agent_task("Research Agent", "Resuma as fontes")
                self.assertEqual(store.list_agent_runs(), [])

    def test_sending_documents_requires_explicit_consent(self):
        with self.assertRaises(PermissionError):
            run_agent_task("Research Agent", "Resuma", include_documents=True,
                           authorize_external_context=False)

    def test_agent_task_records_start_result_and_output(self):
        response = io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "Conclusão com evidência."}}]
        }).encode())
        with patch.dict("os.environ", {
            "TRADING_LAB_LLM_BASE_URL": "https://provider.example/v1",
            "TRADING_LAB_LLM_MODEL": "test-model",
            "TRADING_LAB_LLM_API_KEY": "test-secret",
        }, clear=True), tempfile.TemporaryDirectory() as temp:
            with patch.object(store, "DB_PATH", Path(temp) / "test.db"):
                store.initialize()
                with patch("services.agents.urllib.request.urlopen", return_value=response) as call:
                    result = run_agent_task("Research Agent", "Analise os documentos")
                self.assertEqual(result["output"], "Conclusão com evidência.")
                self.assertEqual(len(store.list_agent_runs()), 1)
                self.assertEqual(store.list_agent_runs()[0]["status"], "completed")
                self.assertEqual(len(store.list_events(limit=20)), 2)
                self.assertNotIn("test-secret", store.list_events()[0]["Atividade"])
                request = call.call_args.args[0]
                payload = json.loads(request.data.decode())
                self.assertEqual(payload["model"], "test-model")


class BacktestServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(store, "DB_PATH", Path(self.tmp.name) / "test.db")
        self.db_patch.start()
        store.initialize()

    def tearDown(self):
        self.db_patch.stop()
        self.tmp.cleanup()

    def csv_fixture(self):
        closes = [10, 9, 8, 9, 10, 12, 14, 7, 6, 5]
        lines = ["timestamp,open,high,low,close,volume"]
        for index, close in enumerate(closes):
            opened = 6.5 if index == 8 else close
            high = max(opened, close) + 1
            low = min(opened, close) - 0.5
            lines.append(f"2026-01-{index + 1:02d}T00:00:00Z,{opened},{high},{low},{close},100")
        return ("\n".join(lines) + "\n").encode()

    def test_csv_is_validated_and_hash_identifies_imported_bars(self):
        parsed = parse_ohlcv_csv(self.csv_fixture(), "synthetic-test-fixture.csv")
        self.assertEqual(len(parsed["bars"]), 10)
        self.assertEqual(len(parsed["sha256"]), 64)
        dataset_id = store.save_historical_dataset(
            parsed["filename"], "TEST", "1d", "fixture somente para teste",
            parsed["sha256"], parsed["bars"],
        )
        self.assertEqual(len(store.get_historical_bars(dataset_id)), 10)

    def test_csv_rejects_out_of_order_and_invalid_ohlc(self):
        invalid_order = b"timestamp,open,high,low,close,volume\n2026-02-02,1,2,0.5,1,1\n2026-02-01,1,2,0.5,1,1\n2026-02-03,1,2,0.5,1,1\n"
        with self.assertRaisesRegex(ValueError, "crescentes"):
            parse_ohlcv_csv(invalid_order, "bad.csv")
        invalid_ohlc = b"timestamp,open,high,low,close,volume\n2026-02-01,1,1,0.5,2,1\n2026-02-02,1,2,0.5,1,1\n2026-02-03,1,2,0.5,1,1\n"
        with self.assertRaisesRegex(ValueError, "máxima"):
            parse_ohlcv_csv(invalid_ohlc, "bad.csv")

    def test_backtest_uses_next_open_fills_and_includes_explicit_costs(self):
        bars = parse_ohlcv_csv(self.csv_fixture(), "fixture.csv")["bars"]
        result = run_sma_crossover(bars, fast_window=2, slow_window=3,
                                   fee_bps=5, slippage_bps=2)
        self.assertEqual(result["trade_count"], 1)
        self.assertEqual(result["trades"][0]["entry_time"], bars[5]["timestamp"])
        self.assertEqual(result["trades"][0]["exit_time"], bars[8]["timestamp"])
        self.assertAlmostEqual(result["total_cost_pct_of_notional"], 0.14)
        self.assertFalse(result["annualized"])

    def test_backtest_rejects_invalid_windows_and_hash_metadata_collision(self):
        bars = parse_ohlcv_csv(self.csv_fixture(), "fixture.csv")["bars"]
        with self.assertRaises(ValueError):
            run_sma_crossover(bars, fast_window=4, slow_window=4)
        digest = "a" * 64
        store.save_historical_dataset("a.csv", "TEST", "1d", "source one", digest, bars)
        with self.assertRaisesRegex(ValueError, "outro símbolo"):
            store.save_historical_dataset("b.csv", "OTHER", "1d", "source two", digest, bars)


if __name__ == "__main__":
    unittest.main()
