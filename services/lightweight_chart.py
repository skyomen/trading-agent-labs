"""HTML renderer for local operation candles using TradingView Lightweight Charts."""

import json


def operation_chart_html(chart, theme="Escuro"):
    """Render the exact stored OHLCV and paper events in an isolated iframe."""
    candles = chart["ohlcv"]
    payload = {
        "candles": candles,
        "markers": chart.get("markers", []),
        "stop": chart.get("stop_line"),
        "target": chart.get("target_line"),
        "exit": chart.get("exit_guide"),
        "theme": theme,
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")
    return f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:transparent;font-family:Arial,sans-serif}}
#wrap{{position:relative;width:100%;height:100%;min-height:390px;overflow:hidden;border:1px solid rgba(130,165,205,.18);border-radius:14px;background:var(--bg)}}
#chart{{position:absolute;inset:0}}#overlay{{position:absolute;inset:0;z-index:10;width:100%;height:100%;pointer-events:none;overflow:visible}}
#error{{display:none;padding:18px;color:var(--ink);font-size:13px}}
</style></head><body><div id="wrap"><div id="chart"></div><svg id="overlay" aria-hidden="true"></svg><div id="error">Não foi possível carregar o gráfico leve. Verifique a conexão e reabra os detalhes.</div></div>
<script>const DATA={encoded};
const script=document.createElement('script');script.src='https://unpkg.com/lightweight-charts@5.2.0/dist/lightweight-charts.standalone.production.js';
script.onload=()=>{{
const isLight=DATA.theme==='Claro', colors=isLight?{{bg:'#ffffff',text:'#637590',grid:'#e4ebf4',up:'#168761',down:'#c8475c'}}:{{bg:'#13243b',text:'#afbfda',grid:'#294363',up:'#40c994',down:'#f06ab8'}};
document.documentElement.style.setProperty('--bg',colors.bg);document.documentElement.style.setProperty('--ink',colors.text);
const host=document.getElementById('chart'), overlay=document.getElementById('overlay');
const chart=LightweightCharts.createChart(host,{{width:host.clientWidth,height:host.clientHeight,layout:{{background:{{color:colors.bg}},textColor:colors.text,fontFamily:'Arial',fontSize:11}},grid:{{vertLines:{{color:colors.grid}},horzLines:{{color:colors.grid}}}},rightPriceScale:{{borderColor:colors.grid,autoScale:true}},timeScale:{{borderColor:colors.grid,timeVisible:true,secondsVisible:false}},crosshair:{{mode:LightweightCharts.CrosshairMode.MagnetOHLC}}}});
const candles=DATA.candles.map(b=>({{time:Math.floor(Date.parse(b.timestamp)/1000),open:b.open,high:b.high,low:b.low,close:b.close}}));
const series=chart.addSeries(LightweightCharts.CandlestickSeries,{{upColor:colors.up,downColor:colors.down,borderUpColor:colors.up,borderDownColor:colors.down,wickUpColor:colors.up,wickDownColor:colors.down,priceLineVisible:false}});series.setData(candles);
const first=candles[0]?.time,last=candles[candles.length-1]?.time;
function addLevel(level,color,dash){{if(!level||!first||!last)return;const start=Math.floor(Date.parse(level.start)/1000),end=Math.floor(Date.parse(level.end)/1000);if(!Number.isFinite(start)||!Number.isFinite(end))return;const line=chart.addSeries(LightweightCharts.LineSeries,{{color,lineWidth:1,lineStyle:dash,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,pointMarkersVisible:false}});line.setData([{{time:start,value:level.price}},{{time:end,value:level.price}}]);}}
addLevel(DATA.stop,'#e9b75e',LightweightCharts.LineStyle.Dashed);addLevel(DATA.target,'#42b8ed',LightweightCharts.LineStyle.Dotted);
chart.timeScale().fitContent();
const ns='http://www.w3.org/2000/svg';
function el(name,attrs){{const node=document.createElementNS(ns,name);for(const [key,val] of Object.entries(attrs))node.setAttribute(key,String(val));return node;}}
function redraw(){{const w=host.clientWidth,h=host.clientHeight;overlay.setAttribute('viewBox',`0 0 ${{w}} ${{h}}`);overlay.replaceChildren();
for(const event of DATA.markers){{const t=Math.floor(Date.parse(event.timestamp)/1000),x=chart.timeScale().timeToCoordinate(t),y=series.priceToCoordinate(event.price);if(x==null||y==null)continue;
const color=event.tipo==='Entrada simulada'?(event.cor||colors.up):(event.cor||colors.down);const tip=el('title',{{}});tip.textContent=`${{event.tipo}} · ${{event.price}} · ${{event.timestamp}}`;
const marker=el('path',{{d:`M ${{x-7}} ${{y-7}} L ${{x+8}} ${{y}} L ${{x-7}} ${{y+7}} Z`,fill:color,stroke:'#081321','stroke-width':1.2}});marker.appendChild(tip);overlay.appendChild(marker);
const label=el('text',{{x:x+11,y:y+4,fill:color,'font-size':10,'font-weight':700,stroke:colors.bg,'stroke-width':3,'paint-order':'stroke'}});label.textContent=event.tipo==='Entrada simulada'?'ENTRADA':'SAÍDA';overlay.appendChild(label);
}}
for(const [level,color,label] of [[DATA.stop,'#e9b75e','STOP'],[DATA.target,'#42b8ed','ALVO']]){{if(!level)continue;const y=series.priceToCoordinate(level.price);if(y==null)continue;const text=el('text',{{x:chart.timeScale().width()-8,y:y-4,fill:color,'font-size':10,'font-weight':700,'text-anchor':'end',stroke:colors.bg,'stroke-width':3,'paint-order':'stroke'}});text.textContent=label;overlay.appendChild(text);}}
if(DATA.exit){{const t=Math.floor(Date.parse(DATA.exit.timestamp)/1000),x=chart.timeScale().timeToCoordinate(t);if(x!=null){{overlay.insertBefore(el('line',{{x1:x,y1:0,x2:x,y2:h,stroke:'#f06ab8','stroke-width':1,'stroke-dasharray':'4 4',opacity:.65}}),overlay.firstChild);}}}}
}}
chart.timeScale().subscribeVisibleTimeRangeChange(redraw);chart.timeScale().subscribeSizeChange(redraw);new ResizeObserver(entries=>{{const box=entries[0].contentRect;chart.applyOptions({{width:box.width,height:box.height}});redraw();}}).observe(host);setTimeout(redraw,80);setTimeout(redraw,350);
}};
script.onerror=()=>document.getElementById('error').style.display='block';document.head.appendChild(script);
</script></body></html>"""
