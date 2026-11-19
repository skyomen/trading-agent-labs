"""Local Streamlit shell for the Operations and Market pages."""

import html
import os
import time
from contextlib import nullcontext

import streamlit as st

from services.config import load_local_env, credential_context

load_local_env()

from database import store
from services import auth as auth_service
from services import credential_vault
import operations_page
import market_page

st.set_page_config(page_title="Operações · Trading Agent Lab", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
:root{color-scheme:dark;--tal-bg:#0b1426;--tal-panel:#13243b;--tal-panel2:#1a304c;--tal-line:#2d4662;--tal-ink:#e8f1ff;--tal-mute:#afbfda;--tal-amber:#76b9ff;--tal-amber-dark:#9dceff;--tal-up:#53ce9b;--tal-down:#f06ab8;--tal-blue:#76b9ff}
@font-face{font-family:Archivo;src:url("app/static/Archivo.woff2") format("woff2");font-style:normal;font-weight:400 800;font-display:swap}
html,body,.stApp,[data-testid="stAppViewContainer"]{background:var(--tal-bg);color:var(--tal-ink);font-family:Archivo,"Segoe UI",sans-serif;font-size:14px;overflow-x:hidden}
[data-testid="stMainBlockContainer"]{max-width:1510px;padding:2rem 2.5rem 8rem}
[data-testid="stSidebar"]{background:var(--tal-panel);border-right:1px solid var(--tal-line)}
[data-testid="stHeader"]{background:var(--tal-bg)}
[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stAppDeployButton"],[data-testid="stDeployButton"]{display:none!important}
[data-testid="stMarkdownContainer"],h1,h2,h3,h4{color:var(--tal-ink)}
h1,h2,h3{letter-spacing:-.025em}h1{font-size:1.8rem}h2{font-size:1.4rem}h3{font-size:1.15rem}
.tal-app-head{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;padding:0 0 1.25rem;border-bottom:1px solid var(--tal-line);margin-bottom:1.25rem}
.tal-app-head h1{margin:0;font-size:1.55rem}.tal-app-head p{margin:.35rem 0 0;color:var(--tal-mute);line-height:1.5}
.tal-safety{display:inline-flex;align-items:center;gap:.4rem;border:1px solid var(--tal-line);border-radius:999px;padding:.35rem .7rem;color:var(--tal-up);font-size:.8rem;font-weight:650;white-space:nowrap}
.tal-pane-header{display:flex;flex-wrap:wrap;align-items:baseline;gap:.4rem 1rem;margin:0 0 1.25rem}.tal-pane-header h2{margin:0}.tal-pane-header p{margin:0;color:var(--tal-mute);flex:1 1 20rem}.tal-state{font-size:.78rem;font-weight:700;color:var(--tal-mute)}.tal-state.warn{color:var(--tal-down)}.tal-state.safe{color:var(--tal-up)}
.tal-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.7rem;margin-bottom:1.5rem}.tal-summary>div{background:var(--tal-panel);border:1px solid var(--tal-line);border-radius:12px;padding:1rem}.tal-summary small{display:block;color:var(--tal-mute)}.tal-summary strong{display:block;margin-top:.35rem;font-size:1.35rem;font-weight:700;font-variant-numeric:tabular-nums}
.tal-connection{display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:.75rem 0;border-bottom:1px solid var(--tal-line)}.tal-connection>div{min-width:0}.tal-connection strong{font-size:.9rem}.tal-connection small{display:block;margin-top:.2rem;color:var(--tal-mute);overflow-wrap:anywhere}.tal-connection span{overflow-wrap:anywhere;text-align:right}
.tal-metric{padding:1rem;background:var(--tal-panel);border:1px solid var(--tal-line);border-radius:12px;margin-bottom:.75rem}.tal-metric small{display:block;color:var(--tal-mute)}.tal-metric strong{font-size:1.4rem}
.tal-agent-row{display:flex;justify-content:space-between;gap:1rem;padding:.8rem 0;border-bottom:1px solid var(--tal-line)}.tal-agent-row span{color:var(--tal-mute)}
.stButton button,.stFormSubmitButton button{min-height:42px}.stButton button:focus-visible,.stFormSubmitButton button:focus-visible{outline:2px solid var(--tal-amber);outline-offset:2px}
.stButton button,.stFormSubmitButton button{background:var(--tal-panel2)!important;color:var(--tal-ink)!important;border:1px solid var(--tal-line)!important;border-radius:8px!important}
.stButton button:hover,.stFormSubmitButton button:hover{border-color:var(--tal-up)!important;color:var(--tal-up)!important}
.stSelectbox .react-aria-ComboBox>div{background:var(--tal-panel)!important;color:var(--tal-ink)!important;border:1px solid var(--tal-line)!important;border-radius:8px!important}
.stSelectbox .react-aria-ComboBox input{color:var(--tal-ink)!important}
[data-testid="stDataFrame"],.stTabs{max-width:100%;min-width:0}*{box-sizing:border-box}::selection{background:var(--tal-amber);color:var(--tal-bg)}
[data-testid="stRadio"] [role="radiogroup"]{display:flex;flex-wrap:wrap;gap:.3rem 1rem}
@media(max-width:800px){[data-testid="stMainBlockContainer"]{padding:1.5rem 1rem 7rem}.tal-summary{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:480px){.tal-app-head{display:block}.tal-safety{margin-top:.8rem}.tal-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.tal-pane-header{display:block}.tal-pane-header p{margin:.5rem 0}.tal-pane-header .tal-state{display:block}.tal-agent-row{display:block}.tal-agent-row span{display:block;margin-top:.2rem}.tal-connection{align-items:flex-start;flex-direction:column;gap:.3rem}.tal-connection span{text-align:left}}
</style>
""",unsafe_allow_html=True)

st.markdown("""
<style>
.tal-bottom-nav{position:fixed;z-index:10000;left:50%;bottom:max(16px,env(safe-area-inset-bottom));transform:translateX(-50%);display:flex;gap:7px;padding:8px;border:1px solid rgba(190,220,255,.2);border-radius:24px;background:rgba(16,31,52,.68);backdrop-filter:blur(28px) saturate(175%);-webkit-backdrop-filter:blur(28px) saturate(175%);box-shadow:0 16px 50px rgba(0,0,0,.34),inset 0 1px rgba(255,255,255,.14)}
.tal-bottom-nav a{display:flex;align-items:center;gap:9px;min-height:48px;padding:0 18px;border-radius:16px;color:var(--tal-mute);font-weight:700;text-decoration:none;white-space:nowrap;transition:background .18s,color .18s,transform .18s}
.tal-bottom-nav a:hover{color:var(--tal-ink);background:rgba(150,190,245,.1);transform:translateY(-1px)}
.tal-bottom-nav a[aria-current="page"]{color:#e8f3ff;background:linear-gradient(135deg,rgba(77,151,232,.35),rgba(100,183,255,.13));box-shadow:inset 0 0 0 1px rgba(156,207,255,.22)}
.tal-bottom-nav .nav-icon{display:grid;place-items:center;width:21px;height:21px;color:#8fc9ff;font-size:19px;line-height:1}
.tal-bottom-nav a:focus-visible{outline:2px solid #9bd2ff;outline-offset:3px}
.market-hero{position:relative;isolation:isolate;display:flex;align-items:center;justify-content:space-between;min-height:126px;margin:0 0 1.1rem;padding:1.5rem 1.8rem;overflow:hidden;border:1px solid rgba(173,205,255,.15);border-radius:24px;background:radial-gradient(ellipse at 82% 45%,rgba(66,125,210,.24),transparent 40%),linear-gradient(112deg,#111c30 0%,#142540 56%,#172c4a 100%);box-shadow:0 16px 36px rgba(2,10,24,.16),inset 0 1px rgba(255,255,255,.07)}
.market-hero h1{position:relative;z-index:1;margin:0;color:#f4f8ff;font-size:2rem;font-weight:720;letter-spacing:-.045em}
.market-hero-art{position:absolute;z-index:0;right:8%;top:50%;width:180px;height:180px;transform:translateY(-50%);border:1px solid rgba(148,194,255,.16);border-radius:50%;background:radial-gradient(circle at 35% 32%,rgba(124,184,255,.16),transparent 56%);box-shadow:0 0 55px rgba(63,140,239,.13),inset 0 0 34px rgba(91,155,238,.08)}
.market-hero-art:before,.market-hero-art:after{position:absolute;content:"";border:1px solid rgba(153,199,255,.2);border-radius:50%;inset:21px;transform:rotate(-34deg) scaleX(.62)}
.market-hero-art:after{inset:44px;transform:rotate(38deg) scaleX(.7);border-color:rgba(107,173,255,.28)}
.market-hero-art i,.market-hero-art b{position:absolute;display:block;width:9px;height:9px;border-radius:50%;background:#9bd5ff;box-shadow:0 0 18px rgba(113,192,255,.85)}
.market-hero-art i{top:29px;right:36px}.market-hero-art b{bottom:39px;left:31px;width:6px;height:6px;background:#7d9eff}
@media(max-width:480px){.market-hero{min-height:108px;padding:1.2rem}.market-hero h1{font-size:1.75rem}.market-hero-art{right:-22px;width:138px;height:138px;opacity:.85}}
@media(max-width:480px){.tal-bottom-nav{width:calc(100% - 32px);justify-content:center;border-radius:22px}.tal-bottom-nav a{flex:1;justify-content:center;padding:0 12px;min-height:50px}}
</style>
""", unsafe_allow_html=True)

def esc(value):
    return html.escape("—" if value is None else str(value))


def _authenticate_ui():
    if os.environ.get("TRADING_LAB_ONLINE_MODE") != "1":
        owner = next((user for user in store.list_identity_users() if user["role"] == "owner"), None)
        return owner or {"id": None, "username": "local", "role": "owner"}
    actor = st.session_state.get("auth-user")
    key = st.session_state.get("vault-key")
    if actor and os.environ.get("TRADING_LAB_ONLINE_MODE") == "1":
        issued_at = st.session_state.get("auth-at", 0)
        if not isinstance(issued_at, (int, float)) or time.time() - issued_at > 8 * 3600:
            st.session_state.clear()
            actor, key = None, None
    if actor and isinstance(key, bytes):
        persisted = store.get_identity_user(user_id=actor.get("id"))
        if persisted and persisted["username"] == actor.get("username") and persisted["role"] == actor.get("role"):
            return actor
        st.session_state.pop("auth-user", None)
        st.session_state.pop("vault-key", None)
    st.title("Trading Agent Lab")
    st.caption("Portal de pesquisa em simulação · entre para abrir seu workspace.")
    first = store.identity_user_count() == 0
    if first and os.environ.get("TRADING_LAB_ONLINE_MODE") == "1":
        st.error("Acesso principal ainda não configurado. O administrador deve criá-lo no console do servidor.")
        return None
    with st.form("workspace-login"):
        username = st.text_input("Usuário", max_chars=32)
        password = st.text_input("Senha", type="password")
        confirmation = st.text_input("Confirme a senha", type="password") if first else None
        submitted = st.form_submit_button("Criar acesso principal" if first else "Entrar", type="primary")
    if submitted:
        try:
            if first:
                if password != confirmation:
                    raise ValueError("As senhas não coincidem.")
                result = auth_service.create_account(username, password, role="owner")
            else:
                result = auth_service.login(username, password)
            st.session_state["auth-user"] = {key: result[key] for key in ("id", "username", "role")}
            st.session_state["vault-key"] = result["vault_key"]
            st.session_state["auth-at"] = time.time()
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
    return None


def _workspace_sidebar(actor, credentials):
    if os.environ.get("TRADING_LAB_ONLINE_MODE") != "1":
        return
    with st.sidebar:
        st.caption("Trading Agent Lab")
        st.write(f"**{actor['username']}** · {'proprietário' if actor['role'] == 'owner' else 'usuário'}")
        if st.button("Sair", key="workspace-logout"):
            st.session_state.clear()
            st.rerun()
        if actor["role"] == "owner":
            with st.expander("Usuários"):
                for user in store.list_identity_users():
                    st.caption(f"{user['username']} · {user['role']}")
                with st.form("create-workspace-user"):
                    username = st.text_input("Novo usuário")
                    password = st.text_input("Senha inicial", type="password")
                    confirmation = st.text_input("Confirmar senha inicial", type="password")
                    create = st.form_submit_button("Criar workspace")
                if create:
                    try:
                        if password != confirmation:
                            raise ValueError("As senhas não coincidem.")
                        auth_service.create_account(username, password, actor=actor)
                        st.success("Workspace criado com seis agentes e histórico próprio.")
                        st.rerun()
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))
        with st.expander("Minhas credenciais"):
            providers = {
                "IA": ("TRADING_LAB_LLM_BASE_URL", "TRADING_LAB_LLM_MODEL", "TRADING_LAB_LLM_API_KEY"),
                "Alpaca IEX": ("ALPACA_API_KEY", "ALPACA_API_SECRET"),
                "Binance Spot Testnet": ("BINANCE_SPOT_TESTNET_API_KEY", "BINANCE_SPOT_TESTNET_API_SECRET"),
            }
            provider = st.selectbox("Serviço", list(providers), key="workspace-provider")
            fields = providers[provider]
            st.caption("Configurado: " + ("sim" if all(credentials.get(name) for name in fields[:2]) else "não"))
            if st.session_state.pop("vault-clear-inputs", False):
                for name in fields:
                    st.session_state.pop(f"vault-input-{provider}-{name}", None)
            with st.form(f"workspace-credentials-{provider}", clear_on_submit=True):
                values = {}
                for name in fields:
                    label = name.replace("TRADING_LAB_", "").replace("BINANCE_SPOT_TESTNET_", "")
                    values[name] = st.text_input(label, type="password" if "KEY" in name or "SECRET" in name else "default",
                                                 key=f"vault-input-{provider}-{name}")
                save = st.form_submit_button("Salvar campos preenchidos")
            if save:
                changes = {name: value for name, value in values.items() if value}
                if not changes:
                    st.warning("Preencha ao menos um campo.")
                else:
                    credential_vault.save_credentials(actor["id"], st.session_state["vault-key"], changes)
                    st.success("Credenciais salvas no seu cofre local.")
                    st.rerun()
            if st.button("Remover configuração deste serviço", key=f"vault-delete-{provider}"):
                credential_vault.save_credentials(actor["id"], st.session_state["vault-key"],
                                                  {name: "" for name in fields})
                st.session_state["vault-clear-inputs"] = True
                st.rerun()


def main():
    actor = _authenticate_ui()
    if actor is None:
        return
    local_mode = os.environ.get("TRADING_LAB_ONLINE_MODE") != "1"
    workspace = store.user_workspace(actor["id"]) if actor["id"] else nullcontext()
    with workspace:
        credentials = {} if local_mode else credential_vault.read_credentials(
            actor["id"], st.session_state["vault-key"])
        with credential_context(credentials):
            store.initialize()
            _workspace_sidebar(actor, credentials)
            try:
                store.record_heartbeat("app", "running")
            except Exception:
                pass  # Health reporting must not prevent access to the workspace.
            theme = st.session_state.get("tal-theme", "Escuro")
            if theme == "Claro":
                st.markdown("<style>:root{color-scheme:light;--tal-bg:#f4f7fc;--tal-panel:#fff;--tal-panel2:#edf3fc;--tal-line:#d8e3f2;--tal-ink:#1e2e48;--tal-mute:#637590;--tal-amber:#2f65ab;--tal-up:#277962;--tal-down:#b65785;--tal-blue:#2f65ab}</style>",
                            unsafe_allow_html=True)
            page = st.query_params.get("pagina", "operacoes")
            if page == "mercado":
                market_page.render()
            else:
                page = "operacoes"
                operations_page.render(actor)
            active_operations = ' aria-current="page"' if page == "operacoes" else ""
            active_market = ' aria-current="page"' if page == "mercado" else ""
            st.markdown(
                '<nav class="tal-bottom-nav" aria-label="Navegação principal">'
                f'<a href="?pagina=operacoes" target="_self"{active_operations}>'
                '<span class="nav-icon" aria-hidden="true">↗</span><span>Operações</span></a>'
                f'<a href="?pagina=mercado" target="_self"{active_market}>'
                '<span class="nav-icon" aria-hidden="true">⌕</span><span>Mercado</span></a>'
                '</nav>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
