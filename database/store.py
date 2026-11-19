import sqlite3
import json
import math
import os
import re
import secrets
from contextvars import ContextVar
from decimal import Decimal
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("TRADING_LAB_DATA_DIR", str(Path(__file__).resolve().parent))) / "trading.db"
IDENTITY_DB_PATH = DB_PATH.with_name("identity.db")
GLOBAL_DB_PATH = DB_PATH.with_name("global_knowledge.db")
WORKSPACES_DIR = DB_PATH.parent / "workspaces"
_workspace_path = ContextVar("workspace_path", default=None)
_active_user = ContextVar("active_user", default=None)

AGENTS = [
    ("Research Agent", "Aguardando documentos", "Extrai conceitos e setups dos PDFs."),
    ("Market Analyst", "Aguardando dados", "Analisa mercado quando houver feed conectado."),
    ("Fundamental Analyst", "Aguardando dados", "Analisa notícias, eventos e fundamentos."),
    ("Strategy & Backtest", "Aguardando setups", "Formaliza regras e executa backtests."),
    ("Risk Manager", "Limites pendentes de revisão", "Aguarda limites documentados; bloqueia propostas sem evidência e exige revisão humana."),
    ("Execution Agent", "Simulação local apenas", "Recebe propostas aprovadas; conector de negociação permanece bloqueado."),
]

@contextmanager
def connect():
    conn = sqlite3.connect(_workspace_path.get() or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def active_user_id():
    return _active_user.get()


@contextmanager
def _special_connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def backup_sqlite_file(source_path, target_path):
    """Create a consistent SQLite snapshot without copying WAL files directly."""
    source_path, target_path = Path(source_path), Path(target_path)
    if not source_path.is_file() or target_path.exists():
        raise ValueError("Origem indisponível ou destino de backup já existe.")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source_path)) as source, closing(sqlite3.connect(target_path)) as target:
        source.backup(target, pages=1000, sleep=0.05)
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Falha na integridade do snapshot SQLite.")


