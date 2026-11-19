"""Market chart must expose only persisted candles and paper records."""

import json
import unittest

from services.charting import build_candle_chart, build_operation_chart


BARS = [
    {"timestamp": "2026-11-18T16:00:00Z", "open": 100.0, "high": 102.0,
     "low": 99.0, "close": 101.0, "volume": 5.0},
    {"timestamp": "2026-11-18T16:01:00+00:00", "open": 101.0, "high": 103.0,
     "low": 100.0, "close": 100.5, "volume": 4.0},
]


class CandleChartTests(unittest.TestCase):
    def test_no_bars_has_no_chart_or_synthetic_marks(self):
        self.assertIsNone(build_candle_chart([]))

    def test_closed_bars_keep_ohlcv_and_utc_order(self):
        chart = build_candle_chart(BARS)
        candles = chart["spec"]["layer"][0]["data"]["values"]
        self.assertEqual(chart["candles"], 2)
        self.assertEqual(chart["markers"], [])
        self.assertEqual([bar["timestamp"] for bar in candles],
                         ["2026-11-18T16:00:00Z", "2026-11-18T16:01:00Z"])
        self.assertEqual(candles[0]["high"], 102.0)
        self.assertEqual(candles[1]["volume"], 4.0)

    def test_candidate_plan_is_distinct_from_confirmed_paper_entry_and_exit(self):
        run = {"id": 7, "decision": "trade_candidate", "setup_name": "BOP",
               "status": "posicao_fechada", "signal_bar_utc": "2026-11-18T16:00:00+00:00",
               "report_json": json.dumps({"execution": {"entrada": 100.25}})}
        operation = {"id": 3, "created_at": "2026-11-18 16:00:30", "entry_price": 100.5,
                     "quantity": 0.2, "state": "closed", "closed_at": "2026-11-18T16:01:00Z",
                     "exit_price": 101.5, "exit_reason": "target"}
        chart = build_candle_chart(BARS, [run], [operation])
        self.assertEqual([item["tipo"] for item in chart["markers"]],
                         ["Plano de sinal", "Abertura paper", "Saída paper"])
        self.assertEqual([item["price"] for item in chart["markers"]],
                         [100.25, 100.5, 101.5])

    def test_no_trade_is_never_drawn_as_a_signal(self):
        no_trade = {"id": 8, "decision": "no_trade", "signal_bar_utc": BARS[0]["timestamp"],
                    "report_json": json.dumps({"execution": {"entrada": 100.25}})}
        outside = {"id": 9, "decision": "trade_candidate", "setup_name": "BOP",
                   "signal_bar_utc": "2026-11-18T15:00:00Z",
                   "report_json": json.dumps({"execution": {"entrada": 100.25}})}
        chart = build_candle_chart(BARS, [no_trade, outside])
        self.assertEqual(chart["markers"], [])

    def test_operation_chart_uses_actual_bar_times_and_separates_slippage(self):
        run = {"id": 7, "signal_bar_utc": BARS[0]["timestamp"],
               "report_json": json.dumps({"execution": {"entrada": 100.5, "stop": 99.5,
                                                           "alvo": 102.5}})}
        operation = {"id": 3, "side": "buy", "state": "closed", "entry_price": 100.5,
                     "exit_price": 101.5 * (1 - 5 / 10000), "exit_reason": "target"}
        journal = {"entry_time": BARS[1]["timestamp"], "exit_time": BARS[1]["timestamp"],
                   "slippage_bps_per_side": 5.0}
        chart = build_operation_chart(BARS, run, operation, journal)
        self.assertEqual(chart["ohlcv"][0]["timestamp"], "2026-11-18T16:00:00Z")
        self.assertEqual(chart["spec"]["layer"][0]["encoding"]["x"]["scale"]["type"], "utc")
        self.assertEqual([marker["tipo"] for marker in chart["markers"]],
                         ["Entrada simulada", "Saída simulada"])
        self.assertEqual(chart["markers"][0]["price"], 100.5)
        self.assertEqual(chart["markers"][0]["shape"], "triangle-right")
        self.assertEqual(chart["markers"][0]["cor"], "#40c994")
        self.assertEqual(chart["markers"][1]["cor"], "#f06ab8")
        self.assertAlmostEqual(chart["markers"][1]["price"], operation["exit_price"])
        self.assertEqual(chart["stop_line"]["price"], 99.5)
        self.assertEqual(chart["stop_line"]["label"], "STOP")
        self.assertEqual(chart["target_line"]["price"], 102.5)
        self.assertEqual(chart["target_line"]["label"], "ALVO")
        self.assertEqual(chart["exit_guide"]["timestamp"], "2026-11-18T16:01:00Z")
        self.assertEqual(chart["exit_guide"]["price"], operation["exit_price"])
        self.assertEqual(chart["verification_rows"][1]["Candle UTC"], "2026-11-18T16:01:00Z")
        self.assertEqual(chart["verification_rows"][1]["Máxima"], 103.0)
        self.assertEqual(chart["spec"]["layer"][-1]["mark"]["size"], 66)


if __name__ == "__main__":
    unittest.main()
