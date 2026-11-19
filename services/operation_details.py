"""Read-only explanations for persisted local paper operations."""

import json
from datetime import datetime, timedelta, timezone

from database import store
from services import charting, market_data
from services.setup_backtest import aggregate_minutes

EXIT_LABELS = {
    "stop": "Stop atingido",
    "trailing_stop": "Stop móvel atingido",
    "target": "Alvo atingido",
    "gap_boundary": "Lacuna nos candles; fechamento na última barra válida",
    "end_of_data": "Fim dos dados disponíveis",
}


def _utc(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json(value):
    try:
        return json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}


def build_view(operation, run=None, journal=None, strategy=None):
    """Build facts only from stored operation, audit trail, journal and rules."""
    report = _json((run or {}).get("report_json"))
    details = _json((journal or {}).get("details_json"))
    rules = _json((strategy or {}).get("rules_json"))
    execution = report.get("execution") or {}
    decision = report.get("decision") or {}
    market = report.get("market") or {}
    risk = report.get("risk") or {}
    net = details.get("net_pnl") if (journal or {}).get("state") == "closed" else None
    outcome = ("positivo" if net > 0 else "negativo" if net < 0 else "zero") if isinstance(net, (int, float)) else None
    return {
        "operation": operation,
        "run": run,
        "journal": journal,
        "details": details,
        "rules": rules,
        "execution": execution,
        "decision": decision,
        "market": market,
        "risk": risk,
        "setup": (run or {}).get("setup_name") or details.get("setup_name"),
        "timeframe": (run or {}).get("timeframe") or details.get("timeframe"),
        "signal_time": (run or {}).get("signal_bar_utc") or details.get("signal_bar_utc"),
        "entry_time": details.get("entry_time") or execution.get("barra_de_entrada_utc"),
        "exit_time": details.get("exit_time"),
        "net_pnl": net,
        "outcome": outcome,
        "exit_label": EXIT_LABELS.get(operation.get("exit_reason"),
                                      operation.get("exit_reason") or "Ainda aberta"),
        "currency": details.get("quote_currency") or
                    ("USDT" if operation["symbol"].endswith("USDT") else None),
    }


def build_steps(view):
    """Chronological paper facts; a planned stop is never called an exchange order."""
    operation, plan, details = view["operation"], view["execution"], view["details"]
    steps = []
    if view["entry_time"] and operation.get("entry_price") is not None:
        steps.append({"title": "Entrada", "time": view["entry_time"],
                      "price": operation["entry_price"],
                      "detail": f"{operation['quantity']:.8f} {operation['symbol'].removesuffix('USDT')} · preço simulado registrado na trilha."})
    if plan.get("stop") is not None:
        steps.append({"title": "Stop definido no plano", "time": view["entry_time"],
                      "price": plan["stop"],
                      "detail": "Nível de proteção definido antes da entrada. Nenhuma ordem de stop foi enviada à Binance."})
    partials = details.get("partials")
    if isinstance(partials, list):
        for partial in partials:
            if (isinstance(partial, dict) and partial.get("time") and
                    isinstance(partial.get("price"), (int, float)) and
                    isinstance(partial.get("quantity"), (int, float))):
                steps.append({"title": "Saída parcial", "time": partial["time"],
                              "price": partial["price"],
                              "detail": f"Quantidade registrada: {partial['quantity']:.8f}."})
    if operation["state"] == "closed" and view["exit_time"] and operation.get("exit_price") is not None:
        steps.append({"title": "Saída final", "time": view["exit_time"],
                      "price": operation["exit_price"],
                      "detail": f"{view['exit_label']} · preço simulado após slippage."})
    return steps