def initialize_identity():
    with _special_connect(IDENTITY_DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            role TEXT NOT NULL CHECK(role IN ('owner','user')),
            password_hash TEXT NOT NULL, vault_salt TEXT NOT NULL,
            failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_owner ON users(role) WHERE role='owner'")


def identity_user_count():
    initialize_identity()
    with _special_connect(IDENTITY_DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_identity_user(username=None, user_id=None):
    initialize_identity()
    with _special_connect(IDENTITY_DB_PATH) as conn:
        if username is not None:
            row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def list_identity_users():
    initialize_identity()
    with _special_connect(IDENTITY_DB_PATH) as conn:
        return [dict(row) for row in conn.execute(
            "SELECT id,username,role,created_at FROM users ORDER BY created_at,id").fetchall()]


def create_identity_user(username, password_hash, vault_salt, role="user"):
    initialize_identity()
    username = username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
        raise ValueError("Usuário deve ter 3 a 32 letras, números, ponto, hífen ou sublinhado.")
    if role not in {"owner", "user"}:
        raise ValueError("Papel de usuário inválido.")
    user_id = secrets.token_hex(16)
    with _special_connect(IDENTITY_DB_PATH) as conn:
        if role == "owner" and conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            raise ValueError("Proprietário já configurado.")
        if role == "user" and not conn.execute("SELECT 1 FROM users WHERE role='owner'").fetchone():
            raise ValueError("Configure o proprietário primeiro.")
        try:
            conn.execute("INSERT INTO users(id,username,role,password_hash,vault_salt) VALUES(?,?,?,?,?)",
                         (user_id, username, role, password_hash, vault_salt))
        except sqlite3.IntegrityError:
            raise ValueError("Nome de usuário indisponível.") from None
    if role == "user":
        with user_workspace(user_id):
            initialize()
    return user_id


def record_login_attempt(user_id, success):
    with _special_connect(IDENTITY_DB_PATH) as conn:
        if success:
            conn.execute("UPDATE users SET failed_attempts=0,locked_until=NULL WHERE id=?", (user_id,))
        else:
            conn.execute("""UPDATE users SET failed_attempts=failed_attempts+1,
                locked_until=CASE WHEN failed_attempts+1>=5 THEN datetime('now','+5 minutes')
                                  ELSE locked_until END WHERE id=?""", (user_id,))


@contextmanager
def user_workspace(user_id):
    user = get_identity_user(user_id=user_id)
    if not user:
        raise ValueError("Usuário desconhecido.")
    if user["role"] == "owner":
        path = DB_PATH
    else:
        WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
        path = WORKSPACES_DIR / f"{user['id']}.db"
    token_path = _workspace_path.set(path)
    token_user = _active_user.set(user["id"])
    try:
        yield user
    finally:
        _active_user.reset(token_user)
        _workspace_path.reset(token_path)


def initialize_global_knowledge():
    with _special_connect(GLOBAL_DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS global_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL, title TEXT NOT NULL, source_path TEXT NOT NULL,
            source_sha256 TEXT NOT NULL, page_number INTEGER NOT NULL,
            evidence TEXT NOT NULL, promoted_by TEXT NOT NULL,
            promoted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(kind,title,source_path,source_sha256,page_number))""")


def promote_global_knowledge(item, promoted_by):
    initialize_global_knowledge()
    with _special_connect(GLOBAL_DB_PATH) as conn:
        conn.execute("""INSERT OR IGNORE INTO global_knowledge
            (kind,title,source_path,source_sha256,page_number,evidence,promoted_by)
            VALUES(?,?,?,?,?,?,?)""",
            (item["kind"], item["title"], item["source_path"], item["source_sha256"],
             item["page_number"], item["evidence"], promoted_by))


def list_global_knowledge():
    initialize_global_knowledge()
    with _special_connect(GLOBAL_DB_PATH) as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM global_knowledge ORDER BY id DESC").fetchall()]

def initialize():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                responsibility TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                agent TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relative_path TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                status TEXT NOT NULL,
                page_count INTEGER NOT NULL DEFAULT 0,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                indexed_at TEXT,
                error TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                page_number INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                UNIQUE(document_id, page_number, chunk_index)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK(kind IN ('concept','setup')),
                title TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'proposed'
                    CHECK(status IN ('proposed','approved','rejected')),
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                evidence TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT,
                reviewed_by TEXT,
                UNIQUE(kind,title,version,source_path,page_number,source_sha256)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent TEXT NOT NULL,
                task TEXT NOT NULL,
                context_summary TEXT NOT NULL DEFAULT '',
                output TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'proposed'
                    CHECK(status IN ('proposed','approved','rejected')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT,
                reviewed_by TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER REFERENCES events(id),
                agent TEXT NOT NULL,
                observation TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                proposed_learning TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open'
                    CHECK(status IN ('open','approved','rejected')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                rules_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft'
                    CHECK(status IN ('draft','approved','archived')),
                source TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, version)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backtests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER REFERENCES strategies(id),
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                data_source TEXT NOT NULL,
                data_sha256 TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS validation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER REFERENCES strategies(id),
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                dataset_id INTEGER,
                data_sha256 TEXT NOT NULL,
                engine_version TEXT NOT NULL,
                holdout_fraction REAL NOT NULL,
                split_json TEXT NOT NULL DEFAULT '{}',
                cost_grid_json TEXT NOT NULL DEFAULT '{}',
                concentration_json TEXT NOT NULL DEFAULT '{}',
                report_json TEXT NOT NULL DEFAULT '{}',
                sample_adequacy TEXT NOT NULL
                    CHECK(sample_adequacy IN ('insuficiente','limitrofe','adequada')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS historical_datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                source TEXT NOT NULL,
                sha256 TEXT NOT NULL UNIQUE,
                row_count INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        dataset_columns = {row[1] for row in conn.execute("PRAGMA table_info(historical_datasets)")}
        if "metadata_json" not in dataset_columns:
            conn.execute("ALTER TABLE historical_datasets ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
        if "canonical_sha256" not in dataset_columns:
            conn.execute("ALTER TABLE historical_datasets ADD COLUMN canonical_sha256 TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS historical_bars (
                dataset_id INTEGER NOT NULL REFERENCES historical_datasets(id) ON DELETE CASCADE,
                timestamp TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                PRIMARY KEY(dataset_id,timestamp)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_bars (
                provider TEXT NOT NULL, symbol TEXT NOT NULL, timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL, open REAL NOT NULL, high REAL NOT NULL,
                low REAL NOT NULL, close REAL NOT NULL, volume REAL NOT NULL,
                received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(provider,symbol,timeframe,timestamp)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_feeds (
                provider TEXT NOT NULL, symbol TEXT NOT NULL, timeframe TEXT NOT NULL,
                status TEXT NOT NULL, last_bar_at TEXT, checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                error TEXT, PRIMARY KEY(provider,symbol,timeframe)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_version TEXT NOT NULL,
                strategy_id INTEGER REFERENCES strategies(id),
                setup_id TEXT NOT NULL, setup_name TEXT NOT NULL,
                symbol TEXT NOT NULL, timeframe TEXT NOT NULL,
                signal_bar_utc TEXT NOT NULL,
                risk_date_utc TEXT,
                decision TEXT NOT NULL CHECK(decision IN ('trade_candidate','no_trade')),
                risk_verdict TEXT NOT NULL CHECK(risk_verdict IN ('autorizado','negado','nao_avaliado')),
                risk_decided_at TEXT,
                denial_reasons_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'avaliado' CHECK(status IN (
                    'sem_oportunidade','entrada_nao_acionada','avaliado',
                    'aguardando_quantidade','posicao_aberta','descartado_pelo_usuario',
                    'expirado','recusado_na_confirmacao')),
                risk_committed_r REAL NOT NULL DEFAULT 0,
                realized_r REAL,
                report_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(strategy_id, symbol, timeframe, signal_bar_utc)
            )
        """)
        pipeline_run_columns = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_runs)")}
        if "pending_since" not in pipeline_run_columns:
            conn.execute("ALTER TABLE pipeline_runs ADD COLUMN pending_since TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
                stage_index INTEGER NOT NULL, stage TEXT NOT NULL, agent TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('ok','sem_fonte','nao_aplicavel','bloqueado','nao_executado')),
                summary TEXT NOT NULL DEFAULT '',
                input_json TEXT NOT NULL DEFAULT '{}', output_json TEXT NOT NULL DEFAULT '{}',
                limitations_json TEXT NOT NULL DEFAULT '[]',
                produced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(run_id, stage_index)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('buy','sell')),
                quantity REAL NOT NULL CHECK(quantity > 0),
                entry_price REAL NOT NULL CHECK(entry_price > 0),
                exit_price REAL CHECK(exit_price > 0),
                fees REAL NOT NULL DEFAULT 0 CHECK(fees >= 0),
                source TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','closed','cancelled')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT
            )
        """)
        operation_columns = {row[1] for row in conn.execute("PRAGMA table_info(paper_operations)")}
        if "pipeline_run_id" not in operation_columns:
            conn.execute("ALTER TABLE paper_operations ADD COLUMN pipeline_run_id INTEGER REFERENCES pipeline_runs(id)")
        if "exit_reason" not in operation_columns:
            conn.execute("ALTER TABLE paper_operations ADD COLUMN exit_reason TEXT")
        conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS paper_operations_pipeline_run
                        ON paper_operations(pipeline_run_id) WHERE pipeline_run_id IS NOT NULL""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id INTEGER NOT NULL UNIQUE REFERENCES paper_operations(id),
                pipeline_run_id INTEGER REFERENCES pipeline_runs(id),
                journal_version TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('open','closed','cancelled')),
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                details_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_learning_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL REFERENCES strategies(id),
                symbol TEXT NOT NULL, timeframe TEXT NOT NULL,
                analyzer_version TEXT NOT NULL,
                evidence_sha256 TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                observation TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                limitations_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'proposed'
                    CHECK(status IN ('proposed','approved','rejected')),
                draft_strategy_id INTEGER REFERENCES strategies(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT, reviewed_by TEXT,
                UNIQUE(strategy_id,symbol,timeframe,analyzer_version,evidence_sha256)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS broker_paper_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES pipeline_runs(id),
                parent_order_id INTEGER REFERENCES broker_paper_orders(id),
                provider TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('entry','exit')),
                client_order_id TEXT NOT NULL UNIQUE,
                exchange_order_id TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
                quantity TEXT NOT NULL,
                limit_price TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'intent',
                executed_qty REAL NOT NULL DEFAULT 0,
                quote_qty REAL NOT NULL DEFAULT 0,
                response_json TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                checked_at TEXT
            )
        """)
        conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS broker_paper_entry_run
                        ON broker_paper_orders(run_id) WHERE role='entry'""")
        for legacy in conn.execute("""SELECT p.* FROM paper_operations p
            LEFT JOIN paper_journal j ON j.operation_id=p.id WHERE j.id IS NULL""").fetchall():
            details = {"kind": "paper_simulation", "source": legacy["source"],
                       "symbol": legacy["symbol"], "side": legacy["side"],
                       "quantity": legacy["quantity"], "entry_price": legacy["entry_price"],
                       "exit_price": legacy["exit_price"], "exit_reason": legacy["exit_reason"],
                       "fees": legacy["fees"], "limitations":
                       ["Registro anterior ao diário; detalhes de sinal e condução não reconstruídos."]}
            conn.execute("""INSERT INTO paper_journal
                (operation_id,pipeline_run_id,journal_version,state,opened_at,closed_at,details_json)
                VALUES(?,?,? ,?,?,?,?)""",
                (legacy["id"], legacy["pipeline_run_id"], "paper_journal_v1",
                 legacy["state"], legacy["created_at"],
                 legacy["closed_at"], json.dumps(details, ensure_ascii=False, sort_keys=True)))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'not_configured',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""CREATE TABLE IF NOT EXISTS operational_controls (
            key TEXT PRIMARY KEY, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
            reason TEXT NOT NULL, actor TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS service_heartbeats (
            component TEXT PRIMARY KEY, state TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '', last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("PRAGMA foreign_keys = ON")
        for name, status, responsibility in AGENTS:
            conn.execute(
                "INSERT OR IGNORE INTO agents(name,status,responsibility) VALUES(?,?,?)",
                (name, status, responsibility),
            )
        for agent_name, old_status, new_status in (
            ("Risk Manager", "Proteções configuradas", "Limites pendentes de revisão"),
            ("Execution Agent", "Execução desabilitada", "Simulação local apenas"),
        ):
            changed = conn.execute(
                "UPDATE agents SET status=? WHERE name=? AND status=?",
                (new_status, agent_name, old_status),
            ).rowcount
            if changed:
                conn.execute(
                    "INSERT INTO events(agent,level,message) VALUES(?,?,?)",
                    ("Trading Lab", "NOTICE", f"Estado corrigido para refletir ausência de integração: {agent_name} → {new_status}"),
                )
        for agent_name, old_responsibility, new_responsibility in (
            ("Risk Manager", "Valida limites de risco; bloqueia ações não autorizadas.",
             "Aguarda limites documentados; bloqueia propostas sem evidência e exige revisão humana."),
            ("Execution Agent", "Executará apenas em ambiente explicitamente autorizado.",
             "Recebe propostas aprovadas; conector de negociação permanece bloqueado."),
        ):
            changed = conn.execute(
                "UPDATE agents SET responsibility=? WHERE name=? AND responsibility=?",
                (new_responsibility, agent_name, old_responsibility),
            ).rowcount
            if changed:
                conn.execute(
                    "INSERT INTO events(agent,level,message) VALUES(?,?,?)",
                    ("Trading Lab", "NOTICE", f"Responsabilidade atualizada com o estado validado: {agent_name}"),
                )

def get_kill_switch():
    with connect() as conn:
        row = conn.execute("SELECT * FROM operational_controls WHERE key='new_entries'").fetchone()
        return dict(row) if row else {"key": "new_entries", "enabled": 0,
                                      "reason": "", "actor": "", "updated_at": None}


def set_kill_switch(enabled, reason, actor):
    if not actor or (enabled and not reason.strip()):
        raise ValueError("Informe responsável e motivo para ativar o bloqueio.")
    with connect() as conn:
        conn.execute("""INSERT INTO operational_controls(key,enabled,reason,actor,updated_at)
            VALUES('new_entries',?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET enabled=excluded.enabled,
            reason=excluded.reason,actor=excluded.actor,updated_at=CURRENT_TIMESTAMP""",
            (int(bool(enabled)), reason.strip()[:300], actor[:100]))
        conn.execute("INSERT INTO events(agent,level,message) VALUES(?,?,?)",
                     ("Trading Lab", "NOTICE", "Bloqueio de novas entradas " +
                      ("ativado" if enabled else "desativado") + f" por {actor[:100]}: {reason.strip()[:300]}"))
    return get_kill_switch()


def record_heartbeat(component, state, details=""):
    if component not in {"app", "collector:BTCUSDT", "collector:ETHUSDT", "paper-auto"}:
        raise ValueError("Componente desconhecido.")
    with connect() as conn:
        conn.execute("""INSERT INTO service_heartbeats(component,state,details,last_seen_at)
            VALUES(?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(component) DO UPDATE SET state=excluded.state,
            details=excluded.details,last_seen_at=CURRENT_TIMESTAMP""",
            (component, state[:50], details[:250]))


def list_heartbeats():
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM service_heartbeats ORDER BY component").fetchall()]


def quick_check():
    with connect() as conn:
        return conn.execute("PRAGMA quick_check").fetchone()[0]


def get_agents():
    with connect() as conn:
        rows = conn.execute("SELECT name,status,responsibility FROM agents ORDER BY id").fetchall()
        return [dict(row) for row in rows]

def add_event(agent, level, message):
    with connect() as conn:
        conn.execute(
            "INSERT INTO events(agent,level,message) VALUES(?,?,?)",
            (agent, level, message),
        )

def list_events(limit=100):
    with connect() as conn:
        rows = conn.execute(
            "SELECT created_at AS Horário, agent AS Agente, level AS Nível, message AS Atividade "
            "FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def counts():
    tables = ("agents", "events", "documents", "agent_runs", "agent_memories",
              "agent_reviews", "strategies", "backtests", "historical_datasets",
              "paper_operations", "knowledge_items", "validation_runs", "pipeline_runs")
    with connect() as conn:
        return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in tables}


def list_documents():
    with connect() as conn:
        rows = conn.execute(
            "SELECT id,relative_path,filename,sha256,status,page_count,chunk_count,indexed_at,error "
            "FROM documents ORDER BY relative_path"
        ).fetchall()
        return [dict(row) for row in rows]


def replace_document(relative_path, filename, sha256, status, page_count, chunks, error=None):
    with connect() as conn:
        conn.execute("""
            INSERT INTO documents(relative_path,filename,sha256,status,page_count,chunk_count,indexed_at,error)
            VALUES(?,?,?,?,?,?,CASE WHEN ?='indexed' THEN CURRENT_TIMESTAMP ELSE NULL END,?)
            ON CONFLICT(relative_path) DO UPDATE SET
                filename=excluded.filename,sha256=excluded.sha256,status=excluded.status,
                page_count=excluded.page_count,chunk_count=excluded.chunk_count,
                indexed_at=excluded.indexed_at,error=excluded.error
        """, (relative_path, filename, sha256, status, page_count, len(chunks), status, error))
        document_id = conn.execute(
            "SELECT id FROM documents WHERE relative_path=?", (relative_path,)
        ).fetchone()[0]
        conn.execute("DELETE FROM document_chunks WHERE document_id=?", (document_id,))
        conn.executemany(
            "INSERT INTO document_chunks(document_id,page_number,chunk_index,content) VALUES(?,?,?,?)",
            [(document_id, page, idx, content) for page, idx, content in chunks],
        )
        return document_id


def get_document_context(agent, limit=12):
    slugs = {
        "Research Agent": "research-agent", "Market Analyst": "market-analyst",
        "Fundamental Analyst": "fundamental-analyst", "Strategy & Backtest": "strategy-backtest",
        "Risk Manager": "risk-manager", "Execution Agent": "execution-agent",
    }
    slug = slugs.get(agent, "")
    private_pattern = (f"reference_docs/workspaces/{active_user_id()}/%"
                       if active_user_id() else "reference_docs/workspaces/none/%")
    with connect() as conn:
        rows = conn.execute("""
            SELECT d.relative_path,d.filename,c.page_number,c.content
            FROM document_chunks c JOIN documents d ON d.id=c.document_id
            WHERE d.status='indexed'
              AND (d.relative_path LIKE 'reference_docs/shared/%'
                   OR d.relative_path LIKE ? OR d.relative_path LIKE ?)
            ORDER BY CASE WHEN d.relative_path LIKE 'reference_docs/shared/%' THEN 1 ELSE 0 END,
                     d.relative_path,c.page_number,c.chunk_index
            LIMIT ?
        """, (f"reference_docs/agents/{slug}/%", private_pattern, limit)).fetchall()
        return [dict(row) for row in rows]


def upsert_knowledge_item(kind, title, source_path, source_sha256, page_number,
                          evidence, details=None):
    with connect() as conn:
        existing = conn.execute("""SELECT 1 FROM knowledge_items WHERE kind=? AND title=?
            AND source_path=? AND source_sha256=? AND page_number=?""",
            (kind, title, source_path, source_sha256, page_number)).fetchone()
        if existing:
            return False
        version = conn.execute("""SELECT COALESCE(MAX(version),0)+1 FROM knowledge_items
            WHERE kind=? AND title=? AND source_path=? AND page_number=?""",
            (kind, title, source_path, page_number)).fetchone()[0]
        conn.execute("""INSERT INTO knowledge_items
            (kind,title,version,source_path,source_sha256,page_number,evidence,details_json)
            VALUES(?,?,?,?,?,?,?,?)""",
            (kind, title, version, source_path, source_sha256, page_number, evidence,
             json.dumps(details or {}, ensure_ascii=False, sort_keys=True)))
        return True


def list_knowledge_items(kind=None, status=None):
    query = "SELECT * FROM knowledge_items WHERE 1=1"
    params = []
    if kind:
        query += " AND kind=?"; params.append(kind)
    if status:
        query += " AND status=?"; params.append(status)
    query += " ORDER BY kind,title,page_number,id"
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
        items = [dict(row) for row in rows]
    for item in items:
        item["details"] = json.loads(item.pop("details_json"))
    return items


def review_knowledge_item(item_id, approved, reviewer="Usuário"):
    status = "approved" if approved else "rejected"
    with connect() as conn:
        cur = conn.execute("""UPDATE knowledge_items SET status=?,reviewed_at=CURRENT_TIMESTAMP,
            reviewed_by=? WHERE id=? AND status='proposed'""", (status, reviewer, item_id))
        return cur.rowcount == 1


def list_agent_runs(agent=None, limit=50):
    query = "SELECT * FROM agent_runs"
    params = []
    if agent:
        query += " WHERE agent=?"
        params.append(agent)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def add_agent_run(agent, task, context_summary, output, status):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO agent_runs(agent,task,context_summary,output,status) VALUES(?,?,?,?,?)",
            (agent, task, context_summary, output, status),
        )
        return cur.lastrowid


def update_agent_run(run_id, output, status):
    with connect() as conn:
        conn.execute("UPDATE agent_runs SET output=?,status=? WHERE id=?",
                     (output, status, run_id))


def list_memories(agent=None, include_pending=True):
    query = "SELECT * FROM agent_memories WHERE 1=1"
    params = []
    if agent:
        query += " AND agent=?"
        params.append(agent)
    if not include_pending:
        query += " AND status='approved'"
    query += " ORDER BY id DESC"
    with connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def add_memory(agent, kind, content, source, status="proposed"):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO agent_memories(agent,kind,content,source,status) VALUES(?,?,?,?,?)",
            (agent, kind, content, source, status),
        )
        return cur.lastrowid


def review_memory(memory_id, approved, reviewer="usuário"):
    status = "approved" if approved else "rejected"
    with connect() as conn:
        conn.execute(
            "UPDATE agent_memories SET status=?,reviewed_at=CURRENT_TIMESTAMP,reviewed_by=? WHERE id=?",
            (status, reviewer, memory_id),
        )


def add_review(agent, observation, hypothesis, proposed_learning, event_id=None):
    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO agent_reviews(event_id,agent,observation,hypothesis,proposed_learning)
            VALUES(?,?,?,?,?)
        """, (event_id, agent, observation, hypothesis, proposed_learning))
        return cur.lastrowid


def list_reviews(agent=None):
    query = "SELECT * FROM agent_reviews"
    params = []
    if agent:
        query += " WHERE agent=?"
        params.append(agent)
    query += " ORDER BY id DESC"
    with connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def decide_review(review_id, approved):
    status = "approved" if approved else "rejected"
    with connect() as conn:
        review = conn.execute("SELECT * FROM agent_reviews WHERE id=?", (review_id,)).fetchone()
        if not review:
            return False
        conn.execute(
            "UPDATE agent_reviews SET status=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, review_id),
        )
        if approved:
            conn.execute("""
                INSERT INTO agent_memories(agent,kind,content,source,status)
                VALUES(?,?,?,?, 'approved')
            """, (review["agent"], "aprendizado", review["proposed_learning"],
                  f"revisão:{review_id}"))
        return True


def upsert_connection(key, provider, status, metadata=None):
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
    with connect() as conn:
        conn.execute("""
            INSERT INTO connections(key,provider,status,metadata_json,updated_at)
            VALUES(?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET provider=excluded.provider,status=excluded.status,
                metadata_json=excluded.metadata_json,updated_at=CURRENT_TIMESTAMP
        """, (key, provider, status, metadata_json))


def list_connections():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM connections ORDER BY key").fetchall()
        return [dict(row) for row in rows]


def save_strategy(name, rules, source, status="draft"):
    rules_json = json.dumps(rules, ensure_ascii=False, sort_keys=True)
    with connect() as conn:
        version = conn.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM strategies WHERE name=?", (name,)
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO strategies(name,version,rules_json,status,source) VALUES(?,?,?,?,?)",
            (name, version, rules_json, status, source),
        )
        return cur.lastrowid


