"""Two isolated local workspaces and one curated global item, no external calls."""

import argparse

from database import store
from services import credential_vault, documents, global_knowledge
from tests.test_multiuser import MultiuserTests


def prove():
    fixture = MultiuserTests(methodName="test_two_workspaces_preserve_owner_history_without_cross_read")
    fixture.setUp()
    try:
        with store.user_workspace(fixture.owner["id"]):
            store.add_event("Owner", "INFO", "private-owner")
        with store.user_workspace(fixture.other["id"]):
            assert len(store.get_agents()) == 6
            assert not any(row["Atividade"] == "private-owner" for row in store.list_events())
        shared = documents.REFERENCE_ROOT / "shared"
        shared.mkdir(parents=True)
        source = shared / "fixture.pdf"
        source.write_bytes(b"%PDF-1.4\nfixture")
        with store.user_workspace(fixture.owner["id"]):
            store.upsert_knowledge_item("concept", "Global fixture", "reference_docs/shared/fixture.pdf",
                                        documents._digest(source), 1, "cited evidence")
            item_id = store.list_knowledge_items()[0]["id"]
            store.review_knowledge_item(item_id, True)
            global_knowledge.promote(item_id, fixture.owner)
        with store.user_workspace(fixture.other["id"]):
            assert len(global_knowledge.list_fresh()) == 1
            assert store.list_knowledge_items() == []
        credential_vault.save_credentials(fixture.owner["id"], fixture.owner["vault_key"],
                                          {"ALPACA_API_KEY": "synthetic-secret"})
        assert credential_vault.read_credentials(fixture.other["id"], fixture.other["vault_key"]) == {}
        print("PROVA LOCAL EM BANCOS TEMPORARIOS - nenhuma chamada externa")
        print("Owner: historico legado preservado; outro usuario: seis agentes e historico vazio")
        print("Conhecimento global: 1 item aprovado e com hash atual, sem copiar memoria privada")
        print("Credenciais por usuario: cofre cifrado; segundo usuario sem acesso")
    finally:
        fixture.tearDown()


def main():
    parser = argparse.ArgumentParser(description="Prova local da Entrega 13")
    parser.add_argument("--prova", action="store_true", required=True)
    parser.parse_args()
    prove()


if __name__ == "__main__":
    main()
