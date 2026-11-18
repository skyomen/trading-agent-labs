"""Local, source-preserving PDF indexing for agent context."""

import hashlib
import os
import re
from pathlib import Path

from pypdf import PdfReader

from database import store

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = Path(os.environ.get("TRADING_LAB_REFERENCE_DIR", str(PROJECT_ROOT / "reference_docs")))
CHUNK_SIZE = 1400
CHUNK_OVERLAP = 180


def save_private_pdf(filename, content):
    user_id = store.active_user_id()
    if not user_id:
        raise PermissionError("Entre no workspace antes de enviar PDFs.")
    safe_name = Path(filename).name
    if safe_name != filename or not re.fullmatch(r"[\w .()\-]{1,100}\.pdf", safe_name, re.IGNORECASE):
        raise ValueError("Nome de PDF inválido.")
    if not content.startswith(b"%PDF-") or len(content) > 20 * 1024 * 1024:
        raise ValueError("O arquivo deve ser um PDF de até 20 MB.")
    folder = REFERENCE_ROOT / "workspaces" / user_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / safe_name
    if path.exists():
        raise ValueError("Já existe um PDF com esse nome no seu workspace.")
    path.write_bytes(content)
    return path


def discover_pdfs():
    """Return PDFs from the shared library and known agent folders only."""
    allowed = [REFERENCE_ROOT / "shared", REFERENCE_ROOT / "agents"]
    if store.active_user_id():
        allowed.append(REFERENCE_ROOT / "workspaces" / store.active_user_id())
    paths = []
    for folder in allowed:
        if folder.exists():
            paths.extend(path for path in folder.rglob("*.pdf") if path.is_file())
    return sorted(paths, key=lambda path: path.as_posix().casefold())


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _chunks(text, page_number):
    text = " ".join((text or "").split())
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start + CHUNK_SIZE // 2:
                end = boundary
        value = text[start:end].strip()
        if value:
            chunks.append((page_number, len(chunks), value))
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def index_pdf(path, force=False):
    """Extract a PDF locally and persist page-addressable text chunks."""
    source_path = Path(path)
    path = source_path.resolve()
    common = (REFERENCE_ROOT / "shared", REFERENCE_ROOT / "agents")
    private = (REFERENCE_ROOT / "workspaces" / store.active_user_id()
               if store.active_user_id() else None)
    if not any(path.is_relative_to(root.resolve()) for root in common) and not (
            private and path.is_relative_to(private.resolve())):
        raise ValueError("O PDF precisa estar dentro de reference_docs/shared ou agents.")
    relative = (Path("reference_docs") / source_path.relative_to(REFERENCE_ROOT)).as_posix()
    digest = _digest(path)
    existing = next((doc for doc in store.list_documents()
                     if doc["relative_path"] == relative), None)
    if existing and existing["sha256"] == digest and existing["status"] in ("indexed", "no_text") and not force:
        return {"path": relative, "status": "unchanged", "pages": existing["page_count"],
                "chunks": existing["chunk_count"]}

    try:
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            raise ValueError("PDF protegido por senha; não foi processado.")
        chunks = []
        for page_number, page in enumerate(reader.pages, start=1):
            chunks.extend(_chunks(page.extract_text() or "", page_number))
        status = "indexed" if chunks else "no_text"
        store.replace_document(relative, path.name, digest, status, len(reader.pages), chunks)
        return {"path": relative, "status": status, "pages": len(reader.pages),
                "chunks": len(chunks)}
    except Exception as exc:
        store.replace_document(relative, path.name, digest, "failed", 0, [], str(exc)[:500])
        return {"path": relative, "status": "failed", "pages": 0, "chunks": 0,
                "error": str(exc)}


def index_library(force=False):
    results = [index_pdf(path, force=force) for path in discover_pdfs()]
    for result in results:
        store.add_event(
            "Research Agent", "INFO" if result["status"] != "failed" else "ERROR",
            f"Biblioteca local: {result['status']} · {result['path']} · "
            f"{result['pages']} páginas · {result['chunks']} trechos"
            + (f" · {result['error']}" if result.get("error") else ""),
        )
    from services.knowledge import refresh_research_status
    refresh_research_status()
    return results


def library_status():
    """Compare the indexed hashes with the PDFs currently on disk."""
    indexed = {item["relative_path"]: item for item in store.list_documents()}
    results = []
    for path in discover_pdfs():
        relative = (Path("reference_docs") / path.relative_to(REFERENCE_ROOT)).as_posix()
        record = indexed.get(relative)
        if not record:
            status = "pending"
        elif record["sha256"] != _digest(path):
            status = "stale"
        else:
            status = record["status"]
        results.append({"path": relative, "filename": path.name, "status": status,
                        "record": record, "bytes": path.stat().st_size})
    return results


def agent_context(agent, limit=12):
    """Return only indexed excerpts whose source file still matches its hash."""
    library = library_status()
    statuses = {item["path"]: item["status"] for item in library}
    records = {item["relative_path"]: item for item in store.list_documents()}
    context = store.get_document_context(agent, limit=1000)
    fresh = [item for item in context
             if statuses.get(item["relative_path"]) == "indexed"
             and records.get(item["relative_path"], {}).get("status") == "indexed"]
    slugs = {
        "Research Agent": "research-agent", "Market Analyst": "market-analyst",
        "Fundamental Analyst": "fundamental-analyst", "Strategy & Backtest": "strategy-backtest",
        "Risk Manager": "risk-manager", "Execution Agent": "execution-agent",
    }
    specific = f"reference_docs/agents/{slugs.get(agent, '')}/"
    stale = sorted(item["path"] for item in library
                   if item["path"].startswith("reference_docs/shared/")
                   or item["path"].startswith(specific)
                   or (store.active_user_id() and item["path"].startswith(
                       f"reference_docs/workspaces/{store.active_user_id()}/"))
                   if item["status"] in {"stale", "pending", "failed", "no_text"})
    return fresh[:limit], stale