def list_strategies():
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM strategies ORDER BY id DESC"
        ).fetchall()]


def get_strategy(strategy_id):
    """One strategy version by id, or None — the single-row counterpart of list_strategies()."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM strategies WHERE id=?", (strategy_id,)).fetchone()
        return dict(row) if row else None


def add_backtest(strategy_id, symbol, timeframe, data_source, data_sha256, metrics, status="completed"):
    metrics_json = json.dumps(metrics, ensure_ascii=False, sort_keys=True)
    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO backtests(strategy_id,symbol,timeframe,data_source,data_sha256,metrics_json,status)
            VALUES(?,?,?,?,?,?,?)
        """, (strategy_id, symbol, timeframe, data_source, data_sha256, metrics_json, status))
        return cur.lastrowid


def list_backtests():
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM backtests ORDER BY id DESC"
        ).fetchall()]


def save_historical_dataset(filename, symbol, timeframe, source, sha256, bars,
                            metadata=None, canonical_sha256=None):
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
    with connect() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO historical_datasets
                (filename,symbol,timeframe,source,sha256,row_count,metadata_json,canonical_sha256)
            VALUES(?,?,?,?,?,?,?,?)
        """, (filename, symbol, timeframe, source, sha256, len(bars), metadata_json, canonical_sha256))
        existing = conn.execute(
            "SELECT id,symbol,timeframe,source,metadata_json,canonical_sha256 FROM historical_datasets WHERE sha256=?", (sha256,)
        ).fetchone()
        if (existing["symbol"], existing["timeframe"], existing["source"],
            existing["metadata_json"], existing["canonical_sha256"]) != (
                symbol, timeframe, source, metadata_json, canonical_sha256):
            raise ValueError("Este hash já está registrado com outro símbolo, período ou origem.")
        dataset_id = existing["id"]
        conn.executemany("""
            INSERT OR IGNORE INTO historical_bars(dataset_id,timestamp,open,high,low,close,volume)
            VALUES(?,?,?,?,?,?,?)
        """, [(dataset_id, bar["timestamp"], bar["open"], bar["high"], bar["low"],
               bar["close"], bar["volume"]) for bar in bars])
        return dataset_id


def list_historical_datasets():
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM historical_datasets ORDER BY id DESC"
        ).fetchall()]


def get_historical_bars(dataset_id):
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT timestamp,open,high,low,close,volume FROM historical_bars "
            "WHERE dataset_id=? ORDER BY timestamp", (dataset_id,)
        ).fetchall()]


def upsert_market_bar(provider, symbol, timeframe, bar):
    with connect() as conn:
        conn.execute("""
            INSERT INTO market_bars(provider,symbol,timeframe,timestamp,open,high,low,close,volume)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(provider,symbol,timeframe,timestamp) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume,
                received_at=CURRENT_TIMESTAMP
        """, (provider, symbol, timeframe, bar["timestamp"], bar["open"],
              bar["high"], bar["low"], bar["close"], bar["volume"]))


def upsert_market_bars(provider, symbol, timeframe, bars):
    with connect() as conn:
        conn.executemany("""
            INSERT INTO market_bars(provider,symbol,timeframe,timestamp,open,high,low,close,volume)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(provider,symbol,timeframe,timestamp) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume,
                received_at=CURRENT_TIMESTAMP
        """, [(provider, symbol, timeframe, bar["timestamp"], bar["open"],
               bar["high"], bar["low"], bar["close"], bar["volume"]) for bar in bars])


def update_market_feed(provider, symbol, timeframe, status, last_bar_at=None, error=None):
    with connect() as conn:
        conn.execute("""
            INSERT INTO market_feeds(provider,symbol,timeframe,status,last_bar_at,error)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(provider,symbol,timeframe) DO UPDATE SET
                status=excluded.status, last_bar_at=COALESCE(excluded.last_bar_at,market_feeds.last_bar_at),
                checked_at=CURRENT_TIMESTAMP, error=excluded.error
        """, (provider, symbol, timeframe, status, last_bar_at, error))


def list_market_feeds():
    with connect() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM market_feeds ORDER BY provider,symbol")]


def get_market_bars(provider, symbol, timeframe, limit=1000):
    with connect() as conn:
        rows = conn.execute("""
            SELECT timestamp,open,high,low,close,volume FROM market_bars
            WHERE provider=? AND symbol=? AND timeframe=? ORDER BY timestamp DESC LIMIT ?
        """, (provider, symbol, timeframe, limit)).fetchall()
        return [dict(row) for row in reversed(rows)]


def get_market_bars_window(provider, symbol, timeframe, start_utc, end_utc, limit=3000):
    """Closed bars in an inclusive UTC time window for one operation's chart."""
    start = _parse_utc_timestamp(start_utc).astimezone(timezone.utc)
    end = _parse_utc_timestamp(end_utc).astimezone(timezone.utc)
    if start > end or limit <= 0:
        raise ValueError("Janela de candles inválida.")
    lower = start.strftime("%Y-%m-%dT%H:%M:%S")
    upper = (end + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S")
    with connect() as conn:
        rows = conn.execute("""
            SELECT timestamp,open,high,low,close,volume FROM market_bars
            WHERE provider=? AND symbol=? AND timeframe=?
              AND timestamp>=? AND timestamp<?
            ORDER BY timestamp ASC LIMIT ?
        """, (provider, symbol, timeframe, lower, upper, limit)).fetchall()
    return [dict(row) for row in rows
            if start <= _parse_utc_timestamp(row["timestamp"]) <= end]


def _parse_utc_timestamp(value):
    """Parse a market_bars-style timestamp ("...Z", "...+00:00" or no suffix) into an
    aware UTC datetime, so callers compare real instants instead of raw strings."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def get_market_bars_since(provider, symbol, timeframe, since_timestamp, limit=20000):
    """Bars from `provider`/`symbol`/`timeframe` at or after `since_timestamp` (inclusive),
    in ASCENDING order (ORDER BY timestamp ASC LIMIT ?) — the opposite of get_market_bars(),
    which orders DESC and truncates the START of the window. That truncation is wrong for
    replay, which needs the start of the window (the entry bar) intact; this function instead
    caps the END of the window when there is more than `limit` bars to return.

    IMPORTANT — callers should pass `since_timestamp` WITHOUT a timezone suffix, e.g.
    "2026-11-12T20:08:00", never "...Z" nor "...+00:00". `market_bars.timestamp` is compared
    as a plain SQL string (`WHERE timestamp >= ?`); the live collector
    (services/market_data.py) writes timestamps with a trailing "Z" while other parts of this
    codebase (and its tests) use "+00:00" for the same instant. Because '+' (0x2B) sorts BELOW
    'Z' (0x5A) as a character, a "...Z"-suffixed bound would wrongly EXCLUDE a boundary row
    that happens to be stored with a "+00:00" suffix for that exact instant — a naive string
    comparison silently drops the very bar a replay most needs (the entry bar). An unsuffixed
    bound is a string-prefix of both suffixed forms, so it always sorts at or below either one
    representing the same instant, which keeps the comparison correct no matter which suffix
    the stored row actually uses.

    As a second safety net — in case a caller ever violates that contract and passes a
    suffixed `since_timestamp` anyway — this function first re-derives the SQL bound from the
    PARSED instant (always re-rendered without a suffix) rather than trusting the caller's raw
    string, and then re-validates every row it gets back by parsing its timestamp too and
    comparing actual datetimes, never the raw strings. The boundary bar is therefore never
    lost regardless of which suffix convention the caller, or the stored rows, happen to use.
    """
    since_dt = _parse_utc_timestamp(since_timestamp)
    sql_bound = since_dt.strftime("%Y-%m-%dT%H:%M:%S")
    with connect() as conn:
        rows = conn.execute("""
            SELECT timestamp,open,high,low,close,volume FROM market_bars
            WHERE provider=? AND symbol=? AND timeframe=? AND timestamp >= ?
            ORDER BY timestamp ASC LIMIT ?
        """, (provider, symbol, timeframe, sql_bound, limit)).fetchall()
    bars = [dict(row) for row in rows]
    return [bar for bar in bars if _parse_utc_timestamp(bar["timestamp"]) >= since_dt]


def approve_strategy(strategy_id):
    with connect() as conn:
        row = conn.execute("SELECT rules_json,status FROM strategies WHERE id=?", (strategy_id,)).fetchone()
        if not row or row["status"] != "draft":
            return False
        rules = json.loads(row["rules_json"])
        if rules.get("engine") == "setup_pattern_v1" and rules.get("approval") != "rules_human_approved":
            raise ValueError("As regras operacionais deste setup ainda exigem aprovação humana.")
        conn.execute("UPDATE strategies SET status='approved' WHERE id=?", (strategy_id,))
        return True


def save_backtest(strategy_id, symbol, timeframe, data_source, data_sha256, metrics):
    metrics_json = json.dumps(metrics, ensure_ascii=False, sort_keys=True)
    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO backtests(strategy_id,symbol,timeframe,data_source,data_sha256,metrics_json,status)
            VALUES(?,?,?,?,?,?, 'completed')
        """, (strategy_id, symbol, timeframe, data_source, data_sha256, metrics_json))
        return cur.lastrowid


