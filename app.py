"""Streamlit portal for the local Trading Agent Lab."""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from services.config import load_local_env

load_local_env()

from database import store
from services import documents
from services import knowledge as knowledge_service
from services import datasets as dataset_service
from services import market_data
from services.agents import provider_summary, run_agent_task
from services.backtest import parse_ohlcv_csv, run_sma_crossover


LOCAL_PORTAL_SCRIPT = r'''
"use strict";
var D=null, SEL=0, TAB="rank", VIEW="sala", START=0;
var HW=58, HH=29, OX=480, OY=168, PASO=2.55, MARGEN=1.15, COMPACT=null;
function $(id){return document.getElementById(id);}
function esc(value){return String(value==null?"":value).replace(/[&<>\"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'\"':"&quot;"}[c];});}
function robot(color,size){return '<svg viewBox="0 0 40 40" width="'+size+'" height="'+size+'" aria-hidden="true"><path d="M6 40v-6a14 11 0 0 1 28 0v6z" fill="'+color+'"/><rect x="9" y="6" width="22" height="20" rx="7" fill="#dfe6ee"/><rect x="12" y="12" width="16" height="7" rx="3.5" fill="#1a2230"/><circle cx="16.5" cy="15.5" r="1.8" fill="'+color+'"/><circle cx="23.5" cy="15.5" r="1.8" fill="'+color+'"/><rect x="19" y="1.5" width="2" height="5" fill="#dfe6ee"/><circle cx="20" cy="2" r="2" fill="'+color+'"/></svg>';}
function agenteDibujo(x,y,color,state){var body=state==="off"?"#5a6577":color,face=state==="off"?"#8792a3":"#dfe6ee",light=state==="off"?"#3a4352":"#56637a";return '<g transform="translate('+x+','+y+')"><ellipse cx="0" cy="2" rx="21" ry="7" fill="#000" opacity=".25"/><path d="M-19 0v-14a19 15 0 0 1 38 0v14z" fill="'+body+'"/><path d="M-19 -14a19 15 0 0 1 38 0" fill="none" stroke="#fff" stroke-opacity=".18" stroke-width="2"/><rect x="-14" y="-47" width="28" height="25" rx="9" fill="'+face+'"/><rect x="-10" y="-40" width="20" height="8" rx="4" fill="#1a2230"/><circle cx="-4.5" cy="-36" r="2" fill="'+light+'"/><circle cx="4.5" cy="-36" r="2" fill="'+light+'"/><rect x="-1" y="-53" width="2" height="6" fill="'+face+'"/><circle cx="0" cy="-54" r="2.4" fill="'+light+'"/></g>';}
function P(u,v){return [OX+(u-v)*HW,OY+(u+v)*HH];}
function pts(list){return list.map(function(p){return p[0].toFixed(1)+","+p[1].toFixed(1);}).join(" ");}
function poly(list,fill,extra){return '<polygon points="'+pts(list)+'" fill="'+fill+'"'+(extra||"")+'/>';}
function sube(p,h){return [p[0],p[1]-h];}
function T(x,y,text,size,fill,extra){return '<text x="'+x+'" y="'+y+'" font-size="'+size+'" fill="'+fill+'" font-family="Archivo,sans-serif"'+(extra||"")+'>'+esc(text)+'</text>';}
function cortar(text,n){text=String(text);return text.length>n?text.slice(0,n-1)+"…":text;}
function caja(u,v,du,dv,h,top,side1,side2){var a=P(u-du/2,v-dv/2),b=P(u+du/2,v-dv/2),c=P(u+du/2,v+dv/2),d=P(u-du/2,v+dv/2);return poly([b,c,sube(c,h),sube(b,h)],side2)+poly([d,c,sube(c,h),sube(d,h)],side1)+poly([sube(a,h),sube(b,h),sube(c,h),sube(d,h)],top);}
function kpi(label,value){return '<div class="kpi"><small>'+label+'</small><strong>'+value+'</strong></div>';}
var LOCAL = window.TAL_DATA || {agents:[], counts:{}, documents:[], events:[], connections:[], market_feeds:[]};
function feedAtual(){return (LOCAL.market_feeds||[]).filter(function(f){return f.effective_status==="connected";});}
function feedResumo(){var n=feedAtual().length;return n?n+" feed(s) cripto de candles fechados":"Sem feed de mercado atual";}
var LOCAL_COLORS = ["#7fb4ff", "#5fd3d0", "#c99bff", "#e8c66a", "#ff9f6b", "#8fdcb0"];
function localText(value){ return esc(value == null ? "" : value); }
function localStateClass(value){ return /apenas|bloque|pendente|aguardando|desconectado|não configurado/i.test(value) ? "off" : "trab"; }
function localLevel(value){return ({INFO:"Informação",NOTICE:"Aviso",WARNING:"Atenção",ERROR:"Erro"})[String(value||"").toUpperCase()]||value||"Evento";}
function localDocumentStatus(value){return ({indexed:"indexado",stale:"desatualizado",error:"erro",pending:"pendente"})[String(value||"").toLowerCase()]||value||"estado não informado";}
function localConnectionStatus(value){return ({not_configured:"não configurado",disconnected:"desconectado",connected:"conectado",error:"erro"})[String(value||"").toLowerCase()]||value||"estado não informado";}
function localInjectStyles(){
  var style = document.createElement("style");
  style.textContent = "html{overflow-x:hidden!important;overflow-y:auto!important;scrollbar-gutter:stable;overscroll-behavior-y:contain}body{overflow:visible!important;min-width:0!important;width:100%;max-width:100%;padding-bottom:0!important}.pane{overflow:visible!important;flex:0 0 auto!important;min-width:0!important}.side{height:auto!important;align-self:stretch;min-width:0!important}.layout,.stage{min-width:0!important;max-width:100%!important;overflow:visible!important}.row{grid-template-columns:40px minmax(0,1fr)!important}.row .spark,.row .res{display:none!important}.tag.off{color:var(--amber)!important}.pill.warn{background:var(--panel);color:var(--amber);border-color:var(--amber)}.salaw{width:calc(100% - 24px)!important;max-width:calc(100% - 24px)!important;margin-left:12px!important;margin-right:12px!important;overflow:hidden!important}.salaw::after{display:none!important}#floor{display:block;width:100%!important;min-width:0!important;max-width:100%!important;height:auto!important;max-height:none!important;overflow:hidden;object-fit:contain}@media(max-width:760px){#floor{height:auto!important}}.local-empty{padding:12px 14px;color:var(--mute);line-height:1.55}.local-room-label{font-size:11px;fill:#aab8c8;letter-spacing:.06em}.local-divider{stroke:#526078;stroke-width:2;stroke-dasharray:7 7}.local-message{color:var(--mute);font-size:12px;line-height:1.55;padding:10px 14px}.local-status{display:inline-flex;align-items:center;gap:7px}.local-status:before{content:'';width:7px;height:7px;border-radius:50%;background:#f0a43a}.local-status.trab:before{background:#42d392}.local-activity{overflow-wrap:anywhere}.local-controls{display:flex;gap:8px;flex-wrap:wrap;padding:8px 14px}.local-metric{padding:10px 14px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:12px}.local-metric span{color:var(--mute)}.local-band{display:flex;gap:12px;flex-wrap:wrap;padding:10px 14px;border-bottom:1px solid var(--line)}@media(max-width:860px){.layout{min-height:0;grid-template-columns:minmax(0,1fr)!important}.side{order:2}.stage{order:1}.pane{max-height:none!important}.local-band{display:grid;grid-template-columns:1fr}}@media(max-width:760px){body{padding-bottom:66px!important}.tabs{overflow:hidden!important;justify-content:space-between!important;flex-wrap:nowrap!important;gap:0!important;padding-left:3px!important;padding-right:3px!important}.tab{white-space:nowrap;min-width:0!important;flex:1 1 0!important;padding-left:3px!important;padding-right:3px!important;font-size:11px!important}.layout{min-height:0}.salaw{margin-top:8px!important}}";
  document.head.appendChild(style);
}
function localFormatTime(value){
  if(!value) return "Horário não informado";
  var d = new Date(String(value).replace(" ", "T") + (String(value).includes("Z") ? "" : "Z"));
  return isNaN(d.getTime()) ? String(value).replace("T", " ").slice(0,16) : d.toLocaleString("pt-BR", {dateStyle:"short", timeStyle:"short"});
}
function localAgentStatus(agent){ return agent.status || "Estado não informado"; }
function pintarCabecera(){
  var c=LOCAL.counts, docs=LOCAL.documents.filter(function(d){return d.status==="indexed";}).length;
  var vals=[["Agentes",c.agents||0],["PDFs indexados",docs],["Tarefas",c.agent_runs||0],["Eventos",c.events||0]];
  $("kpis").innerHTML=vals.map(function(v){return kpi(v[0],String(v[1]));}).join("");
  $("pills").innerHTML='<span class="pill warn">'+localText(feedResumo())+'</span><span class="pill">XP Trader desconectado</span><span class="pill demo">Somente simulação</span>';
  $("parada").className="parada"; $("parada").textContent="";
}
function pintarRanking(){
  $("p-rank").innerHTML='<div class="sec">Mesas dos agentes</div>'+D.agentes.map(function(a){
    var cls=localStateClass(a.status);
    return '<div class="row'+(a.i===SEL?' sel':'')+'" data-i="'+a.i+'" tabindex="0" role="button" aria-label="Abrir '+localText(a.nome)+'">'+
      '<div class="av">'+robot(a.color,34)+'</div><div style="min-width:0"><div class="nm">'+localText(a.nome)+'</div><span class="tag '+(cls==='off'?'off':'')+'">'+localText(a.status)+'</span></div></div>';
  }).join("")+'<p class="note">Os nomes, estados e responsabilidades vêm do SQLite deste laboratório. Nenhum saldo, sinal ou desempenho é presumido.</p>';
  ligarRanking();
}
function pintarOps(){
  var events=LOCAL.events||[];
  $("p-ops").innerHTML='<div class="sec">Atividade registrada</div>'+(events.length?events.map(function(e){
    var message=String(e.Atividade||"").replace(/\bindexed\b/gi,"indexado");
    return '<div class="item local-activity"><time>'+localText(localFormatTime(e["Horário"]))+'</time><span><b>'+localText(e.Agente==="Trading Lab"?"Sistema":e.Agente)+'</b><br>'+localText(localLevel(e.Nível))+' · '+localText(message)+'</span></div>';
  }).join(""):'<p class="local-empty">Ainda não há eventos locais registrados.</p>')+'<p class="note">Este histórico é lido do banco SQLite e permanece após reiniciar o aplicativo.</p>';
}
function pintarInforme(){
  var c=LOCAL.counts, docs=LOCAL.documents.filter(function(d){return d.status==="indexed";}).length;
  $("p-inf").innerHTML='<div class="sec">Estado do laboratório</div>'+[
    ["Agentes cadastrados",c.agents||0],["Tarefas de agentes executadas",c.agent_runs||0],["Documentos indexados",docs],
    ["Estratégias registradas",c.strategies||0],["Backtests registrados",c.backtests||0],["Operações simuladas",c.paper_operations||0]
  ].map(function(x){return '<div class="local-metric"><span>'+localText(x[0])+'</span><b>'+x[1]+'</b></div>';}).join("")+
  '<p class="note">A contagem reflete somente registros locais. Sem tarefas, backtests ou operações gravadas, não há resultado a avaliar.</p>';
}
function pintarControl(){
  var docs=LOCAL.documents||[], con=LOCAL.connections||[];
  $("p-ctl").innerHTML='<div class="sec">Conexões e segurança</div><div class="kv">'+
    '<span>Feed de mercado</span><span>'+localText(feedResumo())+'</span><span>XP Trader 5.0.4.34</span><span>Não conectado</span><span>Modo</span><span>Simulação local</span><span>Ordens reais</span><span>Bloqueadas</span></div>'+
    '<div class="sec">Biblioteca local</div>'+(docs.length?docs.map(function(d){return '<div class="item"><span>'+localText(d.filename)+' · '+localText(localDocumentStatus(d.status))+'</span></div>';}).join(""):'<p class="local-empty">Nenhum documento registrado no índice.</p>')+
    '<div class="sec">Conectores registrados</div>'+(con.length?con.map(function(x){return '<div class="item"><span>'+localText(x.provider||x.key)+' · '+localText(localConnectionStatus(x.status))+'</span></div>';}).join(""):'<p class="local-empty">Nenhum conector foi configurado.</p>')+
    '<p class="note">Este painel não conecta contas nem envia ordens. Uma conexão futura exige configuração e autorização próprias.</p>';
}
function estadoDe(a){ return localStateClass(a.status)==="off"?"off":"espera"; }
function puestoDibujo(a,u,v,sel){
  var c=a.color,h=24,ctr=P(u,v),cx=ctr[0],cy=ctr[1],pw=150;
  var s='<g class="desk'+(sel?' sel':'')+'" data-i="'+a.i+'" tabindex="0" role="button" aria-label="Mesa de '+localText(a.nome)+': '+localText(a.status)+'">';
  s+=poly([P(u-.98,v-.98),P(u+.98,v-.98),P(u+.98,v+.98),P(u-.98,v+.98)],c,' class="hl" fill-opacity=".14" stroke="'+c+'" stroke-width="1.5"');
  s+=agenteDibujo(cx+26,cy-h+4,c,estadoDe(a))+caja(u,v,1.25,.8,h,"#9a6b47","#6f4b31","#5a3c27");
  var mx=cx-62,my=cy-h-58,mw=76,mh=48;
  s+='<rect x="'+(cx-26)+'" y="'+(cy-h-12)+'" width="6" height="10" fill="#2a3240"/><rect x="'+(mx-3)+'" y="'+(my-3)+'" width="'+(mw+6)+'" height="'+(mh+6)+'" rx="4" fill="#0d1219" stroke="#2f3a4c"/><rect x="'+mx+'" y="'+my+'" width="'+mw+'" height="'+mh+'" rx="2" fill="#121820"/>';
  s+='<path d="M'+(mx+5)+' '+(my+25)+'h'+(mw-10)+'" stroke="'+c+'" stroke-width="1.6" opacity=".75"/>'+T(mx+mw/2,my+18,cortar(a.status,13),8.5,"#dce4ed",' text-anchor="middle" font-weight="700"');
  var py=cy+22;
  s+='<rect x="'+(cx-pw/2)+'" y="'+py+'" width="'+pw+'" height="38" rx="6" fill="#141c27" fill-opacity=".94" stroke="'+(sel?c:'#2f3b4e')+'"/><rect x="'+(cx-pw/2+8)+'" y="'+(py+9)+'" width="4" height="20" rx="2" fill="'+c+'"/>';
  s+=T(cx-pw/2+18,py+16,cortar(a.nome,22),12,"#e9eef4",' font-weight="700"');
  s+=T(cx-pw/2+18,py+31,a.status,9,"#aab8c8");
  return s+'</g>';
}
function localTickerTime(value){
  if(!value)return "--:--";var date=new Date(String(value).replace(" ","T")+"Z");
  return isNaN(date.getTime())?String(value).slice(-8):date.toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"});
}
function wrapSvgText(value,maxChars){
  var words=String(value||"").split(/\s+/),lines=[],line="";
  words.forEach(function(word){var next=line?line+" "+word:word;if(next.length>maxChars&&line){lines.push(line);line=word;}else line=next;});
  if(line)lines.push(line);return lines;
}
function resumoEvento(value){
  var message=String(value||"").replace(/\s+/g," ");
  if(/^Responsabilidade atualizada com o estado validado:/i.test(message))return "Responsabilidade atualizada";
  if(/^Estado corrigido para refletir aus[êe]ncia de integra[çc][ãa]o:/i.test(message))return "Integração ausente";
  if(/^Biblioteca local: indexed/i.test(message))return "PDF indexado";
  return cortar(message,30);
}
function pintarSalaCompacta(){
  var floor=$("floor"),agents=D.agentes,counts=LOCAL.counts,docs=LOCAL.documents.filter(function(d){return d.status==="indexed";}).length,latest=LOCAL.events[0];
  floor.setAttribute("viewBox","0 0 390 660");
  var risk=agents.find(function(a){return a.nome==="Risk Manager";}),riskText=risk?risk.status:"Estado de risco não cadastrado",riskColor=/pendente|aguardando|bloque/i.test(riskText)?"#f0a43a":"#42d392";
  var lastTime=latest?localFormatTime(latest["Horário"]):"Sem eventos",lastActor=latest?(latest.Agente==="Trading Lab"?"Sistema":latest.Agente):"Sem agente informado";
  var lastMessage=latest?resumoEvento(latest.Atividade):"Nenhuma atividade registrada";
  var ticker=(LOCAL.events||[]).slice(0,5).reverse().map(function(e){var actor=e.Agente==="Trading Lab"?"Sistema":e.Agente,msg=String(e.Atividade||"").replace(/\bindexed\b/gi,"indexado").replace(/\s+/g," ");return localTickerTime(e["Horário"])+" · "+actor+": "+cortar(msg,48);}).join("     ")||"Nenhuma atividade registrada no SQLite";
  var width=ticker.length*6.2+360,s='<defs><clipPath id="mobile-led" clipPathUnits="userSpaceOnUse"><rect x="16" y="49" width="358" height="23" rx="3"/></clipPath></defs>';
  s+='<rect width="390" height="660" fill="#0f151e"/><path d="M9 9h358l14 174H9z" fill="#19222f" stroke="#33415a" stroke-width="2"/>';
  s+=T(20,31,(counts.agents||0)+" AGENTES",15,"#f0a43a",' font-weight="900"')+T(369,31,(counts.agent_runs||0)+" TAREFAS",12,"#e9eef4",' text-anchor="end" font-weight="700"');
  s+=T(20,44,docs+" PDFs indexados · "+(counts.events||0)+" eventos · "+feedResumo(),10,"#aab8c8");
  s+='<rect x="16" y="49" width="358" height="23" rx="3" fill="#0a0d12" stroke="#33415a"/><g clip-path="url(#mobile-led)"><g class="ticker" style="--fin:-'+Math.round(width)+'px;--dur:'+Math.max(24,Math.round(width/72))+'s"><text x="378" y="65" font-family="Doto,monospace" font-weight="700" font-size="11" fill="#f6c97a" xml:space="preserve">'+localText(ticker+"     "+ticker)+'</text></g></g>';
  s+='<path d="M194 81v63" stroke="#33415a"/><text x="20" y="94" font-family="Archivo,sans-serif" font-size="9" fill="#8d9aab">Último evento registrado</text>'+T(20,113,lastTime,11,"#e9eef4",' font-weight="700"')+T(20,130,lastActor,9,"#aab8c8")+T(20,145,cortar(lastMessage,30),8,"#8d9aab");
  s+=T(205,94,"Estado de risco",9,"#8d9aab")+'<circle cx="211" cy="111" r="4" fill="'+riskColor+'"/>';
  var riskLines=wrapSvgText(riskText,27).slice(0,3);riskLines.forEach(function(line,i){s+=T(221,114+i*13,line,9,riskColor,' font-weight="700"');});
  s+=T(20,160,"Ordens reais bloqueadas",10,"#aab8c8")+T(369,160,"SOMENTE SIMULAÇÃO",9,"#f0a43a",' text-anchor="end" font-weight="700"');
  s+='<text x="17" y="205" font-family="Archivo,sans-serif" font-size="12" fill="#aab8c8" letter-spacing="1">MESAS DE ANÁLISE</text><polygon points="16,220 374,220 385,630 5,630" fill="#26344a" stroke="#33415a" stroke-width="2"/>';
  for(var g=0;g<5;g++){var gy=240+g*106;s+='<path d="M'+(12+g*2)+' '+gy+'L'+(378-g)+' '+gy+'" stroke="#34465f" stroke-width="1" opacity=".8"/>';}
  var slots=[[18,250],[202,250],[18,375],[202,375],[18,500],[202,500]];
  agents.forEach(function(a,i){var x=slots[i][0],y=slots[i][1],color=a.color,sel=a.i===SEL;
    s+='<g class="desk'+(sel?' sel':'')+'" data-i="'+a.i+'" tabindex="0" role="button" aria-label="Mesa de '+localText(a.nome)+': '+localText(a.status)+'">';
    s+='<ellipse cx="'+(x+78)+'" cy="'+(y+39)+'" rx="44" ry="7" fill="#000" opacity=".22"/><path d="M'+(x+26)+' '+(y+28)+'l42-18 41 16-42 19z" fill="#9a6b47" stroke="#bf9368"/><path d="M'+(x+67)+' '+(y+45)+'v7l41-16v-7" fill="#5a3c27"/><rect x="'+(x+59)+'" y="'+(y-7)+'" width="36" height="23" rx="3" fill="#0c121a" stroke="#41516a"/><rect x="'+(x+62)+'" y="'+(y-4)+'" width="30" height="17" rx="2" fill="#17212d"/><path d="M'+(x+65)+' '+(y+7)+'h24" stroke="'+color+'" stroke-width="1.5"/>';
    s+=agenteDibujo(x+127,y+27,color,estadoDe(a));
    s+='<rect x="'+(x+1)+'" y="'+(y+57)+'" width="166" height="49" rx="6" fill="#141c27" stroke="'+(sel?color:'#35465b')+'"/><rect x="'+(x+9)+'" y="'+(y+66)+'" width="3" height="29" rx="1.5" fill="'+color+'"/>';
    s+=T(x+20,y+78,cortar(a.nome,24),10,"#e9eef4",' font-weight="700"');
    var statusLines=wrapSvgText(a.status,27).slice(0,2);statusLines.forEach(function(line,j){s+=T(x+20,y+90+j*11,line,8.5,"#aab8c8");});
    s+='</g>';
  });
  floor.innerHTML=s;
  Array.prototype.forEach.call(floor.querySelectorAll(".desk"),function(el){var i=+el.dataset.i;el.onclick=function(){selecionar(i);};el.onkeydown=function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();selecionar(i);}};});
}
function pintarSala(){
  if(COMPACT===null)COMPACT=window.matchMedia("(max-width: 760px)").matches;
  if(COMPACT){pintarSalaCompacta();return;}
  var floor=$("floor"),n=D.agentes.length,cols=3,rows=Math.max(1,Math.ceil(n/cols));
  var U=MARGEN*2+(cols-1)*PASO,V=MARGEN*2+(rows-1)*PASO;
  HW=Math.min(72,900/(U+V));HH=HW/2;OX=480+(V-U)*HW/2;OY=172;
  var height=Math.round(P(U,V)[1]+74);floor.setAttribute("viewBox","0 0 960 "+height);
  var s='<defs><clipPath id="led" clipPathUnits="userSpaceOnUse"><rect x="0" y="0" width="330" height="86"/></clipPath><linearGradient id="muro" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1d2837"/><stop offset="1" stop-color="#243245"/></linearGradient></defs>';
  s+='<rect width="960" height="'+height+'" fill="#0f151e"/>';
  var A=P(0,0),B=P(U,0),C=P(U,V),Dd=P(0,V),HM=150;
  s+=poly([Dd,A,sube(A,HM),sube(Dd,HM)],"url(#muro)")+poly([A,B,sube(B,HM),sube(A,HM)],"#202c3d");
  s+='<line x1="'+A[0]+'" y1="'+A[1]+'" x2="'+A[0]+'" y2="'+(A[1]-HM)+'" stroke="#2c3b51" stroke-width="2"/>';
  s+=poly([Dd,C,sube(C,-12),sube(Dd,-12)],"#1a2433")+poly([B,C,sube(C,-12),sube(B,-12)],"#151d29")+poly([A,B,C,Dd],"#26344a");
  var lines="";
  for(var k=0;k<=Math.ceil(U);k++){var q=Math.min(k,U),p1=P(q,0),p2=P(q,V);lines+='<line x1="'+p1[0].toFixed(1)+'" y1="'+p1[1].toFixed(1)+'" x2="'+p2[0].toFixed(1)+'" y2="'+p2[1].toFixed(1)+'"/>';}
  for(var m=0;m<=Math.ceil(V);m++){var w=Math.min(m,V),p3=P(0,w),p4=P(U,w);lines+='<line x1="'+p3[0].toFixed(1)+'" y1="'+p3[1].toFixed(1)+'" x2="'+p4[0].toFixed(1)+'" y2="'+p4[1].toFixed(1)+'"/>';}
  s+='<g stroke="#2e3e56" stroke-width="1">'+lines+'</g>';
  var counts=LOCAL.counts,docs=LOCAL.documents.filter(function(d){return d.status==="indexed";}).length,latest=LOCAL.events[0];
  var risk=D.agentes.find(function(a){return a.nome==="Risk Manager";}),riskText=risk?risk.status:"Estado de risco não cadastrado";
  var eventTime=latest?localTickerTime(latest["Horário"]):"--:--",eventActor=latest?(latest.Agente==="Trading Lab"?"Sistema":latest.Agente):"Sem eventos";
  var eventMessage=latest?resumoEvento(latest.Atividade):"Sem atividade registrada";
  var led='<g transform="translate('+(A[0]+52)+','+(A[1]-HM+24)+') skewY(26.565)">';
  led+='<rect x="-8" y="-8" width="346" height="102" rx="6" fill="#0a0d12" stroke="#33415a"/>';
  led+='<text x="4" y="30" font-family="Doto,monospace" font-weight="900" font-size="30" fill="#f0a43a">'+(counts.agents||0)+' AGENTES</text>';
  led+='<text x="326" y="30" text-anchor="end" font-family="Doto,monospace" font-weight="900" font-size="20" fill="#e9eef4">'+(counts.agent_runs||0)+' TAREFAS</text>';
  led+='<text x="4" y="50" font-family="Archivo,sans-serif" font-size="11" fill="#8d9aab">'+docs+' PDFs indexados · '+(counts.events||0)+' eventos · '+localText(feedResumo())+'</text>';
  var ticker=(LOCAL.events||[]).slice(0,5).reverse().map(function(e){var actor=e.Agente==="Trading Lab"?"Sistema":e.Agente;return localTickerTime(e["Horário"])+" · "+actor+": "+String(e.Atividade||"").replace(/\s+/g," ");}).join("     ")||"Nenhum evento registrado";
  var tickerWidth=ticker.length*8.4+340;
  led+='<g clip-path="url(#led)"><g class="ticker" style="--fin:-'+Math.round(tickerWidth)+'px;--dur:'+Math.max(24,Math.round(tickerWidth/38))+'s"><text x="340" y="78" font-family="Doto,monospace" font-weight="700" font-size="15" fill="#f6c97a" xml:space="preserve">'+localText(ticker+"     "+ticker)+'</text></g></g>';
  s+=led+'</g>';
  var left='<g transform="translate('+(Dd[0]+40)+','+(Dd[1]-HM+20)+') skewY(-26.565)">';
  left+='<rect x="0" y="0" width="150" height="64" rx="6" fill="#121923" stroke="#33415a"/>';
  left+='<text x="12" y="20" font-family="Archivo,sans-serif" font-size="11" fill="#8d9aab">Último evento</text>';
  left+='<text x="12" y="44" font-family="Doto,monospace" font-weight="900" font-size="22" fill="#e9eef4">'+localText(eventTime)+'</text>';
  left+='<text x="12" y="58" font-family="Archivo,sans-serif" font-size="10" fill="#8d9aab">'+localText(cortar(eventMessage,24))+'</text>';
  left+='<rect x="170" y="0" width="160" height="64" rx="6" fill="#121923" stroke="#33415a"/>';
  left+='<circle cx="190" cy="32" r="9" fill="#f0a43a"/><circle cx="190" cy="32" r="14" fill="none" stroke="#f0a43a" stroke-opacity=".35" stroke-width="3"/>';
  left+='<text x="210" y="24" font-family="Archivo,sans-serif" font-size="11" fill="#8d9aab">Estado de risco</text>';
  wrapSvgText(riskText,27).slice(0,2).forEach(function(line,i){left+='<text x="210" y="'+(42+i*13)+'" font-family="Archivo,sans-serif" font-weight="700" font-size="10" fill="#f0a43a">'+localText(line)+'</text>';});
  s+=left+'</g>';
  var list=D.agentes.map(function(a,k){var col=k%cols,row=Math.floor(k/cols);return {a:a,u:MARGEN+col*PASO,v:MARGEN+row*PASO};});
  list.sort(function(x,y){return (x.u+x.v)-(y.u+y.v)||x.u-y.u;});
  list.forEach(function(item){s+=puestoDibujo(item.a,item.u,item.v,item.a.i===SEL);});
  var plant=P(U-.35,.35);
  s+='<g transform="translate('+plant[0].toFixed(1)+','+plant[1].toFixed(1)+')"><path d="M-11 0 l3 -18 h16 l3 18 z" fill="#8a5a3c"/><path d="M0 -18 c-18 -6 -20 -26 -6 -34 c2 10 6 16 6 34 c0 -18 4 -26 14 -32 c6 12 0 26 -14 32" fill="#3f8f6a"/></g>';
  floor.innerHTML=s;
  Array.prototype.forEach.call(floor.querySelectorAll(".desk"),function(el){var i=+el.dataset.i;el.onclick=function(){selecionar(i);};el.onkeydown=function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();selecionar(i);}};});
}
function pintarVistazo(){
  $("glance").innerHTML='<div class="gh"><b>Estado dos agentes</b><span>'+D.agentes.length+' cadastrados no SQLite</span></div><div class="gg">'+D.agentes.map(function(a){
    return '<button class="gl '+(a.i===SEL?'sel':'')+'" data-i="'+a.i+'"><i style="background:'+a.color+'"></i><span class="gn">'+localText(a.nome)+'</span><em>'+localText(a.status)+'</em></button>';
  }).join("")+'</div>';
  Array.prototype.forEach.call(document.querySelectorAll(".gl"),function(b){b.onclick=function(){selecionar(+b.dataset.i);};});
}
function pintarParte(){
  var el=$("parte"); if(!el)return; el.hidden=false;
  var indexed=LOCAL.documents.filter(function(d){return d.status==="indexed";}).length;
  var research=D.agentes.find(function(a){return a.nome==="Research Agent";});
  var mismatch=research&&indexed>0&&/aguardando documentos/i.test(research.status)
    ? '<li>Atenção: o Research Agent ainda está marcado como aguardando documentos, embora '+indexed+' PDF(s) estejam indexados. O estado não é atualizado automaticamente.</li>' : '';
  el.innerHTML='<div class="pt"><h3>Diretor geral</h3><div class="tit">Resumo do laboratório</div><ul><li>'+D.agentes.length+' agentes locais cadastrados; o portal não os executa em segundo plano.</li><li>'+((LOCAL.counts.agent_runs||0))+' tarefas executadas e '+((LOCAL.counts.events||0))+' eventos no histórico.</li>'+mismatch+'<li>'+localText(feedResumo())+'; nenhuma ordem real pode ser enviada.</li></ul></div>';
}
function pintarFicha(){
  var a=D.agentes[SEL];if(!a)return;
  $("ficha").innerHTML='<div class="who"><div class="av">'+robot(a.color,34)+'</div><div><b>'+localText(a.nome)+'</b><span>'+localText(a.status)+'</span></div></div><div class="st"><small>Responsabilidade</small><b>'+localText(a.responsibility)+'</b></div>';
}
function pintarLab(){
  $("labsvg").innerHTML=""; $("labtxt").innerHTML='<p class="local-message">Ainda não há backtests registrados no banco local. Não há desempenho ou assertividade a apresentar.</p>';
}
function pintarEvolucion(){
  var font=window.innerWidth<500?32:17;
  $("evchart").innerHTML='<text x="450" y="210" text-anchor="middle" fill="#aab8c8" font-size="'+font+'" font-family="Archivo,sans-serif">Sem operações simuladas encerradas para mostrar.</text>';
  $("leg").innerHTML=""; $("evnote").textContent="A evolução do capital só aparecerá quando existirem operações locais persistidas.";
}
function pintarMercado(){
  $("mhead").innerHTML='<div class="sec">Mercado</div>';
  var font=window.innerWidth<500?32:17;
  var feeds=LOCAL.market_feeds||[];
  $("rng").innerHTML=""; $("mchart").innerHTML='<text x="450" y="220" text-anchor="middle" fill="#aab8c8" font-size="'+font+'" font-family="Archivo,sans-serif">'+localText(feedResumo())+'</text>';
  $("mnote").textContent=feeds.length?feeds.map(function(f){return f.symbol+" · Binance Spot · fechamento 1m "+(f.last_close==null?"indisponível":f.last_close)+" USDT · "+(f.last_bar_at||"sem barra")+" UTC · "+f.effective_status;}).join(" | ")+". Histórico local; nenhuma ordem é enviada.":"Nenhum feed de mercado persistido. Histórico não equivale a cotação atual.";
}
function mercadoActivar(){}
function pintarTab(){
  ["rank","mkt","ops","inf","ctl"].forEach(function(t){$("p-"+t).hidden=t!==TAB;});
  var isMarket=TAB==="mkt", sala=VIEW==="sala";
  $("floor").parentNode.classList.toggle("room-visible",!isMarket&&sala);
  $("top").hidden=isMarket; $("floor").style.display=isMarket||!sala?"none":"";
  $("glance").style.display=isMarket||!sala?"none":""; $("parte").hidden=isMarket||!sala;
  $("labbox").hidden=isMarket||VIEW!=="lab"; $("evbox").hidden=isMarket||VIEW!=="evo"; $("mktbox").hidden=!isMarket;
  if(isMarket)pintarMercado(); else {pintarFicha();if(VIEW==="lab")pintarLab();if(VIEW==="evo")pintarEvolucion();}
  document.querySelectorAll("#vtabs button").forEach(function(b){b.setAttribute("aria-pressed",b.dataset.v===VIEW?"true":"false");});
  document.querySelectorAll(".tab").forEach(function(b){b.setAttribute("aria-selected",b.dataset.t===TAB?"true":"false");});
}
function ligarRanking(){
  document.querySelectorAll("#p-rank .row").forEach(function(row){
    row.onclick=function(){selecionar(+row.dataset.i);};
    row.onkeydown=function(event){if(event.key==="Enter"||event.key===" "){event.preventDefault();selecionar(+row.dataset.i);}};
  });
}
function selecionar(i){SEL=i;pintarRanking();pintarSala();pintarVistazo();pintarFicha();}
function pintarTodo(){pintarCabecera();pintarRanking();pintarOps();pintarInforme();pintarControl();pintarSala();pintarVistazo();pintarParte();pintarTab();}
function recargar(){window.location.reload();}
function inicializarLocal(){
  localInjectStyles();
  D={agentes:(LOCAL.agents||[]).map(function(a,i){return {i:i,nome:a.name,nombre:a.name,status:a.status,responsibility:a.responsibility,color:LOCAL_COLORS[i%LOCAL_COLORS.length],apagado:false,pos:[],serie:[]};}),ops:[],hist:[],estado:{}};
  if(!D.agentes.length){$("p-rank").innerHTML='<p class="local-empty">O banco local não retornou agentes cadastrados.</p>';return;}
  pintarTodo();
  var roomMedia=window.matchMedia("(max-width: 760px)");
  var onRoomResize=function(){var next=roomMedia.matches;if(next!==COMPACT){COMPACT=next;pintarSala();}};
  if(roomMedia.addEventListener)roomMedia.addEventListener("change",onRoomResize);else if(roomMedia.addListener)roomMedia.addListener(onRoomResize);
  document.querySelectorAll("#vtabs button").forEach(function(b){b.addEventListener("click",function(){VIEW=b.dataset.v;pintarTab();});});
  document.querySelectorAll("#tabs .tab").forEach(function(b){
    b.textContent=({rank:"Agentes",mkt:"Mercado",ops:"Operações",inf:"Informe",ctl:"Controle"})[b.dataset.t]||b.textContent;
    b.addEventListener("click",function(){TAB=b.dataset.t;pintarTab();});
  });
}
'''


