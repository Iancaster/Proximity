
from aiosqlite import Connection, connect, Row
from pathlib import Path

DB_PATH = Path(__file__).parent.resolve() / "bot_data.db"

_db: Connection | None = None
_PRAGMAS: tuple[str, ...] = (
    "journal_mode=WAL",
    "synchronous=NORMAL",
    "cache_size=-32000",
    "foreign_keys=ON",
    "busy_timeout=5000")

async def get_db() -> Connection:

    global _db
    if _db is None:
        _db = await connect(DB_PATH)
        _db.row_factory = Row
        await _apply_pragmas(_db, _PRAGMAS)

    return _db

async def close_db() -> None:

    global _db
    if _db:
        await _db.close()
        _db = None
        
    return

async def initialize_db():

    db = await get_db()
    await db.executescript("""

        CREATE TABLE IF NOT EXISTS servers (
            guild_id       INT PRIMARY KEY,
            log_channel_id INT NOT NULL,
            name           TEXT NOT NULL,
            description    TEXT NOT NULL,
            reference      TEXT
        );
                           
        CREATE TABLE IF NOT EXISTS locations (
            channel_id     INT PRIMARY KEY,
            guild_id       INT NOT NULL REFERENCES servers(guild_id) ON DELETE CASCADE,
            name           TEXT NOT NULL,
            description    TEXT,
            reference      TEXT
        );
                           
        CREATE TABLE IF NOT EXISTS routes (
            from_id        INT NOT NULL REFERENCES locations(channel_id) ON DELETE CASCADE,
            to_id          INT NOT NULL REFERENCES locations(channel_id) ON DELETE CASCADE,
            PRIMARY KEY (from_id, to_id)
        );
                           
        CREATE TABLE IF NOT EXISTS characters (
            channel_id     INT PRIMARY KEY,
            guild_id       INT NOT NULL REFERENCES servers(guild_id) ON DELETE CASCADE,
            name           TEXT NOT NULL,
            location_id    INT NOT NULL REFERENCES locations(channel_id),
            reference      TEXT
        );
    
    """)
    await db.commit()
    return

async def _apply_pragmas(db: Connection, pragmas: tuple[str, ...]) -> None:

    pragma_str = "PRAGMA " + ";\nPRAGMA ".join(pragmas) + ";"
    await db.executescript(pragma_str)

    return