def save_validation_run(strategy_id, symbol, timeframe, dataset_id, data_sha256, report):
    """Persist one validation reading; `report` is the full dict from the engine.

    `report_json` keeps the reproducible record whole; `split_json`,
    `cost_grid_json`, `concentration_json` and `sample_adequacy` are the
    queryable projections used by the interface.
    """
    missing = sorted(key for key in ("engine_version", "holdout_fraction", "split",
                                     "cost_grid", "concentration", "sample_adequacy")
                     if key not in report)
    if missing:
        raise ValueError("Relatório de validação incompleto: " + ", ".join(missing))
    dump = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True)
    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO validation_runs(strategy_id,symbol,timeframe,dataset_id,data_sha256,
                engine_version,holdout_fraction,split_json,cost_grid_json,concentration_json,
                report_json,sample_adequacy)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (strategy_id, symbol, timeframe, dataset_id, data_sha256,
              report["engine_version"], float(report["holdout_fraction"]),
              dump(report["split"]), dump(report["cost_grid"]),
              dump(report["concentration"]), dump(report),
              report["sample_adequacy"]))
        return cur.lastrowid


def list_validation_runs(limit=50):
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM validation_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()]


def list_paper_operations(state=None):
    query = "SELECT * FROM paper_operations"
    params = []
    if state is not None:
        query += " WHERE state=?"
        params.append(state)
    query += " ORDER BY id DESC"
    with connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def list_paper_journal(limit=50):
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM paper_journal ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()]


