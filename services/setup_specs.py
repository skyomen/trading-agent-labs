"""Versioned, source-bound draft rules for the four selected setups."""

import json

from database import store
from services import documents

SOURCE = "reference_docs/shared/Oliver Velez/Apostila Oliver Velez.pdf"
SUPPLEMENT = "reference_docs/shared/Oliver Velez/Setups Complementar Op. OV Atualizada.pdf"
# Keep the setup illustrations and context pages with each future proposal.
# The currently approved SQLite versions are immutable and retain their original
# citations; these expanded ranges apply only when a new draft is registered.
PAGES = {
    "VBS": (*range(101, 116), 145, 146, 148, 150, 159, *range(161, 168),
            175, 176, *range(179, 182), 295, 305, 308),
    "VSS": (*range(111, 116), 145, 146, 148, 150, 160, *range(168, 175),
            *range(182, 186)),
    "BOP": (*range(223, 239), 145, 146, 148, 305),
    "BDP": (*range(239, 246), 145, 146, 148),
}
IDS = {"VBS": "SETUP_01", "VSS": "SETUP_02",
       "BOP": "SETUP_03", "BDP": "SETUP_04"}


def _current_sources():
    current = {item["path"]: item for item in documents.library_status()}
    if any(current.get(path, {}).get("status") != "indexed" for path in (SOURCE, SUPPLEMENT)):
        raise ValueError("Os dois PDFs de origem precisam estar indexados e atuais.")
    return {path: current[path]["record"]["sha256"] for path in (SOURCE, SUPPLEMENT)}


def proposed_rules():
    """Return reviewable rules, with implementation choices labelled as proposals."""
    hashes = _current_sources()
    proposals = []
    for name, side in (("VBS", "buy"), ("VSS", "sell"),
                       ("BOP", "buy"), ("BDP", "sell")):
        pullback = name in {"VBS", "VSS"}
        rules = {
            "engine": "setup_pattern_v1",
            "setup_id": IDS[name], "setup_name": name, "side": side,
            "timeframes": ["2m", "5m"], "status": "parameter_review",
            "source": [
                {"path": SOURCE, "sha256": hashes[SOURCE], "pages": list(PAGES[name])},
                {"path": SUPPLEMENT, "sha256": hashes[SUPPLEMENT],
                 "pages": [4, 7] if pullback else [4]},
            ],
            "pattern": (
                {"kind": "three_countertrend_bars", "bars": 3,
                 "trend_ma": 20, "trend_slope_bars": 3,
                 "structure_alternative": "deferred_to_new_version"}
                if pullback else
                {"kind": "compressed_base", "min_bars": 3, "max_bars": 8,
                 "max_range_atr20": 1.5, "volume_below_prior_20_mean": True,
                 "trend_ma": 8, "trend_slope_bars": 3}
            ),
            "entry": {"kind": "next_bar_stop", "offset_ticks": 1,
                      "reference": "setup_bar_extreme" if pullback else "base_extreme"},
            "stop": {"kind": "known_before_entry", "offset_ticks": 1,
                     "reference": "opposite_setup_bar_extreme" if pullback else "opposite_base_extreme"},
            "target": ({"kind": "half_retracement", "lookback_bars": 20,
                        "reject_if_not_beyond_entry": True} if pullback else
                       {"kind": "base_height", "multiple": 1.0}),
            "management": ({"trailing_after_favorable_closes": 2,
                            "trailing_reference": "previous_bar_extreme"} if pullback else
                           {"trailing": False}),
            "filters": {"session_hours": "pending_market_selection",
                        "tick_size": "required_from_dataset"},
            "costs": {"fees_spread_slippage": "required_per_backtest"},
            "intrabar_conflict": "stop_first",
            "approval": "rules_pending_human_review",
        }
        proposals.append((name, rules))
    return proposals


def register_drafts():
    """Persist only new versions; repeat calls leave existing drafts untouched."""
    created = []
    existing = store.list_strategies()
    for name, rules in proposed_rules():
        title = f"{name} · método Oliver Velez"
        serialized = json.dumps(rules, ensure_ascii=False, sort_keys=True)
        if any(row["name"] == title and row["rules_json"] == serialized for row in existing):
            continue
        created.append(store.save_strategy(title, rules,
                                           "PDF local; parâmetros de implementação propostos"))
    return created


def promote_approved_rules(decision_reference):
    """Record the human-reviewed specification as a new immutable version."""
    if not decision_reference.strip():
        raise ValueError("Informe a referência da aprovação humana.")
    created = []
    existing = store.list_strategies()
    candidates = proposed_rules()
    for name, rules in candidates:
        for row in existing:
            if row["name"] != f"{name} · método Oliver Velez" or row["status"] != "approved":
                continue
            old = json.loads(row["rules_json"])
            if old.get("human_decision_reference") == decision_reference and old.get("source") != rules["source"]:
                raise ValueError("A fonte mudou após a aprovação; é necessária nova revisão humana.")
    for name, rules in candidates:
        title = f"{name} · método Oliver Velez"
        rules["approval"] = "rules_human_approved"
        rules["human_decision_reference"] = decision_reference
        rules["status"] = "approved_for_backtest"
        serialized = json.dumps(rules, ensure_ascii=False, sort_keys=True)
        if any(row["name"] == title and row["rules_json"] == serialized
               and row["status"] == "approved" for row in existing):
            continue
        strategy_id = store.save_strategy(title, rules,
                                          f"PDF local; regras aprovadas: {decision_reference}")
        store.approve_strategy(strategy_id)
        created.append(strategy_id)
    return created
