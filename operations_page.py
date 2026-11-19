"""Single Operations surface for the local simulated trading workspace."""

import html
import json
from datetime import datetime, timezone

import streamlit as st
import streamlit.components.v1 as components

from database import store
from services import observability
from services.operation_details import build_view, load_chart, build_steps, method_explanation
from services.lightweight_chart import operation_chart_html


OPERATIONS_CSS = """
<style>
.ops-status{padding:.7rem 0;color:var(--tal-mute);display:flex;gap:.5rem 1.4rem;flex-wrap:wrap;margin:.2rem 0 1.3rem;font-size:.78rem;border-bottom:1px solid var(--tal-line)}
.ops-status strong{color:var(--tal-ink)}.ops-overview{display:flex;justify-content:space-between;align-items:end;gap:1rem;background:var(--tal-panel);border-radius:18px;padding:1.55rem 1.8rem;margin:1rem 0 1.2rem}
.ops-overview .total small{display:block;color:var(--tal-mute);font-size:.8rem}.ops-overview .total strong{display:block;margin-top:.3rem;font-size:2.1rem;font-weight:800;font-variant-numeric:tabular-nums;letter-spacing:-.03em}.ops-overview .counts{color:var(--tal-mute);font-size:.82rem;text-align:right}.ops-overview .counts strong{color:var(--tal-ink);font-size:1rem}
.ops-facts small{display:block;color:var(--tal-mute);font-size:.75rem}
.ops-positive{color:var(--tal-up)!important}.ops-negative{color:var(--tal-down)!important}
.ops-section-title{font-size:1.18rem;font-weight:800;margin:1.5rem 0 .8rem}.ops-day{color:var(--tal-mute);font-size:.78rem;font-weight:700;margin:1.3rem 0 .3rem}
.ops-transaction{display:flex;align-items:center;gap:1rem;text-decoration:none!important;color:var(--tal-ink)!important;padding:1rem .35rem;border-bottom:1px solid var(--tal-line);border-radius:8px;transition:background .16s ease}
.ops-transaction:hover,.ops-transaction:focus-visible{background:var(--tal-panel2);outline:none}.ops-avatar{width:2.6rem;height:2.6rem;flex:none;border-radius:50%;display:grid;place-items:center;background:var(--tal-panel2);color:var(--tal-blue);font-size:.75rem;font-weight:800}
.ops-transaction-main{flex:1;min-width:0}.ops-transaction-main strong{display:block;font-size:.95rem}.ops-transaction-main small{display:block;color:var(--tal-mute);margin-top:.2rem;font-size:.76rem}.ops-transaction-result{text-align:right;font-variant-numeric:tabular-nums}.ops-transaction-result strong{display:block;font-size:.93rem}.ops-transaction-result small{display:block;color:var(--tal-mute);margin-top:.2rem;font-size:.76rem}
.ops-back{display:inline-block;color:var(--tal-blue)!important;text-decoration:none!important;font-weight:700;font-size:.85rem;margin:.2rem 0 1.5rem}.ops-back:hover{text-decoration:underline!important}.ops-back:focus-visible{outline:2px solid var(--tal-blue);outline-offset:4px}
.ops-facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem;margin:1.2rem 0 1.7rem}.ops-facts>div{border-top:1px solid var(--tal-line);padding:.75rem 0}
.ops-facts strong{font-variant-numeric:tabular-nums;overflow-wrap:anywhere;font-size:.92rem}.ops-detail h2{margin:.2rem 0 .35rem;font-size:1.55rem}.ops-detail>p{color:var(--tal-mute);font-size:.8rem}
.ops-result-hero{margin:1.2rem 0 1.4rem}.ops-result-hero small{display:block;color:var(--tal-mute);font-size:.8rem}.ops-result-hero strong{display:block;font-size:2.25rem;line-height:1.2;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.ops-step-panel{background:var(--tal-panel);border-radius:16px;padding:1.5rem;margin:.75rem 0}.ops-step-panel .num{font-size:.75rem;font-weight:800;color:var(--tal-blue)}.ops-step-panel h3{font-size:1.4rem;margin:.4rem 0}.ops-step-panel .price{font-size:1.8rem;font-weight:800;font-variant-numeric:tabular-nums;margin:.5rem 0}.ops-step-panel p{font-size:.95rem;line-height:1.6;max-width:65ch}.ops-step-panel .time{font-size:.78rem;color:var(--tal-mute)}
.ops-method{border-top:1px solid var(--tal-line);padding:.8rem 0}.ops-method strong{display:block;margin-bottom:.3rem}.ops-method p{margin:0;color:var(--tal-mute);line-height:1.55;font-size:.84rem}.ops-fact-line{padding:.45rem 0;border-bottom:1px solid var(--tal-line);font-size:.84rem}
div[data-testid="stVegaLiteChart"]{box-sizing:border-box;width:100%;max-width:100%;min-width:0;overflow:hidden;background:var(--tal-panel2);border:1px solid var(--tal-line);border-radius:10px;padding:clamp(.45rem,2vw,1rem)}
div[data-testid="stVegaLiteChart"]>div{box-sizing:border-box;width:100%!important;max-width:100%!important;min-width:0!important;overflow:hidden}
div[data-testid="stVegaLiteChart"] canvas,div[data-testid="stVegaLiteChart"] svg{display:block;width:100%!important;height:auto!important;max-width:100%!important}
div[data-testid="stVerticalBlockBorderWrapper"]>div{border-color:var(--tal-line);background:var(--tal-panel);border-radius:12px}
div[data-testid="stSegmentedControl"] button{border-radius:999px!important;min-height:38px!important}
@media(max-width:650px){.ops-overview{padding:1.2rem;display:block}.ops-overview .total strong{font-size:1.7rem}.ops-overview .counts{text-align:left;margin-top:.7rem}.ops-facts{grid-template-columns:repeat(2,minmax(0,1fr))}.ops-detail h2{font-size:1.3rem}.ops-transaction{gap:.7rem}.ops-transaction-result strong{font-size:.82rem}}
</style>
"""


