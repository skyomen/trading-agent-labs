"""Local historical-data manifest, validation and reproducible import."""

import hashlib
import json
import math
from datetime import datetime

from database import store
from services.backtest import parse_ohlcv_csv

MINUTES = {"1m": 1, "2m": 2, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}


def canonical_digest(bars):
    content = json.dumps(bars, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def validate_manifest(manifest, bars):
    required = {"symbol", "market", "provider", "timeframe", "timezone",
                "quote_currency", "tick_size", "volume_unit", "license_note"}
    missing = sorted(key for key in required if not str(manifest.get(key, "")).strip())
    if missing:
        raise ValueError("Metadados ausentes: " + ", ".join(missing))
    if manifest["market"] not in {"crypto", "us_equity"}:
        raise ValueError("Mercado deve ser crypto ou us_equity.")
    if manifest["timeframe"] not in MINUTES:
        raise ValueError("Intervalo não suportado.")
    tick = float(manifest["tick_size"])
    if not math.isfinite(tick) or tick <= 0:
        raise ValueError("Incremento mínimo deve ser positivo e finito.")
    if manifest["timezone"] != "UTC":
        raise ValueError("Use timestamps UTC explícitos; fuso local fica nos metadados de apresentação.")
    timestamps = []
    for bar in bars:
        parsed = datetime.fromisoformat(bar["timestamp"].replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("Todas as barras devem trazer timestamp UTC explícito.")
        timestamps.append(parsed)
    interval = MINUTES[manifest["timeframe"]] * 60
    gaps = []
    for previous, current in zip(timestamps, timestamps[1:]):
        delta = (current - previous).total_seconds()
        if delta < interval or (manifest["timeframe"] != "1d" and delta % interval) or (manifest["market"] == "crypto" and delta % interval):
            raise ValueError("Horários incompatíveis com o intervalo informado.")
        if delta > interval:
            gaps.append({"after": previous.isoformat(), "before": current.isoformat(),
                         "missing_intervals": (int(delta // interval) - 1
                                               if manifest["market"] == "crypto" else None)})
    normalized = {key: str(manifest[key]).strip() for key in required}
    for key in ("source_url", "market_session"):
        if manifest.get(key):
            normalized[key] = str(manifest[key]).strip()
    normalized.update({"start_utc": timestamps[0].isoformat(),
                       "end_utc": timestamps[-1].isoformat(), "row_count": len(bars),
                       "gap_count": len(gaps), "gap_examples": gaps[:20]})
    return normalized


def import_csv(content, filename, manifest):
    parsed = parse_ohlcv_csv(content, filename)
    metadata = validate_manifest(manifest, parsed["bars"])
    digest = canonical_digest(parsed["bars"])
    dataset_id = store.save_historical_dataset(
        filename, manifest["symbol"], manifest["timeframe"], manifest["provider"],
        parsed["sha256"], parsed["bars"], metadata=metadata,
        canonical_sha256=digest)
    return {"id": dataset_id, "sha256": parsed["sha256"],
            "canonical_sha256": digest, "metadata": metadata}


def load_verified(dataset_id):
    row = next((item for item in store.list_historical_datasets()
                if item["id"] == dataset_id), None)
    if row is None:
        raise ValueError("Dataset não encontrado.")
    bars = store.get_historical_bars(dataset_id)
    if row["canonical_sha256"] and canonical_digest(bars) != row["canonical_sha256"]:
        raise ValueError("As barras persistidas divergem do hash canônico.")
    return {"dataset": row, "metadata": json.loads(row["metadata_json"]), "bars": bars}
