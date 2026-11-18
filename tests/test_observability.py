"""Health snapshot proof: every field and alert comes only from what is already
persisted (store.py), never from a live network probe. See services/observability.py.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from database import store
from services import observability


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.patch = patch.object(store, "DB_PATH", self.db)
        self.patch.start()
        store.initialize()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_fresh_empty_database_does_not_break_the_snapshot(self):
        snapshot = observability.get_health_snapshot()
        self.assertEqual(
            set(snapshot),
            {"generated_at", "integrity", "heartbeats", "feeds", "uncertain_orders",
             "open_operations", "open_operations_count", "kill_switch", "alerts"},
        )
        self.assertEqual(snapshot["integrity"]["ok"], True)
        self.assertEqual(snapshot["integrity"]["result"], "ok")
        # EXPECTED_COMPONENTS are always reported, even with nothing recorded yet.
        self.assertEqual(len(snapshot["heartbeats"]), 3)
        for item in snapshot["heartbeats"]:
            self.assertEqual(item["status"], "nunca registrado")
        self.assertEqual(snapshot["feeds"], [])
        self.assertEqual(snapshot["uncertain_orders"], [])
        self.assertEqual(snapshot["open_operations"], [])
        self.assertEqual(snapshot["open_operations_count"], 0)
        self.assertFalse(snapshot["kill_switch"]["enabled"])

    def test_old_feed_appears_as_feed_and_as_alert(self):
        now = datetime.now(timezone.utc)
        old_bar = (now - timedelta(seconds=observability.FEED_BAR_MAX_AGE_SECONDS + 30)).isoformat()
        store.update_market_feed("Binance", "BTCUSDT", "2m", "connected", last_bar_at=old_bar)

        snapshot = observability.get_health_snapshot(now=now)

        self.assertEqual(len(snapshot["feeds"]), 1)
        feed = snapshot["feeds"][0]
        self.assertEqual(feed["symbol"], "BTCUSDT")
        self.assertFalse(feed["current"])
        feed_alerts = [a for a in snapshot["alerts"] if a["kind"] == "feed"]
        self.assertEqual(len(feed_alerts), 1)
        self.assertEqual(feed_alerts[0]["severity"], observability.SEVERITY_WARNING)

    def test_current_feed_is_not_an_alert(self):
        now = datetime.now(timezone.utc)
        store.update_market_feed("Binance", "BTCUSDT", "2m", "connected",
                                 last_bar_at=now.isoformat())

        snapshot = observability.get_health_snapshot(now=now)

        self.assertEqual(len(snapshot["feeds"]), 1)
        self.assertTrue(snapshot["feeds"][0]["current"])
        self.assertEqual([a for a in snapshot["alerts"] if a["kind"] == "feed"], [])

    def test_unknown_testnet_order_appears_as_uncertain_and_as_alert(self):
        run_id = store.save_pipeline_run(
            "pipeline_v1", None, "SETUP_01", "VBS", "BTCUSDT", "2m",
            "2026-11-16T10:00:00+00:00", "trade_candidate")
        with store.connect() as conn:
            conn.execute(
                """INSERT INTO broker_paper_orders
                    (run_id,provider,role,client_order_id,symbol,side,quantity,limit_price,state)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                (run_id, "Binance Spot Testnet", "entry", "test-client-order-1",
                 "BTCUSDT", "BUY", "1", "100", "unknown"))

        snapshot = observability.get_health_snapshot()

        self.assertEqual(len(snapshot["uncertain_orders"]), 1)
        self.assertEqual(snapshot["uncertain_orders"][0]["client_order_id"], "test-client-order-1")
        order_alerts = [a for a in snapshot["alerts"] if a["kind"] == "ordem_testnet"]
        self.assertEqual(len(order_alerts), 1)
        self.assertEqual(order_alerts[0]["severity"], observability.SEVERITY_WARNING)

    def test_open_paper_operation_appears_as_open_and_as_informative_alert(self):
        store.open_paper_operation("BTCUSDT", "buy", 0.5, 95000.0, "pipeline")

        snapshot = observability.get_health_snapshot()

        self.assertEqual(len(snapshot["open_operations"]), 1)
        self.assertEqual(snapshot["open_operations_count"], 1)
        operation_alerts = [a for a in snapshot["alerts"] if a["kind"] == "operacao_paper"]
        self.assertEqual(len(operation_alerts), 1)
        # Entrega 15: an open position is a reminder to act, not a failure — informativo,
        # not atencao/critico.
        self.assertEqual(operation_alerts[0]["severity"], observability.SEVERITY_INFO)

    def test_heartbeat_never_recorded_is_reported_as_such(self):
        snapshot = observability.get_health_snapshot()
        by_component = {item["component"]: item for item in snapshot["heartbeats"]}
        self.assertEqual(by_component["collector:BTCUSDT"]["status"], "nunca registrado")
        self.assertIsNone(by_component["collector:BTCUSDT"]["last_seen_at"])
        info_alerts = [a for a in snapshot["alerts"]
                      if a["kind"] == "heartbeat" and "collector:BTCUSDT" in a["message"]]
        self.assertEqual(len(info_alerts), 1)
        self.assertEqual(info_alerts[0]["severity"], observability.SEVERITY_INFO)

    def test_old_collector_heartbeat_is_reported_as_stopped(self):
        store.record_heartbeat("collector:BTCUSDT", "ok", "candle fechado")
        now = datetime.now(timezone.utc) + timedelta(
            seconds=observability.COLLECTOR_HEARTBEAT_MAX_AGE_SECONDS + 30)

        snapshot = observability.get_health_snapshot(now=now)

        by_component = {item["component"]: item for item in snapshot["heartbeats"]}
        self.assertEqual(by_component["collector:BTCUSDT"]["status"], "parado")
        warning_alerts = [a for a in snapshot["alerts"]
                          if a["kind"] == "heartbeat" and "collector:BTCUSDT" in a["message"]]
        self.assertEqual(len(warning_alerts), 1)
        self.assertEqual(warning_alerts[0]["severity"], observability.SEVERITY_WARNING)

    def test_app_heartbeat_with_moderate_age_stays_active_not_critical(self):
        store.record_heartbeat("app", "ok", "render concluido")
        # Older than the collector's own budget (180s) but nowhere near the app's much
        # looser 86400s budget: must still read as "ativo", with no stale alert.
        now = datetime.now(timezone.utc) + timedelta(
            seconds=observability.COLLECTOR_HEARTBEAT_MAX_AGE_SECONDS + 30)

        snapshot = observability.get_health_snapshot(now=now)

        by_component = {item["component"]: item for item in snapshot["heartbeats"]}
        self.assertEqual(by_component["app"]["status"], "ativo")
        self.assertFalse(by_component["app"]["stale"])
        app_alerts = [a for a in snapshot["alerts"]
                     if a["kind"] == "heartbeat" and "app " in a["message"]]
        self.assertEqual(app_alerts, [])

    def test_active_kill_switch_appears_in_snapshot_and_as_alert(self):
        store.set_kill_switch(True, "incidente em investigação", "ana")

        snapshot = observability.get_health_snapshot()

        self.assertTrue(snapshot["kill_switch"]["enabled"])
        self.assertEqual(snapshot["kill_switch"]["reason"], "incidente em investigação")
        self.assertEqual(snapshot["kill_switch"]["actor"], "ana")
        kill_alerts = [a for a in snapshot["alerts"] if a["kind"] == "bloqueio"]
        self.assertEqual(len(kill_alerts), 1)
        self.assertEqual(kill_alerts[0]["severity"], observability.SEVERITY_INFO)


if __name__ == "__main__":
    unittest.main()
