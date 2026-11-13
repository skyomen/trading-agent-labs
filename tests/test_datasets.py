import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import store
from services import datasets


CSV = ("timestamp,open,high,low,close,volume\n"
       "2026-11-13T00:00:00Z,100,102,99,101,10\n"
       "2026-11-13T00:01:00Z,101,103,100,102,11\n"
       "2026-11-13T00:03:00Z,102,104,101,103,12\n").encode()
MANIFEST = {"symbol": "BTCUSDT", "market": "crypto", "provider": "fixture-local",
            "timeframe": "1m", "timezone": "UTC", "quote_currency": "USDT",
            "tick_size": "0.01", "volume_unit": "BTC", "license_note": "test fixture"}


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(store, "DB_PATH", Path(self.temp.name) / "test.db")
        self.patch.start()
        store.initialize()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_import_roundtrip_is_reproducible_and_idempotent(self):
        result = datasets.import_csv(CSV, "fixture.csv", MANIFEST)
        self.assertEqual(result["metadata"]["gap_count"], 1)
        restored = datasets.load_verified(result["id"])
        self.assertEqual(len(restored["bars"]), 3)
        self.assertEqual(restored["dataset"]["sha256"], result["sha256"])
        self.assertEqual(restored["dataset"]["canonical_sha256"], result["canonical_sha256"])
        self.assertEqual(datasets.import_csv(CSV, "fixture.csv", MANIFEST)["id"], result["id"])

    def test_manifest_rejects_missing_metadata_and_hash_collision(self):
        with self.assertRaises(ValueError):
            datasets.import_csv(CSV, "fixture.csv", {"symbol": "BTCUSDT"})
        datasets.import_csv(CSV, "fixture.csv", MANIFEST)
        with self.assertRaises(ValueError):
            datasets.import_csv(CSV, "fixture.csv", {**MANIFEST, "symbol": "ETHUSDT"})

    def test_rejects_non_utc_and_interval_mismatch(self):
        bad_zone = CSV.replace(b"Z", b"-03:00")
        with self.assertRaises(ValueError):
            datasets.import_csv(bad_zone, "zone.csv", MANIFEST)
        bad_interval = CSV.replace(b"00:03:00Z", b"00:03:30Z")
        with self.assertRaises(ValueError):
            datasets.import_csv(bad_interval, "interval.csv", MANIFEST)