def list_broker_paper_orders(limit=100):
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM broker_paper_orders ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()]


def get_broker_paper_order(order_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM broker_paper_orders WHERE id=?", (order_id,)).fetchone()
        return dict(row) if row else None


def get_broker_entry_for_run(run_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM broker_paper_orders WHERE run_id=? AND role='entry'",
                           (run_id,)).fetchone()
        return dict(row) if row else None


def reserve_broker_entry(run_id, provider, client_order_id, symbol, quantity, limit_price):
    """Reserve a single remote paper entry before any network POST."""
    with connect() as conn:
        run = conn.execute("SELECT * FROM pipeline_runs WHERE id=?", (run_id,)).fetchone()
        if (not run or run["status"] != "aguardando_quantidade"
                or run["risk_verdict"] != "autorizado" or run["symbol"] != symbol):
            raise ValueError("Trilha não autorizada ou não está aguardando quantidade.")
        if not run["pending_since"]:
            raise ValueError("Autorização sem prazo de confirmação.")
        pending = datetime.fromisoformat(run["pending_since"].replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - pending).total_seconds() > 900:
            raise ValueError("Autorização expirou; avalie uma nova barra.")
        if conn.execute("SELECT 1 FROM paper_operations WHERE pipeline_run_id=?",
                        (run_id,)).fetchone():
            raise ValueError("Esta trilha já abriu uma operação paper local.")
        if conn.execute("SELECT 1 FROM broker_paper_orders WHERE run_id=? AND role='entry'",
                        (run_id,)).fetchone():
            raise ValueError("Esta trilha já reservou uma ordem Testnet.")
        cur = conn.execute("""INSERT INTO broker_paper_orders
            (run_id,provider,role,client_order_id,symbol,side,quantity,limit_price)
            VALUES(?,?,'entry',?,?,'BUY',?,?)""",
            (run_id, provider, client_order_id, symbol, quantity, limit_price))
        return cur.lastrowid


def reserve_broker_exit(entry_order_id, provider, client_order_id, quantity, limit_price):
    """Reserve a SELL no larger than the reconciled, unsold virtual base quantity."""
    with connect() as conn:
        entry = conn.execute("SELECT * FROM broker_paper_orders WHERE id=? AND role='entry'",
                             (entry_order_id,)).fetchone()
        if not entry or entry["provider"] != provider or entry["executed_qty"] <= 0:
            raise ValueError("Compra Testnet sem preenchimento reconciliado.")
        exits = conn.execute("SELECT * FROM broker_paper_orders WHERE parent_order_id=?",
                             (entry_order_id,)).fetchall()
        if any(row["state"] not in {"CANCELED", "REJECTED", "EXPIRED", "FILLED"} for row in exits):
            raise ValueError("Já existe saída Testnet ativa ou desconhecida.")
        remaining = Decimal(str(entry["executed_qty"])) - sum(
            Decimal(str(row["executed_qty"])) for row in exits)
        if Decimal(str(quantity)) <= 0 or Decimal(str(quantity)) > remaining:
            raise ValueError("Quantidade de saída excede a posição virtual reconciliada.")
        cur = conn.execute("""INSERT INTO broker_paper_orders
            (run_id,parent_order_id,provider,role,client_order_id,symbol,side,quantity,limit_price)
            VALUES(?,?,?,'exit',?,?,'SELL',?,?)""",
            (entry["run_id"], entry_order_id, provider, client_order_id,
             entry["symbol"], quantity, limit_price))
        return cur.lastrowid


def update_broker_paper_order(order_id, state, exchange_order_id=None, executed_qty=0,
                              quote_qty=0, response=None, error=None):
    allowed = {"intent", "unknown", "NEW", "PARTIALLY_FILLED", "FILLED", "CANCELED",
               "REJECTED", "EXPIRED", "PENDING_CANCEL"}
    if state not in allowed:
        raise ValueError("Estado de ordem Testnet desconhecido.")
    with connect() as conn:
        row = conn.execute("SELECT * FROM broker_paper_orders WHERE id=?", (order_id,)).fetchone()
        if not row:
            raise ValueError("Ordem Testnet não encontrada.")
        if Decimal(str(executed_qty)) < Decimal(str(row["executed_qty"])):
            raise ValueError("Consulta reduziria quantidade já preenchida.")
        if Decimal(str(executed_qty)) > Decimal(row["quantity"]):
            raise ValueError("Consulta excederia quantidade solicitada.")
        if row["state"] in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"} and state != row["state"]:
            raise ValueError("Consulta mudaria estado terminal da ordem.")
        conn.execute("""UPDATE broker_paper_orders SET state=?,exchange_order_id=COALESCE(?,exchange_order_id),
            executed_qty=?,quote_qty=?,response_json=?,error=?,checked_at=CURRENT_TIMESTAMP WHERE id=?""",
            (state, exchange_order_id, executed_qty, quote_qty,
             json.dumps(response or {}, ensure_ascii=False, sort_keys=True), error, order_id))
        if row["role"] == "entry":
            if float(executed_qty) > 0:
                conn.execute("UPDATE pipeline_runs SET status='posicao_aberta' WHERE id=?",
                             (row["run_id"],))
            elif state in {"CANCELED", "REJECTED", "EXPIRED"}:
                conn.execute("UPDATE pipeline_runs SET status='descartado_pelo_usuario' WHERE id=?",
                             (row["run_id"],))
        return True


def list_paper_learning_source_rows():
    """Closed journal rows with their persisted operation and pipeline trail."""
    with connect() as conn:
        return [dict(row) for row in conn.execute("""
            SELECT j.operation_id,j.pipeline_run_id,j.state AS journal_state,j.details_json,
                   p.pipeline_run_id AS operation_pipeline_run_id,
                   p.state AS operation_state,p.symbol,p.side,p.quantity,p.entry_price,
                   p.exit_price,p.exit_reason,p.fees,p.closed_at,
                   r.strategy_id,r.setup_name,r.timeframe,r.signal_bar_utc,
                   r.risk_verdict,r.status AS run_status,r.realized_r,r.report_json,
                   s.id AS conduction_stage_id
              FROM paper_journal j
              JOIN paper_operations p ON p.id=j.operation_id
              JOIN pipeline_runs r ON r.id=j.pipeline_run_id
              LEFT JOIN pipeline_stages s ON s.run_id=r.id AND s.stage_index=8
             WHERE j.state='closed' AND p.state='closed'
             ORDER BY j.operation_id
        """).fetchall()]


def list_paper_learning_proposals(limit=100):
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM paper_learning_proposals ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()]


