"""Import 90 closed UTC days and validate the observation-only crypto watchlist.

This workflow is deliberately separate from paper execution. It only writes
immutable historical datasets, backtests and validation reports.
"""

import json
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from database import store
from services import datasets, market_data
from services.setup_backtest import run_approved
from services.validation import ENGINE_VERSION, evaluate_validation

SYMBOLS = market_data.OBSERVATION_ONLY_SYMBOLS
TIMEFRAMES = ("2m", "5m")
HOLDOUT_FRACTION = 0.3
LOOKBACK_DAYS = 90
BAR_MS = 60_000


def _get_page(symbol, start_ms, end_ms):
    url = market_data.REST + "?" + urlencode({
        "symbol": symbol, "interval": "1m", "startTime": start_ms,
        "endTime": end_ms - 1, "limit": 1000,
    })
    last_error = None
    for attempt in range(5):
        try:
            request = Request(url, headers={"User-Agent": "TradingAgentLab/1.0"})
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
            if not isinstance(payload, list):
                raise ValueError("Resposta inesperada da API pública de candles.")
            return payload
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
            if isinstance(exc, HTTPError) and exc.code not in {418, 429, 500, 502, 503, 504}:
                raise
            time.sleep(min(2 ** attempt, 16))
    raise RuntimeError(f"Falha ao baixar candles de {symbol}: {last_error}")


def fetch_closed_days(symbol, start_ms, end_ms):
    bars = []
    cursor = start_ms
    while cursor < end_ms:
        rows = _get_page(symbol, cursor, end_ms)
        if not rows:
            break
        page = [market_data._bar(row) for row in rows
                if start_ms <= int(row[0]) < end_ms and int(row[6]) < end_ms]
        if not page:
            break
        bars.extend(page)
        next_cursor = int(rows[-1][0]) + BAR_MS
        if next_cursor <= cursor:
            raise ValueError(f"Paginação Binance não avançou para {symbol}.")
        cursor = next_cursor
        print(f"  {symbol}: {len(bars):,} candles importados da API...", flush=True)
        time.sleep(0.08)
    if len(bars) < 1000:
        raise ValueError(f"Histórico inesperadamente curto para {symbol}: {len(bars)} candles.")
    return bars


def import_snapshot(symbol, start_ms, end_ms):
    start = datetime.fromtimestamp(start_ms / 1000, timezone.utc)
    end = datetime.fromtimestamp(end_ms / 1000, timezone.utc)
    for existing in store.list_historical_datasets():
        if existing["symbol"] != symbol or existing["timeframe"] != "1m":
            continue
        metadata = json.loads(existing["metadata_json"])
        if (metadata.get("provider") == market_data.PROVIDER
                and metadata.get("start_utc") == start.isoformat()
                and metadata.get("end_utc") == (end - timedelta(minutes=1)).isoformat()):
            datasets.load_verified(existing["id"])
            print(f"{symbol}: reutilizando dataset #{existing['id']} com hash canônico verificado",
                  flush=True)
            return {"id": existing["id"], "sha256": existing["sha256"],
                    "canonical_sha256": existing["canonical_sha256"], "metadata": metadata}
    bars = fetch_closed_days(symbol, start_ms, end_ms)
    meta = market_data.symbol_metadata(symbol)
    result = datasets.import_csv(market_data._csv_bytes(bars),
        f"binance-{symbol}-1m-{start.date()}-{(end - timedelta(days=1)).date()}.csv", {
            "symbol": symbol, "market": "crypto", "provider": market_data.PROVIDER,
            "timeframe": "1m", "timezone": "UTC", "quote_currency": "USDT",
            "tick_size": str(meta["tick_size"]), "volume_unit": symbol.removesuffix("USDT"),
            "license_note": "Binance Spot public market data; pesquisa local; sujeito aos termos da fonte",
            "source_url": market_data.REST, "market_session": "24x7",
        })
    print(f"{symbol}: dataset #{result['id']}, {len(bars):,} barras, "
          f"{result['metadata']['start_utc']} a {result['metadata']['end_utc']}, "
          f"arquivo SHA-256 {result['sha256']}, barras SHA-256 {result['canonical_sha256']}",
          flush=True)
    return result


def main():
    store.initialize()
    # Only fully closed UTC calendar days; the current partial day is excluded.
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=LOOKBACK_DAYS)
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    print(f"Janela: {start.isoformat()} até {end.isoformat()} (90 dias UTC fechados)")

    datasets_by_symbol = {}
    for symbol in SYMBOLS:
        imported = import_snapshot(symbol, start_ms, end_ms)
        row = next(row for row in store.list_historical_datasets() if row["id"] == imported["id"])
        datasets_by_symbol[symbol] = row

    strategies = [row for row in store.list_strategies()
                  if row["status"] == "approved"
                  and json.loads(row["rules_json"]).get("setup_name") in {"VBS", "VSS", "BOP", "BDP"}]
    if not strategies:
        raise ValueError("Nenhum setup aprovado encontrado; validação cancelada.")
    existing_backtests = store.list_backtests()
    existing_validations = store.list_validation_runs(limit=10000)
    for strategy in sorted(strategies, key=lambda item: item["id"]):
        name = json.loads(strategy["rules_json"])["setup_name"]
        for symbol, dataset in datasets_by_symbol.items():
            for timeframe in TIMEFRAMES:
                backtest = next((row for row in existing_backtests
                    if row["strategy_id"] == strategy["id"] and row["symbol"] == symbol
                    and row["timeframe"] == timeframe and row["data_sha256"] == dataset["sha256"]), None)
                if backtest:
                    metrics = json.loads(backtest["metrics_json"])
                    print(f"Backtest {name} {symbol} {timeframe}: já persistido #{backtest['id']}")
                else:
                    metrics = run_approved(strategy, dataset["id"], timeframe,
                                           allowed_symbols=SYMBOLS)
                    metrics["analysis_only"] = True
                    metrics["paper_eligible"] = False
                    backtest_id = store.save_backtest(strategy["id"], symbol, timeframe,
                        "Binance Spot public; análise observacional", dataset["sha256"], metrics)
                    print(f"Backtest #{backtest_id} {name} {symbol} {timeframe}: "
                          f"{metrics['trade_count']} operações históricas simuladas")

                previous = next((row for row in existing_validations
                    if row["strategy_id"] == strategy["id"] and row["dataset_id"] == dataset["id"]
                    and row["timeframe"] == timeframe and row["engine_version"] == ENGINE_VERSION
                    and abs(row["holdout_fraction"] - HOLDOUT_FRACTION) < 1e-9), None)
                if previous:
                    report = json.loads(previous["report_json"])
                    print(f"Validação {name} {symbol} {timeframe}: já persistida #{previous['id']}")
                else:
                    report = evaluate_validation(strategy, dataset["id"], timeframe,
                        HOLDOUT_FRACTION, allowed_symbols=SYMBOLS)
                    report["analysis_only"] = True
                    report["paper_eligible"] = False
                    run_id = store.save_validation_run(strategy["id"], symbol, timeframe,
                        dataset["id"], dataset["sha256"], report)
                    print(f"Validação #{run_id} {name} {symbol} {timeframe}: "
                          f"{report['sample_adequacy']}; treino "
                          f"{report['split']['train']['reference_trade_count']}, holdout "
                          f"{report['split']['holdout']['reference_trade_count']}; "
                          f"fragilidades {len(report['fragility_flags'])}")

    print("Concluído: nenhum risco ou posição paper foi criado; nenhum setup foi promovido.")


if __name__ == "__main__":
    main()
