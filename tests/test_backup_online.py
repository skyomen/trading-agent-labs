"""Cold backup, authenticated encryption, and isolated restore."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import store
from scripts.backup_online import create_backup, verify_backup


class OnlineBackupTests(unittest.TestCase):
    def test_encrypted_backup_restores_database_vault_and_pdf(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            data = root / "data"
            docs = root / "reference_docs"
            data.mkdir()
            docs.mkdir()
            with patch.object(store, "DB_PATH", data / "trading.db"):
                store.initialize()
                store.add_event("Teste", "INFO", "evento-privado")
            (data / "vault").mkdir()
            (data / "vault" / "sample.json").write_text("cofre-cifrado", encoding="utf-8")
            (docs / "shared").mkdir()
            (docs / "shared" / "sample.pdf").write_bytes(b"%PDF-1.4\nfixture")
            backup = root / "backup.tlab"
            self.assertEqual(create_backup(data, docs, backup, "backup-password-123"), 3)
            self.assertNotIn(b"evento-privado", backup.read_bytes())
            self.assertEqual(verify_backup(backup, "backup-password-123"), 3)
            restored = root / "restored"
            verify_backup(backup, "backup-password-123", restored)
            with patch.object(store, "DB_PATH", restored / "data" / "trading.db"):
                self.assertTrue(any(row["Atividade"] == "evento-privado" for row in store.list_events()))
            self.assertEqual((restored / "reference_docs" / "shared" / "sample.pdf").read_bytes(),
                             b"%PDF-1.4\nfixture")
            with self.assertRaisesRegex(ValueError, "vazio"):
                verify_backup(backup, "backup-password-123", restored)

    def test_wrong_password_and_tampering_are_rejected(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            data, docs = root / "data", root / "reference_docs"
            data.mkdir()
            docs.mkdir()
            (data / "sample.txt").write_bytes(b"fixture")
            backup = root / "backup.tlab"
            create_backup(data, docs, backup, "backup-password-123")
            with self.assertRaisesRegex(ValueError, "incorreta"):
                verify_backup(backup, "wrong-password-123")
            raw = bytearray(backup.read_bytes())
            raw[-20] ^= 1
            backup.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "alterado"):
                verify_backup(backup, "backup-password-123")


if __name__ == "__main__":
    unittest.main()
