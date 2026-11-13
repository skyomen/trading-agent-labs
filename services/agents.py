"""Explicitly triggered, auditable calls to an OpenAI-compatible model."""

import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

from database import store
from services import documents

ROLE_GUIDANCE = {
    "Research Agent": "Organize the supplied technical material. Cite each claim as [filename, p. N].",
    "Market Analyst": "Analyze only supplied market observations. Never invent prices, candles, indicators, or signals.",
    "Fundamental Analyst": "Analyze only supplied news and fundamental data. Name missing evidence and its date.",
    "Strategy & Backtest": "Formalize falsifiable rules. Never claim a backtest ran unless result data is supplied.",
    "Risk Manager": "Look for invalid assumptions, missing evidence, stale data, and risk. Block unsupported conclusions.",
    "Execution Agent": "Review approved simulation proposals only. Never prepare or send real orders.",
}


def provider_configured(environ=None):
    env = os.environ if environ is None else environ
    return bool(env.get("TRADING_LAB_LLM_BASE_URL", "").strip()
                and env.get("TRADING_LAB_LLM_MODEL", "").strip())


def provider_summary(environ=None):
    env = os.environ if environ is None else environ
    base = env.get("TRADING_LAB_LLM_BASE_URL", "").strip()
    model = env.get("TRADING_LAB_LLM_MODEL", "").strip()
    key_present = bool(env.get("TRADING_LAB_LLM_API_KEY", "").strip())
    parsed = urlparse(base) if base else None
    local = bool(parsed and parsed.hostname in {"localhost", "127.0.0.1", "::1"})
    safe_transport = bool(parsed and parsed.scheme in {"https", "http"}
                          and parsed.hostname and (parsed.scheme == "https" or local))
    ready = bool(base and model and safe_transport and (local or key_present))
    return {"configured": ready, "base_url": base, "model": model,
            "api_key_present": key_present, "local": local}


def _validate_endpoint(base_url):
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Informe uma URL HTTP(S) válida para o provedor de IA.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Provedores fora da máquina local precisam usar HTTPS.")


def _message_context(agent, include_documents):
    parts = []
    if include_documents:
        fresh, stale = documents.agent_context(agent)
        for item in fresh:
            parts.append(f"[FONTE: {item['filename']}, p. {item['page_number']}]\n{item['content']}")
        if stale:
            parts.append("[AVISO: arquivos sem índice atual e excluídos do contexto: "
                         + ", ".join(stale) + "]")
    memories = store.list_memories(agent, include_pending=False)
    for memory in memories[:12]:
        parts.append(f"[MEMÓRIA APROVADA: {memory['source']}]\n{memory['content']}")
    return "\n\n".join(parts)


def run_agent_task(agent, task, include_documents=False, authorize_external_context=False):
    """Call the configured model only after a user explicitly starts a task."""
    if include_documents and not authorize_external_context:
        raise PermissionError("Confirme o envio de trechos documentais ao provedor antes de continuar.")
    config = provider_summary()
    if not config["configured"]:
        raise RuntimeError("Provedor de IA não configurado. Nenhuma chamada externa foi feita.")
    if agent not in ROLE_GUIDANCE:
        raise ValueError("Agente desconhecido.")
    if not task.strip():
        raise ValueError("Descreva a tarefa do agente.")

    base_url = config["base_url"].rstrip("/")
    _validate_endpoint(base_url)
    context = _message_context(agent, include_documents)
    context_summary = (
        f"documentos={'incluídos' if include_documents else 'não incluídos'}; "
        f"memórias aprovadas consultadas; fonte de preço não conectada"
    )
    run_id = store.add_agent_run(agent, task, context_summary, "", "running")
    store.add_event(agent, "INFO", f"Tarefa de agente iniciada · execução local #{run_id}")
    system = (
        f"Você é {agent}. {ROLE_GUIDANCE[agent]} "
        "Se não houver evidência suficiente, diga explicitamente que não há dados. "
        "Não dê garantia de lucro nem apresente exemplo como resultado de mercado. "
        "Proponha mudanças de conhecimento como propostas que exigem aprovação humana."
    )
    user_content = f"TAREFA\n{task.strip()}"
    if context:
        user_content += f"\n\nCONTEXTO LOCAL AUTORIZADO\n{context}"
    payload = json.dumps({
        "model": config["model"],
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user_content}],
        "temperature": 0.2,
        "max_tokens": 1200,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("TRADING_LAB_LLM_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        f"{base_url}/chat/completions", data=payload, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
        output = data["choices"][0]["message"]["content"].strip()
        if not output:
            raise ValueError("O provedor retornou uma resposta vazia.")
        store.update_agent_run(run_id, output, "completed")
        store.add_event(agent, "INFO", f"Tarefa concluída · execução local #{run_id}")
        return {"id": run_id, "output": output, "context": context_summary}
    except Exception as exc:
        store.update_agent_run(run_id, str(exc)[:2000], "failed")
        store.add_event(agent, "ERROR", f"Tarefa falhou · execução local #{run_id} · {str(exc)[:300]}")
        raise
