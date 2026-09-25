import os, re, sqlite3
from pathlib import Path
from contextlib import contextmanager

# Postgres in production, SQLite locally. One switch, because the local box
# also runs the WhatsApp sidecar and should not need a network database.
DATABASE_URL = os.getenv("DATABASE_URL", "")
IS_PG = DATABASE_URL.startswith("postgres")

_DB_PATH = Path(os.getenv("DATA_DIR", "./data")) / "tugas.db"
_SCHEMA = Path(__file__).parent / ("schema.pg.sql" if IS_PG else "schema.sql")

_QMARK = re.compile(r"\?(?=(?:[^']*'[^']*')*[^']*$)")


def _to_pg(sql: str) -> str:
    """SQLite's ? placeholders to Postgres %s, leaving any inside string
    literals alone. Translating here keeps ~80 existing queries untouched."""
    sql = _QMARK.sub("%s", sql)
    # SQLite spells this as a prefix, Postgres as a trailing clause.
    if sql.lstrip().upper().startswith("INSERT OR IGNORE"):
        sql = re.sub(r"^\s*INSERT\s+OR\s+IGNORE", "INSERT", sql, flags=re.I)
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return sql


if IS_PG:
    import psycopg

    class _Row(dict):
        """Allows access by column name (row['title']) and by index (row[0]),
        matching sqlite3.Row behavior."""
        def __getitem__(self, item):
            if isinstance(item, int):
                return list(self.values())[item]
            return super().__getitem__(item)

    def _row_factory(cursor):
        fields = [c.name for c in cursor.description] if cursor.description else []
        def make_row(values):
            return _Row(zip(fields, values))
        return make_row

    class _Cur:
        """Wraps a psycopg cursor so callers keep using sqlite3's shape:
        execute() returns something iterable, and rows index by column name."""

        def __init__(self, cur):
            self._c = cur

        def execute(self, sql, params=()):
            self._c.execute(_to_pg(sql), params)
            return self

        def fetchone(self):
            return self._c.fetchone()

        def fetchall(self):
            return self._c.fetchall()

        def __iter__(self):
            return iter(self._c.fetchall())

        @property
        def rowcount(self):
            return self._c.rowcount

    class _Conn:
        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, params=()):
            return _Cur(self._conn.cursor()).execute(sql, params)

        def executescript(self, sql):
            self._conn.execute(sql)

        def commit(self):
            self._conn.commit()

        def rollback(self):
            self._conn.rollback()

        def close(self):
            self._conn.close()

    # Supabase's direct endpoint (db.<ref>.supabase.co) resolves to IPv6 only, and
    # serverless functions have no IPv6 egress — hence 'Cannot assign requested
    # address'. The session pooler is IPv4 and is also what serverless should use
    # anyway, since a direct connection per invocation exhausts Postgres. Rewriting
    # here means the deployment does not depend on the env var being reshaped by
    # hand.
    _SUPABASE_DIRECT = re.compile(r"^db\.([a-z0-9]+)\.supabase\.co$")

    # Tried in order; the first that connects is reused for the process.
    _POOLER_REGIONS = [
        "ap-southeast-1", "ap-southeast-2", "ap-south-1",
        "us-east-1", "us-west-1", "eu-central-1", "eu-west-2",
    ]

    _resolved_dsn = None


    def _pooler_candidates(raw: str) -> list[str]:
        """Pooler DSNs for a direct Supabase URL, or just the URL if it is already
        pooled or not Supabase. The password is copied through untouched."""
        from urllib.parse import urlsplit, urlunsplit, quote
        u = urlsplit(raw)
        m = _SUPABASE_DIRECT.match(u.hostname or "")
        if not m or "pooler" in (u.hostname or ""):
            return [raw]

        ref = m.group(1)
        user = quote(f"{u.username or 'postgres'}.{ref}", safe="")
        pwd = quote(u.password or "", safe="")
        out = []
        for region in _POOLER_REGIONS:
            netloc = f"{user}:{pwd}@aws-0-{region}.pooler.supabase.com:6543"
            out.append(urlunsplit((u.scheme, netloc, u.path or "/postgres", u.query, "")))
        return out


    def _pg_connect():
        global _resolved_dsn
        import psycopg
        if _resolved_dsn:
            return psycopg.connect(_resolved_dsn, row_factory=_row_factory, autocommit=False)

        last = None
        for dsn in _pooler_candidates(DATABASE_URL):
            try:
                conn = psycopg.connect(dsn, row_factory=_row_factory, autocommit=False)
                _resolved_dsn = dsn
                return conn
            except Exception as exc:
                last = exc
        raise last


    def _connect():
        # Supabase's pooler expects one short-lived connection per request,
        # which is also what a serverless invocation gives us.
        return _Conn(_pg_connect())

else:
    def _connect() -> sqlite3.Connection:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


# (table, column, definition) — applied only when the column is absent, since
# CREATE TABLE IF NOT EXISTS silently skips tables that already exist.
_MIGRATIONS = [
    ("messages", "wa_msg_id", "TEXT"),
    ("messages", "sender_name", "TEXT"),
    ("users", "openrouter_key", "TEXT"),
]


def init_db() -> None:
    conn = _connect()
    conn.executescript(_SCHEMA.read_text())

    for table, column, decl in _MIGRATIONS:
        if IS_PG:
            # Postgres has the idempotent form built in.
            conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {decl}")
        else:
            existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_wa ON messages(user_id, wa_msg_id)"
    )
    conn.commit()
    conn.close()


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
