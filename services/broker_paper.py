"""Explicit, auditable broker paper flow, separate from local paper_operations."""

import json
from datetime import datetime, timezone
from decimal import Decimal

from database import store
from services.brokers.binance_spot_testnet import BinanceSpotTestnet, BrokerError, SYMBOLS
from services.risk import MAX_OPEN_POSITIONS

PROVIDER = "Binance Spot Testnet"
MAX_PRICE_DIVERGENCE = Decimal("0.01")
TERMINAL = {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}


def _adapter(adapter):
    return adapter if adapter is not None else BinanceSpotTestnet()


def readiness(adapter=None):
    broker = _adapter(adapter)
    return {"provider": PROVIDER, "configured": broker.configured,
            "state": "configurado_sem_validacao" if broker.configured else "desconectado",
            "limit": "Somente Testnet; ordens reais bloqueadas. Consulta privada apenas por ação explícita."}


def check_connection(adapter=None):
    return _adapter(adapter).connection_status()


def preview(symbol, quantity, limit_price, adapter=None, side="BUY"):
    broker = _adapter(adapter)
    if symbol not in SYMBOLS:
        raise ValueError("Ativo não elegível para Binance Spot Testnet.")
    qty, price = broker.validate_limit(symbol, quantity, limit_price)
    quote = broker.quote(symbol)
    quote_time = datetime.fromisoformat(quote["fetched_at"].replace("Z", "+00:00"))
    if quote_time.tzinfo is None or abs((datetime.now(timezone.utc) - quote_time).total_seconds()) > 30:
        raise BrokerError("Cotação Testnet ausente ou antiga; consulte novamente.")
    reference = Decimal(quote["ask"] if side == "BUY" else quote["bid"])
    divergence = abs(Decimal(price) / reference - 1)
    return {"provider": PROVIDER, "symbol": symbol, "quantity": qty,
            "limit_price": price, "quote": quote, "divergence_pct": float(divergence * 100),
            "eligible": divergence <= MAX_PRICE_DIVERGENCE}


def _clean_response(response, expected_client_id):
    if response.get("clientOrderId") not in {None, expected_client_id}:
        raise BrokerError("Identificador da ordem Testnet divergiu.")
    state = response.get("status")
    if state not in {"NEW", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED",
                     "EXPIRED", "PENDING_CANCEL"}:
        raise BrokerError("Estado de ordem Testnet desconhecido.")
    for key in ("orderId", "executedQty", "cummulativeQuoteQty"):
        if key not in response:
            raise BrokerError("Resposta da ordem Testnet incompleta.")
    for key in ("executedQty", "cummulativeQuoteQty"):
        value = Decimal(str(response[key]))
        if not value.is_finite() or value < 0:
            raise BrokerError("Resposta da ordem Testnet inválida.")
    return {key: response[key] for key in ("symbol", "orderId", "clientOrderId", "status",
                                          "origQty", "price", "executedQty", "cummulativeQuoteQty",
                                          "transactTime", "updateTime") if key in response}


def _apply(order_id, response):
    order = store.get_broker_paper_order(order_id)
    clean = _clean_response(response, order["client_order_id"])
    store.update_broker_paper_order(
        order_id, clean["status"], exchange_order_id=str(clean.get("orderId")) if clean.get("orderId") else None,
        executed_qty=float(clean.get("executedQty", order["executed_qty"])),
        quote_qty=float(clean.get("cummulativeQuoteQty", order["quote_qty"])), response=clean)
    return store.get_broker_paper_order(order_id)


def _send_reserved(order_id, adapter):
    order = store.get_broker_paper_order(order_id)
    try:
        response = adapter.place_limit(order["symbol"], order["side"], order["quantity"],
                                       order["limit_price"], order["client_order_id"])
        return _apply(order_id, response)
    except (BrokerError, ValueError, TimeoutError, OSError):
        store.update_broker_paper_order(order_id, "unknown",
                                         executed_qty=order["executed_qty"],
                                         quote_qty=order["quote_qty"],
                                         error="Envio sem confirmação; consultar ordem pelo identificador persistido.")
        raise BrokerError("Resultado da Testnet desconhecido; consulte a ordem antes de outra ação.") from None


def submit_entry(run_id, quantity, limit_price, confirmed=False, adapter=None):
    """Human confirmed long-only LIMIT BUY. No local paper operation is opened."""
    if not confirmed:
        raise ValueError("Confirme explicitamente a ordem virtual Testnet.")
    broker = _adapter(adapter)
    if not broker.configured:
        raise ValueError("Credenciais exclusivas da Binance Spot Testnet ausentes.")
    run = store.get_pipeline_run(run_id)
    if not run or run["status"] != "aguardando_quantidade" or run["risk_verdict"] != "autorizado":
        raise ValueError("Trilha não autorizada para envio Testnet.")
    plan = json.loads(run["report_json"]).get("execution") or {}
    if run["symbol"] not in SYMBOLS or plan.get("side") != "buy":
        raise ValueError("Spot Testnet aceita apenas candidatos comprados nesta entrega.")
    if store.count_reserved_exposure() - 1 >= MAX_OPEN_POSITIONS:
        raise ValueError("Exposição máxima ocupada por outras posições ou autorizações.")
    check = preview(run["symbol"], quantity, limit_price, broker)
    if not check["eligible"]:
        raise ValueError("Preço limite diverge mais de 1% da compra Testnet atual.")
    client_id = f"tal{run_id}entry"
    order_id = store.reserve_broker_entry(run_id, PROVIDER, client_id, run["symbol"],
                                          check["quantity"], check["limit_price"])
    return _send_reserved(order_id, broker)


def reconcile(order_id, adapter=None):
    order = store.get_broker_paper_order(order_id)
    if not order or order["provider"] != PROVIDER:
        raise ValueError("Ordem Testnet não encontrada.")
    response = _adapter(adapter).get_order(order["symbol"], order["client_order_id"])
    return _apply(order_id, response)


def cancel(order_id, adapter=None):
    order = store.get_broker_paper_order(order_id)
    if not order or order["provider"] != PROVIDER or order["state"] in TERMINAL:
        raise ValueError("Ordem Testnet não pode ser cancelada neste estado.")
    response = _adapter(adapter).cancel_order(order["symbol"], order["client_order_id"])
    return _apply(order_id, response)


def submit_exit(entry_order_id, quantity, limit_price, confirmed=False, adapter=None):
    if not confirmed:
        raise ValueError("Confirme explicitamente a venda virtual Testnet.")
    broker = _adapter(adapter)
    if not broker.configured:
        raise ValueError("Credenciais exclusivas da Binance Spot Testnet ausentes.")
    entry = store.get_broker_paper_order(entry_order_id)
    if not entry or entry["role"] != "entry" or entry["provider"] != PROVIDER:
        raise ValueError("Compra Testnet não encontrada.")
    check = preview(entry["symbol"], quantity, limit_price, broker, side="SELL")
    if not check["eligible"]:
        raise ValueError("Preço de venda diverge mais de 1% da Testnet atual.")
    attempts = sum(1 for row in store.list_broker_paper_orders(limit=10000)
                   if row["parent_order_id"] == entry_order_id)
    client_id = f"tal{entry['run_id']}exit{attempts+1}"
    order_id = store.reserve_broker_exit(entry_order_id, PROVIDER, client_id,
                                         check["quantity"], check["limit_price"])
    return _send_reserved(order_id, broker)
