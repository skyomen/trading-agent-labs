"""Local health snapshot built only from records already persisted.

Reads integrity, heartbeats, market-feed freshness, uncertain Testnet orders, open
paper operations and the operational block. Nothing here opens a network connection,
calls a broker or invents activity: a component with no record is reported as absent,
never as healthy.

Writing heartbeats is the job of the processes themselves (`app.py` once per Streamlit
rerun, `services/market_data.py` inside the collector loop); this module only reads them.
"""

from datetime import datetime, timezone

from database import store

# Market-feed freshness. A feed only counts as current when the collector checked in
# recently AND the last closed candle is recent. These are the thresholds the market
# view has used since Entrega 4; `app.py` imports them from here so the portal and the
# health snapshot can never disagree about what "atrasado" means.
FEED_CHECK_MAX_AGE_SECONDS = 120
FEED_BAR_MAX_AGE_SECONDS = 180

# Heartbeat staleness (Entrega 15 decision).
#
# The collector is a continuous loop: it stamps a heartbeat on the same events where it
# updates the feed (backfill, stream open, each closed candle, disconnect, stop), so a
# gap means the process is gone, not idle. It gets the same 180s budget as the feed's
# last candle, keeping "feed atrasado" and "coletor parado" from telling opposite stories
# about the same silence.
COLLECTOR_HEARTBEAT_MAX_AGE_SECONDS = 180

# The Streamlit app is not a daemon: it only runs this code while a page is rendering,
# so an old app heartbeat usually means nobody opened the browser tab — not a failure.
# A one-day budget keeps the alert meaningful ("o laboratório não é aberto há mais de um
# dia") instead of firing every time the user steps away from the computer.
APP_HEARTBEAT_MAX_AGE_SECONDS = 86400

# Components that are expected to exist in a complete local install. Absence is reported
# explicitly instead of being silently skipped. Must stay a subset of the vocabulary
# validated by `store.record_heartbeat`.
EXPECTED_COMPONENTS = ("app", "collector:BTCUSDT", "collector:ETHUSDT",
                       "collector:SOLUSDT", "collector:BNBUSDT",
                       "collector:XRPUSDT", "collector:ADAUSDT")

SEVERITY_CRITICAL = "critico"
SEVERITY_WARNING = "atencao"
SEVERITY_INFO = "informativo"


def heartbeat_max_age_seconds(component):
    """Staleness budget for a component, in seconds."""
    return APP_HEARTBEAT_MAX_AGE_SECONDS if component == "app" else COLLECTOR_HEARTBEAT_MAX_AGE_SECONDS


