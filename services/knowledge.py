"""Local, deterministic discovery of source-cited knowledge proposals."""

from database import store
from services import documents

SETUPS = {
    1: ["NRB — Narrow Range Bar", "GIFT — o Presente"],
    2: ["PD — Poder das Duplas", "TM — Topo Menor"],
    3: ["Marching Bull / Bear Elephant", "Ma20 Halt Buy — Parada da 20"],
    4: ["CDB — Compra de Declínio Climático", "CAS — Venda de Avanço Climático",
        "BOP — Breakout Play", "BDP — Breakdown Play",
        "VBS — Velez Buy Setup", "VSS — Velez Sell Setup"],
    5: ["RBI — Red Bar Ignored", "GBI — Green Bar Ignored", "BE — Barra Elefante",
        "Bull and Bear 180"],
    7: ["BT — Bottoming Tail", "TT — Topping Tail", "BT/TT Kamikaze"],
    8: ["TTTO — Topping Tail Take Out", "BTTO — Bottoming Tail Take Out"],
    9: ["DTTTO — Delayed Topping Tail Take Out",
        "DBTTO — Delayed Bottoming Tail Take Out", "RBTO — Red Bar Take Out",
        "GBTO — Green Bar Take Out"],
}

CONCEPTS = {
    2: "Abertura como referência de leitura da barra",
    3: "Barra elefante e disputa entre compradores e vendedores",
    6: "Barra elefante como ignição ou exaustão",
    7: "Controle absoluto pela negociação no extremo da barra",
    8: "Regra de dois terços para perda de controle",
    22: "Lei do momentum descrita na apostila",
}


def _page_text(path, page):
    rows = store.get_document_context("Research Agent", limit=5000)
    matches = [row["content"] for row in rows
               if row["relative_path"] == path and row["page_number"] == page]
    return "\n".join(matches)


def extract_proposals():
    """Create idempotent proposals from fresh indexed pages; never calls a model."""
    library = {item["path"]: item for item in documents.library_status()}
    created = 0
    for path, record in library.items():
        if record["status"] != "indexed":
            continue
        db_doc = record["record"]
        page_map = SETUPS if "Setups Complementar" in record["filename"] else {}
        concepts = CONCEPTS if "Apostila Oliver" in record["filename"] else {}
        for page, titles in page_map.items():
            evidence = _page_text(path, page)
            if not evidence:
                continue
            for title in titles:
                created += store.upsert_knowledge_item(
                    "setup", title, path, db_doc["sha256"], page, evidence,
                    {"lifecycle": "DISCOVERED", "rule_fields": "not_formalized"})
        for page, title in concepts.items():
            evidence = _page_text(path, page)
            if evidence:
                created += store.upsert_knowledge_item(
                    "concept", title, path, db_doc["sha256"], page, evidence,
                    {"lifecycle": "PROPOSED"})
    summary = refresh_research_status()
    return {"created": created, **summary}


def refresh_research_status():
    """Synchronize the persisted Research Agent state from current local records."""
    library = {item["path"]: item for item in documents.library_status()}
    current_hashes = {path: (item["record"] or {}).get("sha256")
                      for path, item in library.items() if item["status"] == "indexed"}
    items = [item for item in store.list_knowledge_items()
             if current_hashes.get(item["source_path"]) == item["source_sha256"]]
    proposed = sum(item["status"] == "proposed" for item in items)
    approved = sum(item["status"] == "approved" for item in items)
    if not items:
        status = "Aguardando documentos" if not any(x["status"] == "indexed" for x in library.values()) else "Aguardando extração de conhecimento"
    elif proposed:
        status = "Revisão humana pendente"
    else:
        status = "Conhecimento revisado" if approved else "Conhecimento rejeitado"
    with store.connect() as conn:
        prior = conn.execute("SELECT status FROM agents WHERE name='Research Agent'").fetchone()
        if prior and prior[0] != status:
            conn.execute("UPDATE agents SET status=? WHERE name='Research Agent'", (status,))
            conn.execute("INSERT INTO events(agent,level,message) VALUES(?,?,?)",
                         ("Research Agent", "INFO", f"Estado atualizado a partir da biblioteca local: {status}"))
    return {"items": len(items), "proposed": proposed, "approved": approved,
            "status": status}
