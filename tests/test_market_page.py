import unittest

from market_page import _widget_html


class MarketPageTests(unittest.TestCase):
    def test_advanced_chart_exposes_research_tools_and_keeps_widget_source_external(self):
        page = _widget_html("Escuro")
        self.assertIn("https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js", page)
        self.assertIn('"allow_symbol_change": true', page)
        self.assertIn('"symbol": "BINANCE:BTCUSDT"', page)
        self.assertIn('"interval": "5"', page)
        self.assertIn('"hide_side_toolbar": false', page)
        self.assertIn('"hide_top_toolbar": false', page)
        self.assertIn('"theme": "dark"', page)

    def test_widget_theme_follows_local_appearance(self):
        self.assertIn('"theme": "light"', _widget_html("Claro"))
        self.assertIn('"backgroundColor": "#f4f7fc"', _widget_html("Claro"))


if __name__ == "__main__":
    unittest.main()