def _esc(value):
    return html.escape("—" if value is None else str(value))


def _money(value, currency="USDT"):
    return "Sem resultado" if value is None else f"{value:+.6f} {currency}"


def _price(value):
    return "—" if value is None else f"{value:,.4f}"


def _when(value):
    if not value:
        return "Não registrado"
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone().strftime("%d/%m/%Y %H:%M")


def _items():
    journals = {row["operation_id"]: row for row in store.list_paper_journal(limit=10000)}
    items = []
    for operation in store.list_paper_operations():
        run = store.get_pipeline_run(operation["pipeline_run_id"]) if operation["pipeline_run_id"] else None
        strategy = store.get_strategy(run["strategy_id"]) if run else None
        items.append(build_view(operation, run, journals.get(operation["id"]), strategy))
    return items


def _status():
    now = datetime.now(timezone.utc)
    beat = next((item for item in store.list_heartbeats() if item["component"] == "paper-auto"), None)
    active = False
    if beat and beat["state"] == "running":
        stamp = datetime.fromisoformat(beat["last_seen_at"]).replace(tzinfo=timezone.utc)
        active = (now - stamp).total_seconds() < 35
    feeds = [row for row in store.list_market_feeds() if row["symbol"] in {"BTCUSDT", "ETHUSDT"}]
    feed_count = sum(observability.feed_freshness(row, now)["current"] for row in feeds)
    blocked = store.get_kill_switch()["enabled"]
    label = ("Entradas pausadas" if blocked else "Acompanhamento ativo" if active and feed_count == 2
             else "Automação ativa; feed parcial" if active else "Automação parada")
    st.markdown(f'<div class="ops-status"><strong>{_esc(label)}</strong><span>Feeds atuais: '
                f'<strong>{feed_count}/2</strong></span><span>Entrada simulada: <strong>2 USDT</strong></span>'
                '<span>Tela atualiza a cada 10 s</span></div>', unsafe_allow_html=True)