def method_explanation(view):
    """Explain recorded operational rules and market evidence without inventing a base."""
    if not view["run"] or not view["rules"]:
        return []
    name, rules, market, plan = view["setup"], view["rules"], view["market"], view["execution"]
    pattern = rules.get("pattern") or {}
    items = []
    if name in {"BOP", "BDP"} and pattern.get("kind") == "compressed_base":
        direction = "positiva" if name == "BOP" else "negativa"
        boundary = "máxima" if name == "BOP" else "mínima"
        opposite = "mínima" if name == "BOP" else "máxima"
        items.append(("Formação", f"A regra aprovada procura uma base comprimida de {pattern.get('min_bars')} a {pattern.get('max_bars')} candles. A amplitude deve ficar até {pattern.get('max_range_atr20')} × ATR20; o volume médio da base deve ficar abaixo da média das 20 barras anteriores. O número exato de candles escolhido não foi gravado nesta trilha."))
        slope = (market.get("tendencia") or {}).get("inclinacao")
        ratio = market.get("volume_vs_media_20")
        atr = market.get("atr20")
        evidence = [f"SMA{pattern.get('trend_ma')} com inclinação {direction}"]
        if isinstance(slope, (int, float)):
            evidence.append(f"inclinação registrada {slope:+.4f}")
        if isinstance(atr, (int, float)):
            evidence.append(f"ATR20 registrado {atr:.4f}")
        if isinstance(ratio, (int, float)):
            evidence.append(f"volume atual/média20 {ratio:.3f}")
        items.append(("Contexto medido", "; ".join(evidence) + ". A razão de volume é contexto do candle avaliado, não prova isolada da média da base."))
        tick = (market.get("tick_size") or {}).get("valor")
        tick_text = f" (tick declarado {tick})" if tick is not None else ""
        items.append(("Gatilho", f"Na barra seguinte ao sinal, o plano exige rompimento de um tick além da {boundary} da base{tick_text}. Entrada planejada: {plan.get('entrada')} USDT. O nível foi calculado a partir das barras fechadas; a composição exata da base não foi persistida."))
        items.append(("Proteção e alvo", f"Stop um tick além da {opposite} da base: {plan.get('stop')} USDT. Alvo pela altura da base: {plan.get('alvo')} USDT. São níveis do plano de simulação definidos antes da abertura."))
        items.append(("Limite de fidelidade ao material", "Esta versão do detector é uma aproximação operacional: mede compressão por ATR e volume médio e só dispara além do extremo completo da base. As páginas do método descrevem rompimento da região dos dois terços, barras estreitas (NRBs), posição da base no movimento anterior e proximidade da média móvel. Esses critérios não estão todos codificados nem foram persistidos como evidência nesta operação; portanto, não é possível afirmar que o sinal reproduziu integralmente o setup ilustrado."))
    elif name in {"VBS", "VSS"} and pattern.get("kind") == "three_countertrend_bars":
        items.append(("Formação", f"A regra aprovada exige {pattern.get('bars')} candles contrários à tendência, com a SMA{pattern.get('trend_ma')} inclinada a favor da direção e o fechamento do sinal do lado favorável da média."))
        items.append(("Gatilho", f"Um tick além do extremo do candle do setup na barra seguinte. Entrada planejada: {plan.get('entrada')} USDT."))
        items.append(("Proteção e alvo", f"Stop: {plan.get('stop')} USDT, além do extremo oposto do setup. Alvo: {plan.get('alvo')} USDT, pelo meio da retração das 20 barras anteriores."))
        items.append(("Limite de fidelidade ao material", "Esta versão cobre apenas três candles corretivos e inclinação da média. As páginas do método também descrevem uma alternativa por estrutura de máximas/mínimas, sinal de reversão, suporte/resistência, proximidade da média e contexto de horário; a apostila ainda ilustra entradas de 55% e 100%. Esses elementos não estão todos codificados nem foram persistidos como evidência nesta operação. O sinal reproduz apenas a formalização aprovada, não o setup visual completo."))
    if items:
        items.append(("Decisão", "O sinal passou pela decisão e pelo Risk registrados na trilha. Aprovação de risco autoriza apenas a abertura simulada; não demonstra que a estratégia seja lucrativa ou robusta."))
    return items


def load_chart(view):
    """Plot this operation with markers on its recorded entry/exit bars."""
    run = view["run"]
    operation = view["operation"]
    timeframe = view["timeframe"]
    entry = _utc(view["entry_time"])
    if not run or not entry or timeframe not in {"1m", "2m", "5m"}:
        return None
    minutes = int(timeframe[:-1])
    exit_time = _utc(view["exit_time"])
    end = (exit_time or datetime.now(timezone.utc)) + timedelta(minutes=minutes * 8)
    start = entry - timedelta(minutes=minutes * 40)
    raw = store.get_market_bars_window(
        market_data.PROVIDER, operation["symbol"], "1m",
        start.isoformat(), end.isoformat(), limit=3000)
    if minutes == 1:
        bars, coverage = raw, None
    else:
        bars, coverage = aggregate_minutes(raw, minutes)
    if not bars:
        return None
    chart = charting.build_operation_chart(bars, run, operation, view["details"])
    return {**chart, "coverage": coverage, "truncated": len(raw) >= 3000} if chart else None