st.set_page_config(page_title="Trading Agent Lab", layout="wide", initial_sidebar_state="collapsed")
store.initialize()
knowledge_service.refresh_research_status()

AGENT_ICONS = {
    "Research Agent": "book", "Market Analyst": "chart", "Fundamental Analyst": "news",
    "Strategy & Backtest": "flask", "Risk Manager": "shield", "Execution Agent": "route",
}
PANEL_PAGES = ["Agentes", "Mercado", "Operações", "Informe", "Controle"]
STAGE_VIEWS = ["Sala", "Laboratório", "Evolução do capital"]
AGENT_COLORS = {
    "Research Agent": "#7fb4ff", "Market Analyst": "#5fd3d0",
    "Fundamental Analyst": "#c99bff", "Strategy & Backtest": "#e8c66a",
    "Risk Manager": "#ff9f6b", "Execution Agent": "#8fdcb0",
}


st.markdown("""
<style>
:root { color-scheme:dark; --tal-bg:#131a24; --tal-panel:#19222f; --tal-panel2:#1f2a39; --tal-line:#2a3648; --tal-ink:#e9eef4; --tal-mute:#9aa8ba; --tal-amber:#f0a43a; --tal-amber-dark:#b97a22; --tal-up:#42d392; --tal-down:#ff786b; --tal-blue:#7fb4ff; }
@font-face { font-family:Archivo; src:url("app/static/Archivo.woff2") format("woff2"); font-style:normal; font-weight:400 800; font-stretch:62% 125%; font-display:swap; }
@font-face { font-family:Doto; src:url("app/static/Doto.woff2") format("woff2"); font-style:normal; font-weight:700 900; font-display:swap; }
html,body,[data-testid="stAppViewContainer"],.stApp { background:var(--tal-bg); color:var(--tal-ink); font-family:Archivo, "Segoe UI", sans-serif; font-size:14px; font-variant-numeric:tabular-nums; }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"], [data-testid="stDeployButton"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display:none !important; }
[data-testid="stMainBlockContainer"] { max-width:1800px; padding:.15rem 0 4rem; }
[data-testid="stVerticalBlock"] { gap:.55rem; }
.stMarkdown, [data-testid="stMarkdownContainer"] { color:var(--tal-ink); }
h1,h2,h3,h4 { font-family:Archivo, "Segoe UI", sans-serif; letter-spacing:-.02em; color:var(--tal-ink); }
.st-key-tal-header { padding:13px 22px 12px; border-bottom:1px solid var(--tal-line); }
.st-key-tal-header [data-testid="stVerticalBlock"] { gap:0; }
.tal-topbar { display:flex; align-items:center; gap:26px; width:100%; min-width:0; }
.tal-brand { flex:0 0 auto; line-height:1.08; }
.tal-brand b { display:block; font-size:21px; font-weight:800; font-stretch:112%; letter-spacing:-.02em; }
.tal-brand span { display:block; margin-top:3px; color:var(--tal-mute); font-size:12px; }
.tal-kpis { display:flex; align-items:center; flex-wrap:wrap; gap:12px 25px; min-width:0; }
.tal-kpi small { display:block; color:var(--tal-mute); font-size:11px; }
.tal-kpi strong { display:block; margin-top:1px; font-family:Doto, Archivo, "Segoe UI", sans-serif; font-size:19px; font-weight:700; font-stretch:92%; letter-spacing:.025em; white-space:nowrap; }
.tal-pills { display:flex; align-items:center; justify-content:flex-end; flex-wrap:wrap; gap:6px; margin-left:auto; }
.tal-pill { padding:5px 9px; border:1px solid var(--tal-line); border-radius:6px; background:var(--tal-panel); color:var(--tal-ink); font-size:11px; font-weight:650; white-space:nowrap; }
.tal-pill.safe { color:var(--tal-up); }
.tal-pill.warn { color:var(--tal-amber); }
.st-key-tal-layout { padding:0 12px; }
.st-key-tal-layout > [data-testid="stVerticalBlock"] { gap:0; }
.st-key-tal-layout [data-testid="stHorizontalBlock"] { gap:0; }
.st-key-tal-side { min-height:calc(100vh - 74px); padding:0 0 22px; border-right:1px solid var(--tal-line); background:var(--tal-panel); }
.st-key-tal-side > [data-testid="stVerticalBlock"] { gap:.35rem; }
.st-key-tal-stage { min-width:0; padding:0 0 12px 12px; }
.st-key-tal-nav, .st-key-tal-view, .st-key-tal-room { padding:7px 8px 4px; border-bottom:1px solid var(--tal-line); }
.st-key-tal-nav [data-testid="stWidgetLabel"], .st-key-tal-view [data-testid="stWidgetLabel"], .st-key-tal-room [data-testid="stWidgetLabel"] { display:none; }
.st-key-tal-nav [role="radiogroup"], .st-key-tal-view [role="radiogroup"], .st-key-tal-room [role="radiogroup"] { display:flex; flex-wrap:wrap; gap:3px; }
.st-key-tal-nav label[data-baseweb="radio"], .st-key-tal-view label[data-baseweb="radio"], .st-key-tal-room label[data-baseweb="radio"] { min-height:40px; padding:7px 8px; border-radius:6px; color:var(--tal-mute); font-size:12px; font-weight:650; cursor:pointer; }
.st-key-tal-nav label[data-baseweb="radio"]:has(input:checked), .st-key-tal-view label[data-baseweb="radio"]:has(input:checked), .st-key-tal-room label[data-baseweb="radio"]:has(input:checked) { background:var(--tal-panel2); color:var(--tal-ink); box-shadow:inset 0 -2px var(--tal-amber); }
.st-key-tal-nav label[data-baseweb="radio"] > div:first-child, .st-key-tal-view label[data-baseweb="radio"] > div:first-child, .st-key-tal-room label[data-baseweb="radio"] > div:first-child { display:none; }
.tal-pane-title { padding:13px 14px 7px; font-size:14px; font-weight:750; }
.tal-pane-note { padding:0 14px 10px; color:var(--tal-mute); font-size:12px; line-height:1.45; }
.tal-agent-row { padding:8px 10px; border-bottom:1px solid var(--tal-line); }
.tal-agent-row.selected { background:var(--tal-panel2); box-shadow:inset 3px 0 var(--tal-amber); }
.tal-agent-icon { display:grid; width:36px; height:36px; place-items:center; border:1px solid var(--tal-line); border-radius:7px; background:#121923; color:var(--tal-agent-color); }
.tal-agent-icon svg { width:24px; height:24px; }
.tal-agent-meta { padding-top:3px; color:var(--tal-mute); font-size:11px; line-height:1.4; }
[class*="st-key-tal-agent-"] { padding:7px 8px; border-bottom:1px solid var(--tal-line); }
.st-key-tal-agent-current { background:var(--tal-panel2); box-shadow:inset 3px 0 var(--tal-amber); }
[class*="st-key-tal-agent-"] [data-testid="stButton"] button { min-height:34px; padding:0; border:0; background:transparent; color:var(--tal-ink); text-align:left; font-size:13px; font-weight:750; }
[class*="st-key-tal-agent-"] [data-testid="stButton"] button:hover { color:var(--tal-amber); }
[class*="st-key-tal-agent-"] [data-testid="stCaptionContainer"] { padding:0; }
.tal-status-dot { display:inline-block; width:7px; height:7px; margin-right:6px; border-radius:50%; background:var(--tal-amber); vertical-align:1px; }
.tal-status-dot.ready { background:var(--tal-up); }
.tal-ficha { display:flex; align-items:center; flex-wrap:wrap; gap:10px 24px; padding:11px 15px; border:1px solid var(--tal-line); border-radius:9px; background:var(--tal-panel); }
.tal-ficha-who { display:flex; flex:1 1 190px; align-items:center; gap:11px; min-width:0; }
.tal-ficha-icon { display:grid; flex:none; width:42px; height:42px; place-items:center; border:1px solid var(--tal-line); border-radius:8px; background:#121923; color:var(--tal-agent-color); }
.tal-ficha-icon svg { width:28px; height:28px; }
.tal-ficha-name { font-size:18px; font-weight:800; font-stretch:112%; line-height:1.13; }
.tal-ficha-status { margin-top:3px; color:var(--tal-mute); font-size:11px; }
.tal-fact small { display:block; color:var(--tal-mute); font-size:11px; }
.tal-fact b { display:block; margin-top:1px; font-size:16px; font-weight:700; white-space:nowrap; }
.tal-room-head { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:7px 12px; }
.tal-room-head strong { font-size:13px; }
.tal-room-head span { color:var(--tal-mute); font-size:11px; }
.tal-floor-wrap { width:100%; overflow:visible; border:1px solid #202b3a; border-radius:9px; background:#0f151e; }
.tal-floor-wide svg { display:block; width:100%; min-width:0; max-height:none; height:auto; object-fit:contain; }
.tal-floor-compact { display:none; }
.tal-stage-caption { padding:6px 9px 0; color:var(--tal-mute); font-size:11px; }
.tal-view-title { margin:4px 0 2px; font-size:17px; font-weight:750; }
.tal-board { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:7px; }
.tal-board-item { padding:8px 10px; border:1px solid var(--tal-line); border-radius:7px; background:var(--tal-panel); }
.tal-board-item small { display:block; color:var(--tal-mute); font-size:10px; letter-spacing:.04em; text-transform:uppercase; }
.tal-board-item b { display:block; margin-top:3px; color:var(--tal-ink); font-size:12px; }
.tal-glance-head { display:flex; justify-content:space-between; align-items:baseline; gap:12px; margin:8px 0 5px; font-size:12px; }
.tal-glance-head strong { font-weight:750; }
.tal-glance-head span { color:var(--tal-mute); font-size:11px; }
.tal-glance-card { display:flex; align-items:center; gap:8px; min-height:58px; padding:8px 9px; border:1px solid var(--tal-line); border-radius:7px; background:var(--tal-panel); }
.tal-glance-mark { flex:none; width:8px; height:8px; border-radius:2px; background:var(--tal-agent-color); }
.tal-glance-copy { min-width:0; flex:1; }
.tal-glance-copy b { display:block; overflow:hidden; color:var(--tal-ink); font-size:11px; text-overflow:ellipsis; white-space:nowrap; }
.tal-glance-copy span { display:block; overflow:hidden; margin-top:2px; color:var(--tal-mute); font-size:10px; text-overflow:ellipsis; white-space:nowrap; }
.tal-director { margin-top:7px; padding:11px 13px; border:1px solid var(--tal-line); border-radius:8px; background:var(--tal-panel); }
.tal-director-head { display:flex; justify-content:space-between; gap:10px; align-items:baseline; }
.tal-director-head strong { font-size:13px; }
.tal-director-head span { color:var(--tal-mute); font-size:10px; }
.tal-director p { margin:5px 0 0; color:#cbd4df; font-size:12px; line-height:1.5; }
.tal-director ul { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:3px 16px; margin:7px 0 0; padding-left:18px; color:var(--tal-mute); font-size:11px; }
.tal-director li::marker { color:var(--tal-amber); }
.tal-pane-header { padding:11px 14px 6px; border-bottom:1px solid var(--tal-line); }
.tal-pane-header h2 { margin:0; font-size:15px; font-weight:750; }
.tal-pane-header p { margin:3px 0 6px; color:var(--tal-mute); font-size:11px; line-height:1.45; }
.tal-connection { display:flex; justify-content:space-between; gap:10px; align-items:center; padding:9px 12px; border-bottom:1px solid var(--tal-line); }
.tal-connection strong { display:block; font-size:12px; }
.tal-connection small { display:block; margin-top:2px; color:var(--tal-mute); font-size:10px; line-height:1.4; }
.tal-state { display:inline-flex; align-items:center; gap:5px; padding:4px 7px; border:1px solid var(--tal-line); border-radius:6px; color:var(--tal-mute); font-size:10px; white-space:nowrap; }
.tal-state:before { content:""; width:6px; height:6px; border:1px solid currentColor; border-radius:50%; }
.tal-state.safe { color:var(--tal-up); }
.tal-state.warn { color:var(--tal-amber); }
.tal-small { color:var(--tal-mute); font-size:10px; }
.tal-source { padding:8px 10px; border:1px solid var(--tal-line); border-radius:7px; background:var(--tal-panel); color:var(--tal-mute); font-size:11px; line-height:1.5; }
.tal-agent-detail { padding:10px 12px; }
.tal-agent-detail h2 { margin:0; font-size:14px; }
.tal-wall-head { display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:.8rem; }
.tal-metric { padding:9px 10px; border:1px solid var(--tal-line); border-radius:7px; background:var(--tal-panel); }
.tal-metric small { color:var(--tal-mute); font-size:10px; }
.tal-metric strong { display:block; margin-top:2px; font-size:18px; font-weight:700; }
.tal-metric span { color:var(--tal-mute); font-size:10px; }
.tal-board-item { font-variant-numeric:tabular-nums; }
div[data-testid="stButton"] > button { min-height:42px; border-radius:6px; border-color:var(--tal-line); background:var(--tal-panel); color:var(--tal-ink); font-family:Archivo,"Segoe UI",sans-serif; }
div[data-testid="stButton"] > button[kind="primary"] { border-color:var(--tal-amber-dark); background:var(--tal-amber-dark); color:#160f05; }
div[data-testid="stButton"] > button:focus-visible, input:focus-visible, textarea:focus-visible { outline:2px solid var(--tal-amber); outline-offset:2px; }
[data-testid="stAlert"] { border-radius:7px; }
[data-testid="stDataFrame"] { border:1px solid var(--tal-line); border-radius:7px; }
[data-testid="stExpander"] { border-color:var(--tal-line); border-radius:7px; background:var(--tal-panel); }
[data-testid="stTabs"] [role="tablist"] { gap:4px; border-bottom:1px solid var(--tal-line); }
[data-testid="stTabs"] button[role="tab"] { min-height:38px; padding:5px 9px; color:var(--tal-mute); font-size:11px; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color:var(--tal-ink); border-bottom-color:var(--tal-amber); }
a { color:var(--tal-amber); }
::selection { background:#8c5a1a; color:#fff; }
@media(max-width:1100px) {
  .tal-topbar { flex-wrap:wrap; gap:9px 18px; }
  .tal-pills { margin-left:0; justify-content:flex-start; }
  .tal-kpis { gap:8px 17px; }
  .tal-glance-card { min-height:54px; }
}
@media(max-width:860px) {
  [data-testid="stMainBlockContainer"] { padding-top:0; }
  .st-key-tal-layout > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] { flex-direction:column-reverse !important; }
  .st-key-tal-layout [data-testid="column"] { width:100% !important; flex:1 1 100% !important; min-width:0 !important; }
  .st-key-tal-side { min-height:0; border-top:1px solid var(--tal-line); border-right:0; }
  .st-key-tal-stage { padding:8px 0 16px; }
  .tal-ficha { gap:8px 14px; }
  .tal-kpis { flex:1 1 100%; order:3; }
  .tal-brand { flex:1 1 58%; }
  .tal-pills { flex:1 1 auto; order:4; }
  .tal-director ul { grid-template-columns:1fr; }
}
@media(max-width:760px) {
  .st-key-tal-header { padding:10px 12px; }
  .tal-topbar { gap:8px 10px; }
  .tal-brand b { font-size:18px; }
  .tal-brand span { font-size:11px; }
  .tal-kpis { gap:6px 13px; }
  .tal-kpi strong { font-size:16px; }
  .tal-kpi small { font-size:10px; }
  .tal-pill { padding:4px 7px; font-size:10px; }
  .st-key-tal-layout { padding:0 8px; }
  .st-key-tal-nav { position:fixed; z-index:100; right:0; bottom:0; left:0; padding:5px 4px calc(5px + env(safe-area-inset-bottom)); border-top:1px solid var(--tal-line); border-bottom:0; background:var(--tal-panel); }
  .st-key-tal-nav [role="radiogroup"] { flex-wrap:nowrap; justify-content:space-around; gap:0; }
  .st-key-tal-nav label[data-baseweb="radio"] { flex:1 1 20%; justify-content:center; min-height:48px; padding:7px 3px; font-size:11px; text-align:center; }
  .st-key-tal-stage { padding-bottom:16px; }
  .tal-board { grid-template-columns:1fr; }
  .tal-floor-wide { display:none; }
  .tal-floor-compact { display:block; width:100%; }
  .tal-floor-compact svg { display:block; width:100%; height:auto; min-width:0; }
  .tal-pills { gap:5px; }
}
@media(prefers-reduced-motion:reduce) { *,*:before,*:after { scroll-behavior:auto !important; animation:none !important; transition:none !important; } }
</style>
""", unsafe_allow_html=True)