def _overview(items):
    open_count = sum(item["operation"]["state"] == "open" for item in items)
    closed = [item for item in items if item["operation"]["state"] == "closed"]
    pnl = [item["net_pnl"] for item in closed if item["net_pnl"] is not None]
    total = _money(sum(pnl)) if pnl else "Sem resultado"
    tone = "ops-positive" if sum(pnl) > 0 else "ops-negative" if sum(pnl) < 0 else ""
    st.markdown('<div class="ops-overview">'
                f'<div class="total"><small>Resultado realizado · simulação</small><strong class="{tone}">{_esc(total)}</strong></div>'
                f'<div class="counts"><strong>{open_count}</strong> em andamento &nbsp;·&nbsp; '
                f'<strong>{len(closed)}</strong> encerradas</div>'
                '</div>', unsafe_allow_html=True)
    if len(pnl) != len(closed):
        st.caption(f"{len(closed)-len(pnl)} operação(ões) encerrada(s) sem P&L íntegro no diário; "
                   "não entram no total.")


def _list(items):
    st.markdown('<div class="ops-section-title">Atividade</div>', unsafe_allow_html=True)
    if not items:
        st.info("Nenhuma operação registrada. As entradas simuladas aparecerão aqui quando ocorrerem.")
        return
    filter_column, search_column = st.columns([2, 1], vertical_alignment="bottom")
    with filter_column:
        selected_filter = st.segmented_control("Estado", ["Todas", "Em andamento", "Encerradas"],
                                               default="Todas", key="operation-filter")
    with search_column:
        search = st.text_input("Buscar", placeholder="Ativo ou setup", key="operation-search").strip().casefold()
    visible = [item for item in items if selected_filter == "Todas" or
               (selected_filter == "Em andamento" and item["operation"]["state"] == "open") or
               (selected_filter == "Encerradas" and item["operation"]["state"] == "closed")]
    if search:
        visible = [item for item in visible if search in item["operation"]["symbol"].casefold() or
                   search in (item["setup"] or "").casefold() or
                   search in str(item["operation"]["id"])]
    if not visible:
        st.info("Nenhuma operação corresponde aos filtros. Altere o estado ou a busca para ver o histórico disponível.")
        return
    current_day = None
    for item in visible:
        operation = item["operation"]
        closed = operation["state"] == "closed"
        result = _money(item["net_pnl"], item["currency"] or "USDT") if closed else "Aguardando saída"
        tone = "ops-positive" if item["outcome"] == "positivo" else "ops-negative" if item["outcome"] == "negativo" else ""
        when = _when(item["entry_time"] or operation["created_at"])
        day = when.split(" ")[0]
        if day != current_day:
            st.markdown(f'<div class="ops-day">{_esc(day)}</div>', unsafe_allow_html=True)
            current_day = day
        symbol = operation["symbol"]
        code = symbol.removesuffix("USDT")[:3]
        st.markdown(f'<a class="ops-transaction" href="?operacao={operation["id"]}" target="_self" '
                    f'aria-label="Ver detalhes da operação #{operation["id"]}">'
                    f'<span class="ops-avatar">{_esc(code)}</span>'
                    f'<span class="ops-transaction-main"><strong>{_esc(symbol)}</strong>'
                    f'<small>{_esc(item["setup"] or "Setup não registrado")} · '
                    f'{_esc(item["timeframe"] or "intervalo não registrado")} · '
                    f'{_esc(when.split(" ")[-1])}</small></span>'
                    f'<span class="ops-transaction-result"><strong class="{tone}">{_esc(result)}</strong>'
                    f'<small>{_esc(item["exit_label"] if closed else "Em andamento")}</small></span>'
                    '</a>', unsafe_allow_html=True)


