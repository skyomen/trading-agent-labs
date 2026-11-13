import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from database import store

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
REFERENCE_PATH = APP_PATH.with_name("referencia.html")


def app_for_local_lab():
    app = AppTest.from_file(str(APP_PATH))
    app.query_params["lab"] = "1"
    return app


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
        self.assertIn("counts.agents||0", rendered)
        self.assertIn("cortar(a.status,13)", rendered)
        self.assertIn("function pintarSalaCompacta()", rendered)
        self.assertIn("wrapSvgText(a.status,27)", rendered)
        self.assertIn('viewBox","0 0 390 660"', rendered)
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

    def test_default_portal_embeds_persisted_event_history_without_fake_operations(self):
        store.add_event("Risk Manager", "NOTICE", "Revisão local aguardando aprovação")
        app = AppTest.from_file(str(APP_PATH)).run()

        self.assertFalse(app.exception, [item.message for item in app.exception])
        rendered = app.get("iframe")[0].proto.srcdoc
        self.assertIn("Revisão local aguardando aprovação", rendered)
        self.assertIn('"agent_runs": 0', rendered)
        self.assertIn('"paper_operations": 0', rendered)
        self.assertNotIn("Dinero ficticio", rendered)

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


if __name__ == "__main__":
    unittest.main()
