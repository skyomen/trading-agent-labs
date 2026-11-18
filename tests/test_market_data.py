import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import store
from services import market_data, datasets


class MarketDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(store, "DB_PATH", Path(self.temp.name) / "test.db")
        self.db_patch.start()
        store.initialize()

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def test_public_klines_import_closed_bars_and_roundtrip(self):
        rows = [[i * 60000, "100", "102", "99", "101", "5", (i + 1) * 60000 - 1]
                for i in range(4)]
        with patch.object(market_data, "urlopen", return_value=io.BytesIO(json.dumps(rows).encode())), \
             patch.object(market_data.time, "time", return_value=210):
            result = market_data.import_recent("BTCUSDT", limit=4)
        self.assertEqual(result["metadata"]["row_count"], 3)
        self.assertEqual(result["metadata"]["source_url"], market_data.REST)
        self.assertEqual(len(datasets.load_verified(result["id"])["bars"]), 3)

    def test_stock_connector_requires_local_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "ALPACA_API_KEY"):
                market_data.import_alpaca_stock("AAPL", "2026-11-10T00:00:00Z", "2026-11-11T00:00:00Z")
        self.assertEqual(store.list_historical_datasets(), [])

    def test_public_stock_sample_is_historical_and_reproducible(self):
        content = ("symbol,timestamp,open,high,low,close,volume\n"
                   "AAPL,2026-11-10T14:00:00Z,100,102,99,101,1000\n"
                   "AAPL,2026-11-10T15:00:00Z,101,103,100,102,1100\n"
                   "AAPL,2026-11-10T16:00:00Z,102,104,101,103,1200\n").encode()
        with patch.object(market_data, "urlopen", return_value=io.BytesIO(content)):
            result = market_data.import_public_stock_history("AAPL")
        restored = datasets.load_verified(result["id"])
        self.assertEqual(restored["metadata"]["market_session"], "historical sample; not live")
        self.assertEqual(len(restored["bars"]), 3)


if __name__ == "__main__":
    unittest.main()
