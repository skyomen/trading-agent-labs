"""CSV validation and a deliberately small, reproducible SMA crossover engine."""

import csv
import hashlib
import io
import math
from datetime import datetime


REQUIRED_FIELDS = ("timestamp", "open", "high", "low", "close", "volume")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_BARS = 500_000


def parse_ohlcv_csv(content, filename):
    if not content:
        raise ValueError("O arquivo está vazio.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("O arquivo excede o limite de 50 MB.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Use CSV codificado em UTF-8.") from exc
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;	")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    aliases = {"datetime": "timestamp", "date": "timestamp", "time": "timestamp"}
    field_map = {}
    for name in reader.fieldnames or []:
        normalized = name.strip().casefold()
        field_map[aliases.get(normalized, normalized)] = name
    missing = set(REQUIRED_FIELDS) - set(field_map)
    if missing:
        raise ValueError(f"Colunas ausentes: {', '.join(sorted(missing))}.")

    bars = []
    previous = None
    timezone_kind = None
    for line_number, raw in enumerate(reader, start=2):
        if len(bars) >= MAX_BARS:
            raise ValueError("O arquivo excede o limite de 500.000 barras.")
        stamp = (raw.get(field_map["timestamp"]) or "").strip()
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            current_tz = "aware" if parsed.tzinfo else "naive"
            if timezone_kind is None:
                timezone_kind = current_tz
            elif timezone_kind != current_tz:
                raise ValueError("Mistura de horários com e sem fuso.")
            values = {key: float(raw[field_map[key]]) for key in REQUIRED_FIELDS[1:]}
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"Linha {line_number}: horário ou valor numérico inválido.") from exc
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError(f"Linha {line_number}: o arquivo contém valor não finito.")
        if previous is not None and parsed <= previous:
            raise ValueError(f"Linha {line_number}: horários precisam ser únicos e crescentes.")
        previous = parsed
        if any(value <= 0 for key, value in values.items() if key != "volume") or values["volume"] < 0:
            raise ValueError(f"Linha {line_number}: preços devem ser positivos e volume não pode ser negativo.")
        if values["high"] < max(values["open"], values["close"], values["low"]):
            raise ValueError(f"Linha {line_number}: máxima incompatível com OHLC.")
        if values["low"] > min(values["open"], values["close"], values["high"]):
            raise ValueError(f"Linha {line_number}: mínima incompatível com OHLC.")
        bars.append({"timestamp": stamp, **values})
    if len(bars) < 3:
        raise ValueError("O backtest precisa de pelo menos três barras.")
    return {"bars": bars, "sha256": hashlib.sha256(content).hexdigest(), "filename": filename}


def _sma(closes, end, window):
    start = end - window + 1
    return sum(closes[start:end + 1]) / window


def run_sma_crossover(bars, fast_window, slow_window, fee_bps=0.0, slippage_bps=0.0):
    """Long-only SMA cross; signals use closes and fills use the next bar open."""
    if fast_window < 2 or slow_window <= fast_window:
        raise ValueError("A janela rápida precisa ser ≥ 2 e menor que a janela lenta.")
    if fee_bps < 0 or slippage_bps < 0:
        raise ValueError("Custos e slippage não podem ser negativos.")
    if len(bars) <= slow_window:
        raise ValueError("O histórico é menor que a janela lenta escolhida.")

    closes = [float(bar["close"]) for bar in bars]
    trades = []
    entry = None
    for index in range(slow_window, len(bars) - 1):
        fast_prev = _sma(closes, index - 1, fast_window)
        slow_prev = _sma(closes, index - 1, slow_window)
        fast_now = _sma(closes, index, fast_window)
        slow_now = _sma(closes, index, slow_window)
        crossed_up = fast_prev <= slow_prev and fast_now > slow_now
        crossed_down = fast_prev >= slow_prev and fast_now < slow_now
        if entry is None and crossed_up:
            entry = {"index": index + 1, "price": float(bars[index + 1]["open"])}
        elif entry is not None and crossed_down:
            trades.append((entry, {"index": index + 1, "price": float(bars[index + 1]["open"])}))
            entry = None
    if entry is not None:
        trades.append((entry, {"index": len(bars) - 1, "price": float(bars[-1]["close"])}))

    round_trip_cost = 2 * (fee_bps + slippage_bps) / 10_000
    equity = 1.0
    peak = equity
    max_drawdown = 0.0
    outcomes = []
    total_cost = 0.0
    for opened, closed in trades:
        gross = closed["price"] / opened["price"] - 1
        net = gross - round_trip_cost
        equity *= (1 + net)
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak if peak else 0.0)
        total_cost += round_trip_cost
        outcomes.append({
            "entry_time": bars[opened["index"]]["timestamp"],
            "exit_time": bars[closed["index"]]["timestamp"],
            "entry_price": opened["price"], "exit_price": closed["price"],
            "gross_return_pct": gross * 100, "net_return_pct": net * 100,
        })
    wins = sum(1 for trade in outcomes if trade["net_return_pct"] > 0)
    return {
        "rule": "SMA crossover, long-only; close signal, next-bar-open fill",
        "fast_window": fast_window, "slow_window": slow_window,
        "fee_bps_per_side": fee_bps, "slippage_bps_per_side": slippage_bps,
        "trade_count": len(outcomes), "win_rate_pct": wins / len(outcomes) * 100 if outcomes else 0.0,
        "net_return_pct": (equity - 1) * 100, "max_drawdown_pct": max_drawdown * 100,
        "total_cost_pct_of_notional": total_cost * 100, "annualized": False,
        "trades": outcomes,
    }