def esc(value):
    return html.escape(str(value or ""))


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def agent_svg(agent_name):
    paths = {
        "book": '<path d="M12 7v14m0-14C10.5 6 8.5 5 5 5H3v14h3c2.5 0 4 .6 6 2m0-14c1.5-1 3.5-2 7-2h2v14h-3c-2.5 0-4 .6-6 2"/><path d="m15 12 2 2 4-4"/>',
        "chart": '<path d="M4 20V4m0 16h17"/><path d="M7 15h3v3H7zm5-7h3v10h-3zm5 3h3v7h-3z"/>',
        "news": '<path d="M5 4h14v17H5z"/><path d="M8 8h8M8 12h8M8 16h4"/><path d="M3 7v12a2 2 0 0 0 2 2"/>',
        "flask": '<path d="M9 3h6m-5 0v7l-5.8 8.2A2.3 2.3 0 0 0 6.1 22h11.8a2.3 2.3 0 0 0 1.9-3.8L14 10V3"/><path d="M8 16h8"/>',
        "shield": '<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11z"/><path d="m9 12 2 2 4-4"/>',
        "route": '<circle cx="6" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 6h4a4 4 0 0 1 4 4v4a4 4 0 0 0 4 4"/><path d="M8 18h2"/>',
    }
    icon = AGENT_ICONS.get(agent_name, "book")
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[icon]}</svg>'