def _watchlist_radar():
    from services.market_data import OBSERVATION_ONLY_SYMBOLS, PROVIDER

    with st.expander("Radar de setups · observação", expanded=False):
        st.caption("SOL, BNB, XRP e ADA · Binance Spot · candles fechados. "
                   "Sem backtest validado nesses pares, sem reserva de risco e sem abertura paper.")
        feeds = {item["symbol"]: item for item in store.list_market_feeds()
                 if item["provider"] == PROVIDER and item["timeframe"] == "1m"}
        feed_states = []
        for symbol in OBSERVATION_ONLY_SYMBOLS:
            feed = feeds.get(symbol)
            fresh = observability.feed_freshness(feed)["current"] if feed else False
            state = "atual" if fresh else "desatualizado" if feed else "sem feed"
            feed_states.append(f"{symbol.removesuffix('USDT')} {state}")
        st.caption("Feeds: " + " · ".join(feed_states))
        observations = store.list_setup_observations(limit=30, symbols=OBSERVATION_ONLY_SYMBOLS)
        if not observations:
            st.info("Ainda não há setup ou gatilho observado neste radar. "
                    "A análise começa quando o coletor estiver atualizado.")
            return
        rows = []
        for item in observations:
            report = json.loads(item["report_json"])
            signal = report.get("signal") or {}
            rows.append({
                "Ativo": item["symbol"],
                "Setup": item["setup_name"],
                "Lado": "Compra" if signal.get("side") == "buy" else "Venda",
                "Gráfico": item["timeframe"],
                "Estado": "Gatilho observado" if item["state"] == "gatilho_observado" else "Aguardando gatilho",
                "Candle UTC": item["signal_bar_utc"],
                "Entrada ref.": report.get("entry_reference"),
                "Stop ref.": signal.get("stop"),
                "Alvo ref.": signal.get("target"),
                "Incremento": report.get("tick_size"),
            })
        st.dataframe(rows, hide_index=True, width="stretch")
        chosen_id = st.selectbox(
            "Abrir contexto do sinal",
            [item["id"] for item in observations],
            format_func=lambda item_id: next(
                f"{item['symbol']} · {item['setup_name']} · {item['timeframe']} · {item['signal_bar_utc']}"
                for item in observations if item["id"] == item_id),
            key="setup-radar-selection",
        )
        chosen = next(item for item in observations if item["id"] == chosen_id)
        report = json.loads(chosen["report_json"])
        signal = report["signal"]
        rules = report.get("rules") or {}
        if not rules and chosen.get("strategy_id"):
            strategy = store.get_strategy(chosen["strategy_id"])
            if strategy:
                persisted_rules = json.loads(strategy["rules_json"])
                rules = {key: persisted_rules.get(key) for key in
                         ("pattern", "entry", "stop", "target", "filters", "source")}
        pattern = rules.get("pattern") or {}
        if pattern.get("kind") == "compressed_base":
            reason = (f"Base comprimida de {pattern.get('min_bars')} a {pattern.get('max_bars')} candles; "
                      f"amplitude máxima de {pattern.get('max_range_atr20')} ATR20 e volume abaixo da média anterior. "
                      f"Tendência medida pela SMA{pattern.get('trend_ma')}.")
        else:
            reason = (f"Setup de retração com {pattern.get('bars')} candles contra a tendência; "
                      f"tendência medida pela SMA{pattern.get('trend_ma')}.")
        state = "o preço acionador foi tocado no candle seguinte" if report.get("triggered") else \
                "o candle seguinte ainda não tocou o preço acionador"
        st.markdown(f"**Por que apareceu:** {reason}")
        st.write(f"Candle do sinal: `{chosen['signal_bar_utc']}` · candle verificador: "
                 f"`{report.get('trigger_bar_utc')}`; {state}.")
        st.write(f"Referências do setup: entrada {_price(report.get('entry_reference'))} · "
                 f"stop {_price(signal.get('stop'))} · alvo {_price(signal.get('target'))} · "
                 f"tickSize {_price(report.get('tick_size'))}.")
        sources = rules.get("source") or []
        if sources:
            st.caption("Método: " + "; ".join(
                f"{item.get('path')} · páginas {item.get('pages')} · hash {item.get('sha256')}"
                for item in sources))
        st.warning("Esta observação não foi validada por backtest neste ativo. Não é ordem nem entrada paper; "
                   "Risk não foi executado e o limite diário não foi consumido.")


