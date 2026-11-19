"""Explicit Binance public-data import and continuous closed-candle collector.

Only market data is accessed. No trading endpoint, account or order capability.
"""

import argparse
import csv
import io
import json
import logging
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from database import store
from services import datasets
from services.config import current_credentials, load_local_env

REST = "https://data-api.binance.vision/api/v3/klines"
EXCHANGE_INFO = "https://data-api.binance.vision/api/v3/exchangeInfo"
STREAM = "wss://data-stream.binance.vision:443/ws/{}@kline_1m"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
ANALYSIS_SYMBOLS = SYMBOLS + ("SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT")
OBSERVATION_ONLY_SYMBOLS = tuple(symbol for symbol in ANALYSIS_SYMBOLS if symbol not in SYMBOLS)
PROVIDER = "Binance Spot public"
ALPACA_BARS = "https://data.alpaca.markets/v2/stocks/bars"
MARKET_HISTORY = "https://getmarkethistory.com/api/v1/bars/stocks/us/{}/1h?format=csv"
STOCKS = ("AAPL", "MSFT")
_SYMBOL_METADATA_CACHE = {}


def _stamp(milliseconds):
    return datetime.fromtimestamp(int(milliseconds) / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def _bar(row):
    bar = {"timestamp": _stamp(row[0]), "open": float(row[1]),
           "high": float(row[2]), "low": float(row[3]),
           "close": float(row[4]), "volume": float(row[5])}
    if any(value <= 0 for key, value in bar.items() if key not in {"timestamp", "volume"}):
        raise ValueError("Barra inválida da fonte.")
    return bar


def fetch_closed_klines(symbol, limit=1000, timeframe="1m"):
    if symbol not in ANALYSIS_SYMBOLS or timeframe not in {"1m", "5m"} or not 3 <= limit <= 1000:
        raise ValueError("Símbolo, intervalo ou limite não suportado.")
    url = REST + "?" + urlencode({"symbol": symbol, "interval": timeframe, "limit": limit})
    with urlopen(url, timeout=15) as response:
        payload = json.load(response)
    if not isinstance(payload, list):
        raise ValueError("Resposta de candles inesperada.")
    now_ms = int(time.time() * 1000)
    bars = [_bar(row) for row in payload if int(row[6]) < now_ms]
    if len(bars) < 3:
        raise ValueError("Menos de três candles fechados foram recebidos.")
    return bars


def symbol_metadata(symbol):
    """Read current public Spot filters; never guess an instrument tick size."""
    if symbol not in ANALYSIS_SYMBOLS:
        raise ValueError("Símbolo fora da lista de análise autorizada.")
    cached = _SYMBOL_METADATA_CACHE.get(symbol)
    if cached and time.time() - cached["loaded_at"] < 3600:
        return dict(cached["metadata"])
    request = Request(EXCHANGE_INFO + "?" + urlencode({"symbol": symbol}),
                      headers={"User-Agent": "TradingAgentLab/1.0"})
    with urlopen(request, timeout=15) as response:
        payload = json.load(response)
    entries = payload.get("symbols", [])
    item = next((row for row in entries if row.get("symbol") == symbol), None)
    if not item or item.get("status") != "TRADING" or item.get("quoteAsset") != "USDT":
        raise ValueError(f"{symbol} não está ativo como par Spot/USDT na fonte consultada.")
    price_filter = next((row for row in item.get("filters", [])
                         if row.get("filterType") == "PRICE_FILTER"), None)
    if not price_filter:
        raise ValueError(f"A fonte não informou PRICE_FILTER para {symbol}.")
    tick_size = float(price_filter.get("tickSize", 0))
    if tick_size <= 0:
        raise ValueError(f"Incremento de preço inválido para {symbol}.")
    metadata = {"symbol": symbol, "status": item["status"], "quote_asset": item["quoteAsset"],
                "tick_size": tick_size, "tick_size_source": "Binance Spot exchangeInfo",
                "min_notional": next((float(row.get("minNotional", 0))
                                       for row in item.get("filters", [])
                                       if row.get("filterType") in {"NOTIONAL", "MIN_NOTIONAL"}), None)}
    _SYMBOL_METADATA_CACHE[symbol] = {"loaded_at": time.time(), "metadata": metadata}
    return dict(metadata)


def _csv_bytes(bars):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["timestamp", "open", "high", "low", "close", "volume"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(bars)
    return output.getvalue().encode("utf-8")


def import_recent(symbol, limit=1000):
    """Import a bounded, immutable snapshot on an explicit user action."""
    if symbol not in SYMBOLS:
        raise ValueError("Snapshots elegíveis para backtest permanecem limitados a BTCUSDT/ETHUSDT.")
    bars = fetch_closed_klines(symbol, limit=limit)
    result = datasets.import_csv(_csv_bytes(bars), f"binance-{symbol}-1m-{bars[0]['timestamp']}.csv", {
        "symbol": symbol, "market": "crypto", "provider": PROVIDER,
        "timeframe": "1m", "timezone": "UTC", "quote_currency": "USDT",
        "tick_size": "0.01", "volume_unit": symbol.removesuffix("USDT"),
        "license_note": "Binance Spot public market data; pesquisa local; sujeito aos termos da fonte",
        "source_url": REST, "market_session": "24x7",
    })
    return result


def import_alpaca_stock(symbol, start_utc, end_utc):
    """Import IEX historical bars when local read-only data credentials exist."""
    if symbol not in STOCKS:
        raise ValueError("Ação não suportada.")
    key = current_credentials().get("ALPACA_API_KEY", "")
    secret = current_credentials().get("ALPACA_API_SECRET", "")
    if not key or not secret:
        raise ValueError("Configure ALPACA_API_KEY e ALPACA_API_SECRET no ambiente local.")
    start = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_utc.replace("Z", "+00:00"))
    if not start.tzinfo or not end.tzinfo or start >= end:
        raise ValueError("Informe um intervalo UTC válido.")
    query = urlencode({"symbols": symbol, "timeframe": "1Min", "start": start_utc,
                       "end": end_utc, "limit": 1000, "feed": "iex", "adjustment": "raw"})
    request = Request(ALPACA_BARS + "?" + query, headers={
        "APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
    with urlopen(request, timeout=15) as response:
        payload = json.load(response)
    if payload.get("next_page_token"):
        raise ValueError("A consulta contém mais de 1.000 barras; divida o período para evitar truncamento.")
    source_bars = payload.get("bars", {}).get(symbol, [])
    bars = [{"timestamp": item["t"], "open": item["o"], "high": item["h"],
             "low": item["l"], "close": item["c"], "volume": item["v"]}
            for item in source_bars]
    return datasets.import_csv(_csv_bytes(bars), f"alpaca-iex-{symbol}-{start_utc}.csv", {
        "symbol": symbol, "market": "us_equity", "provider": "Alpaca IEX",
        "timeframe": "1m", "timezone": "UTC", "quote_currency": "USD",
        "tick_size": "0.01", "volume_unit": "shares",
        "license_note": "Alpaca IEX via credenciais próprias; sujeito aos termos da conta",
        "source_url": ALPACA_BARS, "market_session": "IEX trades only",
    })


def import_public_stock_history(symbol):
    """Import the provider's free, no-account hourly historical sample."""
    if symbol not in STOCKS:
        raise ValueError("Ação não suportada.")
    url = MARKET_HISTORY.format(symbol)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/csv"})
    with urlopen(request, timeout=15) as response:
        content = response.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise ValueError("Resposta histórica excede o limite de 2 MB.")
    try:
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        if len(rows) < 3 or any(row.get("symbol") != symbol for row in rows):
            raise ValueError("Amostra da fonte vazia ou com outro símbolo.")
        bars = [{key: row[key] for key in ("timestamp", "open", "high", "low", "close", "volume")}
                for row in rows]
    except (UnicodeDecodeError, KeyError) as exc:
        raise ValueError("Resposta CSV inválida da fonte.") from exc
    return datasets.import_csv(_csv_bytes(bars), f"market-history-{symbol}-1h.csv", {
        "symbol": symbol, "market": "us_equity", "provider": "Market History US consolidated",
        "timeframe": "1h", "timezone": "UTC", "quote_currency": "USD",
        "tick_size": "0.0001", "volume_unit": "shares",
        "license_note": "Amostra pública para pesquisa local; redistribuição de dados brutos proibida pelos termos da fonte",
        "source_url": url, "market_session": "historical sample; not live",
    })


def _heartbeat(symbol, state, details=""):
    """Stamp collector liveness next to the feed update it already performs.

    Observability only: a failure here must never interrupt collection, so it is logged
    and swallowed instead of being mistaken for a disconnect.
    """
    try:
        store.record_heartbeat(f"collector:{symbol}", state, details)
    except Exception as exc:
        logging.debug("Heartbeat do coletor %s não registrado: %s", symbol, exc)


def _backfill(symbol):
    bars = fetch_closed_klines(symbol, limit=1000)
    store.upsert_market_bars(PROVIDER, symbol, "1m", bars)
    store.update_market_feed(PROVIDER, symbol, "1m", "connected", bars[-1]["timestamp"])
    _heartbeat(symbol, "connected", "backfill concluído")


def collect_symbol_forever(symbol, stop_event=None):
    """Backfill gaps then reconnect after disconnect; persist only closed candles."""
    if symbol not in ANALYSIS_SYMBOLS:
        raise ValueError("Símbolo não suportado.")
    from websockets.sync.client import connect

    stop_event = stop_event or threading.Event()
    while not stop_event.is_set():
        try:
            _backfill(symbol)
            with connect(STREAM.format(symbol.lower()), open_timeout=15, close_timeout=5) as socket:
                store.update_market_feed(PROVIDER, symbol, "1m", "connected")
                _heartbeat(symbol, "connected", "stream aberto")
                while not stop_event.is_set():
                    message = json.loads(socket.recv(timeout=90))
                    candle = message.get("k", {})
                    if not candle.get("x") or candle.get("s") != symbol or candle.get("i") != "1m":
                        continue
                    bar = _bar([candle["t"], candle["o"], candle["h"], candle["l"], candle["c"], candle["v"]])
                    store.upsert_market_bar(PROVIDER, symbol, "1m", bar)
                    store.update_market_feed(PROVIDER, symbol, "1m", "connected", bar["timestamp"])
                    _heartbeat(symbol, "connected", f"candle fechado {bar['timestamp']}")
        except Exception as exc:
            logging.warning("Feed %s desconectado: %s", symbol, exc)
            store.update_market_feed(PROVIDER, symbol, "1m", "disconnected", error=str(exc)[:500])
            _heartbeat(symbol, "disconnected", str(exc)[:250])
            stop_event.wait(10)
    store.update_market_feed(PROVIDER, symbol, "1m", "stopped")
    _heartbeat(symbol, "stopped", "coletor encerrado")


def main():
    load_local_env()
    parser = argparse.ArgumentParser(description="Coletor público Binance; só candles fechados")
    parser.add_argument("command", choices=["import", "import-stock", "stream"])
    parser.add_argument("--symbol", choices=ANALYSIS_SYMBOLS + STOCKS)
    args = parser.parse_args()
    store.initialize()
    if args.command == "import":
        if args.symbol not in SYMBOLS:
            parser.error("--symbol BTCUSDT ou ETHUSDT é obrigatório")
        result = import_recent(args.symbol)
        print(f"Dataset #{result['id']} {args.symbol} {result['metadata']['row_count']} barras; sha256:{result['sha256']}")
    elif args.command == "import-stock":
        if args.symbol not in STOCKS:
            parser.error("--symbol AAPL ou MSFT é obrigatório")
        result = import_public_stock_history(args.symbol)
        print(f"Dataset #{result['id']} {args.symbol} {result['metadata']['row_count']} barras; sha256:{result['sha256']}")
    else:
        if args.symbol and args.symbol not in ANALYSIS_SYMBOLS:
            parser.error("O coletor ao vivo suporta a lista de pares Spot/USDT de análise")
        symbols = (args.symbol,) if args.symbol else ANALYSIS_SYMBOLS
        threads = [threading.Thread(target=collect_symbol_forever, args=(symbol,), daemon=True)
                   for symbol in symbols]
        for thread in threads:
            thread.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Coletor encerrado; reinicie para voltar a receber dados.")


if __name__ == "__main__":
    main()
