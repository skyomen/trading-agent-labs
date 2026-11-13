import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "trading.db"

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
    conn = sqlite3.connect(DB_PATH)
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
              "paper_operations")
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
    with connect() as conn:
        rows = conn.execute("""
            SELECT d.relative_path,d.filename,c.page_number,c.content
            FROM document_chunks c JOIN documents d ON d.id=c.document_id
            WHERE d.status='indexed'
              AND (d.relative_path LIKE 'reference_docs/shared/%'
                   OR d.relative_path LIKE ?)
            ORDER BY CASE WHEN d.relative_path LIKE 'reference_docs/shared/%' THEN 1 ELSE 0 END,
                     d.relative_path,c.page_number,c.chunk_index
            LIMIT ?
        """, (f"reference_docs/agents/{slug}/%", limit)).fetchall()
        return [dict(row) for row in rows]


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


def save_historical_dataset(filename, symbol, timeframe, source, sha256, bars):
    with connect() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO historical_datasets(filename,symbol,timeframe,source,sha256,row_count)
            VALUES(?,?,?,?,?,?)
        """, (filename, symbol, timeframe, source, sha256, len(bars)))
        existing = conn.execute(
            "SELECT id,symbol,timeframe,source FROM historical_datasets WHERE sha256=?", (sha256,)
        ).fetchone()
        if (existing["symbol"], existing["timeframe"], existing["source"]) != (symbol, timeframe, source):
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


def approve_strategy(strategy_id):
    with connect() as conn:
        conn.execute("UPDATE strategies SET status='approved' WHERE id=?", (strategy_id,))


def save_backtest(strategy_id, symbol, timeframe, data_source, data_sha256, metrics):
    metrics_json = json.dumps(metrics, ensure_ascii=False, sort_keys=True)
    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO backtests(strategy_id,symbol,timeframe,data_source,data_sha256,metrics_json,status)
            VALUES(?,?,?,?,?,?, 'completed')
        """, (strategy_id, symbol, timeframe, data_source, data_sha256, metrics_json))
        return cur.lastrowid


def list_paper_operations():
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM paper_operations ORDER BY id DESC"
        ).fetchall()]