def get_paper_learning_proposal(proposal_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM paper_learning_proposals WHERE id=?",
                           (proposal_id,)).fetchone()
        return dict(row) if row else None


def save_paper_learning_proposal(strategy_id, symbol, timeframe, analyzer_version,
                                 evidence_sha256, evidence, observation, hypothesis, limitations):
    with connect() as conn:
        conn.execute("""INSERT INTO paper_learning_proposals
            (strategy_id,symbol,timeframe,analyzer_version,evidence_sha256,evidence_json,
             observation,hypothesis,limitations_json)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(strategy_id,symbol,timeframe,analyzer_version,evidence_sha256)
            DO NOTHING""",
            (strategy_id, symbol, timeframe, analyzer_version, evidence_sha256,
             json.dumps(evidence, ensure_ascii=False, sort_keys=True), observation, hypothesis,
             json.dumps(limitations, ensure_ascii=False, sort_keys=True)))
        return conn.execute("""SELECT id FROM paper_learning_proposals WHERE
            strategy_id=? AND symbol=? AND timeframe=? AND analyzer_version=? AND evidence_sha256=?""",
            (strategy_id, symbol, timeframe, analyzer_version, evidence_sha256)).fetchone()[0]


def review_paper_learning_proposal(proposal_id, approved, reviewer="Usuário"):
    with connect() as conn:
        return conn.execute("""UPDATE paper_learning_proposals
            SET status=?,reviewed_at=CURRENT_TIMESTAMP,reviewed_by=?
            WHERE id=? AND status='proposed'""",
            ("approved" if approved else "rejected", reviewer, proposal_id)).rowcount == 1