def header(title, description, status="Ambiente local"):
    st.markdown(
        f'<div class="tal-pane-header"><h2>{esc(title)}</h2><p>{esc(description)}</p>'
        f'<span class="tal-state">{esc(status)}</span></div>', unsafe_allow_html=True
    )


def current_crypto_feeds():
    now = datetime.now(timezone.utc)
    active = []
    for feed in store.list_market_feeds():
        if feed["provider"] != market_data.PROVIDER or feed["status"] != "connected" or not feed["last_bar_at"]:
            continue
        checked = datetime.fromisoformat(feed["checked_at"] + "+00:00")
        bar_time = datetime.fromisoformat(feed["last_bar_at"].replace("Z", "+00:00"))
        if (now - checked).total_seconds() < 120 and (now - bar_time).total_seconds() < 180:
            active.append(feed)
    return active


def topbar(agents, counts):
    indexed = sum(item["status"] == "indexed" for item in store.list_documents())
    live_count = len(current_crypto_feeds())
    values = [
        ("Agentes", str(len(agents))),
        ("PDFs no índice", str(indexed)),
        ("Tarefas", str(counts["agent_runs"])),
        ("Eventos", str(counts["events"])),
        ("Feeds cripto", f"{live_count} / 2"),
    ]
    metrics = "".join(
        f'<div class="tal-kpi"><small>{esc(label)}</small><strong>{esc(value)}</strong></div>'
        for label, value in values
    )
    st.markdown(
        '<div class="tal-topbar"><div class="tal-brand"><b>Trading Agent Lab</b>'
        '<span>Escritório de pesquisa · simulação local</span></div>'
        f'<div class="tal-kpis">{metrics}</div>'
        f'<div class="tal-pills"><span class="tal-pill warn">● {"Candles cripto atuais" if live_count else "Sem feed de mercado atual"}</span>'
        '<span class="tal-pill safe">Ordens reais bloqueadas</span>'
        '<span class="tal-pill">Modo simulação</span></div></div>',
        unsafe_allow_html=True,
    )


