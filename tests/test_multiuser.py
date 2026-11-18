"""Local multi-user isolation, credential vault and global-knowledge gates."""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

from database import store
from services import auth, credential_vault, documents, global_knowledge
from services.agents import provider_summary
from services.brokers.binance_spot_testnet import BinanceSpotTestnet
from services.config import credential_context
from tests.test_app import APP_PATH


class MultiuserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(store, "DB_PATH", root / "trading.db"),
            patch.object(store, "IDENTITY_DB_PATH", root / "identity.db"),
            patch.object(store, "GLOBAL_DB_PATH", root / "global.db"),
            patch.object(store, "WORKSPACES_DIR", root / "workspaces"),
            patch.object(credential_vault, "VAULT_DIR", root / "vault"),
            patch.object(documents, "PROJECT_ROOT", root),
            patch.object(documents, "REFERENCE_ROOT", root / "reference_docs"),
        ]
        for item in self.patches:
            item.start()
        store.initialize()
        self.owner = auth.create_account("owner", "owner-password-123", role="owner")
        self.other = auth.create_account("other", "other-password-123", actor=self.owner)

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def test_two_workspaces_preserve_owner_history_without_cross_read(self):
        with store.user_workspace(self.owner["id"]):
            store.add_event("Owner", "INFO", "private-owner")
            self.assertEqual(len(store.get_agents()), 6)
        with store.user_workspace(self.other["id"]):
            self.assertEqual(len(store.get_agents()), 6)
            self.assertFalse(any(row["Atividade"] == "private-owner" for row in store.list_events()))
            store.add_event("Other", "INFO", "private-other")
        with store.user_workspace(self.owner["id"]):
            self.assertFalse(any(row["Atividade"] == "private-other" for row in store.list_events()))
        self.assertEqual(store.identity_user_count(), 2)

    def test_login_and_lockout(self):
        self.assertEqual(auth.login("owner", "owner-password-123")["id"], self.owner["id"])
        for _ in range(5):
            with self.assertRaisesRegex(ValueError, "inválidos"):
                auth.login("other", "wrong")
        with self.assertRaisesRegex(ValueError, "bloqueado"):
            auth.login("other", "other-password-123")

    def test_vault_is_per_user_encrypted_and_no_process_fallback(self):
        credential_vault.save_credentials(self.owner["id"], self.owner["vault_key"], {
            "BINANCE_SPOT_TESTNET_API_KEY": "owner-key",
            "BINANCE_SPOT_TESTNET_API_SECRET": "owner-secret",
        })
        raw = next(credential_vault.VAULT_DIR.glob("*.json")).read_text(encoding="utf-8")
        self.assertNotIn("owner-secret", raw)
        self.assertEqual(credential_vault.read_credentials(self.other["id"],
                                                           self.other["vault_key"]), {})
        with patch.dict("os.environ", {"BINANCE_SPOT_TESTNET_API_KEY": "process-key",
                                    "BINANCE_SPOT_TESTNET_API_SECRET": "process-secret",
                                    "TRADING_LAB_LLM_BASE_URL": "https://example.test",
                                    "TRADING_LAB_LLM_MODEL": "test"}):
            with credential_context({}):
                self.assertFalse(BinanceSpotTestnet().configured)
                self.assertFalse(provider_summary()["configured"])
            with credential_context(credential_vault.read_credentials(
                    self.owner["id"], self.owner["vault_key"])):
                self.assertTrue(BinanceSpotTestnet().configured)

    def test_only_owner_can_promote_approved_current_shared_knowledge(self):
        shared = documents.REFERENCE_ROOT / "shared"
        shared.mkdir(parents=True)
        source = shared / "fixture.pdf"
        source.write_bytes(b"%PDF-1.4\nfixture")
        digest = documents._digest(source)
        path = "reference_docs/shared/fixture.pdf"
        with store.user_workspace(self.owner["id"]):
            store.upsert_knowledge_item("concept", "Conceito", path, digest, 1, "evidência")
            item_id = store.list_knowledge_items()[0]["id"]
            with self.assertRaises(ValueError):
                global_knowledge.promote(item_id, self.owner)
            store.review_knowledge_item(item_id, True)
            global_knowledge.promote(item_id, self.owner)
        with store.user_workspace(self.other["id"]):
            self.assertEqual(store.list_knowledge_items(), [])
            self.assertEqual(len(global_knowledge.list_fresh()), 1)
            with self.assertRaises(PermissionError):
                global_knowledge.promote(item_id, self.other)
        source.write_bytes(b"%PDF-1.4\nchanged")
        with store.user_workspace(self.other["id"]):
            self.assertEqual(global_knowledge.list_fresh(), [])

    def test_private_pdf_is_confined_to_user_folder(self):
        with store.user_workspace(self.owner["id"]):
            source = documents.save_private_pdf("my-note.pdf", b"%PDF-1.4\nowner")
            self.assertIn(source, documents.discover_pdfs())
            with self.assertRaises(ValueError):
                documents.save_private_pdf("../escape.pdf", b"%PDF-1.4\nowner")
        with store.user_workspace(self.other["id"]):
            self.assertNotIn(source, documents.discover_pdfs())
            with self.assertRaises(ValueError):
                documents.index_pdf(source)

    def test_login_gate_and_portal_snapshot_use_active_workspace(self):
        with store.user_workspace(self.owner["id"]):
            store.add_event("Owner", "INFO", "owner-only-event")
        app = AppTest.from_file(str(APP_PATH)).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("iframe")), 0)
        app.text_input[0].set_value("other")
        app.text_input[1].set_value("other-password-123")
        next(button for button in app.button if button.label == "Entrar").click().run()
        self.assertFalse(app.exception, [item.message for item in app.exception])
        self.assertEqual(len(app.get("iframe")), 1)
        self.assertNotIn("owner-only-event", app.get("iframe")[0].proto.srcdoc)
        next(button for button in app.button if button.label == "Sair").click().run()
        self.assertEqual(len(app.get("iframe")), 0)

    def test_first_run_bootstrap_preserves_legacy_workspace(self):
        with patch.object(store, "IDENTITY_DB_PATH", Path(self.tmp.name) / "fresh_identity.db"):
            store.add_event("Legacy", "INFO", "historico-preservado")
            app = AppTest.from_file(str(APP_PATH)).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.get("iframe")), 0)
            app.text_input[0].set_value("new_owner")
            app.text_input[1].set_value("new-owner-password-123")
            app.text_input[2].set_value("new-owner-password-123")
            next(button for button in app.button if button.label == "Criar acesso principal").click().run()
            self.assertFalse(app.exception, [item.message for item in app.exception])
            self.assertEqual(len(app.get("iframe")), 1)
            self.assertIn("historico-preservado", app.get("iframe")[0].proto.srcdoc)

    def test_online_mode_never_offers_public_owner_registration(self):
        with patch.object(store, "IDENTITY_DB_PATH", Path(self.tmp.name) / "online_identity.db"), \
             patch.dict("os.environ", {"TRADING_LAB_ONLINE_MODE": "1"}):
            app = AppTest.from_file(str(APP_PATH)).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.get("iframe")), 0)
            self.assertFalse(any(button.label == "Criar acesso principal" for button in app.button))
            self.assertEqual(store.identity_user_count(), 0)

    def test_online_session_expires_after_eight_hours(self):
        with patch.dict("os.environ", {"TRADING_LAB_ONLINE_MODE": "1"}):
            app = AppTest.from_file(str(APP_PATH))
            app.session_state["auth-user"] = {key: self.owner[key] for key in ("id", "username", "role")}
            app.session_state["vault-key"] = self.owner["vault_key"]
            app.session_state["auth-at"] = time.time() - 9 * 3600
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.get("iframe")), 0)


if __name__ == "__main__":
    unittest.main()
