"""Offline acceptance proof for the broker paper gate, without Testnet network calls."""

import argparse

from database import store
from services import broker_paper
from tests.test_broker_paper import BrokerPaperTests


def prove():
    fixture = BrokerPaperTests(methodName="test_timeout_is_unknown_and_reconciles_without_resend")
    fixture.setUp()
    try:
        fixture.fake.fail_next = True
        try:
            broker_paper.submit_entry(fixture.run_id, 1, 100, confirmed=True,
                                      adapter=fixture.fake)
        except broker_paper.BrokerError:
            pass
        entry = store.get_broker_entry_for_run(fixture.run_id)
        assert entry["state"] == "unknown" and len(fixture.fake.sent) == 1
        fixture.fake.responses[entry["client_order_id"]] = fixture.fake._response(
            entry["client_order_id"], "FILLED", "1")
        assert broker_paper.reconcile(entry["id"], fixture.fake)["state"] == "FILLED"
        exit_order = broker_paper.submit_exit(entry["id"], 1, 99.9, confirmed=True,
                                              adapter=fixture.fake)
        assert exit_order["side"] == "SELL"
        fixture.fake.responses[exit_order["client_order_id"]] = fixture.fake._response(
            exit_order["client_order_id"], "FILLED", "1")
        assert broker_paper.reconcile(exit_order["id"], fixture.fake)["state"] == "FILLED"
        assert store.list_paper_operations() == []
        print("PROVA OFFLINE EM BANCO TEMPORARIO - sem chamadas a Testnet")
        print("Autorizacao -> intencao persistida -> timeout desconhecido -> consulta -> compra preenchida")
        print("Venda manual LIMIT -> consulta -> saida preenchida; diario paper local separado")
        print("Nenhum reenvio automatico apos timeout; nenhuma ordem real")
    finally:
        fixture.tearDown()


def main():
    parser = argparse.ArgumentParser(description="Prova offline da Entrega 11")
    parser.add_argument("--prova", action="store_true", required=True)
    parser.parse_args()
    prove()


if __name__ == "__main__":
    main()
