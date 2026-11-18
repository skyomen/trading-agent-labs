"""Hardwired Binance Spot Testnet adapter; no production URL or fallback."""

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from services.config import current_credentials, load_local_env

BASE_URL = "https://testnet.binance.vision"
SYMBOLS = frozenset({"BTCUSDT", "ETHUSDT"})


class BrokerError(ValueError):
    pass


def _decimal(value, label):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise BrokerError(f"{label} inválido.") from None
    if not number.is_finite() or number <= 0:
        raise BrokerError(f"{label} deve ser positivo e finito.")
    return number


class BinanceSpotTestnet:
    name = "Binance Spot Testnet"

    def __init__(self, opener=urlopen, clock_ms=None):
        load_local_env()
        self._opener = opener
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._key = current_credentials().get("BINANCE_SPOT_TESTNET_API_KEY", "")
        self._secret = current_credentials().get("BINANCE_SPOT_TESTNET_API_SECRET", "")

    @property
    def configured(self):
        return bool(self._key and self._secret)

    def _request(self, method, path, params=None, signed=False):
        if not path.startswith("/api/v3/") or "//" in path:
            raise BrokerError("Endpoint Testnet não permitido.")
        if signed and not self.configured:
            raise BrokerError("Credenciais exclusivas da Binance Spot Testnet ausentes.")
        payload = dict(params or {})
        if signed:
            payload["timestamp"] = self._clock_ms()
            payload["recvWindow"] = 5000
        query = urlencode(payload)
        if signed:
            signature = hmac.new(self._secret.encode("utf-8"), query.encode("utf-8"),
                                 hashlib.sha256).hexdigest()
            query += "&signature=" + signature
        url = BASE_URL + path
        body = None
        if method in {"GET", "DELETE"}:
            if query:
                url += "?" + query
        elif method == "POST":
            body = query.encode("utf-8")
        else:
            raise BrokerError("Método HTTP não permitido.")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if signed:
            headers["X-MBX-APIKEY"] = self._key
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener(request, timeout=15) as response:
                data = json.load(response)
        except HTTPError as exc:
            raise BrokerError(f"Testnet recusou a requisição (HTTP {exc.code}).") from None
        except (URLError, TimeoutError, OSError):
            raise BrokerError("Conexão com a Testnet indisponível; consulte a ordem antes de reenviar.") from None
        if not isinstance(data, dict):
            raise BrokerError("Resposta inesperada da Testnet.")
        if data.get("code") is not None and data.get("code") != 0:
            raise BrokerError(f"Testnet recusou a requisição (código {data['code']}).")
        return data

    def connection_status(self):
        if not self.configured:
            return {"state": "disconnected", "provider": self.name,
                    "reason": "credenciais Testnet ausentes"}
        account = self._request("GET", "/api/v3/account", signed=True)
        return {"state": "connected", "provider": self.name,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "can_trade": bool(account.get("canTrade"))}

    def quote(self, symbol):
        if symbol not in SYMBOLS:
            raise BrokerError("Símbolo fora do escopo da Testnet.")
        data = self._request("GET", "/api/v3/ticker/bookTicker", {"symbol": symbol})
        bid, ask = _decimal(data.get("bidPrice"), "bid"), _decimal(data.get("askPrice"), "ask")
        if bid > ask:
            raise BrokerError("Cotação Testnet inconsistente.")
        return {"symbol": symbol, "bid": str(bid), "ask": str(ask),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "provider": self.name}

    def symbol_rules(self, symbol):
        if symbol not in SYMBOLS:
            raise BrokerError("Símbolo fora do escopo da Testnet.")
        data = self._request("GET", "/api/v3/exchangeInfo", {"symbol": symbol})
        rows = data.get("symbols") or []
        if len(rows) != 1 or rows[0].get("symbol") != symbol or rows[0].get("status") != "TRADING":
            raise BrokerError("Símbolo indisponível para negociação na Testnet.")
        row = rows[0]
        if "LIMIT" not in row.get("orderTypes", []):
            raise BrokerError("Ordem LIMIT indisponível para o símbolo.")
        return {item["filterType"]: item for item in row.get("filters", [])}

    def validate_limit(self, symbol, quantity, price):
        quantity = _decimal(quantity, "Quantidade")
        price = _decimal(price, "Preço limite")
        filters = self.symbol_rules(symbol)
        price_filter, lot = filters.get("PRICE_FILTER"), filters.get("LOT_SIZE")
        if not price_filter or not lot:
            raise BrokerError("Filtros de preço/quantidade indisponíveis na Testnet.")
        for value, lower, upper, step, label in (
            (price, price_filter["minPrice"], price_filter["maxPrice"], price_filter["tickSize"], "Preço"),
            (quantity, lot["minQty"], lot["maxQty"], lot["stepSize"], "Quantidade"),
        ):
            minimum, maximum, increment = map(Decimal, (lower, upper, step))
            if minimum > 0 and value < minimum or maximum > 0 and value > maximum:
                raise BrokerError(f"{label} fora dos filtros da Testnet.")
            if increment > 0 and value % increment != 0:
                raise BrokerError(f"{label} não respeita o incremento da Testnet.")
        minimum_notional = filters.get("NOTIONAL", {}).get("minNotional") or filters.get("MIN_NOTIONAL", {}).get("minNotional")
        if minimum_notional and price * quantity < Decimal(minimum_notional):
            raise BrokerError("Valor da ordem abaixo do mínimo da Testnet.")
        return str(quantity), str(price)

    def place_limit(self, symbol, side, quantity, price, client_order_id):
        if side not in {"BUY", "SELL"} or symbol not in SYMBOLS:
            raise BrokerError("Lado ou símbolo não permitido.")
        quantity, price = self.validate_limit(symbol, quantity, price)
        return self._request("POST", "/api/v3/order", {
            "symbol": symbol, "side": side, "type": "LIMIT", "timeInForce": "GTC",
            "quantity": quantity, "price": price, "newClientOrderId": client_order_id,
            "newOrderRespType": "FULL"}, signed=True)

    def get_order(self, symbol, client_order_id):
        if symbol not in SYMBOLS:
            raise BrokerError("Símbolo fora do escopo da Testnet.")
        return self._request("GET", "/api/v3/order", {
            "symbol": symbol, "origClientOrderId": client_order_id}, signed=True)

    def cancel_order(self, symbol, client_order_id):
        if symbol not in SYMBOLS:
            raise BrokerError("Símbolo fora do escopo da Testnet.")
        return self._request("DELETE", "/api/v3/order", {
            "symbol": symbol, "origClientOrderId": client_order_id}, signed=True)
