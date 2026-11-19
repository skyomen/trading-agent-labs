import unittest

from services.lightweight_chart import operation_chart_html


class LightweightChartTests(unittest.TestCase):
    def test_html_uses_exact_local_candles_and_trade_levels(self):
        chart = {
            "ohlcv": [{"timestamp": "2026-11-19T12:00:00Z", "open": 100,
                       "high": 102, "low": 99, "close": 101, "volume": 4}],
            "markers": [{"timestamp": "2026-11-19T12:00:00Z", "price": 100.5,
                         "tipo": "Entrada simulada", "cor": "#40c994"}],
            "stop_line": {"start": "2026-11-19T12:00:00Z", "end": "2026-11-19T12:00:00Z",
                          "price": 99, "label": "STOP"},
            "target_line": {"start": "2026-11-19T12:00:00Z", "end": "2026-11-19T12:00:00Z",
                            "price": 102, "label": "ALVO"},
            "exit_guide": None,
        }
        page = operation_chart_html(chart)
        self.assertIn("lightweight-charts@5.2.0", page)
        self.assertIn("2026-11-19T12:00:00Z", page)
        self.assertIn('"price":100.5', page)
        self.assertIn('"price":99', page)
        self.assertIn('"price":102', page)
        self.assertIn("series.priceToCoordinate(event.price)", page)
        self.assertIn("M ${x-7} ${y-7} L ${x+8} ${y}", page)


if __name__ == "__main__":
    unittest.main()
