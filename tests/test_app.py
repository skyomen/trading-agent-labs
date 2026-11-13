import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from database import store
from services import datasets as dataset_service

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
REFERENCE_PATH = APP_PATH.with_name("referencia.html")

SOURCE_PDF = "reference_docs/shared/fixture.pdf"
INDEXED_LIBRARY = [{"path": SOURCE_PDF, "status": "indexed",
                    "record": {"sha256": "fixture-pdf-hash"}}]


def app_for_local_lab():
    app = AppTest.from_file(str(APP_PATH))
    app.query_params["lab"] = "1"
    return app


def approved_setup_strategy():
    """An approved setup version bound to an indexed fixture PDF."""
    rules = {"engine": "setup_pattern_v1", "setup_id": "SETUP_03", "setup_name": "BOP",
             "side": "buy", "timeframes": ["2m"], "approval": "rules_human_approved",
             "pattern": {"kind": "compressed_base", "min_bars": 3, "max_bars": 8,
                         "max_range_atr20": 1.5, "trend_ma": 8, "trend_slope_bars": 3},
             "source": [{"path": SOURCE_PDF, "sha256": "fixture-pdf-hash", "pages": [1]}]}
    strategy_id = store.save_strategy("BOP · fixture", rules, "PDF local")
    store.approve_strategy(strategy_id)
    return next(row for row in store.list_strategies() if row["id"] == strategy_id)