def _detail(view):
    st.markdown('<a class="ops-back" href="?" target="_self">← Todas as operações</a>', unsafe_allow_html=True)
    operation = view["operation"]
    closed = operation["state"] == "closed"
    st.markdown('<div class="ops-detail">'
                f'<h2>{_esc(operation["symbol"])} · {_esc(view["setup"] or "Setup não registrado")}</h2>'
                f'<p>Operação #{operation["id"]} · '
                f'{_esc(view["timeframe"] or "intervalo não registrado")} · '
                f'{"Encerrada" if closed else "Em andamento"} · simulação local</p></div>',
                unsafe_allow_html=True)
    tone = "ops-positive" if view["outcome"] == "positivo" else "ops-negative" if view["outcome"] == "negativo" else ""
    st.markdown('<div class="ops-result-hero"><small>Resultado líquido realizado</small>'
                f'<strong class="{tone}">{_esc(_money(view["net_pnl"], view["currency"] or "USDT"))}</strong></div>',
                unsafe_allow_html=True)
    metrics = [("Entrada simulada", _price(operation["entry_price"])),
               ("Saída simulada", _price(operation["exit_price"]) if closed else "Ainda aberta"),
               ("Quantidade", f"{operation['quantity']:.8f} {operation['symbol'].removesuffix('USDT')}"),
               ("Estado", "Encerrada" if closed else "Em andamento")]
    st.markdown('<div class="ops-facts">' + ''.join(
        f'<div><small>{_esc(label)}</small><strong>{_esc(value)}</strong></div>'
        for label, value in metrics) + '</div>', unsafe_allow_html=True)
    if closed:
        rr = view["details"].get("realized_r")
        st.caption(f"Resultado {view['outcome'] or 'indisponível'} · "
                   f"{rr:+.2f}R" if isinstance(rr, (int, float)) else
                   f"Resultado {view['outcome'] or 'indisponível'} · R indisponível")

    st.subheader("No gráfico")
    chart = load_chart(view)
    if chart:
        st.caption(f"Binance Spot {operation['symbol']} · TradingView: BINANCE:{operation['symbol']} · "
                   f"{view['timeframe']} · {chart['candles']} candles fechados · início do candle em UTC. "
                   "▶ verde = compra simulada · ▶ fúcsia = venda simulada. "
                   "Linha âmbar tracejada = STOP planejado · linha azul pontilhada = ALVO planejado. "
                   "Triângulo e guia vertical marcam a SAÍDA simulada no candle/preço registrado. "
                   "Esses níveis são da simulação; nenhuma ordem foi enviada à Binance.")
        light = st.session_state.get("tal-theme") == "Claro"
        components.html(operation_chart_html(chart, "Claro" if light else "Escuro"),
                        height=430, scrolling=False)
        if chart["verification_rows"]:
            with st.expander("Conferir OHLCV dos candles marcados"):
                st.dataframe(chart["verification_rows"], hide_index=True, width="stretch")
                st.caption("Compare o mesmo par Binance Spot e intervalo, com fuso UTC. "
                           "Lacunas no feed local ficam indicadas abaixo.")
        coverage = chart["coverage"] or {}
        if coverage.get("discarded_blocks") or coverage.get("gaps_between_complete_blocks"):
            st.caption(f"Agregação: {coverage.get('discarded_blocks', 0)} blocos incompletos, "
                       f"{coverage.get('gaps_between_complete_blocks', 0)} lacunas.")
    else:
        st.info("Candles da operação indisponíveis. Os preços e horários registrados continuam abaixo.")

    st.subheader("Acompanhe a operação")
    steps = build_steps(view)
    if steps:
        labels = [f"{index:02d}  {step['title']}" for index, step in enumerate(steps, 1)]
        step_key = f"operation-step-{operation['id']}"
        if st.session_state.get(step_key) not in labels:
            st.session_state[step_key] = labels[0]
        selected_step = st.segmented_control("Etapa", labels, key=step_key)
        index = labels.index(selected_step or labels[0])
        step = steps[index]
        st.markdown(f'<div class="ops-step-panel"><span class="num">ETAPA {index+1:02d} DE {len(steps):02d}</span>'
                    f'<h3>{_esc(step["title"])}</h3><div class="time">{_esc(_when(step["time"]))}</div>'
                    f'<div class="price">{_esc(_price(step["price"]))} {_esc(view["currency"] or "")}</div>'
                    f'<p>{_esc(step["detail"])}</p></div>', unsafe_allow_html=True)
        if index + 1 < len(steps):
            st.button(f"Próxima etapa: {steps[index+1]['title']} →", key=f"next-step-{operation['id']}",
                      on_click=lambda: st.session_state.update({step_key: labels[index+1]}))
        if not any(step["title"] == "Saída parcial" for step in steps):
            st.caption("Nenhuma saída parcial registrada nesta operação. A condução atual registra saída integral.")
    else:
        st.info("Esta operação não tem etapas de entrada e saída completas no diário.")

    st.subheader("Por que entrou")
    if view["run"]:
        explanation = method_explanation(view)
        if explanation:
            for title, description in explanation:
                st.markdown(f'<div class="ops-method"><strong>{_esc(title)}</strong>'
                            f'<p>{_esc(description)}</p></div>', unsafe_allow_html=True)
        else:
            st.info("As regras versionadas desta operação não permitem uma explicação detalhada.")
        decision, risk, market = view["decision"], view["risk"], view["market"]
        st.markdown(f'<p class="ops-fact-line"><b>Sinal:</b> {_esc(_when(view["signal_time"]))} · '
                    f'<b>Barra de entrada:</b> {_esc(_when(view["entry_time"]))}</p>'
                    f'<p class="ops-fact-line"><b>Decisão:</b> {_esc(decision.get("decisao"))} · '
                    f'<b>Risco:</b> {_esc(risk.get("verdict"))}</p>'
                    f'<p class="ops-fact-line"><b>Plano:</b> stop {_price(view["execution"].get("stop"))} · '
                    f'alvo {_price(view["execution"].get("alvo"))} {_esc(view["currency"] or "")}</p>',
                    unsafe_allow_html=True)
        trend = market.get("tendencia") or {}
        slope = trend.get("inclinacao")
        if isinstance(slope, (int, float)):
            st.caption(f"Contexto registrado: {market.get('provedor') or 'fonte não registrada'} · "
                       f"feed {market.get('feed_status') or 'sem estado'} · "
                       f"SMA{trend.get('media_movel_periodo') or '—'} com inclinação {slope:.4f}.")
        with st.expander("Ver verificações de risco e ressalvas"):
            for check in risk.get("checks") or []:
                st.write(f"{check.get('estado', '—')}: {check.get('detalhe', 'sem detalhe')}")
            for factor in decision.get("fatores_contrarios") or []:
                st.warning(factor)
        sources = view["rules"].get("source") or []
        if sources:
            st.caption("Regras operacionais versionadas com fonte PDF: " + "; ".join(
                f"{source.get('path')} · páginas {source.get('pages')}" for source in sources))
    else:
        st.info("Operação legada sem trilha de decisão. O motivo da entrada não foi reconstruído.")

    st.subheader("Como saiu")
    details = view["details"]
    if not closed:
        st.info("Posição em andamento. Stop e alvo são verificados continuamente pelo processo de simulação "
                "quando chegam candles fechados. Ainda não há resultado realizado.")
    elif not view["journal"] or not view["exit_time"]:
        st.info("Fechamento legado sem diário completo; causa e resultado não foram reconstruídos.")
    else:
        st.markdown(f'<p class="ops-fact-line"><b>Motivo:</b> {_esc(view["exit_label"])} · '
                    f'<b>barra de saída:</b> {_esc(_when(view["exit_time"]))}</p>'
                    f'<p class="ops-fact-line"><b>Preço:</b> {_price(operation["exit_price"])} '
                    f'{_esc(view["currency"] or "")} · <b>taxas simuladas:</b> '
                    f'{_esc(_money(details.get("fees"), view["currency"] or "USDT"))}</p>'
                    f'<p class="ops-fact-line"><b>Resultado líquido:</b> '
                    f'{_esc(_money(view["net_pnl"], view["currency"] or "USDT"))} '
                    f'({_esc(view["outcome"] or "indisponível")}).</p>', unsafe_allow_html=True)
        conduction = details.get("conduction") or {}
        if conduction.get("final_stop") is not None:
            st.caption(f"Stop inicial {_price(conduction.get('initial_stop'))} · "
                       f"stop final {_price(conduction.get('final_stop'))} · "
                       f"taxa {details.get('fee_bps_per_side', '—')} bps/lado · "
                       f"slippage adverso {details.get('slippage_bps_per_side', '—')} bps/lado.")

    with st.expander("Fonte e trilha de auditoria"):
        st.caption("Simulação local: entrada baseada em candle já fechado. Não é saldo nem execução da Binance.")
        st.write(f"Registro #{operation['id']} · criado {operation['created_at']} UTC · "
                 f"fechado {operation['closed_at'] or 'ainda aberto'}")
        st.write(f"Origem: {operation['source']}")
        if view["run"]:
            st.write(f"Trilha #{view['run']['id']} · estratégia versão #{view['run']['strategy_id']}")
            for source in view["rules"].get("source") or []:
                st.caption(f"PDF {source.get('path')} · páginas {source.get('pages')} · "
                           f"hash {source.get('sha256')}")
            for stage in view["run"]["stages"]:
                st.caption(f"{stage['stage_index']}. {stage['agent']} · {stage['status']} · {stage['summary']}")
        for limitation in details.get("limitations") or []:
            st.warning(limitation)


