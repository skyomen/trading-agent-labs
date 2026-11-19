"""Build a standalone visual proposal from the owner's persisted paper trade."""

import html
from datetime import datetime, timedelta, timezone
from pathlib import Path

from database import store
from services import market_data
from services.operation_details import build_view
from services.setup_backtest import aggregate_minutes


OUT = Path(__file__).resolve().parents[1] / "docs" / "design" / "operacoes-preview.html"


def utc(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def pt(value):
    return utc(value).astimezone().strftime("%d/%m %H:%M") if value else "Não registrado"


def candle_chart(bars, view):
    width, height, left, right, top, bottom = 960, 350, 57, 24, 27, 47
    plot_w, plot_h = width - left - right, height - top - bottom
    lo = min(bar["low"] for bar in bars)
    hi = max(bar["high"] for bar in bars)
    pad = (hi - lo) * .1 or 1
    lo, hi = lo - pad, hi + pad
    y = lambda price: top + (hi - price) / (hi - lo) * plot_h
    x = lambda index: left + (index + .5) / len(bars) * plot_w
    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Candles reais Binance Spot com sinal, entrada e saída paper">']
    for step in range(5):
        price = lo + (hi - lo) * step / 4
        yy = y(price)
        parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{width-right}" y2="{yy:.1f}" stroke="#e7e9e8"/><text x="{left-9}" y="{yy+4:.1f}" text-anchor="end" class="axis">{price:.0f}</text>')
    body_w = max(3, min(9, plot_w / len(bars) * .55))
    for i, bar in enumerate(bars):
        xx = x(i)
        color = "#277962" if bar["close"] >= bar["open"] else "#c26659"
        parts.append(f'<line x1="{xx:.1f}" y1="{y(bar["high"]):.1f}" x2="{xx:.1f}" y2="{y(bar["low"]):.1f}" stroke="{color}" stroke-width="1.4"/>')
        yy1, yy2 = y(bar["open"]), y(bar["close"])
        parts.append(f'<rect x="{xx-body_w/2:.1f}" y="{min(yy1,yy2):.1f}" width="{body_w:.1f}" height="{max(1,abs(yy1-yy2)):.1f}" fill="{color}" rx="1"/>')
    marks = [(view["signal_time"], "Sinal", "#66748a", 15),
             (view["entry_time"], "Entrada", "#286d91", 30),
             (view["exit_time"], "Saída", "#bc664e", 45)]
    for stamp, label, color, label_y in marks:
        if not stamp:
            continue
        bar_index = next((i for i, bar in enumerate(bars) if utc(bar["timestamp"]) == utc(stamp)), None)
        if bar_index is None:
            continue
        xx = x(bar_index)
        parts.append(f'<line x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{height-bottom}" stroke="{color}" stroke-dasharray="3 5" opacity=".75"/>')
        parts.append(f'<text x="{xx:.1f}" y="{label_y}" text-anchor="middle" class="mark" fill="{color}">{label}</text>')
    for i in range(0, len(bars), max(1, len(bars)//5)):
        parts.append(f'<text x="{x(i):.1f}" y="{height-12}" text-anchor="middle" class="axis">{utc(bars[i]["timestamp"]).strftime("%H:%M")}</text>')
    return "".join(parts) + "</svg>"


def build():
    store.initialize()
    operations = store.list_paper_operations()
    if not operations:
        raise SystemExit("Nenhuma operação paper registrada para compor a prévia.")
    operation = next((row for row in operations if row["id"] == 1), None)
    if not operation or operation["state"] != "closed" or operation["exit_reason"] != "stop":
        raise SystemExit("A operação paper #1 desta prévia não está disponível ou mudou de estado.")
    run = store.get_pipeline_run(operation["pipeline_run_id"]) if operation["pipeline_run_id"] else None
    journal = next((row for row in store.list_paper_journal() if row["operation_id"] == operation["id"]), None)
    strategy = store.get_strategy(run["strategy_id"]) if run else None
    view = build_view(operation, run, journal, strategy)
    if view["net_pnl"] is None or view["net_pnl"] >= 0:
        raise SystemExit("O resultado registrado da operação #1 não corresponde à prévia.")
    entry = utc(view["entry_time"])
    end = utc(view["exit_time"]) if view["exit_time"] else datetime.now(timezone.utc)
    interval = int(view["timeframe"][:-1])
    raw = store.get_market_bars_window(market_data.PROVIDER, operation["symbol"], "1m",
                                       (entry - timedelta(minutes=interval*40)).isoformat(),
                                       (end + timedelta(minutes=interval*8)).isoformat(), limit=3000)
    bars, coverage = aggregate_minutes(raw, interval) if interval > 1 else (raw, {})
    if not bars:
        raise SystemExit("Sem candles persistidos para a operação selecionada.")
    esc = lambda value: html.escape(str(value))
    net = view["net_pnl"]
    net_text = f"{net:+.6f} USDT" if net is not None else "Sem resultado"
    quote = operation["symbol"].removesuffix("USDT")
    chart = candle_chart(bars, view)
    template = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Prévia · Operações</title><style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root{font-family:'DM Sans',Arial,sans-serif;color:#263240;background:#f5f5f2}*{box-sizing:border-box}body{margin:0}button{font:inherit;cursor:pointer}.shell{max-width:1510px;margin:auto;padding:28px 42px 70px}.top{display:flex;justify-content:space-between;align-items:center;gap:20px;padding-bottom:24px;border-bottom:1px solid #dbdfdd}.brand{display:flex;align-items:center;gap:14px;font-family:Manrope,sans-serif;font-size:15px;font-weight:800;letter-spacing:-.03em}.brandmark{width:31px;height:31px;border-radius:8px;background:#253d40;display:grid;place-items:center;color:#e3eadf;font-size:17px}.topright{display:flex;gap:10px;align-items:center}.tag{font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;padding:7px 10px;border:1px solid #d2d9d4;border-radius:100px;color:#456359}.tag.paper{background:#e5eee8;border-color:#d4e4d9}.eyebrow{text-transform:uppercase;letter-spacing:.15em;color:#628075;font-size:10px;font-weight:800}.heading{padding:36px 0 28px;display:flex;justify-content:space-between;align-items:end;gap:20px}.heading h1{font-family:Manrope,sans-serif;font-size:35px;letter-spacing:-.055em;line-height:1.1;margin:9px 0}.heading p{color:#6d7b80;margin:0;font-size:13px}.snapshot{color:#8c9999;font-size:11px;white-space:nowrap}.stats{display:grid;grid-template-columns:repeat(3,1fr);background:#fff;border:1px solid #e1e5e1;border-radius:13px;margin-bottom:24px;overflow:hidden}.stat{padding:17px 22px;border-right:1px solid #e8ebe8}.stat:last-child{border:0}.stat small{display:block;color:#81908d;font-size:11px;font-weight:700}.stat strong{display:block;margin-top:6px;font:800 23px Manrope,sans-serif;letter-spacing:-.04em}.negative{color:#b6574b}.workspace{display:grid;grid-template-columns:290px minmax(0,1fr);gap:24px}.rail,.detail{background:#fff;border:1px solid #e1e5e1;border-radius:13px;min-width:0}.rail{align-self:start;padding:20px}.rail h2{font:800 17px Manrope,sans-serif;margin:0 0 2px}.rail>p{color:#87928e;font-size:12px;margin:0 0 20px}.rail-item{width:100%;text-align:left;border:1px solid #d6e2db;background:#f2f7f3;border-radius:10px;padding:15px}.rail-item strong{display:block;font:800 16px Manrope,sans-serif}.rail-item .sub{display:block;color:#6c7d78;font-size:11px;margin:4px 0 16px}.rail-item .footer{display:flex;justify-content:space-between;align-items:center;color:#b6574b;font-size:11px;font-weight:700}.rail-item .footer b{font-size:13px}.rail-foot{font-size:11px;color:#83918e;line-height:1.5;margin:19px 2px 2px}.detail-head{padding:27px 31px 22px;border-bottom:1px solid #e8ebe8}.detail-title{display:flex;justify-content:space-between;align-items:start;gap:16px}.detail-title h2{font:800 26px Manrope,sans-serif;letter-spacing:-.05em;margin:6px 0}.detail-title p{margin:0;color:#71807d;font-size:12px}.badge{border-radius:100px;background:#f8ebe7;color:#ae594b;padding:7px 10px;font-size:10px;font-weight:800;white-space:nowrap}.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;padding-top:25px}.fact small{display:block;color:#899591;font-size:10px;font-weight:700;margin-bottom:6px}.fact strong{font:800 15px Manrope,sans-serif;letter-spacing:-.03em}.content{padding:27px 31px 32px}.section-head{display:flex;justify-content:space-between;align-items:center;gap:15px}.section-head h3{font:800 15px Manrope,sans-serif;margin:0}.section-head span{font-size:11px;color:#7d8d8a}.chart-wrap{border:1px solid #e5e9e6;border-radius:10px;margin-top:14px;padding:14px 12px 6px;background:#fdfefd}.chart{display:block;width:100%;height:auto}.axis{font:11px 'DM Sans',sans-serif;fill:#899894}.mark{font:700 10px 'DM Sans',sans-serif}.legend{display:flex;flex-wrap:wrap;gap:16px;margin:9px 6px 4px;color:#74837f;font-size:10px}.legend b{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px}.columns{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:29px}.note{border-top:1px solid #e7ebe7;padding-top:18px}.note h3{font:800 15px Manrope,sans-serif;margin:0 0 14px}.note p{font-size:12px;line-height:1.65;color:#61716d;margin:0 0 12px}.timeline{display:grid;grid-template-columns:60px 1fr;gap:6px 12px;font-size:11px;line-height:1.5}.timeline time{color:#8a9995}.timeline span{color:#4b5f5a}.source{margin-top:24px;padding:14px 16px;background:#f4f7f4;border-radius:8px;color:#687b74;font-size:11px;line-height:1.5}.source strong{color:#395e54}.preview-strip{margin-top:22px;text-align:center;color:#8a9793;font-size:11px}.rail-item:focus-visible{outline:2px solid #277962;outline-offset:3px}@media(max-width:900px){.shell{padding:19px}.workspace{grid-template-columns:1fr}.rail{padding:16px}.rail-foot{display:none}.rail-item{max-width:360px}.stats{margin-bottom:16px}}@media(max-width:580px){.topright .tag:first-child{display:none}.heading{display:block;padding:28px 0 21px}.heading h1{font-size:29px}.snapshot{display:block;margin-top:12px}.stat{padding:13px 11px}.stat strong{font-size:17px}.stat small{font-size:9px}.detail-head,.content{padding:20px 16px}.detail-title h2{font-size:22px}.facts{grid-template-columns:repeat(2,1fr);gap:17px}.columns{grid-template-columns:1fr}.section-head{display:block}.section-head span{display:block;margin-top:4px}}
</style></head><body><div class="shell"><header class="top"><div class="brand"><span class="brandmark">↗</span> Trading Agent Lab <span style="color:#bcc8c2;font-weight:400">/</span> Operações</div><div class="topright"><span class="tag">Prévia visual</span><span class="tag paper">Somente simulação</span></div></header><div class="heading"><div><span class="eyebrow">Acompanhamento paper local</span><h1>Operações</h1><p>Entradas, saídas e o motivo de cada decisão, em uma única página.</p></div><span class="snapshot">Retrato dos registros locais · 18/11/2026</span></div><div class="stats"><div class="stat"><small>Em andamento</small><strong>__OPEN__</strong></div><div class="stat"><small>Encerradas</small><strong>__CLOSED__</strong></div><div class="stat"><small>Resultado realizado · paper</small><strong class="negative">__TOTAL__</strong></div></div><main class="workspace"><aside class="rail"><h2>Histórico</h2><p>Selecione uma operação para investigar.</p><button class="rail-item" onclick="document.getElementById('detalhe').scrollIntoView({behavior:'smooth'})"><strong>#__ID__ · __SYMBOL__</strong><span class="sub">__SETUP__ · __TIMEFRAME__ · Encerrada</span><span class="footer"><span>Stop atingido</span><b>__NET__</b></span></button><p class="rail-foot">Valores exibidos vêm do diário paper. Sem saldo de conta ou ordens reais.</p></aside><article id="detalhe" class="detail"><div class="detail-head"><div class="detail-title"><div><span class="eyebrow">Operação #__ID__ · Trilha #__RUN__</span><h2>__SYMBOL__ <span style="color:#a4b3ab;font-weight:400">/</span> __SETUP__</h2><p>Compra simulada · candle de __TIMEFRAME__ · Binance Spot</p></div><span class="badge">Resultado negativo</span></div><div class="facts"><div class="fact"><small>Entrada paper</small><strong>__ENTRY__ USDT</strong></div><div class="fact"><small>Saída paper</small><strong>__EXIT__ USDT</strong></div><div class="fact"><small>Quantidade</small><strong>__QTY__ __BASE__</strong></div><div class="fact"><small>Resultado líquido</small><strong class="negative">__NET__</strong></div></div></div><div class="content"><div class="section-head"><h3>O movimento no gráfico</h3><span>__CANDLES__ candles fechados · horário UTC · __TIMEFRAME__</span></div><div class="chart-wrap">__CHART__<div class="legend"><span><b style="background:#66748a"></b>Sinal</span><span><b style="background:#286d91"></b>Entrada paper</span><span><b style="background:#bc664e"></b>Saída paper</span></div></div><div class="columns"><section class="note"><h3>Por que entrou</h3><div class="timeline"><time>__SIGNAL_TIME__</time><span>O setup __SETUP__ gerou sinal após a barra fechada.</span><time>__ENTRY_TIME__</time><span>Entrada paper registrada após autorização de risco.</span></div><p style="margin-top:15px">Plano registrado: stop em __STOP__ USDT · alvo em __TARGET__ USDT.</p></section><section class="note"><h3>Como saiu</h3><div class="timeline"><time>__EXIT_TIME__</time><span>Stop atingido. Saída paper registrada em __EXIT__ USDT.</span></div><p style="margin-top:15px">Taxas simuladas: __FEES__ USDT. O preço paper de saída incorpora slippage adverso.</p></section></div><div class="source"><strong>Fonte e limite</strong> · Candles fechados persistidos da Binance Spot; sinais e execução paper do SQLite local. A marca de saída indica o candle do gatilho; o preço de saída paper é mostrado acima. __COVERAGE__ Este registro não representa operação na conta Binance.</div></div></article></main><div class="preview-strip">Proposta visual isolada · a aplicação atual permanece com seu design anterior até aprovação.</div></div></body></html>"""
    closed = [row for row in operations if row["state"] == "closed"]
    journal_by_id = {row["operation_id"]: row for row in store.list_paper_journal(limit=10000)}
    import json
    pnl_values = []
    for row in closed:
        j = journal_by_id.get(row["id"])
        if j and j["state"] == "closed":
            value = json.loads(j["details_json"] or "{}").get("net_pnl")
            if isinstance(value, (int, float)):
                pnl_values.append(value)
    total = f"{sum(pnl_values):+.6f} USDT" if pnl_values else "Sem resultado"
    values = {"OPEN": sum(row["state"] == "open" for row in operations), "CLOSED": len(closed),
              "TOTAL": total, "ID": operation["id"], "SYMBOL": operation["symbol"],
              "SETUP": view["setup"], "TIMEFRAME": view["timeframe"], "NET": net_text,
              "RUN": run["id"], "ENTRY": f"{operation['entry_price']:.4f}",
              "EXIT": f"{operation['exit_price']:.4f}" if operation["exit_price"] else "—",
              "QTY": f"{operation['quantity']:.8f}", "BASE": quote, "CANDLES": len(bars),
              "CHART": chart, "SIGNAL_TIME": pt(view["signal_time"]),
              "ENTRY_TIME": pt(view["entry_time"]), "EXIT_TIME": pt(view["exit_time"]),
              "STOP": f"{view['execution']['stop']:.4f}",
              "TARGET": f"{view['execution']['alvo']:.4f}",
              "FEES": f"{operation['fees']:.6f}",
              "COVERAGE": f"Agregação: {coverage.get('discarded_blocks', 0)} blocos incompletos; {coverage.get('gaps_between_complete_blocks', 0)} lacunas."}
    template = template.replace('Por que entrou</h3>', 'Por que entrou <small style="font:500 10px DM Sans;color:#8a9995">· horário de Brasília</small></h3>')
    for key, value in values.items():
        template = template.replace(f"__{key}__", str(value) if key == "CHART" else esc(value))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(template, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    build()