def create_paper_learning_draft(proposal_id, parent_strategy_id, rules):
    """Create exactly one draft for an approved proposal, atomically linking it."""
    with connect() as conn:
        proposal = conn.execute("SELECT * FROM paper_learning_proposals WHERE id=?",
                                (proposal_id,)).fetchone()
        if not proposal or proposal["status"] != "approved":
            raise ValueError("A proposta precisa de aprovação humana antes do rascunho.")
        if proposal["strategy_id"] != parent_strategy_id:
            raise ValueError("Estratégia de origem não corresponde à proposta.")
        if proposal["draft_strategy_id"] is not None:
            raise ValueError("Esta proposta já gerou um rascunho.")
        parent = conn.execute("SELECT * FROM strategies WHERE id=?",
                              (parent_strategy_id,)).fetchone()
        if not parent or parent["status"] != "approved":
            raise ValueError("A versão de origem precisa continuar aprovada.")
        version = conn.execute("SELECT COALESCE(MAX(version),0)+1 FROM strategies WHERE name=?",
                               (parent["name"],)).fetchone()[0]
        cur = conn.execute("""INSERT INTO strategies(name,version,rules_json,status,source)
                              VALUES(?,?,?,'draft',?)""",
                           (parent["name"], version, json.dumps(rules, ensure_ascii=False, sort_keys=True),
                            f"aprendizado paper proposta #{proposal_id}; origem estratégia #{parent_strategy_id}"))
        conn.execute("UPDATE paper_learning_proposals SET draft_strategy_id=? WHERE id=?",
                     (cur.lastrowid, proposal_id))
        return cur.lastrowid


def open_paper_operation(symbol, side, quantity, entry_price, source, pipeline_run_id=None, fees=0.0):
    """Insert a real (simulated) open position; never fills exit_price/closed_at.

    Validates in Python, with pt-BR messages, before the INSERT — the table's
    own CHECK constraints are a backstop, not the primary error path.
    """
    if side not in ("buy", "sell"):
        raise ValueError("Lado da operação deve ser 'buy' ou 'sell'.")
    if not math.isfinite(float(quantity)) or float(quantity) <= 0:
        raise ValueError("Quantidade deve ser um número positivo.")
    if not math.isfinite(float(entry_price)) or float(entry_price) <= 0:
        raise ValueError("Preço de entrada deve ser um número positivo.")
    if not math.isfinite(float(fees)) or float(fees) < 0:
        raise ValueError("Taxas devem ser um número finito e não negativo.")
    with connect() as conn:
        if pipeline_run_id and conn.execute(
                "SELECT 1 FROM broker_paper_orders WHERE run_id=? AND role='entry'",
                (pipeline_run_id,)).fetchone():
            raise ValueError("Esta trilha já reservou uma ordem Testnet.")
        cur = conn.execute("""
            INSERT INTO paper_operations(symbol,side,quantity,entry_price,fees,source,
                state,pipeline_run_id)
            VALUES(?,?,?,?,?,?,'open',?)
        """, (symbol, side, float(quantity), float(entry_price), float(fees), source,
              pipeline_run_id))
        operation_id = cur.lastrowid
        run = conn.execute("SELECT * FROM pipeline_runs WHERE id=?", (pipeline_run_id,)).fetchone() if pipeline_run_id else None
        report = json.loads(run["report_json"]) if run else {}
        details = {
            "kind": "paper_simulation", "source": source,
            "symbol": symbol, "side": side, "quantity": float(quantity),
            "entry_price": float(entry_price),
            "signal_bar_utc": run["signal_bar_utc"] if run else None,
            "setup_name": run["setup_name"] if run else None,
            "timeframe": run["timeframe"] if run else None,
            "risk_verdict": run["risk_verdict"] if run else None,
            "risk": report.get("risk"), "execution": report.get("execution"),
            "limitations": ["Trilha de pipeline ausente; origem legada."] if not run else
                           ["Condução sob demanda; feed de candles fechados, não preço executável."],
        }
        conn.execute("""INSERT INTO paper_journal(operation_id,pipeline_run_id,journal_version,state,opened_at,details_json)
                        VALUES(?,?,?,'open',?,?)""",
                     (operation_id, pipeline_run_id, "paper_journal_v1",
                      datetime.now(timezone.utc).isoformat(), json.dumps(details, ensure_ascii=False, sort_keys=True)))
        return operation_id


def close_paper_operation(operation_id, exit_price, exit_reason, closed_at, fees=0.0, realized_r=None,
                          journal_details=None, conduction_stage=None):
    """Close a simulated position. Uses a conditional UPDATE, never a read-then-write:

    only a row still in state='open' is closed; `cur.rowcount == 0` means someone else
    already closed it (a race, or a second call) and nothing is touched, including
    `pipeline_runs`. When `cur.rowcount == 1` this call is the one that actually closed it:
    in the SAME transaction (same connection, before commit), if the operation carries a
    `pipeline_run_id`, also stamps `pipeline_runs.realized_r`.

    Returns True when this call is the one that really closed the position, False when it
    was already closed (race/duplicate call) and nothing was written.
    """
    with connect() as conn:
        cur = conn.execute("""
            UPDATE paper_operations
               SET exit_price=?, exit_reason=?, closed_at=?, fees=?, state='closed'
             WHERE id=? AND state='open'
        """, (exit_price, exit_reason, closed_at, fees, operation_id))
        if cur.rowcount == 0:
            return False
        operation = conn.execute(
            "SELECT pipeline_run_id FROM paper_operations WHERE id=?", (operation_id,)
        ).fetchone()
        if operation and operation["pipeline_run_id"] is not None:
            conn.execute("UPDATE pipeline_runs SET realized_r=? WHERE id=?",
                        (realized_r, operation["pipeline_run_id"]))
        journal = conn.execute("SELECT details_json FROM paper_journal WHERE operation_id=?",
                               (operation_id,)).fetchone()
        if journal:
            details = json.loads(journal["details_json"])
            details.update(journal_details or {})
            details.update({"exit_price": exit_price, "exit_reason": exit_reason,
                            "fees": fees, "realized_r": realized_r})
            conn.execute("""UPDATE paper_journal SET state='closed',closed_at=?,details_json=?
                            WHERE operation_id=?""",
                         (closed_at, json.dumps(details, ensure_ascii=False, sort_keys=True), operation_id))
        if conduction_stage and operation and operation["pipeline_run_id"] is not None:
            stage = conduction_stage
            conn.execute("""INSERT INTO pipeline_stages
                (run_id,stage_index,stage,agent,status,summary,input_json,output_json,limitations_json)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id,stage_index) DO NOTHING""",
                (operation["pipeline_run_id"], stage["stage_index"], stage["stage"],
                 stage["agent"], stage["status"], stage["summary"],
                 json.dumps(stage["input"], ensure_ascii=False, sort_keys=True),
                 json.dumps(stage["output"], ensure_ascii=False, sort_keys=True),
                 json.dumps(stage["limitations"], ensure_ascii=False, sort_keys=True)))
        return True


