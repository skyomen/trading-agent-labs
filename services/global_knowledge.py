"""Owner-curated, source-current concepts shared across local workspaces."""

from pathlib import Path

from database import store
from services import documents


def _current(item):
    relative = Path(item["source_path"])
    if relative.parts[:2] != ("reference_docs", "shared") and relative.parts[:2] != (
            "reference_docs", "agents"):
        return False
    source = (documents.REFERENCE_ROOT / relative.relative_to("reference_docs")).resolve()
    if not source.is_relative_to(documents.REFERENCE_ROOT.resolve()) or not source.is_file():
        return False
    return documents._digest(source) == item["source_sha256"]


def promote(item_id, actor):
    if actor.get("role") != "owner" or actor.get("id") != store.active_user_id():
        raise PermissionError("Apenas o proprietário promove conhecimento global.")
    item = next((row for row in store.list_knowledge_items(status="approved")
                 if row["id"] == item_id), None)
    if not item or not _current(item):
        raise ValueError("Conhecimento não aprovado ou fonte desatualizada.")
    store.promote_global_knowledge(item, actor["id"])
    return True


def list_fresh():
    if not store.active_user_id():
        return []
    return [row for row in store.list_global_knowledge() if _current(row)]
