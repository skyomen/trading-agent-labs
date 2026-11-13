"""Causal signal detection for the approved setup rule family.

This module emits proposed entry orders; it never fills trades or contacts a broker.
"""

import math


def _mean(values):
    return sum(values) / len(values)


def _sma(bars, end, length):
    return _mean([bar["close"] for bar in bars[end - length + 1:end + 1]])


def signal_at(bars, index, rules, tick_size):
    """Evaluate completed bars through index and return a next-bar stop order."""
    if rules.get("engine") != "setup_pattern_v1" or rules.get("setup_name") not in {"VBS", "VSS", "BOP", "BDP"}:
        raise ValueError("Regra de setup não reconhecida.")
    if not math.isfinite(tick_size) or tick_size <= 0:
        raise ValueError("Informe incremento mínimo positivo e finito.")
    if index < 28 or index >= len(bars) - 1:
        return None
    name = rules["setup_name"]
    side = rules["side"]
    direction = 1 if side == "buy" else -1
    pattern = rules["pattern"]
    ma = pattern["trend_ma"]
    slope = _sma(bars, index, ma) - _sma(bars, index - pattern["trend_slope_bars"], ma)
    if direction * slope <= 0:
        return None
    if name in {"VBS", "VSS"}:
        recent = bars[index - 2:index + 1]
        if not all((b["close"] < b["open"]) if side == "buy" else (b["close"] > b["open"]) for b in recent):
            return None
        if direction * (bars[index]["close"] - _sma(bars, index, ma)) <= 0:
            return None
        entry = (bars[index]["high"] + tick_size if side == "buy"
                 else bars[index]["low"] - tick_size)
        stop = (bars[index]["low"] - tick_size if side == "buy"
                else bars[index]["high"] + tick_size)
        prior = bars[index - pattern["trend_ma"]:index]
        swing = max(b["high"] for b in prior) if side == "buy" else min(b["low"] for b in prior)
        extreme = bars[index]["low"] if side == "buy" else bars[index]["high"]
        target = extreme + 0.5 * (swing - extreme)
    else:
        selected = None
        for length in range(pattern["max_bars"], pattern["min_bars"] - 1, -1):
            base = bars[index - length + 1:index + 1]
            prior = bars[index - length - 19:index - length + 1]
            if len(prior) != 20:
                continue
            true_ranges = []
            for offset, bar in enumerate(prior):
                previous_close = bars[index - length - 20 + offset]["close"]
                true_ranges.append(max(bar["high"] - bar["low"],
                                       abs(bar["high"] - previous_close),
                                       abs(bar["low"] - previous_close)))
            height = max(b["high"] for b in base) - min(b["low"] for b in base)
            if height <= pattern["max_range_atr20"] * _mean(true_ranges) and \
               _mean([b["volume"] for b in base]) < _mean([b["volume"] for b in prior]):
                selected = base
                break
        if selected is None:
            return None
        high = max(b["high"] for b in selected)
        low = min(b["low"] for b in selected)
        height = high - low
        entry = high + tick_size if side == "buy" else low - tick_size
        stop = low - tick_size if side == "buy" else high + tick_size
        target = entry + direction * height
    if direction * (target - entry) <= 0 or direction * (entry - stop) <= 0:
        return None
    return {"setup_id": rules["setup_id"], "side": side,
            "signal_bar": bars[index]["timestamp"], "valid_on_next_bar": True,
            "entry": entry, "stop": stop, "target": target,
            "intrabar_conflict": "stop_first"}
