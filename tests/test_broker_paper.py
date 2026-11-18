"""Offline proof of the external virtual-order gate and reconciliation."""

import tempfile
import unittest
import hashlib
import hmac
import json
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from database import store
from services import broker_paper, execution
from services.brokers.binance_spot_testnet import BinanceSpotTestnet, BrokerError, BASE_URL


class FakeBroker:
    configured = True
    name = "Binance Spot Testnet"

    def __init__(self):
        self.sent = []
        self.responses = {}
        self.fail_next = False

    def quote(self, symbol):
        return {"symbol": symbol, "ask": "100", "bid": "99.9",
                "fetched_at": datetime.now(timezone.utc).isoformat(), "provider": self.name}

    def validate_limit(self, symbol, quantity, price):
        quantity, price = float(quantity), float(price)
        if quantity <= 0 or price <= 0 or quantity * price < 10:
            raise BrokerError("Filtros inválidos.")
        return str(quantity), str(price)

    def place_limit(self, symbol, side, quantity, price, client_order_id):
        self.sent.append((symbol, side, client_order_id))
        if self.fail_next:
            self.fail_next = False
            raise TimeoutError()
        response = self._response(client_order_id, "NEW", "0")
        self.responses[client_order_id] = response
        return response

    def _response(self, client_id, state, filled):
        return {"symbol": "BTCUSDT", "orderId": 123,
                "clientOrderId": client_id, "status": state,
                "executedQty": filled, "cummulativeQuoteQty": str(float(filled) * 100)}

    def get_order(self, symbol, client_id):
        return self.responses[client_id]

    def cancel_order(self, symbol, client_id):
        response = dict(self.responses[client_id], status="CANCELED")
        self.responses[client_id] = response
        return response


class BrokerPaperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch_db = patch.object(store, "DB_PATH", Path(self.tmp.name) / "test.db")
        self.patch_db.start()
        store.initialize()
        self.fake = FakeBroker()
        self.run_id = store.save_pipeline_run(
            "test", None, "VBS", "VBS", "BTCUSDT", "2m",
            "2026-01-01T00:00:00+00:00", "trade_candidate",
            risk_verdict="autorizado", status="aguardando_quantidade",
            report={"execution": {"side": "buy", "entrada": 100}},
            pending_since=datetime.now(timezone.utc).isoformat())

    def tearDown(self):
        self.patch_db.stop()
        self.tmp.cleanup()

    def test_human_gate_intent_and_no_duplicate_local_open(self):
        with self.assertRaisesRegex(ValueError, "Confirme"):
            broker_paper.submit_entry(self.run_id, 1, 100, adapter=self.fake)
        self.assertEqual(self.fake.sent, [])
        order = broker_paper.submit_entry(self.run_id, 1, 100, confirmed=True, adapter=self.fake)
        self.assertEqual(order["state"], "NEW")
        self.assertEqual(len(self.fake.sent), 1)
        with self.assertRaises(ValueError):
            broker_paper.submit_entry(self.run_id, 1, 100, confirmed=True, adapter=self.fake)
        with self.assertRaises(ValueError):
            execution.confirm_open(self.run_id, 1)
        self.assertEqual(len(self.fake.sent), 1)
        self.assertEqual(store.list_paper_operations(), [])

    def test_timeout_is_unknown_and_reconciles_without_resend(self):
        self.fake.fail_next = True
        with self.assertRaisesRegex(BrokerError, "desconhecido"):
            broker_paper.submit_entry(self.run_id, 1, 100, confirmed=True, adapter=self.fake)
        order = store.get_broker_entry_for_run(self.run_id)
        self.assertEqual(order["state"], "unknown")
        self.assertEqual(len(self.fake.sent), 1)
        with self.assertRaises(ValueError):
            broker_paper.submit_entry(self.run_id, 1, 100, confirmed=True, adapter=self.fake)
        self.fake.responses[order["client_order_id"]] = self.fake._response(
            order["client_order_id"], "FILLED", "1")
        observed = broker_paper.reconcile(order["id"], self.fake)
        self.assertEqual(observed["executed_qty"], 1)
        self.assertEqual(store.get_pipeline_run(self.run_id)["status"], "posicao_aberta")
        self.assertEqual(len(self.fake.sent), 1)

    def test_cancel_and_exit_quantity_cap(self):
        order = broker_paper.submit_entry(self.run_id, 1, 100, confirmed=True, adapter=self.fake)
        client_id = order["client_order_id"]
        self.fake.responses[client_id] = self.fake._response(client_id, "PARTIALLY_FILLED", "0.6")
        broker_paper.reconcile(order["id"], self.fake)
        canceled = broker_paper.cancel(order["id"], self.fake)
        self.assertEqual(canceled["state"], "CANCELED")
        with self.assertRaises(ValueError):
            broker_paper.submit_exit(order["id"], 1, 99.9, confirmed=True, adapter=self.fake)
        sold = broker_paper.submit_exit(order["id"], 0.6, 99.9,
                                        confirmed=True, adapter=self.fake)
        self.assertEqual(sold["side"], "SELL")
        self.assertEqual(self.fake.sent[-1][1], "SELL")
        self.assertEqual(store.list_paper_operations(), [])

    def test_short_signal_rejected(self):
        run_id = store.save_pipeline_run(
            "test", None, "VSS", "VSS", "ETHUSDT", "2m",
            "2026-01-01T00:02:00+00:00", "trade_candidate",
            risk_verdict="autorizado", status="aguardando_quantidade",
            report={"execution": {"side": "sell", "entrada": 100}},
            pending_since=datetime.now(timezone.utc).isoformat())
        with self.assertRaisesRegex(ValueError, "comprados"):
            broker_paper.submit_entry(run_id, 1, 100, confirmed=True, adapter=self.fake)
        self.assertEqual(self.fake.sent, [])

    def test_reconciliation_cannot_undo_fill_or_oversell(self):
        order = broker_paper.submit_entry(self.run_id, 1, 100, confirmed=True, adapter=self.fake)
        client_id = order["client_order_id"]
        self.fake.responses[client_id] = self.fake._response(client_id, "FILLED", "1")
        broker_paper.reconcile(order["id"], self.fake)
        self.fake.responses[client_id] = self.fake._response(client_id, "NEW", "0")
        with self.assertRaises(ValueError):
            broker_paper.reconcile(order["id"], self.fake)
        self.assertEqual(store.get_broker_paper_order(order["id"])["state"], "FILLED")
        with self.assertRaises(ValueError):
            store.reserve_broker_exit(order["id"], broker_paper.PROVIDER,
                                      "oversell", "1.000000001", "100")

    def test_adapter_has_fixed_testnet_host_and_no_keys_without_credentials(self):
        with patch.dict("os.environ", {"BINANCE_SPOT_TESTNET_API_KEY": "",
                                     "BINANCE_SPOT_TESTNET_API_SECRET": ""}):
            adapter = BinanceSpotTestnet(opener=lambda *a, **kw: self.fail("network called"))
            self.assertFalse(adapter.configured)
            self.assertEqual(adapter.connection_status()["state"], "disconnected")
            with self.assertRaises(BrokerError):
                adapter.get_order("BTCUSDT", "id")
        self.assertEqual(BASE_URL, "https://testnet.binance.vision")

    def test_adapter_signs_only_fixed_testnet_request(self):
        captured = []

        def opener(request, timeout):
            captured.append(request)
            return BytesIO(json.dumps({"canTrade": True}).encode())

        with patch.dict("os.environ", {"BINANCE_SPOT_TESTNET_API_KEY": "test-key",
                                     "BINANCE_SPOT_TESTNET_API_SECRET": "test-secret"}):
            adapter = BinanceSpotTestnet(opener=opener, clock_ms=lambda: 123456)
            self.assertEqual(adapter.connection_status()["state"], "connected")
        request = captured[0]
        parsed = urlparse(request.full_url)
        self.assertEqual(parsed.netloc, "testnet.binance.vision")
        self.assertEqual(parsed.path, "/api/v3/account")
        params = parse_qs(parsed.query)
        signature = params.pop("signature")[0]
        self.assertEqual(params["timestamp"], ["123456"])
        unsigned = parsed.query.split("&signature=")[0]
        self.assertEqual(signature, hmac.new(b"test-secret", unsigned.encode(),
                                             hashlib.sha256).hexdigest())
        self.assertNotIn("test-secret", request.full_url)

    def test_submit_entry_refuses_when_kill_switch_is_active_and_reserves_nothing(self):
        store.set_kill_switch(True, "incidente em investigação", "ana")
        with self.assertRaisesRegex(ValueError, "[Bb]loquead"):
            broker_paper.submit_entry(self.run_id, 1, 100, confirmed=True, adapter=self.fake)
        self.assertEqual(self.fake.sent, [])
        self.assertIsNone(store.get_broker_entry_for_run(self.run_id))

    def test_cancel_submit_exit_and_reconcile_still_work_while_kill_switch_is_active(self):
        order = broker_paper.submit_entry(self.run_id, 1, 100, confirmed=True, adapter=self.fake)
        client_id = order["client_order_id"]
        self.fake.responses[client_id] = self.fake._response(client_id, "PARTIALLY_FILLED", "0.6")

        store.set_kill_switch(True, "incidente em investigação", "ana")

        reconciled = broker_paper.reconcile(order["id"], self.fake)
        self.assertEqual(reconciled["executed_qty"], 0.6)
        canceled = broker_paper.cancel(order["id"], self.fake)
        self.assertEqual(canceled["state"], "CANCELED")
        sold = broker_paper.submit_exit(order["id"], 0.6, 99.9,
                                        confirmed=True, adapter=self.fake)
        self.assertEqual(sold["side"], "SELL")

    def test_adapter_validates_exchange_filters(self):
        def opener(request, timeout):
            data = {"symbols": [{"symbol": "BTCUSDT", "status": "TRADING",
                                 "orderTypes": ["LIMIT"], "filters": [
                                     {"filterType": "PRICE_FILTER", "minPrice": "1", "maxPrice": "1000", "tickSize": "0.1"},
                                     {"filterType": "LOT_SIZE", "minQty": "0.1", "maxQty": "100", "stepSize": "0.1"},
                                     {"filterType": "MIN_NOTIONAL", "minNotional": "10"}]}]}
            return BytesIO(json.dumps(data).encode())

        adapter = BinanceSpotTestnet(opener=opener)
        self.assertEqual(adapter.validate_limit("BTCUSDT", "0.1", "100"), ("0.1", "100"))
        for quantity, price in (("0.11", "100"), ("0.1", "100.01"), ("0.1", "50")):
            with self.assertRaises(BrokerError):
                adapter.validate_limit("BTCUSDT", quantity, price)


if __name__ == "__main__":
    unittest.main()