def _svg_icon(agent_name, x, y, size=24):
    svg = agent_svg(agent_name)
    body = svg.split(">", 1)[1].rsplit("</svg>", 1)[0]
    color = AGENT_COLORS.get(agent_name, "#7fb4ff")
    return (f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{body}</svg>')


def room_svg(agents, counts, events, room):
    execution = room == "Execução"
    members = [a for a in agents if (a["name"] == "Execution Agent") == execution]
    positions = [(250, 220), (480, 220), (710, 220), (365, 405), (595, 405)]
    svg = [
        '<svg viewBox="0 0 960 590" role="img" aria-label="'
        f'Escritório isométrico: sala de {esc(room.lower())}, mesas e quadro de evidências locais">',
        '<defs><linearGradient id="tal-left-wall" x1="0" y1="0" x2="1" y2="1">'
        '<stop stop-color="#1d2837"/><stop offset="1" stop-color="#243245"/></linearGradient>'
        '<linearGradient id="tal-right-wall" x1="0" y1="0" x2="1" y2="1">'
        '<stop stop-color="#30214f"/><stop offset="1" stop-color="#19142d"/></linearGradient>'
        '<linearGradient id="tal-floor" x1="0" y1="0" x2="0" y2="1">'
        '<stop stop-color="#2b2145"/><stop offset="1" stop-color="#121923"/></linearGradient>'
        '</defs><rect width="960" height="590" fill="#0f151e"/>',
        '<path d="M36 255 480 48v282L36 492z" fill="url(#tal-left-wall)" stroke="#34445a"/>'
        '<path d="m480 48 444 207v237L480 330z" fill="url(#tal-right-wall)" stroke="#34445a"/>'
        '<path d="M36 492 480 330l444 162-444 82z" fill="url(#tal-floor)" stroke="#34445a"/>',
        '<g opacity=".3" stroke="#2e3e56" stroke-width="1">'
        '<path d="m140 454 443 160M245 416l444 162M350 378l444 162M455 339l444 162"/>'
        '<path d="m155 536 314-208M275 580l393-262M405 590l394-260M540 590l330-218"/>'
        '</g>',
    ]

    if execution:
        panels = [(65, 98, "PROPOSTAS", "RECEPÇÃO DESLIGADA"),
                  (710, 276, "GESTÃO DE RISCO", "REVISÃO HUMANA"),
                  (390, 68, "ORDENS", "BLOQUEADAS")]
    else:
        panels = [(65, 365, "DOCUMENTOS", f"{counts['documents']} REGISTRADOS"),
                  (710, 365, "MERCADO", "SEM FEED"),
                  (390, 68, "ESTADO DO LAB", "DADOS LOCAIS")]
    for x, y, title, value in panels:
        svg.append(
            f'<g><rect x="{x}" y="{y}" width="190" height="72" rx="6" fill="#121923" '
            f'stroke="#33415a"/><path d="M{x+13} {y+15}h20" stroke="#f0a43a" stroke-width="2"/>'
            f'<text x="{x+14}" y="{y+33}" fill="#8d9aab" font-size="9" font-family="Archivo">{esc(title)}</text>'
            f'<text x="{x+14}" y="{y+55}" fill="#e9eef4" font-size="11" font-weight="700" font-family="Archivo">{esc(value)}</text></g>'
        )

    if execution:
        analyst_names = [a["name"] for a in agents if a["name"] != "Execution Agent"]
        for index, name in enumerate(analyst_names):
            y = 180 + index * 42
            svg.append(f'<circle cx="115" cy="{y}" r="6" fill="#f0a43a" fill-opacity=".55"/>')
            svg.append(f'<text x="132" y="{y+4}" fill="#aab7c7" font-size="11" font-family="Archivo">{esc(name)}</text>')
            svg.append(f'<path d="M240 {y} C330 {y} 345 320 420 340" fill="none" stroke="#71839a" stroke-width="1" stroke-dasharray="4 6" opacity=".45"/>')
        svg.append('<text x="78" y="156" fill="#9aa8ba" font-size="9" letter-spacing="1.1" font-family="Archivo">FLUXO PREVISTO · INATIVO</text>')

    def station(agent, center_x, center_y, index):
        accent = AGENT_COLORS.get(agent["name"], "#7fb4ff")
        name = esc(agent["name"])
        state = esc(agent["status"])
        screen_state = {
            "Aguardando documentos": "DOCS PENDENTES",
            "Aguardando dados": "DADOS PENDENTES",
            "Aguardando setups": "SETUPS PENDENTES",
            "Limites pendentes de revisão": "LIMITES PENDENTES",
            "Simulação local apenas": "SIMULAÇÃO LOCAL",
        }.get(agent["status"], "ESTADO LOCAL")
        width = 188
        left = center_x - width / 2
        table_top = center_y + 15
        result = [
            f'<g class="tal-svg-station" aria-label="{name}: {state}">',
            f'<path d="M{center_x-58} {center_y+8}v28m116-28v28" stroke="#53647a" stroke-width="3"/>',
            f'<path d="M{center_x-84} {table_top} {center_x} {center_y-15} {center_x+84} {table_top} {center_x} {center_y+52}z" fill="#76569c" stroke="#c39af2" stroke-width="1.5"/>',
            f'<path d="M{center_x-84} {table_top}v15l84 39v-17zM{center_x+84} {table_top}v15l-84 37v-17z" fill="#493461" stroke="#342447"/>',
            f'<rect x="{center_x-38}" y="{center_y-72}" width="76" height="49" rx="4" fill="#0b1118" stroke="#60738b" stroke-width="1.2"/>',
            f'<rect x="{center_x-32}" y="{center_y-66}" width="64" height="36" rx="2" fill="#121d29"/>',
            f'<path d="M{center_x-10} {center_y-22}h20l5 7h-30z" fill="#64768c"/>',
            f'<circle cx="{center_x-20}" cy="{center_y-54}" r="3" fill="{accent}"/>',
            f'<text x="{center_x-11}" y="{center_y-51}" fill="#b7c4d4" font-size="7" letter-spacing=".7" font-family="Archivo">LOCAL</text>',
            f'<text x="{center_x-39}" y="{center_y-37}" fill="#f0a43a" font-size="7" font-weight="700" font-family="Archivo">{esc(screen_state)}</text>',
            f'<circle cx="{center_x+70}" cy="{center_y+8}" r="16" fill="#121923" stroke="{accent}" stroke-opacity=".75"/>',
            _svg_icon(agent["name"], center_x+58, center_y-4, 24),
            f'<rect x="{left}" y="{center_y+79}" width="{width}" height="44" rx="5" fill="#131c28" stroke="#35465b"/>',
            f'<rect x="{left}" y="{center_y+79}" width="3" height="44" rx="1" fill="{accent}"/>',
            f'<text x="{left+12}" y="{center_y+96}" fill="#e9eef4" font-size="11" font-weight="700" font-family="Archivo">{name}</text>',
            f'<text x="{left+12}" y="{center_y+113}" fill="#9aa8ba" font-size="9" font-family="Archivo">{state}</text>',
            f'<text x="{left+width-12}" y="{center_y+98}" text-anchor="end" fill="{accent}" font-size="8" font-weight="700" font-family="Archivo">{index:02d}</text>',
            '</g>',
        ]
        return "".join(result)

    if execution and members:
        svg.append(station(members[0], 520, 325, 1))
    elif members:
        for index, agent in enumerate(members):
            center_x, center_y = positions[index]
            svg.append(station(agent, center_x, center_y, index + 1))

    recent = events[0] if events else None
    ticker = (f"{recent['Agente']} · {recent['Atividade']}" if recent
              else "AGUARDANDO REGISTRO DE ATIVIDADE")
    svg.append('<path d="M36 566h888" stroke="#2a3648"/>')
    svg.append(f'<circle cx="54" cy="578" r="3" fill="#f0a43a"/>')
    svg.append(f'<text x="65" y="582" fill="#9aa8ba" font-size="9" font-family="Archivo">{esc(ticker[:125])}</text>')
    svg.append('</svg>')
    return "".join(svg)


def room_svg_compact(agents, counts, events, room):
    execution = room == "Execução"
    members = [a for a in agents if (a["name"] == "Execution Agent") == execution]
    recent = events[0] if events else None
    event_time = str(recent.get("Horário", "Horário não informado"))[:16] if recent else "Sem eventos registrados"
    event_actor = recent.get("Agente", "Sistema") if recent else "Sistema"
    risk = next((a["status"] for a in agents if a["name"] == "Risk Manager"), "Estado não cadastrado")
    title = "Sala de execução" if execution else "Sala de analistas"
    slots = [(16, 210), (198, 210), (16, 296), (198, 296), (16, 382), (198, 382)]
    svg = [
        '<svg viewBox="0 0 390 536" role="img" aria-label="'
        f'Escritório compacto: {esc(title)}, estado, evento e mesas">',
        '<rect width="390" height="536" fill="#0f151e"/>',
        '<rect x="8" y="8" width="374" height="164" rx="10" fill="#19222f" stroke="#33415a"/>',
        f'<text x="18" y="29" fill="#f0a43a" font-size="12" font-weight="800" font-family="Archivo">{esc(title.upper())}</text>',
        f'<text x="372" y="29" text-anchor="end" fill="#e9eef4" font-size="10" font-weight="700" font-family="Archivo">{len(members)} ESTAÇÕES</text>',
        f'<text x="18" y="48" fill="#e9eef4" font-size="11" font-weight="700" font-family="Archivo">{counts["agent_runs"]} tarefas · {counts["documents"]} documentos · {counts["events"]} eventos</text>',
        '<path d="M18 57h354" stroke="#33415a"/>',
        '<rect x="15" y="66" width="171" height="60" rx="6" fill="#121923" stroke="#33415a"/>',
        '<rect x="194" y="66" width="181" height="60" rx="6" fill="#121923" stroke="#33415a"/>',
        f'<text x="25" y="82" fill="#9aa8ba" font-size="8" font-family="Archivo">ÚLTIMO EVENTO · {esc(event_time)}</text>',
        f'<text x="25" y="101" fill="#e9eef4" font-size="10" font-weight="700" font-family="Archivo">{esc(event_actor[:24])}</text>',
        f'<text x="204" y="82" fill="#9aa8ba" font-size="8" font-family="Archivo">ESTADO DE RISCO</text>',
        f'<text x="204" y="101" fill="#f0a43a" font-size="9" font-weight="700" font-family="Archivo">{esc(risk[:31])}</text>',
        '<text x="18" y="148" fill="#aab8c8" font-size="9" font-family="Archivo">Mercado sem feed · ordens reais bloqueadas</text>',
        f'<text x="16" y="193" fill="#aab8c8" font-size="9" letter-spacing="1" font-family="Archivo">{esc(title.upper())}</text>',
        '<path d="M8 201 195 188 382 201v283L195 507 8 484z" fill="#26344a" stroke="#33415a"/>',
        '<path d="M18 294h354M18 380h354" stroke="#34465f" opacity=".7"/>',
    ]

    for index, agent in enumerate(members):
        if execution:
            x, y = 107, 295
        else:
            x, y = slots[index]
        color = AGENT_COLORS.get(agent["name"], "#7fb4ff")
        state = agent["status"]
        status_lines = []
        current_line = ""
        for word in state.split():
            candidate = f"{current_line} {word}".strip()
            if len(candidate) > 24 and current_line:
                status_lines.append(current_line)
                current_line = word
            else:
                current_line = candidate
        if current_line:
            status_lines.append(current_line)
        svg.extend([
            f'<g class="tal-svg-station" aria-label="{esc(agent["name"])}: {esc(state)}">',
            f'<rect x="{x}" y="{y}" width="176" height="72" rx="7" fill="#131c28" stroke="{color}" stroke-opacity=".8"/>',
            f'<rect x="{x}" y="{y}" width="4" height="72" rx="2" fill="{color}"/>',
            f'<circle cx="{x+17}" cy="{y+17}" r="4" fill="{color}"/>',
            f'<text x="{x+28}" y="{y+22}" fill="#e9eef4" font-size="11.5" font-weight="700" font-family="Archivo">{esc(agent["name"])}</text>',
            f'<text x="{x+12}" y="{y+44}" fill="#aab8c8" font-size="9.5" font-family="Archivo">{esc(status_lines[0]) if status_lines else ""}</text>',
            f'<text x="{x+12}" y="{y+59}" fill="{color}" font-size="9" font-weight="700" font-family="Archivo">{esc(status_lines[1]) if len(status_lines) > 1 else "Estado local"}</text>',
            '</g>',
        ])

    ticker = (f'{recent.get("Agente", "Sistema")} · {recent.get("Atividade", "")}' if recent
              else "Nenhuma atividade registrada no SQLite")
    svg.extend([
        '<path d="M16 496h358" stroke="#2a3648"/>',
        '<circle cx="22" cy="515" r="3" fill="#f0a43a"/>',
        f'<text x="32" y="519" fill="#9aa8ba" font-size="8.5" font-family="Archivo">{esc(ticker[:70])}</text>',
        '</svg>',
    ])
    return "".join(svg)


def render_agent_profile(agent):
    color = AGENT_COLORS.get(agent["name"], "#7fb4ff")
    runs = store.list_agent_runs(agent["name"], limit=1000)
    memories = store.list_memories(agent["name"], include_pending=False)
    reviews = store.list_reviews(agent["name"])
    pending_reviews = sum(review["status"] == "open" for review in reviews)
    excerpts = store.get_document_context(agent["name"], limit=100)
    facts = [
        ("Execuções", str(len(runs))),
        ("Trechos disponíveis", str(len(excerpts))),
        ("Memórias aprovadas", str(len(memories))),
        ("Revisões abertas", str(pending_reviews)),
    ]
    fact_html = "".join(f'<div class="tal-fact"><small>{label}</small><b>{value}</b></div>' for label, value in facts)
    st.markdown(
        f'<div class="tal-ficha" style="--tal-agent-color:{color}"><div class="tal-ficha-who">'
        f'<span class="tal-ficha-icon">{agent_svg(agent["name"])}</span><span><span class="tal-ficha-name">{esc(agent["name"])}</span>'
        f'<span class="tal-ficha-status"><i class="tal-status-dot"></i>{esc(agent["status"])} · {esc(agent["responsibility"])}</span></span>'
        f'</div>{fact_html}</div>', unsafe_allow_html=True,
    )


def page_rooms(agents, counts):
    if not agents:
        st.error("O banco local não retornou agentes.")
        return
    selected_name = st.session_state.get("selected_agent", agents[0]["name"])
    room_before_render = st.session_state.get("tal-room", "Analistas")
    if room_before_render == "Execução" and selected_name != "Execution Agent":
        selected_name = "Execution Agent"
        st.session_state.selected_agent = selected_name
    elif room_before_render == "Analistas" and selected_name == "Execution Agent":
        selected_name = next((a["name"] for a in agents if a["name"] != "Execution Agent"), agents[0]["name"])
        st.session_state.selected_agent = selected_name
    selected_agent = next((a for a in agents if a["name"] == selected_name), agents[0])
    render_agent_profile(selected_agent)
    with st.expander("Contexto, memória, revisões e tarefas do agente"):
        render_agent_detail(selected_agent)
    view = st.radio("Vista principal", STAGE_VIEWS, horizontal=True, key="tal-view", label_visibility="collapsed")
    if view == "Sala":
        room = st.radio("Sala", ["Analistas", "Execução"], horizontal=True, key="tal-room", label_visibility="collapsed")
        events = store.list_events(limit=100)
        st.markdown(
            f'<div class="tal-room-head"><strong>Sala de {esc(room.lower())}</strong>'
            f'<span>{"5 mesas de análise" if room == "Analistas" else "1 posto de execução · recepção bloqueada"}</span></div>'
            f'<div class="tal-floor-wrap"><div class="tal-floor-wide">{room_svg(agents, counts, events, room)}</div>'
            f'<div class="tal-floor-compact">{room_svg_compact(agents, counts, events, room)}</div></div>'
            '<div class="tal-stage-caption">Estados do SQLite local. Selecione uma mesa pela lista de agentes; nenhum feed ou ordem está ativo.</div>',
            unsafe_allow_html=True,
        )
        team = [a for a in agents if (a["name"] == "Execution Agent") == (room == "Execução")]
        st.markdown(
            f'<div class="tal-glance-head"><strong>Estado das mesas</strong>'
            f'<span>{len(team)} estações · {counts["agent_runs"]} tarefas registradas</span></div>',
            unsafe_allow_html=True,
        )
        glance_cols = st.columns(3)
        for index, agent in enumerate(team):
            runs = store.list_agent_runs(agent["name"], limit=1000)
            color = AGENT_COLORS.get(agent["name"], "#7fb4ff")
            with glance_cols[index % len(glance_cols)]:
                st.markdown(
                    f'<div class="tal-glance-card" style="--tal-agent-color:{color}"><i class="tal-glance-mark"></i>'
                    f'<span class="tal-glance-copy"><b>{esc(agent["name"])}</b>'
                    f'<span>{esc(agent["status"])} · {len(runs)} execuções registradas</span></span></div>',
                    unsafe_allow_html=True,
                )
        director_items = [
            f"{len(agents)} agentes cadastrados no banco local.",
            f"{counts['documents']} documentos indexados; {counts['agent_runs']} tarefas de IA registradas.",
            "Fontes de mercado: desconectadas para criptoativos e ações dos EUA.",
            "Sala de execução isolada; ordens reais bloqueadas e sem envio de operações.",
        ]
        st.markdown(
            '<div class="tal-director"><div class="tal-director-head"><strong>Parte do diretor</strong>'
            '<span>Resumo determinístico do estado local · sem análise de mercado</span></div>'
            '<p>O laboratório mantém a atividade organizada e rastreável. A operação continua aguardando as conexões e os critérios de risco.</p>'
            f'<ul>{"".join(f"<li>{esc(item)}</li>" for item in director_items)}</ul></div>',
            unsafe_allow_html=True,
        )
    elif view == "Laboratório":
        st.markdown('<div class="tal-view-title">Laboratório de estratégias</div>', unsafe_allow_html=True)
        page_backtests(counts)
    else:
        st.markdown('<div class="tal-view-title">Evolução do capital</div>', unsafe_allow_html=True)
        page_capital()


def show_events(events):
    if not events:
        st.info("Ainda não há eventos neste filtro. As atividades aparecerão aqui depois de serem registradas.")
        return
    for event in events:
        created = event.get("Horário", event.get("created_at", ""))
        agent = event.get("Agente", event.get("agent", ""))
        level = event.get("Nível", event.get("level", ""))
        message = event.get("Atividade", event.get("message", ""))
        st.markdown(
            f'<div class="tal-connection"><div><strong>{esc(agent)} · {esc(level)}</strong>'
            f'<small>{esc(message)}</small></div><span class="tal-small">{esc(created)} UTC</span></div>',
            unsafe_allow_html=True,
        )


def render_agent_detail(agent):
    st.markdown('<div class="tal-agent-detail">', unsafe_allow_html=True)
    st.markdown(f"### {agent['name']}")
    st.caption(f"{agent['status']} · {agent['responsibility']}")
    overview, knowledge, memory, review, task_tab = st.tabs(
        ["Visão", "Conhecimento", "Memória", "Revisão", "Tarefa"]
    )
    with overview:
        st.markdown(
            '<div class="tal-source">Estado e histórico vêm do SQLite local. O agente só produzirá análise '
            'quando um provedor estiver configurado e a tarefa for iniciada explicitamente.</div>',
            unsafe_allow_html=True,
        )
        runs = store.list_agent_runs(agent["name"], limit=5)
        if runs:
            st.markdown("##### Execuções recentes")
            for run in runs:
                st.markdown(f"**{run['status']} · {run['created_at']}** — {esc(run['task'])}")
                if run["output"]:
                    with st.expander("Abrir resultado"):
                        st.write(run["output"])
        else:
            st.info("Nenhuma tarefa de IA foi executada para este agente.")
    with knowledge:
        if agent["name"] == "Research Agent":
            st.markdown("#### Conhecimento extraído para revisão")
            st.caption("Extração determinística local. Propostas não formalizam regra nem autorizam backtest ou operação.")
            if st.button("Extrair propostas dos PDFs indexados", key="extract-knowledge"):
                summary = knowledge_service.extract_proposals()
                store.add_event("Research Agent", "INFO",
                                f"Extração local concluída · {summary['items']} registros · {summary['proposed']} aguardam revisão")
                st.success(f"{summary['items']} registros rastreáveis; {summary['proposed']} aguardam revisão humana.")
                st.rerun()
            items = store.list_knowledge_items()
            if not items:
                st.info("Ainda não há propostas estruturadas. Execute a extração local para iniciar a revisão.")
            for item in items:
                citation = f"{item['source_path']} · p. {item['page_number']} · SHA-256 {item['source_sha256']}"
                with st.expander(f"{item['status'].upper()} · {item['kind'].title()} · {item['title']}"):
                    st.caption(citation)
                    st.write(item["evidence"])
                    if item["kind"] == "setup":
                        st.info("Descoberto na fonte; regras, gatilho, invalidação, custos e critérios ainda exigem formalização humana.")
                    if item["status"] == "proposed":
                        left, right = st.columns(2)
                        with left:
                            if st.button("Aprovar conhecimento", key=f"approve-knowledge-{item['id']}"):
                                store.review_knowledge_item(item["id"], True)
                                store.add_event("Usuário", "INFO", f"Conhecimento #{item['id']} aprovado para Research Agent")
                                st.rerun()
                        with right:
                            if st.button("Rejeitar proposta", key=f"reject-knowledge-{item['id']}"):
                                store.review_knowledge_item(item["id"], False)
                                store.add_event("Usuário", "INFO", f"Conhecimento #{item['id']} rejeitado para Research Agent")
                                st.rerun()
        docs, stale = documents.agent_context(agent["name"], limit=100)
        if stale:
            st.warning("Há arquivos sem índice atual, ainda não processados ou com falha. Eles não entram no contexto do agente: " + ", ".join(stale))
        st.caption(f"{len(docs)} trechos locais indexados disponíveis para este agente.")
        for item in docs[:20]:
            with st.expander(f"{item['filename']} · página {item['page_number']}"):
                st.write(item["content"])
        if not docs:
            st.info("Indexe a biblioteca em Controle para disponibilizar documentos com origem e página.")
    with memory:
        memories = store.list_memories(agent["name"])
        if memories:
            for memory in memories:
                st.markdown(f"**{memory['status'].upper()} · {memory['kind']}** — {memory['content']}")
                st.caption(f"Origem: {memory['source']} · {memory['created_at']}")
                if memory["status"] == "proposed":
                    approve, reject = st.columns(2)
                    with approve:
                        if st.button("Aprovar memória", key=f"approve-memory-{memory['id']}"):
                            store.review_memory(memory["id"], True)
                            store.add_event("Usuário", "INFO", f"Memória #{memory['id']} aprovada para {agent['name']}")
                            st.rerun()
                    with reject:
                        if st.button("Rejeitar", key=f"reject-memory-{memory['id']}"):
                            store.review_memory(memory["id"], False)
                            store.add_event("Usuário", "INFO", f"Memória #{memory['id']} rejeitada para {agent['name']}")
                            st.rerun()
        else:
            st.info("A memória começa vazia. Nenhuma lembrança foi criada automaticamente.")
        with st.form(f"memory-form-{slug(agent['name'])}"):
            content = st.text_area("Nova nota ou aprendizado proposto", max_chars=2000)
            source = st.text_input("Origem (evento, documento/página ou decisão)")
            if st.form_submit_button("Salvar como proposta"):
                if not content.strip() or not source.strip():
                    st.error("Informe o conteúdo e a origem para manter a trilha auditável.")
                else:
                    store.add_memory(agent["name"], "nota", content.strip(), source.strip())
                    store.add_event("Usuário", "INFO", f"Proposta de memória criada para {agent['name']}")
                    st.success("Proposta salva. Ela só entra no contexto depois da aprovação.")
                    st.rerun()
    with review:
        reviews = store.list_reviews(agent["name"])
        if reviews:
            for review in reviews:
                st.markdown(f"**{review['status'].upper()} · {review['created_at']}**")
                st.write(f"Observação: {review['observation']}")
                st.write(f"Hipótese: {review['hypothesis']}")
                st.write(f"Aprendizado proposto: {review['proposed_learning']}")
                if review["status"] == "open":
                    left, right = st.columns(2)
                    with left:
                        if st.button("Aprovar e memorizar", key=f"review-approve-{review['id']}"):
                            store.decide_review(review["id"], True)
                            store.add_event("Usuário", "INFO", f"Revisão #{review['id']} aprovada para {agent['name']}; aprendizado promovido")
                            st.rerun()
                    with right:
                        if st.button("Rejeitar proposta", key=f"review-reject-{review['id']}"):
                            store.decide_review(review["id"], False)
                            store.add_event("Usuário", "INFO", f"Revisão #{review['id']} rejeitada para {agent['name']}")
                            st.rerun()
        else:
            st.info("Sem revisões registradas. Correções futuras exigem evidência e aprovação humana.")
        with st.form(f"review-form-{slug(agent['name'])}"):
            observation = st.text_area("O que aconteceu?", max_chars=2000)
            hypothesis = st.text_area("Qual hipótese explica o erro?", max_chars=2000)
            learning = st.text_area("Qual aprendizado deve ser avaliado?", max_chars=2000)
            if st.form_submit_button("Registrar revisão"):
                if not all((observation.strip(), hypothesis.strip(), learning.strip())):
                    st.error("Preencha observação, hipótese e aprendizado proposto.")
                else:
                    review_id = store.add_review(agent["name"], observation.strip(), hypothesis.strip(), learning.strip())
                    store.add_event("Usuário", "INFO", f"Revisão de erro #{review_id} criada para {agent['name']}")
                    st.success("Revisão registrada; nenhuma regra foi alterada.")
                    st.rerun()
    with task_tab:
        config = provider_summary()
        if not config["configured"]:
            st.warning("Provedor de IA desconectado. Configure a conexão em Controle para habilitar tarefas.")
        with st.form(f"task-form-{slug(agent['name'])}"):
            task = st.text_area("Tarefa do agente", max_chars=4000,
                                placeholder="Especifique a pergunta e o período; nenhum dado de mercado será presumido.")
            include_docs = st.checkbox("Incluir trechos dos PDFs indexados")
            allow_context = st.checkbox("Autorizo enviar este contexto ao provedor configurado")
            submitted = st.form_submit_button("Executar tarefa", type="primary",
                                              disabled=not config["configured"])
        if submitted:
            try:
                with st.spinner(f"{agent['name']} está trabalhando na tarefa…"):
                    result = run_agent_task(agent["name"], task, include_docs, allow_context)
                st.success(f"Execução #{result['id']} concluída e registrada.")
                st.write(result["output"])
            except Exception as exc:
                st.error(f"A tarefa não foi concluída: {exc}")
    st.markdown("</div>", unsafe_allow_html=True)


def page_market():
    header("Mercado", "Cotações e análises só aparecem quando uma fonte verificável, com horário e cobertura, estiver conectada.", "SEM FEED")
    crypto, stocks = st.tabs(["Criptoativos", "Ações dos EUA"])
    for tab, title in ((crypto, "Criptoativos"), (stocks, "Ações dos EUA")):
        with tab:
            st.markdown(f"### {title}")
            st.info("Nenhuma fonte está conectada. Este painel não exibe cotações, candles, indicadores nem sinais de exemplo.")
            st.caption("Escolha e conecte um provedor em Controle; a integração será identificada por fonte e horário de atualização.")


def page_operations():
    header("Operações", "Histórico de paper trading conciliado. Eventos de sistema permanecem separados de operações financeiras.", "SEM OPERAÇÕES")
    operations = store.list_paper_operations()
    if operations:
        st.dataframe(operations, hide_index=True, width="stretch")
    else:
        st.info("Nenhuma operação simulada conciliada foi registrada. Eventos locais não são trades.")
    st.markdown("#### Eventos e trilha de atividade")
    show_events(store.list_events(limit=100))


def page_reports(counts):
    header("Informe", "Resumo factual do estado local. Conclusões analíticas só serão exibidas quando vierem de uma execução identificada.", "RELATÓRIO LOCAL")
    metrics = [("Agentes", "agents"), ("Documentos", "documents"),
               ("Tarefas IA", "agent_runs"), ("Revisões", "agent_reviews")]
    for offset in (0, 2):
        cols = st.columns(2)
        for col, (label, key) in zip(cols, metrics[offset:offset + 2]):
            with col:
                st.markdown(f'<div class="tal-metric"><small>{label}</small><strong>{counts[key]}</strong><span>registro SQLite</span></div>', unsafe_allow_html=True)
    st.markdown("#### Síntese do diretor")
    st.write("Os agentes e o histórico local estão disponíveis. Fontes de mercado e conexão de negociação não estão ativas. Nenhuma avaliação de desempenho ou recomendação é calculada sem esses insumos.")
    runs = store.list_agent_runs(limit=20)
    if runs:
        st.markdown("#### Resultados registrados")
        for run in runs:
            with st.expander(f"{run['agent']} · {run['status']} · {run['created_at']}"):
                st.write(run["task"])
                st.write(run["output"] or "Sem saída registrada.")
    st.markdown("#### Atividade recente")
    show_events(store.list_events(limit=20))


def page_controls():
    header("Controle", "Estado das proteções e bloqueios do ambiente. Esta tela não autoriza nem envia ordens.", "MODO LOCAL")
    rows = [
        ("Ordens reais", "Bloqueadas"), ("Conta XP Trader", "Não conectada"),
        ("Feed de mercado", f"{len(current_crypto_feeds())} / 2 cripto atuais; ações sem feed"), ("Validação de risco", "Limites aguardam configuração"),
        ("Promoção de aprendizado", "Aprovação humana obrigatória"),
        ("Credenciais", "Não armazenadas no SQLite"),
    ]
    for label, value in rows:
        st.markdown(f'<div class="tal-connection"><strong>{label}</strong><span class="tal-state">{value}</span></div>', unsafe_allow_html=True)
    st.warning("A sala de execução não prepara ordens. Compatibilidade e simulação do XP Trader 5.0.4.34 ainda precisam de validação técnica independente.")
    st.markdown("### Conexões e biblioteca local")
    page_connections()


def page_capital():
    operations = [item for item in store.list_paper_operations() if item["state"] == "closed" and item["exit_price"] is not None]
    if not operations:
        st.info("Ainda não há operações simuladas encerradas. Não exibimos saldo ou curva ilustrativa.")
        return
    realized = []
    cumulative = 0.0
    for operation in reversed(operations):
        direction = 1 if operation["side"] == "buy" else -1
        pnl = (operation["exit_price"] - operation["entry_price"]) * operation["quantity"] * direction - operation["fees"]
        cumulative += pnl
        realized.append({"Operação": operation["id"], "P&L realizado": pnl, "Acumulado realizado": cumulative})
    st.metric("P&L realizado acumulado", f"{cumulative:,.2f}", help="Não inclui saldo inicial, posições abertas ou custos não registrados.")
    st.line_chart([{ "operação": row["Operação"], "P&L realizado": row["Acumulado realizado"]} for row in realized], x="operação", y="P&L realizado")
    st.caption("Fonte: operações simuladas fechadas no SQLite. Não equivale ao saldo da conta.")


def page_connections():
    library = documents.library_status()
    st.markdown("### Biblioteca de PDFs")
    st.markdown(f'<div class="tal-connection"><div><strong>{len(library)} arquivos encontrados</strong><small>Originais lidos somente localmente; contexto para IA exige autorização explícita por tarefa.</small></div><span class="tal-state">{sum(1 for item in library if item["status"] == "indexed")} atualizados</span></div>', unsafe_allow_html=True)
    if library:
        if st.button("Indexar PDFs locais", type="primary"):
            with st.spinner("Extraindo texto local e preservando página e hash..."):
                results = documents.index_library()
            for result in results:
                if result["status"] == "failed":
                    st.error(f"{result['path']}: {result.get('error', 'falha ao indexar')}")
                else:
                    st.success(f"{result['path']} · {result['status']} · {result['pages']} páginas · {result['chunks']} trechos")
            st.rerun()
        for item in library:
            label = {"pending": "Aguardando indexação", "stale": "Índice desatualizado"}.get(item["status"], item["status"])
            error = item["record"].get("error") if item["record"] else None
            st.markdown(f'<div class="tal-connection"><div><strong>{esc(item["filename"])}</strong><small>{esc(item["path"])} · {item["bytes"]:,} bytes{f" · {esc(error)}" if error else ""}</small></div><span class="tal-state">{esc(label)}</span></div>', unsafe_allow_html=True)
    else:
        st.info("Adicione PDFs a reference_docs/shared/ ou reference_docs/agents/<slug>/.")
    st.markdown("### Provedor de IA")
    config = provider_summary()
    if config["configured"]:
        st.success(f"Conector compatível configurado · modelo {esc(config['model'])} · chave {'presente' if config['api_key_present'] else 'não necessária para serviço local'}.")
    else:
        st.warning("Provedor não configurado. Nenhuma chamada de IA será feita automaticamente.")
    st.code("TRADING_LAB_LLM_BASE_URL\nTRADING_LAB_LLM_MODEL\nTRADING_LAB_LLM_API_KEY (opcional para modelo local)", language="text")
    st.caption("A chamada só ocorre quando você inicia uma tarefa. Para incluir PDFs, o formulário exige autorização explícita de envio ao provedor configurado.")
    st.markdown("### Dados e plataforma")
    for name, detail in [
        ("Criptoativos", "Fonte de dados e cobertura ainda não escolhidas."),
        ("Ações dos EUA", "Fonte de dados e cobertura ainda não escolhidas."),
        ("XP Trader 5.0.4.34", "Integração não confirmada para esta licença e versão."),
    ]:
        st.markdown(f'<div class="tal-connection"><div><strong>{name}</strong><small>{detail}</small></div><span class="tal-state">Desconectado</span></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="tal-source">A Nelogica descreve a ProfitDLL como produto licenciado separado para aplicações externas. A documentação pública consultada lista cobertura BM&amp;F/Bovespa; não confirma suporte à licença XP Trader 5.0.4.34 nem a criptoativos ou ações dos EUA. Consulte a <a href="https://ajuda.nelogica.com.br/hc/pt-br/articles/11166353435035-Introdu%C3%A7%C3%A3o-ao-Produto-DLL-Real-Time" target="_blank" rel="noopener">documentação oficial da ProfitDLL</a> e confirme a licença/SDK antes de integrar.
    </div>
    """, unsafe_allow_html=True)


def page_backtests(counts):
    st.markdown('<div class="tal-board">' + ''.join(
        f'<div class="tal-board-item"><small>{label}</small><b>{value}</b></div>'
        for label, value in [("DOCUMENTOS", f"{counts['documents']} registrados"),
                             ("ESTRATÉGIAS", f"{counts['strategies']} versionadas"),
                             ("EXECUÇÕES", f"{counts['backtests']} persistidas")]
    ) + '</div>', unsafe_allow_html=True)
    st.warning("Importe apenas dados cujo uso você está autorizado a fazer. O nome da fonte é declarado por você e não é validado pelo aplicativo.")
    with st.expander("Fonte pública BTC e ETH · Binance Spot"):
        st.caption("Importação explícita de até 1.000 candles fechados de 1 minuto via API pública. BTCUSDT e ETHUSDT são pares spot cotados em USDT; cada captura é um histórico imutável, não uma cotação ao vivo.")
        crypto_symbol = st.selectbox("Par", market_data.SYMBOLS)
        if st.button("Buscar e validar histórico público"):
            try:
                result = market_data.import_recent(crypto_symbol)
                st.success(f"Dataset #{result['id']} · {result['metadata']['row_count']} barras · SHA-256 {result['sha256']}")
                st.rerun()
            except Exception as exc:
                st.error(f"Falha na importação: {exc}")
        st.caption("Atualização contínua: execute `python -m services.market_data stream` em um processo local supervisionado. O estado abaixo reflete apenas barras persistidas; sem processo ativo, fica atrasado ou desconectado.")
    with st.expander("Ações dos EUA · históricos públicos e Alpaca IEX"):
        st.caption("Amostra histórica pública sem conta: AAPL ou MSFT, barras horárias da Market History. A fonte atualiza historicamente e não oferece tempo real.")
        public_stock = st.selectbox("Ação para histórico público", market_data.STOCKS)
        if st.button("Buscar histórico público de ações"):
            try:
                result = market_data.import_public_stock_history(public_stock)
                st.success(f"Dataset #{result['id']} · {result['metadata']['row_count']} barras · SHA-256 {result['sha256']}")
                st.rerun()
            except Exception as exc:
                st.error(f"Falha na importação pública: {exc}")
        st.caption("AAPL e MSFT são candidatos. A fonte IEX cobre uma bolsa, não o mercado consolidado. A importação exige credenciais locais de dados da Alpaca; nenhuma chave é armazenada no SQLite ou digitada nesta página.")
        if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_API_SECRET"):
            st.info("Fonte não configurada. Defina ALPACA_API_KEY e ALPACA_API_SECRET no ambiente local para habilitar a importação.")
        else:
            stock_symbol = st.selectbox("Ação", market_data.STOCKS)
            from datetime import datetime, timedelta, timezone
            stock_end = datetime.now(timezone.utc).replace(microsecond=0)
            stock_start = stock_end - timedelta(days=3)
            if st.button("Buscar histórico IEX de três dias"):
                try:
                    result = market_data.import_alpaca_stock(stock_symbol, stock_start.isoformat(), stock_end.isoformat())
                    st.success(f"Dataset #{result['id']} · {result['metadata']['row_count']} barras · SHA-256 {result['sha256']}")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Falha na importação IEX: {exc}")
    feeds = store.list_market_feeds()
    if feeds:
        from datetime import datetime, timezone
        feed_rows = []
        for feed in feeds:
            last = feed["last_bar_at"]
            checked = datetime.fromisoformat(feed["checked_at"] + "+00:00")
            fresh = (datetime.now(timezone.utc) - checked).total_seconds() < 120
            feed_rows.append({"Fonte": feed["provider"], "Par": feed["symbol"],
                              "Estado": feed["status"] if fresh else "atrasado / processo inativo",
                              "Última barra UTC": last or "nenhuma",
                              "Última checagem UTC": feed["checked_at"]})
        st.dataframe(feed_rows, hide_index=True, width="stretch")
    with st.expander("Importar histórico OHLCV"):
        st.caption("CSV UTF-8 com timestamp UTC explícito, open, high, low, close e volume. Aceita cabeçalho Date/Datetime para timestamp.")
        with st.form("dataset-form"):
            upload = st.file_uploader("Arquivo CSV", type=["csv"])
            c1, c2 = st.columns(2)
            with c1:
                symbol = st.text_input("Símbolo", placeholder="Ex.: ativo informado no arquivo")
                timeframe = st.selectbox("Intervalo das barras", ["1m", "2m", "5m", "15m", "1h", "1d"])
            with c2:
                market = st.selectbox("Mercado", ["crypto", "us_equity"])
                source = st.text_input("Origem declarada", placeholder="Provedor ou arquivo de origem")
            c3, c4, c5 = st.columns(3)
            quote_currency = c3.text_input("Moeda de cotação", placeholder="USDT ou USD")
            tick_size = c4.text_input("Incremento mínimo", placeholder="0.01")
            volume_unit = c5.text_input("Unidade de volume", placeholder="BTC ou ações")
            license_note = st.text_input("Direito de uso / licença da fonte", placeholder="Descreva a autorização e o limite de uso")
            imported = st.form_submit_button("Validar e guardar histórico")
        if imported:
            if not upload:
                st.error("Selecione um CSV.")
            else:
                try:
                    result = dataset_service.import_csv(upload.getvalue(), upload.name, {
                        "symbol": symbol, "market": market, "provider": source,
                        "timeframe": timeframe, "timezone": "UTC",
                        "quote_currency": quote_currency, "tick_size": tick_size,
                        "volume_unit": volume_unit, "license_note": license_note,
                    })
                    store.add_event("Strategy & Backtest", "INFO", f"Histórico #{result['id']} importado · {symbol.strip()} · {result['metadata']['row_count']} barras · sha256:{result['sha256'][:16]}")
                    st.success(f"{result['metadata']['row_count']} barras validadas e guardadas. Fonte declarada: {source.strip()}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"O arquivo não foi guardado: {exc}")

    datasets = store.list_historical_datasets()
    if datasets:
        st.markdown("#### Históricos cadastrados")
        st.dataframe([{ "Símbolo": row["symbol"], "Intervalo": row["timeframe"],
                        "Origem declarada": row["source"], "Arquivo": row["filename"],
                        "Barras": row["row_count"],
                        "Início UTC": json.loads(row["metadata_json"]).get("start_utc", "legado"),
                        "Fim UTC": json.loads(row["metadata_json"]).get("end_utc", "legado"),
                        "Lacunas": json.loads(row["metadata_json"]).get("gap_count", "não avaliado"),
                        "SHA-256": row["sha256"][:16] + "…" }
                      for row in datasets], hide_index=True, width="stretch")
        selected_dataset = st.selectbox("Reproduzir histórico", datasets,
                                        format_func=lambda row: f"#{row['id']} · {row['symbol']} · {row['timeframe']}")
        if st.button("Verificar integridade e reproduzir"):
            try:
                restored = dataset_service.load_verified(selected_dataset["id"])
                st.success(f"Integridade verificada: {len(restored['bars'])} barras; hash canônico {selected_dataset['canonical_sha256'] or 'indisponível (legado)'}.")
                st.json(restored["metadata"])
                st.dataframe(restored["bars"], hide_index=True, width="stretch")
            except ValueError as exc:
                st.error(str(exc))

    st.markdown("#### Criar estratégia versionada")
    st.caption("Modelo disponível: cruzamento de médias móveis simples, posição comprada, sinal no fechamento e preenchimento na abertura seguinte. É um modelo mecânico, não uma recomendação nem um setup extraído dos PDFs.")
    with st.form("strategy-form"):
        name = st.text_input("Nome da estratégia")
        c1, c2, c3, c4 = st.columns(4)
        fast = c1.number_input("Janela rápida", min_value=2, max_value=500, value=5)
        slow = c2.number_input("Janela lenta", min_value=3, max_value=1000, value=20)
        fees = c3.number_input("Taxa por lado (bps)", min_value=0.0, value=0.0, step=0.1)
        slippage = c4.number_input("Slippage por lado (bps)", min_value=0.0, value=0.0, step=0.1)
        created = st.form_submit_button("Salvar como rascunho")
    if created:
        if not name.strip():
            st.error("Informe um nome para a estratégia.")
        elif slow <= fast:
            st.error("A janela lenta precisa ser maior que a rápida.")
        else:
            rules = {"engine": "sma_crossover_v1", "fast_window": int(fast),
                     "slow_window": int(slow), "fee_bps": fees, "slippage_bps": slippage,
                     "position": "long_only", "signal": "close_next_open"}
            strategy_id = store.save_strategy(name.strip(), rules, "configuração manual do usuário")
            store.add_event("Usuário", "INFO", f"Estratégia #{strategy_id} criada como rascunho")
            st.success("Rascunho salvo. Aprove a regra antes de executar um backtest.")
            st.rerun()

    strategies = store.list_strategies()
    if strategies:
        st.markdown("#### Estratégias e execução")
    for strategy in strategies:
        rules = json.loads(strategy["rules_json"])
        with st.container(border=True):
            st.markdown(f"**{strategy['name']} · v{strategy['version']}** · {strategy['status']}")
            is_setup = rules.get("engine") == "setup_pattern_v1"
            if is_setup:
                st.caption(f"{rules['setup_id']} · {rules['side']} · {', '.join(rules['timeframes'])} · {strategy['source']}")
                if strategy["status"] == "draft":
                    st.info("Versão em revisão dos parâmetros. A aprovação de conhecimento não autoriza backtest.")
                else:
                    st.info("Regras aprovadas para backtest. A execução exige histórico compatível, incremento mínimo e custos informados; o motor de backtest dos quatro setups vem na Entrega 5.")
                st.json({key: value for key, value in rules.items() if key not in {"source"}})
                for source in rules["source"]:
                    st.caption(f"Fonte: {source['path']} · páginas {', '.join(map(str, source['pages']))} · SHA-256 {source['sha256']}")
            else:
                st.caption(f"Regra {rules.get('engine')} · rápida {rules.get('fast_window')} / lenta {rules.get('slow_window')} · taxa {rules.get('fee_bps')} bps/lado · slippage {rules.get('slippage_bps')} bps/lado · {strategy['source']}")
            if strategy["status"] == "draft" and not is_setup:
                if st.button("Aprovar versão", key=f"approve-strategy-{strategy['id']}"):
                    store.approve_strategy(strategy["id"])
                    store.add_event("Usuário", "INFO", f"Estratégia #{strategy['id']} aprovada para backtest histórico")
                    st.rerun()
            elif strategy["status"] == "approved" and datasets and not is_setup:
                dataset = st.selectbox(
                    "Histórico para teste", datasets,
                    format_func=lambda item: f"{item['symbol']} · {item['timeframe']} · {item['filename']} · {item['row_count']} barras",
                    key=f"dataset-for-{strategy['id']}",
                )
                confirm_costs = st.checkbox(
                    "Confirmo as taxas e o slippage configurados, inclusive se forem zero",
                    key=f"confirm-costs-{strategy['id']}",
                )
                if st.button("Executar backtest", key=f"run-backtest-{strategy['id']}",
                             type="primary", disabled=not confirm_costs):
                    try:
                        bars = store.get_historical_bars(dataset["id"])
                        metrics = run_sma_crossover(
                            bars, rules["fast_window"], rules["slow_window"],
                            rules["fee_bps"], rules["slippage_bps"],
                        )
                        backtest_id = store.save_backtest(
                            strategy["id"], dataset["symbol"], dataset["timeframe"],
                            dataset["source"], dataset["sha256"], metrics,
                        )
                        store.add_event("Strategy & Backtest", "INFO", f"Backtest histórico #{backtest_id} concluído · {dataset['symbol']} · sha256:{dataset['sha256'][:16]}")
                        st.success(f"Backtest histórico #{backtest_id} concluído. Resultado persistido.")
                        st.json({key: value for key, value in metrics.items() if key != "trades"})
                    except Exception as exc:
                        store.add_event("Strategy & Backtest", "ERROR", f"Backtest falhou · {str(exc)[:250]}")
                        st.error(f"Backtest não concluído: {exc}")

    backtests = store.list_backtests()
    if backtests:
        st.markdown("#### Resultados históricos persistidos")
        for result in backtests:
            metrics = json.loads(result["metrics_json"])
            with st.expander(f"{result['symbol']} · {result['timeframe']} · {result['created_at']} · #{result['id']}"):
                st.caption(f"Origem declarada: {result['data_source']} · SHA-256: {result['data_sha256']}")
                st.json({key: value for key, value in metrics.items() if key != "trades"})
    st.markdown("#### Limites do cálculo")
    st.caption("Long-only, uma posição por vez, sem capital inicial, alavancagem, benchmark, dividendos ou cálculo anualizado. Taxas e slippage vêm dos campos informados; revise custos e qualidade do arquivo antes de interpretar. Backtest não prevê desempenho futuro.")


def local_lab_main():
    agents = store.get_agents()
    counts = store.counts()
    with st.container(key="tal-header"):
        topbar(agents, counts)
    with st.container(key="tal-layout"):
        side, stage = st.columns([0.94, 2.35], gap="small", vertical_alignment="top")
        with side:
            with st.container(key="tal-side"):
                panel = st.radio("Navegação", PANEL_PAGES, horizontal=True,
                                 label_visibility="collapsed", key="tal-nav")
                if panel == "Agentes":
                    header("Agentes", "Mesas especializadas · selecione um agente", f"{len(agents)} CADASTRADOS")
                    for agent in agents:
                        selected = st.session_state.get("selected_agent", agents[0]["name"] if agents else "") == agent["name"]
                        row_key = "tal-agent-current" if selected else f"tal-agent-{slug(agent['name'])}"
                        with st.container(key=row_key):
                            icon, body = st.columns([0.13, 0.87], vertical_alignment="center")
                            with icon:
                                st.markdown(
                                    f'<span class="tal-agent-icon" style="--tal-agent-color:{AGENT_COLORS.get(agent["name"], "#7fb4ff")}">{agent_svg(agent["name"])}</span>',
                                    unsafe_allow_html=True,
                                )
                            with body:
                                material = {"Research Agent": "menu_book", "Market Analyst": "monitoring",
                                            "Fundamental Analyst": "newspaper", "Strategy & Backtest": "science",
                                            "Risk Manager": "verified_user", "Execution Agent": "conversion_path"}.get(agent["name"], "smart_toy")
                                if st.button(agent["name"], key=f"select-{slug(agent['name'])}",
                                             icon=f":material/{material}:", width="stretch"):
                                    st.session_state.selected_agent = agent["name"]
                                    st.session_state["tal-room"] = "Execução" if agent["name"] == "Execution Agent" else "Analistas"
                                st.markdown(f'<div class="tal-agent-meta"><i class="tal-status-dot"></i>{esc(agent["status"])}</div>', unsafe_allow_html=True)
                    st.markdown("<div class='tal-pane-note'>Estados e atividade vêm do banco local. A cor identifica a mesa, não desempenho.</div>", unsafe_allow_html=True)
                elif panel == "Mercado":
                    page_market()
                elif panel == "Operações":
                    page_operations()
                elif panel == "Informe":
                    page_reports(counts)
                else:
                    page_controls()
        with stage:
            with st.container(key="tal-stage"):
                page_rooms(agents, counts)


def render_reference():
    source = Path(__file__).with_name("referencia.html")
    reference_html = source.read_text(encoding="utf-8")
    from datetime import datetime, timezone
    feed_snapshot = []
    for feed in store.list_market_feeds():
        last = store.get_market_bars(feed["provider"], feed["symbol"], feed["timeframe"], limit=1)
        checked = datetime.fromisoformat(feed["checked_at"] + "+00:00")
        bar_time = datetime.fromisoformat(feed["last_bar_at"].replace("Z", "+00:00")) if feed["last_bar_at"] else None
        current = (feed["status"] == "connected" and
                   (datetime.now(timezone.utc) - checked).total_seconds() < 120 and
                   bar_time is not None and
                   (datetime.now(timezone.utc) - bar_time).total_seconds() < 180)
        feed_snapshot.append({"symbol": feed["symbol"], "provider": feed["provider"],
                              "effective_status": "connected" if current else "atrasado ou desconectado",
                              "last_bar_at": feed["last_bar_at"],
                              "last_close": last[-1]["close"] if last else None})
    snapshot = {
        "agents": store.get_agents(),
        "counts": store.counts(),
        "documents": store.list_documents(),
        "events": store.list_events(limit=200),
        "connections": store.list_connections(),
        "market_feeds": feed_snapshot,
    }
    payload = json.dumps(snapshot, ensure_ascii=False).replace("</", "<\\/")
    reference_html = reference_html.replace('<html lang="es">', '<html lang="pt-BR">', 1)
    reference_html = reference_html.replace("<title>Oficina de agentes</title>", "<title>Trading Agent Lab</title>", 1)
    reference_html = reference_html.replace('<link rel="manifest" href="manifest.webmanifest">', "")
    reference_html = reference_html.replace('<link rel="icon" href="icon-192.png">', "")
    reference_html = reference_html.replace('<link rel="apple-touch-icon" href="icon-192.png">', "")
    reference_html = reference_html.replace('<div class="brand"><b>Oficina de agentes</b><span>Sala de operaciones con dinero ficticio</span></div>', '<div class="brand"><b>Trading Agent Lab</b><span>Central local de análise · somente simulação</span></div>')
    for spanish, portuguese in {
        ">Ranking<": ">Agentes<", ">Laboratorio<": ">Laboratório<",
        ">Operaciones<": ">Operações<", ">Control<": ">Controle<",
        ">Evolución del capital<": ">Evolução do capital<",
        'aria-label="Evolución del capital de cada agente"': 'aria-label="Evolução de capital registrada"',
        'aria-label="Sala de operaciones: un puesto por agente, panel del fondo y teletipo de operaciones"': 'aria-label="Sala de análise com uma mesa por agente e painel de atividade local"',
        'aria-label="Gráfico de velas en tiempo real"': 'aria-label="Gráfico de mercado indisponível sem fonte conectada"',
        "Desliza para ver toda la sala": "Deslize para ver todas as mesas",
    }.items():
        reference_html = reference_html.replace(spanish, portuguese)
    script_start = reference_html.index("<script>")
    script_end = reference_html.index("</script>", script_start) + len("</script>")
    local_scripts = (
        "<script>window.TAL_DATA=" + payload + ";</script>\n<script>"
        + LOCAL_PORTAL_SCRIPT + "\ninicializarLocal();</script>"
    )
    reference_html = reference_html[:script_start] + local_scripts + reference_html[script_end:]
    st.markdown("""
    <style>
      html, body, [data-testid="stAppViewContainer"], .stApp { margin:0!important; padding:0!important; overflow:hidden!important; background:#131a24!important; }
      [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display:none!important; }
      [data-testid="stMainBlockContainer"] { width:100vw!important; max-width:none!important; margin:0!important; padding:0!important; }
      [data-testid="stVerticalBlock"] { gap:0!important; }
      [data-testid="stElementContainer"] { margin:0!important; padding:0!important; }
      [data-testid="stIFrame"] { width:100vw!important; height:100vh!important; margin:0!important; padding:0!important; }
      [data-testid="stIFrame"] iframe { display:block!important; width:100vw!important; height:100vh!important; min-height:100vh!important; border:0!important; }
    </style>
    """, unsafe_allow_html=True)
    st.iframe(
        reference_html,
        width="stretch",
        height=1000,
        tab_index=0,
        alt="Trading Agent Lab, painel local de análise em simulação",
    )


def main():
    if st.query_params.get("lab") == "1":
        local_lab_main()
    else:
        render_reference()


if __name__ == "__main__":
    main()
