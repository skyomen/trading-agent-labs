"""Temporary-database proof of controlled paper learning, using synthetic fixtures."""

import argparse
import json

from database import store
from services import paper_learning
from tests.test_paper_learning import PaperLearningTests


def prove():
    fixture = PaperLearningTests(methodName="test_zero_and_short_cohorts_never_generate_hypothesis")
    fixture.setUp()  # Patches store.DB_PATH to a disposable temporary database.
    try:
        assert paper_learning.analyze_cohort(fixture.strategy_id, "BTCUSDT", "2m")["state"] == "insufficient"
        for index in range(29):
            fixture.seed_trade(index, day=index // 15)
        assert paper_learning.analyze_cohort(fixture.strategy_id, "BTCUSDT", "2m")["state"] == "insufficient"
        fixture.seed_trade(29, day=1)
        result = paper_learning.analyze_cohort(fixture.strategy_id, "BTCUSDT", "2m")
        assert result["state"] == "proposed" and result["closed_count"] == 30
        repeated = paper_learning.analyze_cohort(fixture.strategy_id, "BTCUSDT", "2m")
        assert repeated["proposal_id"] == result["proposal_id"]
        proposal_id = result["proposal_id"]
        assert store.review_paper_learning_proposal(proposal_id, True)
        assert not store.review_paper_learning_proposal(proposal_id, False)
        changed = json.loads(json.dumps(fixture.rules))
        changed["pattern"]["min_bars"] = 4
        draft_id = paper_learning.create_draft(proposal_id, changed)
        assert store.get_strategy(draft_id)["status"] == "draft"
        assert store.get_strategy(fixture.strategy_id)["status"] == "approved"
        print("PROVA SINTETICA EM BANCO TEMPORARIO - nenhuma observacao de mercado")
        print("0 e 29 operacoes: amostra insuficiente, sem proposta")
        print(f"30 operacoes em dois dias UTC: proposta #{proposal_id} com hash {result['evidence_sha256'][:16]}...")
        print(f"Revisao humana: aprovada; nova versao #{draft_id} em rascunho, origem preservada")
        print("Idempotencia de proposta e revisao: OK; nenhuma regra promovida automaticamente")
    finally:
        fixture.tearDown()


def main():
    parser = argparse.ArgumentParser(description="Prova local da Entrega 10")
    parser.add_argument("--prova", action="store_true", required=True)
    parser.parse_args()
    prove()


if __name__ == "__main__":
    main()