def _as_utc(value):
    """Parse a stored timestamp into an aware UTC datetime.

    SQLite `CURRENT_TIMESTAMP` writes "YYYY-MM-DD HH:MM:SS" (UTC, no suffix) while bar
    timestamps carry "Z" or "+00:00"; both conventions live side by side in this schema.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _age_seconds(value, now):
    moment = _as_utc(value)
    return None if moment is None else (now - moment).total_seconds()


def feed_freshness(feed, now=None):
    """Freshness of one `market_feeds` row, without deciding how to display it.

    Shared by `app.py` (market view and the live-feed counter) and by the health
    snapshot, so the 120s/180s rule exists in exactly one place.
    """
    now = now or datetime.now(timezone.utc)
    checked_age = _age_seconds(feed.get("checked_at"), now)
    bar_age = _age_seconds(feed.get("last_bar_at"), now)
    current = (feed.get("status") == "connected"
               and checked_age is not None and checked_age < FEED_CHECK_MAX_AGE_SECONDS
               and bar_age is not None and bar_age < FEED_BAR_MAX_AGE_SECONDS)
    return {"current": current, "checked_age_seconds": checked_age, "bar_age_seconds": bar_age}


def _integrity(alerts):
    try:
        result = store.quick_check()
    except Exception as exc:  # the database itself is the subject of this check
        alerts.append({"kind": "integridade", "severity": SEVERITY_CRITICAL,
                       "message": f"Não foi possível verificar a integridade do banco: {exc}"})
        return {"result": "indisponível", "ok": False}
    ok = result == "ok"
    if not ok:
        alerts.append({"kind": "integridade", "severity": SEVERITY_CRITICAL,
                       "message": f"PRAGMA quick_check não retornou ok: {result}"})
    return {"result": result, "ok": ok}


def _heartbeats(alerts, now):
    recorded = {row["component"]: row for row in store.list_heartbeats()}
    components = list(EXPECTED_COMPONENTS) + [name for name in sorted(recorded)
                                              if name not in EXPECTED_COMPONENTS]
    items = []
    for component in components:
        row = recorded.get(component)
        budget = heartbeat_max_age_seconds(component)
        age = _age_seconds(row["last_seen_at"], now) if row else None
        if row is None:
            status = "nunca registrado"
        elif age is None or age >= budget:
            status = "parado"
        else:
            status = "ativo"
        items.append({"component": component,
                      "state": row["state"] if row else None,
                      "details": row["details"] if row else "",
                      "last_seen_at": row["last_seen_at"] if row else None,
                      "age_seconds": age,
                      "max_age_seconds": budget,
                      "status": status,
                      "stale": status != "ativo"})
        if status == "nunca registrado":
            alerts.append({"kind": "heartbeat", "severity": SEVERITY_INFO,
                           "message": f"Sem registro de atividade de {component} neste workspace."})
        elif status == "parado":
            alerts.append({"kind": "heartbeat", "severity": SEVERITY_WARNING,
                           "message": (f"{component} sem sinal desde {row['last_seen_at']} UTC "
                                       f"(limite de {budget}s).")})
    return items


def _feeds(alerts, now):
    items = []
    for feed in store.list_market_feeds():
        freshness = feed_freshness(feed, now)
        item = {"provider": feed["provider"], "symbol": feed["symbol"],
                "timeframe": feed["timeframe"], "status": feed["status"],
                "checked_at": feed["checked_at"], "last_bar_at": feed["last_bar_at"],
                "error": feed["error"], **freshness}
        items.append(item)
        if not freshness["current"]:
            reason = ("desconectado" if feed["status"] != "connected"
                      else "sem candle fechado recente")
            alerts.append({"kind": "feed", "severity": SEVERITY_WARNING,
                           "message": (f"Feed {feed['symbol']} {feed['timeframe']} "
                                       f"{reason}; última barra: {feed['last_bar_at'] or 'nenhuma'}.")})
    return items


def _uncertain_orders(alerts):
    items = [{"id": order["id"], "run_id": order["run_id"], "role": order["role"],
              "symbol": order["symbol"], "side": order["side"],
              "quantity": order["quantity"], "limit_price": order["limit_price"],
              "client_order_id": order["client_order_id"],
              "created_at": order["created_at"], "checked_at": order["checked_at"],
              "error": order["error"]}
             for order in store.list_broker_paper_orders(limit=100)
             if order["state"] == "unknown"]
    if items:
        alerts.append({"kind": "ordem_testnet", "severity": SEVERITY_WARNING,
                       "message": (f"{len(items)} ordem(ns) Testnet em estado desconhecido; "
                                   "consulte pelo identificador persistido antes de qualquer reenvio.")})
    return items


def _open_operations(alerts):
    """Open paper positions. Management runs on demand (Entrega 8), with no stored
    timestamp of the last pass, so an open position is by definition awaiting a manual
    run — this is a reminder of how many, never a staleness alert."""
    items = [{"id": operation["id"], "symbol": operation["symbol"], "side": operation["side"],
              "quantity": operation["quantity"], "entry_price": operation["entry_price"],
              "source": operation["source"], "created_at": operation["created_at"],
              "pipeline_run_id": operation["pipeline_run_id"]}
             for operation in store.list_paper_operations(state="open")]
    if items:
        alerts.append({"kind": "operacao_paper", "severity": SEVERITY_INFO,
                       "message": (f"{len(items)} operação(ões) paper aberta(s) aguardando condução "
                                   "sob demanda; a condução só roda quando você abre a tela.")})
    return items


def _kill_switch(alerts):
    control = store.get_kill_switch()
    if control["enabled"]:
        alerts.append({"kind": "bloqueio", "severity": SEVERITY_INFO,
                       "message": (f"Bloqueio de novas entradas ativo desde {control['updated_at']} "
                                   f"por {control['actor']}: {control['reason']}")})
    return control


def get_health_snapshot(now=None):
    """Read-only snapshot of local health, deterministic alerts and the operational block.

    `now` overrides the reference instant (tests and reproducible proofs); defaults to
    the current UTC time. Never writes and never contacts an external service.
    """
    now = now or datetime.now(timezone.utc)
    alerts = []
    integrity = _integrity(alerts)
    heartbeats = _heartbeats(alerts, now)
    feeds = _feeds(alerts, now)
    uncertain_orders = _uncertain_orders(alerts)
    open_operations = _open_operations(alerts)
    kill_switch = _kill_switch(alerts)
    return {"generated_at": now.isoformat(),
            "integrity": integrity,
            "heartbeats": heartbeats,
            "feeds": feeds,
            "uncertain_orders": uncertain_orders,
            "open_operations": open_operations,
            "open_operations_count": len(open_operations),
            "kill_switch": kill_switch,
            "alerts": alerts}