def _controls(actor):
    with st.expander("Controle de novas entradas"):
        switch = store.get_kill_switch()
        if switch["enabled"]:
            st.warning(f"Novas entradas pausadas: {switch['reason']}")
            phrase = st.text_input("Digite DESBLOQUEAR para retomar", key="kill-switch-confirm-off")
            if st.button("Retomar entradas simuladas", key="kill-switch-deactivate"):
                if phrase.strip() != "DESBLOQUEAR":
                    st.error("Digite DESBLOQUEAR para retomar.")
                else:
                    store.set_kill_switch(False, "Retomada pela página Operações", actor["username"])
                    st.rerun()
        else:
            reason = st.text_input("Motivo da pausa", key="kill-switch-reason-on")
            if st.button("Pausar novas entradas", key="kill-switch-activate"):
                try:
                    store.set_kill_switch(True, reason, actor["username"])
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        st.caption("A pausa impede novas entradas. O acompanhamento e a saída de posições existentes continuam.")


@st.fragment(run_every="10s")
def _content(actor):
    items = _items()
    try:
        selected_id = int(st.query_params.get("operacao", ""))
    except (TypeError, ValueError):
        selected_id = None
    selected = next((item for item in items if item["operation"]["id"] == selected_id), None)
    if selected:
        _detail(selected)
    else:
        _overview(items)
        _status()
        _list(items)
        _watchlist_radar()
        _controls(actor)


def render(actor):
    st.markdown(OPERATIONS_CSS, unsafe_allow_html=True)
    heading, theme_column = st.columns([5, 1], vertical_alignment="bottom")
    with heading:
        st.title("Operações")
    with theme_column:
        st.selectbox("Aparência", ["Escuro", "Claro"], key="tal-theme")
    st.caption("Entradas, saídas e o motivo de cada decisão.")
    st.markdown('<p style="color:var(--tal-mute);font-size:.78rem">Somente simulação · ordens reais bloqueadas</p>', unsafe_allow_html=True)
    _content(actor)