def save_pipeline_run(pipeline_version, strategy_id, setup_id, setup_name, symbol, timeframe,
                      signal_bar_utc, decision, risk_verdict="nao_avaliado", risk_date_utc=None,
                      risk_decided_at=None, denial_reasons=None, status="avaliado",
                      risk_committed_r=0.0, realized_r=None, report=None, pending_since=None):
    """Insert one pipeline run; same (strategy,symbol,timeframe,signal_bar) never duplicates.

    Idempotent by bar: on conflict with the UNIQUE key, returns the id of the
    row already recorded instead of inserting a second trail for the same bar.
    """
    denial_reasons_json = json.dumps(denial_reasons or [], ensure_ascii=False, sort_keys=True)
    report_json = json.dumps(report or {}, ensure_ascii=False, sort_keys=True)
    with connect() as conn:
        conn.execute("""
            INSERT INTO pipeline_runs(pipeline_version,strategy_id,setup_id,setup_name,symbol,
                timeframe,signal_bar_utc,risk_date_utc,decision,risk_verdict,risk_decided_at,
                denial_reasons_json,status,risk_committed_r,realized_r,report_json,pending_since)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(strategy_id,symbol,timeframe,signal_bar_utc) DO NOTHING
        """, (pipeline_version, strategy_id, setup_id, setup_name, symbol, timeframe,
              signal_bar_utc, risk_date_utc, decision, risk_verdict, risk_decided_at,
              denial_reasons_json, status, risk_committed_r, realized_r, report_json,
              pending_since))
        row = conn.execute("""
            SELECT id FROM pipeline_runs
            WHERE strategy_id IS ? AND symbol=? AND timeframe=? AND signal_bar_utc=?
        """, (strategy_id, symbol, timeframe, signal_bar_utc)).fetchone()
        return row["id"]


def update_pipeline_run_status(run_id, status, **fields):
    """Update `status` plus any related columns (risk_verdict, denial_reasons_json, ...).

    `denial_reasons` and `report` are accepted as Python values and serialized
    to their `_json` columns; every other keyword must name an existing column.
    """
    allowed = {"risk_verdict", "risk_decided_at", "risk_date_utc", "denial_reasons_json",
               "risk_committed_r", "realized_r", "report_json", "pending_since"}
    assignments = {"status": status}
    for key, value in fields.items():
        if key == "denial_reasons":
            assignments["denial_reasons_json"] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        elif key == "report":
            assignments["report_json"] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        elif key in allowed:
            assignments[key] = value
        else:
            raise ValueError(f"Campo desconhecido para pipeline_runs: {key}")
    set_clause = ",".join(f"{key}=?" for key in assignments)
    with connect() as conn:
        conn.execute(f"UPDATE pipeline_runs SET {set_clause} WHERE id=?",
                     (*assignments.values(), run_id))


def add_pipeline_stage(run_id, stage_index, stage, agent, status, summary="",
                       input_json=None, output_json=None, limitations_json=None):
    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO pipeline_stages(run_id,stage_index,stage,agent,status,summary,
                input_json,output_json,limitations_json)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (run_id, stage_index, stage, agent, status, summary,
              json.dumps(input_json or {}, ensure_ascii=False, sort_keys=True),
              json.dumps(output_json or {}, ensure_ascii=False, sort_keys=True),
              json.dumps(limitations_json or [], ensure_ascii=False, sort_keys=True)))
        return cur.lastrowid


def list_pipeline_runs(limit=50):
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()]


def get_pipeline_run(run_id):
    with connect() as conn:
        run = conn.execute("SELECT * FROM pipeline_runs WHERE id=?", (run_id,)).fetchone()
        if not run:
            return None
        stages = conn.execute(
            "SELECT * FROM pipeline_stages WHERE run_id=? ORDER BY stage_index", (run_id,)
        ).fetchall()
        return {**dict(run), "stages": [dict(stage) for stage in stages]}


def list_pending_pipeline_runs():
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            """SELECT * FROM pipeline_runs r WHERE status='aguardando_quantidade'
               AND NOT EXISTS(SELECT 1 FROM broker_paper_orders b WHERE b.run_id=r.id AND b.role='entry')
               ORDER BY id ASC"""
        ).fetchall()]


def expire_stale_pipeline_runs(max_age_seconds=900):
    """Mark every `aguardando_quantidade` run older than `max_age_seconds` as `expirado`.

    Compares against `pending_since` (set when the run entered
    `aguardando_quantidade`), not `created_at` — the clock the DEC describes is
    "~15 minutes since the entry price went stale", which starts when Execution
    parks the run awaiting quantity, not when the run was first recorded.
    """
    with connect() as conn:
        rows = conn.execute("""
            SELECT id FROM pipeline_runs r
            WHERE status='aguardando_quantidade' AND pending_since IS NOT NULL
              AND NOT EXISTS(SELECT 1 FROM broker_paper_orders b WHERE b.run_id=r.id AND b.role='entry')
              AND (julianday('now') - julianday(pending_since)) * 86400 > ?
        """, (max_age_seconds,)).fetchall()
        ids = [row["id"] for row in rows]
        conn.executemany("UPDATE pipeline_runs SET status='expirado' WHERE id=?",
                         [(run_id,) for run_id in ids])
        return ids


def count_committed_risk_r(date_utc):
    """Sum `risk_committed_r` for every authorized run decided on `date_utc` (UTC).

    Per the DEC (item 5 + item 9 + "Motivo"/"Consequências"): a pending
    authorization already spends the daily budget, and spending is never
    returned — `aguardando_quantidade`, `expirado` and `descartado_pelo_usuario`
    all still count, exactly like `posicao_aberta`. Only the authorization
    itself (`risk_verdict='autorizado'`) and its decision date matter here.
    """
    with connect() as conn:
        row = conn.execute("""
            SELECT COALESCE(SUM(risk_committed_r), 0) AS total FROM pipeline_runs
            WHERE risk_verdict='autorizado' AND date(risk_decided_at)=date(?)
        """, (date_utc,)).fetchone()
        return row["total"]


def count_reserved_exposure():
    """Count open paper positions tied to a pipeline run, plus unexpired pending runs.

    Per the DEC item 9, a pending authorization reserves one of the 2 exposure
    slots (otherwise the limit would be trivially bypassed by stacking pending
    runs); once a run is `expirado` or `descartado_pelo_usuario` it no longer
    reserves a slot — only `aguardando_quantidade` (not yet expired) and an
    actually open `paper_operations` row count.
    """
    with connect() as conn:
        open_positions = conn.execute("""
            SELECT COUNT(*) FROM paper_operations
            WHERE state='open' AND pipeline_run_id IS NOT NULL
        """).fetchone()[0]
        pending = conn.execute("""
            SELECT COUNT(*) FROM pipeline_runs WHERE status='aguardando_quantidade'
        """).fetchone()[0]
        broker_positions = conn.execute("""
            SELECT COUNT(*) FROM broker_paper_orders entry
             WHERE entry.role='entry' AND entry.executed_qty >
               COALESCE((SELECT SUM(exit.executed_qty) FROM broker_paper_orders exit
                         WHERE exit.parent_order_id=entry.id),0) + 1e-9
               AND NOT EXISTS(SELECT 1 FROM pipeline_runs r
                              WHERE r.id=entry.run_id AND r.status='aguardando_quantidade')
        """).fetchone()[0]
        return open_positions + pending + broker_positions
