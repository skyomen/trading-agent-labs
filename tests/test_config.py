import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import config


class LocalConfigTests(unittest.TestCase):
    def test_env_file_loads_without_replacing_process_values(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, ".env").write_text(
                "ALPACA_API_KEY=fixture-file-key\nALPACA_API_SECRET=fixture-secret\n",
                encoding="utf-8",
            )
            with patch.object(config, "ROOT", Path(folder)), \
                 patch.dict(os.environ, {"ALPACA_API_KEY": "fixture-process-key"}, clear=True):
                self.assertTrue(config.load_local_env())
                self.assertEqual(os.environ["ALPACA_API_KEY"], "fixture-process-key")
                self.assertEqual(os.environ["ALPACA_API_SECRET"], "fixture-secret")


if __name__ == "__main__":
    unittest.main()
