"""The first rebuilt screen shows only real, persisted paper operations."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from database import store
from services import credential_vault, market_data

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class OperationsPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(store, "DB_PATH", root / "trading.db"),
            patch.object(store, "IDENTITY_DB_PATH", root / "identity.db"),
            patch.object(store, "GLOBAL_DB_PATH", root / "global.db"),
            patch.object(store, "WORKSPACES_DIR", root / "workspaces"),
            patch.object(credential_vault, "VAULT_DIR", root / "vault"),
        ]
        for item in self.patches:
            item.start()
        store.initialize()
        store.create_identity_user("test_owner", "testhash", "dGVzdHNhbHQxMjM0NTY3OA==", "owner")

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def app(self):
        app = AppTest.from_file(str(APP_PATH))
        app.run(timeout=15)
        self.assertFalse(app.exception, [item.message for item in app.exception])
        return app

    def seed_closed_operation(self):
        rules = {"engine": "setup_pattern_v1", "setup_id": "SETUP_03", "setup_name": "BOP",
                 "side": "buy", "approval": "rules_human_approved",
                 "pattern": {"kind": "compressed_base", "min_bars": 3, "max_bars": 8,
                             "max_range_atr20": 1.5, "trend_ma": 8}}
        strategy_id = store.save_strategy("BOP", rules, "fixture")
        store.approve_strategy(strategy_id)
        signal = "2026-11-18T22:05:00+00:00"
        entry = "2026-11-18T22:10:00+00:00"
        exit_time = "2026-11-18T22:45:00+00:00"
        report = {
            "execution": {"entrada": 100.0, "stop": 99.0, "alvo": 101.0,
                          "side": "buy", "barra_de_entrada_utc": entry},
            "decision": {"decisao": "trade_candidate", "fatores_contrarios": ["Amostra curta."]},
            "risk": {"verdict": "autorizado", "checks": [{"estado": "ok", "detalhe": "Risco dentro do limite."}]},
            "market": {"provedor": market_data.PROVIDER, "feed_status": "connected",
                       "tendencia": {"media_movel_periodo": 8, "inclinacao": 0.4}},
        }
        run_id = store.save_pipeline_run("agent_pipeline_v1", strategy_id, "SETUP_03",
                                         "BOP", "ETHUSDT", "5m", signal,
                                         "trade_candidate", risk_verdict="autorizado",
                                         status="aguardando_quantidade", report=report)
        operation_id = store.open_paper_operation("ETHUSDT", "buy", 0.02, 100.0,
                                                  "pipeline fixture", pipeline_run_id=run_id)
        store.close_paper_operation(
            operation_id, 99.9, "stop", datetime.now(timezone.utc).isoformat(),
            fees=0.004, realized_r=-0.7,
            journal_details={"entry_time": entry, "exit_time": exit_time,
                             "net_pnl": -0.006, "quote_currency": "USDT",
                             "fee_bps_per_side": 10, "slippage_bps_per_side": 5,
                             "conduction": {"initial_stop": 99.0, "final_stop": 99.0}})
        origin = datetime(2026, 11, 18, 21, 0, tzinfo=timezone.utc)
        bars = [{"timestamp": (origin + timedelta(minutes=i)).isoformat(),
                 "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
                 "volume": 3.0} for i in range(150)]
        store.upsert_market_bars(market_data.PROVIDER, "ETHUSDT", "1m", bars)
        return operation_id

    def test_local_operations_open_without_login(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        self.assertFalse(app.exception)
        self.assertFalse(any(item.key == "tal-page" for item in app.radio))
        self.assertTrue(any("Operações" in str(item.value) for item in app.title))
        self.assertFalse(any("Usuário" in str(item.label) or "Senha" in str(item.label)
                             for item in app.text_input))

    def test_operations_page_and_explicit_empty_state(self):
        app = self.app()
        self.assertEqual(len(app.get("iframe")), 0)
        self.assertFalse(any(item.key == "tal-page" for item in app.radio))
        rendered = "\n".join(str(item.value) for item in app.markdown)
        self.assertTrue(any("Operações" in str(item.value) for item in app.title))
        self.assertIn("Somente simulação", rendered)
        self.assertTrue(any("Nenhuma operação" in str(item.value) for item in app.info))
        rendered = "\n".join(str(item.value) for item in app.markdown)
        self.assertIn('href="?pagina=mercado"', rendered)
        self.assertIn("tal-bottom-nav", rendered)

    def test_market_page_has_title_card_and_no_explanatory_copy(self):
        app = self.app()
        app.query_params["pagina"] = "mercado"
        app.run()
        self.assertFalse(app.exception, [item.message for item in app.exception])
        self.assertEqual(len(app.get("iframe")), 1)
        rendered = "\n".join(str(item.value) for item in app.markdown)
        self.assertIn('class="market-hero"', rendered)
        self.assertIn("<h1>Mercado</h1>", rendered)
        self.assertEqual(len(app.caption), 0)
        self.assertFalse(any(str(item.label) == "Aparência" for item in app.selectbox))
        self.assertNotIn("BINANCE:BTCUSDT", rendered)
        self.assertNotIn("feed local persistido", rendered)
        self.assertIn('href="?pagina=operacoes"', rendered)

    def test_click_opens_detail_with_setup_timeframe_cause_and_result(self):
        operation_id = self.seed_closed_operation()
        app = self.app()
        rendered = "\n".join(str(item.value) for item in app.markdown)
        self.assertIn("BOP", rendered)
        self.assertIn("5m", rendered)
        self.assertIn("-0.006000 USDT", rendered)
        self.assertIn(f'?operacao={operation_id}', rendered)
        app.query_params["operacao"] = str(operation_id)
        app.run()
        self.assertFalse(app.exception, [item.message for item in app.exception])
        rendered = "\n".join(str(item.value) for item in app.markdown)
        self.assertIn(f"Operação #{operation_id}", rendered)
        self.assertTrue(any("Por que entrou" in str(item.value) for item in app.subheader))
        self.assertTrue(any("Como saiu" in str(item.value) for item in app.subheader))
        self.assertTrue(any("Acompanhe a operação" in str(item.value) for item in app.subheader))
        next(button for button in app.button if button.key == f"next-step-{operation_id}").click().run()
        self.assertFalse(app.exception, [item.message for item in app.exception])
        rendered = "\n".join(str(item.value) for item in app.markdown)
        self.assertIn("Stop definido no plano", rendered)
        self.assertIn("Nenhuma saída parcial registrada", "\n".join(str(item.value) for item in app.caption))
        self.assertIn("Formação", rendered)
        self.assertTrue(any("Binance Spot ETHUSDT" in str(item.value) for item in app.caption))
        self.assertIn('href="?"', rendered)
        app.query_params.pop("operacao")
        app.run()
        self.assertFalse(app.exception, [item.message for item in app.exception])
        self.assertIn(f'?operacao={operation_id}', "\n".join(str(item.value) for item in app.markdown))

    def test_kill_switch_still_accessible_on_only_page(self):
        app = self.app()
        app.text_input(key="kill-switch-reason-on").set_value("Pausa operacional")
        app.button(key="kill-switch-activate").click().run()
        self.assertTrue(store.get_kill_switch()["enabled"])
        app.text_input(key="kill-switch-confirm-off").set_value("DESBLOQUEAR")
        app.button(key="kill-switch-deactivate").click().run()
        self.assertFalse(store.get_kill_switch()["enabled"])


if __name__ == "__main__":
    unittest.main()
