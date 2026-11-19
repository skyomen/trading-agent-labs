"""Read-only candle chart assembled from persisted market and paper records."""

import json
from datetime import datetime, timezone


def _utc(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def build_candle_chart(bars, runs=(), operations=(), journal_by_operation=None):
    """Return a Vega-Lite spec and marker counts; never infer missing trades.

    `bars` are closed market bars in ascending order. Signal markers use the
    proposed entry from a persisted pipeline report. Operation markers use the
    persisted confirmation/exit times and prices, which may differ from the
    signal candle.
    """
    if not bars:
        return None
    candles = []
    for bar in bars:
        stamp = _utc(bar["timestamp"])
        if stamp is None:
            continue
        candles.append({
            "timestamp": _stamp(stamp), "open": bar["open"], "high": bar["high"],
            "low": bar["low"], "close": bar["close"], "volume": bar["volume"],
            "direcao": "Alta" if bar["close"] >= bar["open"] else "Baixa",
        })
    if not candles:
        return None
    start, end = _utc(candles[0]["timestamp"]), _utc(candles[-1]["timestamp"])
    markers = []

    def add_marker(moment, price, kind, detail):
        instant = _utc(moment)
        if instant is not None and start <= instant <= end and price is not None:
            markers.append({"timestamp": _stamp(instant), "price": price,
                            "tipo": kind, "detalhe": detail})

    for run in runs:
        if run.get("decision") != "trade_candidate":
            continue
        try:
            report = json.loads(run.get("report_json") or "{}")
        except (TypeError, ValueError):
            continue
        proposed_entry = (report.get("execution") or {}).get("entrada")
        add_marker(run.get("signal_bar_utc"), proposed_entry, "Plano de sinal",
                   f"Trilha #{run['id']} · {run.get('setup_name') or 'setup'} · {run.get('status') or 'sem estado'}")

    for operation in operations:
        journal = (journal_by_operation or {}).get(operation["id"], {})
        add_marker(journal.get("entry_time") or operation.get("created_at"),
                   operation.get("entry_price"), "Abertura paper",
                   f"Operação #{operation['id']} · quantidade {operation.get('quantity')}")
        if operation.get("state") == "closed":
            add_marker(journal.get("exit_time") or operation.get("closed_at"),
                       operation.get("exit_price"), "Saída paper",
                       f"Operação #{operation['id']} · {operation.get('exit_reason') or 'motivo não registrado'}")

    x = {"field": "timestamp", "type": "temporal", "title": "Horário UTC",
         "scale": {"type": "utc"}, "axis": {"format": "%H:%M", "labelOverlap": True}}
    candle_color = {"field": "direcao", "type": "nominal", "legend": None,
                    "scale": {"domain": ["Alta", "Baixa"], "range": ["#168761", "#c8475c"]}}
    tooltip = [
        {"field": "timestamp", "type": "nominal", "title": "Início do candle UTC"},
        {"field": "open", "type": "quantitative", "title": "Abertura"},
        {"field": "high", "type": "quantitative", "title": "Máxima"},
        {"field": "low", "type": "quantitative", "title": "Mínima"},
        {"field": "close", "type": "quantitative", "title": "Fechamento"},
        {"field": "volume", "type": "quantitative", "title": "Volume"},
    ]
    layers = [
        {"data": {"values": candles}, "mark": {"type": "rule"},
         "encoding": {"x": x,
                      "y": {"field": "low", "type": "quantitative", "title": "Preço (USDT)",
                            "scale": {"zero": False}},
                      "y2": {"field": "high"}, "color": candle_color, "tooltip": tooltip}},
        {"data": {"values": candles}, "mark": {"type": "bar", "size": 5},
         "encoding": {"x": x,
                      "y": {"field": "open", "type": "quantitative", "scale": {"zero": False}},
                      "y2": {"field": "close"}, "color": candle_color, "tooltip": tooltip}},
    ]
    if markers:
        layers.append({
            "data": {"values": markers}, "mark": {"type": "point", "filled": True, "size": 115},
            "encoding": {
                "x": x, "y": {"field": "price", "type": "quantitative"},
                "color": {"field": "tipo", "type": "nominal", "title": "Registro",
                          "scale": {"domain": ["Plano de sinal", "Abertura paper", "Saída paper"],
                                    "range": ["#a97700", "#4268d5", "#8e51ba"]}},
                "tooltip": [
                    {"field": "timestamp", "type": "nominal", "title": "Início do candle UTC"},
                    {"field": "price", "type": "quantitative", "title": "Preço registrado"},
                    {"field": "tipo", "type": "nominal", "title": "Registro"},
                    {"field": "detalhe", "type": "nominal", "title": "Origem"},
                ],
            },
        })
    return {
        "spec": {"$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                 "height": 320, "layer": layers, "resolve": {"scale": {"color": "independent"}}},
        "candles": len(candles), "ohlcv": candles, "first": candles[0]["timestamp"],
        "last": candles[-1]["timestamp"], "markers": markers,
    }


def build_operation_chart(bars, run, operation, journal):
    """Chart one paper operation against the exact stored candles and bar times.

    Simulated entry/exit use small trade triangles. Planned stop and target are
    separately labelled horizontal guides; exit also gets a vertical time guide.
    """
    chart = build_candle_chart(bars)
    if chart is None:
        return None
    report = json.loads(run.get("report_json") or "{}")
    details = journal or {}
    execution = report.get("execution") or {}
    candles = {_stamp(_utc(bar["timestamp"])): bar for bar in bars}
    events = []

    def add(kind, moment, price, explanation, color):
        stamp = _stamp(_utc(moment)) if moment else None
        if stamp in candles and price is not None:
            events.append({"timestamp": stamp, "price": price,
                           "tipo": kind, "detalhe": explanation, "shape": "triangle-right",
                           "cor": color})

    entry_time = details.get("entry_time") or execution.get("barra_de_entrada_utc")
    add("Entrada simulada", entry_time, operation.get("entry_price"),
        "Preço simulado de entrada; não é execução na Binance",
        "#40c994" if operation.get("side") == "buy" else "#f06ab8")
    entry_stamp = _stamp(_utc(entry_time)) if entry_time else None
    exit_stamp = _stamp(_utc(details["exit_time"])) if details.get("exit_time") else None
    level_end = exit_stamp if exit_stamp in candles else chart["last"]

    def add_level(label, price, color, dash):
        if price is None or entry_stamp not in candles:
            return None
        level = {"start": entry_stamp, "end": level_end, "price": price,
                 "label": label}
        chart["spec"]["layer"].append({
            "data": {"values": [level]},
            "mark": {"type": "rule", "strokeDash": dash, "strokeWidth": 1.5,
                     "color": color, "opacity": 0.9},
            "encoding": {"x": {"field": "start", "type": "temporal", "scale": {"type": "utc"}},
                         "x2": {"field": "end"},
                         "y": {"field": "price", "type": "quantitative"},
                         "tooltip": [{"field": "label", "type": "nominal", "title": "Nível"},
                                     {"field": "price", "type": "quantitative", "title": "Preço planejado"}]},
        })
        chart["spec"]["layer"].append({
            "data": {"values": [level]},
            "mark": {"type": "text", "align": "right", "baseline": "bottom",
                     "dx": -6, "dy": -4, "fontSize": 10, "fontWeight": 700,
                     "color": color},
            "encoding": {"x": {"field": "end", "type": "temporal", "scale": {"type": "utc"}},
                         "y": {"field": "price", "type": "quantitative"},
                         "text": {"field": "label"}},
        })
        return level

    stop_line = add_level("STOP", execution.get("stop"), "#e9b75e", [5, 4])
    target_line = add_level("ALVO", execution.get("alvo"), "#42b8ed", [2, 3])

    exit_guide = None
    if operation.get("state") == "closed":
        exit_time = details.get("exit_time")
        fill = operation.get("exit_price")
        add("Saída simulada", exit_time, fill,
            "Preço final simulado após slippage; não é execução na Binance",
            "#f06ab8" if operation.get("side") == "buy" else "#40c994")
        if exit_stamp in candles:
            exit_guide = {"timestamp": exit_stamp, "price": fill,
                          "label": "Saída simulada"}
            guide_color = "#f06ab8" if operation.get("side") == "buy" else "#40c994"
            chart["spec"]["layer"].append({
                "data": {"values": [exit_guide]},
                "mark": {"type": "rule", "strokeDash": [3, 3], "strokeWidth": 1,
                         "color": guide_color, "opacity": 0.65},
                "encoding": {
                    "x": {"field": "timestamp", "type": "temporal", "scale": {"type": "utc"}},
                    "tooltip": [{"field": "label", "type": "nominal", "title": "Evento"},
                                {"field": "timestamp", "type": "temporal", "title": "Candle UTC"},
                                {"field": "price", "type": "quantitative", "title": "Preço final"}],
                },
            })
            chart["spec"]["layer"].append({
                "data": {"values": [exit_guide]},
                "mark": {"type": "text", "align": "left", "baseline": "bottom",
                         "dx": 6, "dy": -6, "fontSize": 10, "fontWeight": 700,
                         "color": guide_color},
                "encoding": {"x": {"field": "timestamp", "type": "temporal", "scale": {"type": "utc"}},
                             "y": {"field": "price", "type": "quantitative"},
                             "text": {"value": "SAÍDA"}},
            })
    if events:
        chart["spec"]["layer"].append({
            "data": {"values": events},
            "mark": {"type": "point", "filled": True, "size": 66},
            "encoding": {
                "x": {"field": "timestamp", "type": "temporal", "scale": {"type": "utc"}},
                "y": {"field": "price", "type": "quantitative"},
                "color": {"field": "cor", "type": "nominal", "scale": None, "legend": None},
                "shape": {"value": "triangle-right"},
                "tooltip": [
                    {"field": "timestamp", "type": "nominal", "title": "Início do candle UTC"},
                    {"field": "price", "type": "quantitative", "title": "Nível no gráfico"},
                    {"field": "tipo", "type": "nominal", "title": "Evento"},
                    {"field": "detalhe", "type": "nominal", "title": "Explicação"},
                ],
            },
        })
    verification = []
    for kind in ("Entrada simulada", "Saída simulada"):
        event = next((row for row in events if row["tipo"] == kind), None)
        if event:
            bar = candles[event["timestamp"]]
            verification.append({"Evento": kind, "Candle UTC": event["timestamp"],
                                 "Preço marcado": event["price"],
                                 "Abertura": bar["open"], "Máxima": bar["high"],
                                 "Mínima": bar["low"], "Fechamento": bar["close"],
                                 "Volume": bar["volume"]})
    return {**chart, "markers": events, "stop_line": stop_line,
            "target_line": target_line, "exit_guide": exit_guide,
            "verification_rows": verification}
