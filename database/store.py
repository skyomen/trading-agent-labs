import sqlite3
import json
import math
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
        conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS paper_operations_pipeline_run
                        ON paper_operations(pipeline_run_id) WHERE pipeline_run_id IS NOT NULL""")
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
        cur = conn.execute("""
            INSERT INTO paper_operations(symbol,side,quantity,entry_price,fees,source,
                state,pipeline_run_id)
            VALUES(?,?,?,?,?,?,'open',?)
        """, (symbol, side, float(quantity), float(entry_price), float(fees), source,
              pipeline_run_id))
        return cur.lastrowid


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
            "SELECT * FROM pipeline_runs WHERE status='aguardando_quantidade' ORDER BY id ASC"
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
            SELECT id FROM pipeline_runs
            WHERE status='aguardando_quantidade' AND pending_since IS NOT NULL
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
        return open_positions + pending
