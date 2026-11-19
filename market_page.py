"""Independent TradingView workspace for chart research and study."""

import json

import streamlit as st
import streamlit.components.v1 as components


def _widget_html(theme):
    options = {
        "allow_symbol_change": True,
        "autosize": True,
        "backgroundColor": "#0b1426" if theme == "Escuro" else "#f4f7fc",
        "calendar": False,
        "details": False,
        "hide_side_toolbar": False,
        "hide_top_toolbar": False,
        "hide_legend": False,
        "hide_volume": False,
        "hotlist": False,
        "interval": "5",
        "locale": "br",
        "gridColor": "rgba(150,180,215,0.12)" if theme == "Escuro" else "rgba(80,100,130,0.12)",
        "save_image": True,
        "show_popup_button": True,
        "style": "1",
        "studies": [],
        "symbol": "BINANCE:BTCUSDT",
        "theme": "dark" if theme == "Escuro" else "light",
        "timezone": "Etc/UTC",
        "withdateranges": True,
    }
    config = json.dumps(options, ensure_ascii=True).replace("</", "<\\/")
    return f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>html,body,#tv{{height:100%;width:100%;margin:0;overflow:hidden;background:transparent}}.tradingview-widget-container,.tradingview-widget-container__widget{{height:100%;width:100%}}</style>
</head><body><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div>
<script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
{config}
</script></div></body></html>"""


def render():
    theme = st.session_state.get("tal-theme", "Escuro")
    st.markdown(
        '<section class="market-hero" aria-label="Mercado">'
        '<h1>Mercado</h1><span class="market-hero-art" aria-hidden="true"><i></i><b></b></span>'
        '</section>',
        unsafe_allow_html=True,
    )
    components.html(_widget_html(theme), height=690, scrolling=False)