def verified_crypto_dataset(count=400):
    """A flat Binance-shaped 1m snapshot: verifiable, and it produces no signal."""
    origin = datetime(2026, 11, 12, 20, 0, tzinfo=timezone.utc)
    bars = [{"timestamp": (origin + timedelta(minutes=i)).isoformat(),
             "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 5.0}
            for i in range(count)]
    metadata = {"symbol": "BTCUSDT", "market": "crypto", "provider": "Binance Spot public",
                "timeframe": "1m", "timezone": "UTC", "quote_currency": "USDT",
                "tick_size": "0.01", "volume_unit": "BTC", "license_note": "fixture",
                "start_utc": bars[0]["timestamp"], "end_utc": bars[-1]["timestamp"],
                "row_count": len(bars), "gap_count": 0, "gap_examples": []}
    dataset_id = store.save_historical_dataset(
        "btc-fixture.csv", "BTCUSDT", "1m", "Binance Spot public", "fixture-file-hash",
        bars, metadata=metadata, canonical_sha256=dataset_service.canonical_digest(bars))
    return next(row for row in store.list_historical_datasets() if row["id"] == dataset_id)


def closed_paper_operation(symbol, side, quantity, entry_price, exit_price, fees):
    """Insert a closed paper operation directly (no store helper exists for this yet)."""
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO paper_operations (symbol, side, quantity, entry_price, exit_price, "
            "fees, source, state, closed_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (symbol, side, quantity, entry_price, exit_price, fees, "fixture", "closed",
             "2026-11-13T00:00:00Z"),
        )
    return store.list_paper_operations()[0]


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "dashboard.db"
        self.db_patch = patch.object(store, "DB_PATH", self.db_path)
        self.db_patch.start()
        store.initialize()

    def tearDown(self):
        self.db_patch.stop()
        self.tmp.cleanup()

    def test_default_portal_localizes_reference_and_uses_local_agent_records(self):
        app = AppTest.from_file(str(APP_PATH)).run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        self.assertEqual(len(app.get("iframe")), 1)
        iframe = app.get("iframe")[0]
        rendered = iframe.proto.srcdoc
        self.assertIn('<html lang="pt-BR">', rendered)
        self.assertIn("Trading Agent Lab", rendered)
        for agent in store.get_agents():
            self.assertIn(agent["name"], rendered)
            self.assertIn(agent["status"], rendered)
        self.assertIn("Sem feed de mercado", rendered)
        self.assertIn("XP Trader desconectado", rendered)
        self.assertIn("Operações", rendered)
        self.assertIn("function pintarTab()", rendered)
        self.assertIn("function selecionar(i)", rendered)
        self.assertIn("Último evento registrado", rendered)
        self.assertIn("Estado de risco", rendered)
        self.assertIn('class="ticker"', rendered)
        self.assertIn("function saldoRealizado()", rendered)
        self.assertIn("cortar(a.status,13)", rendered)
        self.assertIn("function pintarSalaCompacta()", rendered)
        self.assertIn("wrapSvgText(a.status,27)", rendered)
        self.assertIn('floor.setAttribute("viewBox","0 0 390 "+alto)', rendered)
        self.assertIn('width="358" height="23"', rendered)
        self.assertIn('width="166" height="49"', rendered)
        self.assertIn("overflow-x:hidden!important;overflow-y:auto!important", rendered)
        self.assertIn(".tabs{overflow:hidden!important", rendered)
        self.assertNotIn(".tabs{overflow-x:auto", rendered)
        self.assertNotIn("KakidLuffy/oficina-agentes", rendered)
        self.assertNotIn("raw.githubusercontent.com", rendered)
        self.assertNotIn("api.kraken.com", rendered)
        self.assertNotIn("Cruce 10/30", rendered)
        self.assertNotIn("Dinero ficticio", rendered)
        self.assertIn(".pane{overflow:visible!important", rendered)
        self.assertIn(".salaw{width:calc(100% - 24px)!important", rendered)
        self.assertIn("#floor{display:block;width:100%!important;min-width:0!important", rendered)
        self.assertEqual(iframe.proto.alt, "Trading Agent Lab, painel local de análise em simulação")

    def test_default_portal_separates_analyst_room_from_execution_desk(self):
        """AppTest não roda o JS do portal; o que se verifica aqui é a fonte embutida."""
        app = AppTest.from_file(str(APP_PATH)).run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        rendered = app.get("iframe")[0].proto.srcdoc
        self.assertIn('VIEW="sala", START=0, ROOM="Analistas"', rendered)
        self.assertIn('function salaDoAgente(a){return a&&a.nome==="Execution Agent"'
                      '?"Execução":"Analistas";}', rendered)
        self.assertIn("function agentesDaSala()", rendered)
        self.assertIn('data-room="Analistas"', rendered)
        self.assertIn('data-room="Execução"', rendered)
        self.assertIn('b.setAttribute("aria-pressed",b.dataset.room===ROOM?"true":"false")', rendered)
        self.assertIn('" de execução · recepção bloqueada"', rendered)
        self.assertIn('" de análise"', rendered)
        self.assertIn("POSTO DE EXECUÇÃO", rendered)
        self.assertIn("MESAS DE ANÁLISE", rendered)
        self.assertIn('var floor=$("floor"),roomAgents=agentesDaSala()', rendered)
        self.assertIn("var list=roomAgents.map(", rendered)
        self.assertIn('var floor=$("floor"),agents=agentesDaSala()', rendered)
        self.assertIn('var seletor=$("roomsel"); if(seletor)seletor.style.display='
                      'isMarket||!sala?"none":"";', rendered)
        self.assertNotIn("var slots=[[18,250],[202,250]", rendered)

    def test_default_portal_room_switch_keeps_selection_and_blocked_orders_notice(self):
        """Trocar de sala não pode deixar a ficha num agente fora da sala visível."""
        app = AppTest.from_file(str(APP_PATH)).run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        rendered = app.get("iframe")[0].proto.srcdoc
        self.assertIn("var atual=D.agentes[SEL];", rendered)
        self.assertIn("if(!atual||salaDoAgente(atual)!==ROOM){var primeiro=agentesDaSala()[0];"
                      "if(primeiro)SEL=primeiro.i;}", rendered)
        self.assertIn("function selecionar(i){SEL=i;var a=D.agentes[i];"
                      "if(a)ROOM=salaDoAgente(a);", rendered)
        self.assertIn("pintarRanking();pintarSala();pintarVistazo();pintarFicha();pintarSeletorSala();",
                      rendered)
        self.assertIn("'<div class=\"gh\"><b>Estado dos agentes</b><span>'+D.agentes.length", rendered)
        self.assertIn('T(20,160,"Ordens reais bloqueadas",10,"#aab8c8")', rendered)
        self.assertIn("SOMENTE SIMULAÇÃO", rendered)

    def test_default_portal_embeds_persisted_event_history_without_fake_operations(self):
        store.add_event("Risk Manager", "NOTICE", "Revisão local aguardando aprovação")
        app = AppTest.from_file(str(APP_PATH)).run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        rendered = app.get("iframe")[0].proto.srcdoc
        self.assertIn("Revisão local aguardando aprovação", rendered)
        self.assertIn('"agent_runs": 0', rendered)
        self.assertIn('"paper_operations": 0', rendered)
        self.assertNotIn("Dinero ficticio", rendered)

    def test_sala_balance_card_shows_neutral_state_without_closed_operations(self):
        app = AppTest.from_file(str(APP_PATH)).run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        rendered = app.get("iframe")[0].proto.srcdoc
        self.assertIn('"paper_operations": []', rendered)
        self.assertIn("SEM OPERAÇÕES", rendered)
        self.assertIn(
            'saldo.hasClosed?((saldo.total>=0?"+":"")+saldo.total.toFixed(2)+" SALDO"):"SEM OPERAÇÕES"',
            rendered,
        )
        self.assertNotIn('(counts.agents||0)+" AGENTES"', rendered)
        self.assertNotIn("(counts.agents||0)+' AGENTES'", rendered)

    def test_sala_balance_card_reflects_positive_realized_pnl(self):
        operation = closed_paper_operation(
            "BTCUSDT", "buy", quantity=2, entry_price=100.0, exit_price=150.0, fees=5.0)
        expected_pnl = (operation["exit_price"] - operation["entry_price"]) * operation["quantity"] - operation["fees"]
        self.assertEqual(expected_pnl, 95.0)
        app = AppTest.from_file(str(APP_PATH)).run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        rendered = app.get("iframe")[0].proto.srcdoc
        self.assertIn('"paper_operations": 1', rendered)
        self.assertIn('"side": "buy"', rendered)
        self.assertIn('"entry_price": 100.0', rendered)
        self.assertIn('"exit_price": 150.0', rendered)
        self.assertIn('"quantity": 2.0', rendered)
        self.assertIn('"fees": 5.0', rendered)
        self.assertIn('"state": "closed"', rendered)
        self.assertIn('saldo.total>=0?"#42d392":"#ff6f61"', rendered)

    def test_sala_balance_card_reflects_negative_realized_pnl(self):
        operation = closed_paper_operation(
            "BTCUSDT", "buy", quantity=2, entry_price=150.0, exit_price=100.0, fees=5.0)
        expected_pnl = (operation["exit_price"] - operation["entry_price"]) * operation["quantity"] - operation["fees"]
        self.assertEqual(expected_pnl, -105.0)
        app = AppTest.from_file(str(APP_PATH)).run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        rendered = app.get("iframe")[0].proto.srcdoc
        self.assertIn('"paper_operations": 1', rendered)
        self.assertIn('"entry_price": 150.0', rendered)
        self.assertIn('"exit_price": 100.0', rendered)
        self.assertIn('saldo.total>=0?"#42d392":"#ff6f61"', rendered)

    def test_default_portal_embeds_persisted_backtest_summary(self):
        rules = {"engine": "setup_pattern_v1", "setup_name": "VBS"}
        strategy_id = store.save_strategy("VBS", rules, "PDF local", status="approved")
        store.save_backtest(strategy_id, "BTCUSDT", "2m", "Binance Spot public", "abc123",
                            {"kind": "historical_simulation", "signal_count": 4, "trade_count": 1})
        app = AppTest.from_file(str(APP_PATH)).run()
        self.assertFalse(app.exception, [item.message for item in app.exception])
        rendered = app.get("iframe")[0].proto.srcdoc
        self.assertIn('"setup_name": "VBS"', rendered)
        self.assertIn('"signal_count": 4', rendered)
        self.assertIn('"trade_count": 1', rendered)
        self.assertIn("Abrir laboratório completo", rendered)

    def test_market_pages_show_historical_iex_and_connector_readiness(self):
        bars = [{"timestamp": f"2026-11-12T14:3{i}:00Z", "open": 100.0,
                 "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10.0}
                for i in range(3)]
        store.save_historical_dataset("iex.csv", "AAPL", "1m", "Alpaca IEX", "fixture-hash",
                                      bars, metadata={"market": "us_equity", "end_utc": bars[-1]["timestamp"]},
                                      canonical_sha256="fixture-canonical")
        with patch.dict("os.environ", {"ALPACA_API_KEY": "test-key", "ALPACA_API_SECRET": "test-secret"}):
            portal = AppTest.from_file(str(APP_PATH)).run()
            self.assertFalse(portal.exception)
            rendered = portal.get("iframe")[0].proto.srcdoc
            self.assertIn('"source": "Alpaca IEX"', rendered)
            self.assertIn('"alpaca_configured": true', rendered)
            self.assertNotIn("test-secret", rendered)
            app = app_for_local_lab()
            app.session_state["tal-nav"] = "Mercado"
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Alpaca IEX" in str(item.value) for item in app.dataframe))

    def test_local_lab_dashboard_uses_real_persisted_state(self):
        app = app_for_local_lab().run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        self.assertEqual(len(store.get_agents()), 6)
        self.assertIn("Trading Agent Lab", "\n".join(str(item.value) for item in app.markdown))
        rendered = "\n".join(str(item.value) for item in app.markdown)
        self.assertIn("tal-topbar", rendered)
        self.assertIn("tal-floor-wrap", rendered)
        self.assertIn("tal-director", rendered)
        self.assertIn("Ordens reais bloqueadas", rendered)
        self.assertIn("Sem feed de mercado", rendered)
        self.assertIn("Execution Agent", [button.label for button in app.button])
        self.assertEqual(app.radio(key="tal-nav").options, ["Agentes", "Mercado", "Operações", "Informe", "Controle"])
        self.assertEqual(app.radio(key="tal-view").options, ["Sala", "Laboratório", "Evolução do capital"])
        self.assertNotIn("Registrar rodada de demonstração", [button.label for button in app.button])

    def test_selecting_a_desk_shows_persisted_database_details(self):
        app = app_for_local_lab().run()
        next(button for button in app.button if button.label == "Market Analyst").click().run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        self.assertEqual(app.session_state["selected_agent"], "Market Analyst")
        rendered = "\n".join(str(item.value) for item in app.markdown)
        self.assertIn("Market Analyst", rendered)
        self.assertEqual(len(app.tabs), 5)
        self.assertEqual(store.counts()["agent_runs"], 0)

    def test_five_panels_and_three_workspace_views_render_without_errors(self):
        for panel in ["Agentes", "Mercado", "Operações", "Informe", "Controle"]:
            app = app_for_local_lab()
            app.session_state["tal-nav"] = panel
            app.run()
            self.assertFalse(app.exception, f"{panel}: {[item.message for item in app.exception]}")
            self.assertEqual(app.radio(key="tal-nav").value, panel)
        for view in ["Sala", "Laboratório", "Evolução do capital"]:
            app = app_for_local_lab()
            app.session_state["tal-view"] = view
            app.run()
            self.assertFalse(app.exception, f"{view}: {[item.message for item in app.exception]}")
            self.assertEqual(app.radio(key="tal-view").value, view)

    def test_execution_room_is_separate_and_selects_only_execution_agent(self):
        app = app_for_local_lab()
        app.session_state["tal-room"] = "Execução"
        app.run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        self.assertEqual(app.session_state["selected_agent"], "Execution Agent")
        self.assertIn("1 posto de execução", "\n".join(str(item.value) for item in app.markdown))
        self.assertEqual(app.radio(key="tal-room").value, "Execução")

    def test_demo_or_market_data_are_not_presented_as_real_activity(self):
        store.add_event("Market Analyst", "INFO", "Evento local de teste")
        app = app_for_local_lab()
        app.session_state["tal-nav"] = "Operações"
        app.run()
        rendered = "\n".join(str(item.value) for item in app.markdown)
        self.assertIn("Eventos de sistema permanecem separados", rendered)
        self.assertTrue(any("Nenhuma operação simulada conciliada" in str(item.value) for item in app.info))
        self.assertIn("Evento local de teste", rendered)

    def test_memory_note_starts_pending_and_requires_approval(self):
        app = app_for_local_lab().run()
        next(item for item in app.text_area if item.label == "Nova nota ou aprendizado proposto").set_value("Bloquear análise com dado atrasado")
        next(item for item in app.text_input if item.label.startswith("Origem")).set_value("evento:12")
        next(button for button in app.button if button.label == "Salvar como proposta").click().run()

        memories = store.list_memories("Research Agent")
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["status"], "proposed")
        self.assertEqual(store.list_memories("Research Agent", include_pending=False), [])

    def test_review_approval_promotes_learning_and_records_human_action(self):
        app = app_for_local_lab().run()
        next(item for item in app.text_area if item.label == "O que aconteceu?").set_value("O contexto estava sem horário")
        next(item for item in app.text_area if item.label == "Qual hipótese explica o erro?").set_value("A fonte não enviou timestamp")
        next(item for item in app.text_area if item.label == "Qual aprendizado deve ser avaliado?").set_value("Bloquear candles sem timestamp")
        next(button for button in app.button if button.label == "Registrar revisão").click().run()
        self.assertEqual(store.list_reviews("Research Agent")[0]["status"], "open")

        next(button for button in app.button if button.label == "Aprovar e memorizar").click().run()
        memories = store.list_memories("Research Agent", include_pending=False)
        self.assertEqual([item["content"] for item in memories], ["Bloquear candles sem timestamp"])
        self.assertTrue(any(event["Agente"] == "Usuário" for event in store.list_events()))

    def test_knowledge_library_shows_citation_and_human_review_action(self):
        store.upsert_knowledge_item(
            "setup", "NRB — Narrow Range Bar", "reference_docs/shared/setup.pdf",
            "sha256-test", 1, "Trecho de evidência da página")
        item_id = store.list_knowledge_items()[0]["id"]
        app = app_for_local_lab().run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        self.assertTrue(any("PROPOSED" in item.label and "NRB" in item.label for item in app.expander))
        self.assertIn("reference_docs/shared/setup.pdf · p. 1 · SHA-256 sha256-test",
                      [item.value for item in app.caption])
        next(button for button in app.button if button.label == "Aprovar conhecimento").click().run()

        reviewed = next(item for item in store.list_knowledge_items() if item["id"] == item_id)
        self.assertEqual(reviewed["status"], "approved")
        self.assertEqual(reviewed["reviewed_by"], "Usuário")

    def test_validation_section_runs_a_split_and_persists_the_labelled_sample(self):
        strategy = approved_setup_strategy()
        verified_crypto_dataset()
        app = app_for_local_lab()
        app.session_state["tal-view"] = "Laboratório"
        with patch("services.setup_backtest.documents.library_status", return_value=INDEXED_LIBRARY):
            app.run()
            self.assertFalse(app.exception, [item.message for item in app.exception])
            self.assertIn("Validation Engine · treino e out-of-sample",
                          "\n".join(str(item.value) for item in app.markdown))
            run_button = next(button for button in app.button
                              if button.key == f"run-validation-{strategy['id']}")
            self.assertEqual(run_button.label, "Rodar validação")
            run_button.click().run()
            self.assertFalse(app.exception, [item.message for item in app.exception])

        runs = store.list_validation_runs()
        self.assertEqual(len(runs), 1)
        row = runs[0]
        self.assertEqual((row["symbol"], row["timeframe"], row["strategy_id"]),
                         ("BTCUSDT", "2m", strategy["id"]))
        self.assertEqual(row["engine_version"], "validation_engine_v1")
        self.assertEqual(row["sample_adequacy"], "insuficiente")
        split = json.loads(row["split_json"])
        self.assertLess(split["train_end_utc"], split["holdout_start_utc"])
        self.assertEqual(split["order"], "chronological_no_shuffle")
        self.assertEqual(len(json.loads(row["cost_grid_json"])["holdout"]["scenarios"]), 4)
        self.assertIn("concentração", json.loads(row["concentration_json"])["train"]["note"])
        self.assertTrue(any("AMOSTRA INSUFICIENTE" in str(item.value) for item in app.error))

    def test_default_portal_embeds_validation_summary_without_leaking_secrets(self):
        strategy = approved_setup_strategy()
        dataset = verified_crypto_dataset()
        with patch("services.setup_backtest.documents.library_status", return_value=INDEXED_LIBRARY):
            from services.validation import evaluate_validation
            report = evaluate_validation(strategy, dataset["id"], "2m")
        store.save_validation_run(strategy["id"], "BTCUSDT", "2m", dataset["id"],
                                  dataset["sha256"], report)
        with patch.dict("os.environ", {"ALPACA_API_KEY": "test-key", "ALPACA_API_SECRET": "test-secret"}):
            portal = AppTest.from_file(str(APP_PATH)).run()

        self.assertFalse(portal.exception, [item.message for item in portal.exception])
        rendered = portal.get("iframe")[0].proto.srcdoc
        self.assertIn('"validation_runs"', rendered)
        self.assertIn('"sample_adequacy": "insuficiente"', rendered)
        self.assertIn('"engine_version": "validation_engine_v1"', rendered)
        self.assertIn('"setup_name": "BOP"', rendered)
        self.assertIn('"validation_runs": 1', rendered)
        self.assertIn("Validações com amostra insuficiente", rendered)
        self.assertIn("function blocoValidacao()", rendered)
        self.assertIn("amostra insuficiente", rendered)
        self.assertNotIn("test-secret", rendered)
        self.assertNotIn("test-key", rendered)
        self.assertNotIn("ALPACA_API_SECRET", rendered)

    def test_reports_panel_counts_validations_and_insufficient_samples(self):
        strategy = approved_setup_strategy()
        dataset = verified_crypto_dataset()
        with patch("services.setup_backtest.documents.library_status", return_value=INDEXED_LIBRARY):
            from services.validation import evaluate_validation
            report = evaluate_validation(strategy, dataset["id"], "2m")
        store.save_validation_run(strategy["id"], "BTCUSDT", "2m", dataset["id"],
                                  dataset["sha256"], report)
        app = app_for_local_lab()
        app.session_state["tal-nav"] = "Informe"
        app.run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        written = "\n".join(str(item.value) for item in app.markdown)
        self.assertIn("1 validações executadas, 1 com amostra insuficiente", written)

    def test_approved_setup_is_visible_without_sma_backtest_action(self):
        rules = {"engine": "setup_pattern_v1", "setup_id": "SETUP_01",
                 "side": "buy", "timeframes": ["2m", "5m"], "source": [],
                 "approval": "rules_human_approved"}
        strategy_id = store.save_strategy("VBS", rules, "PDF local")
        self.assertTrue(store.approve_strategy(strategy_id))
        app = app_for_local_lab()
        app.session_state["tal-view"] = "Laboratório"
        app.run()
        self.assertFalse(app.exception, [item.message for item in app.exception])
        self.assertTrue(any("Regras aprovadas para simulação histórica" in item.value for item in app.info))
        self.assertFalse(any("run-backtest" in str(button.key) for button in app.button))


if __name__ == "__main__":
    unittest.main()
