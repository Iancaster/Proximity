
from aiosqlite import Connection, connect, Row, \
    register_adapter, register_converter
from sqlite3 import PARSE_DECLTYPES
from asyncio import Lock
from enum import StrEnum
from pathlib import Path

DB_PATH = Path(__file__).parent.resolve() / "bot_data.db"

from datetime import datetime, timezone

def _adapt_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

def _convert_timestamp(raw: bytes) -> datetime:
    return datetime.fromisoformat(raw.decode())

register_adapter(datetime, _adapt_datetime)
register_converter("timestamp", _convert_timestamp)

_db: Connection | None = None
_PRAGMAS: tuple[str, ...] = (
    "journal_mode = WAL",
    "synchronous = NORMAL",
    "cache_size = -32000",
    "foreign_keys = ON",
    "busy_timeout = 5000")

_db: Connection | None = None
_init_lock = Lock()

async def get_db() -> Connection:
    global _db
    if _db is None:
        async with _init_lock:
            if _db is None:
                _db = await connect(DB_PATH, detect_types = PARSE_DECLTYPES)
                _db.row_factory = Row
                pragma_str = "PRAGMA " + ";\nPRAGMA ".join(_PRAGMAS) + ";"
                await _db.executescript(pragma_str)

    return _db

DEFAULT_CHAR_LIMIT = 10
DEFAULT_LOC_LIMIT = 10
DEFAULT_SUB_LIMIT = 7

async def initialize_db():

    global DEFAULT_CHAR_LIMIT, DEFAULT_LOC_LIMIT

    db = await get_db()
    await db.executescript(f"""

        CREATE TABLE IF NOT EXISTS roleplays (
            roleplay_id        INT NOT NULL PRIMARY KEY,
            log_channel_id     INT,
            locations_cat      INT,
            characters_cat     INT,
            name               TEXT NOT NULL,
            description        TEXT,
            reference          TEXT,
            character_limit    INT NOT NULL DEFAULT {DEFAULT_CHAR_LIMIT},
            location_limit     INT NOT NULL DEFAULT {DEFAULT_LOC_LIMIT},
            creation_time      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            subscription_end   TIMESTAMP DEFAULT (DATETIME('now', '+{DEFAULT_SUB_LIMIT} day')));
                           
        CREATE TABLE IF NOT EXISTS locations (
            location_id    INT NOT NULL PRIMARY KEY,
            roleplay_id    INT REFERENCES roleplays(roleplay_id) ON DELETE CASCADE,
            name           TEXT NOT NULL,
            description    TEXT,
            reference      TEXT);
                           
        CREATE TABLE IF NOT EXISTS routes (
            from_id        INT REFERENCES locations(location_id) ON DELETE CASCADE,
            to_id          INT REFERENCES locations(location_id) ON DELETE CASCADE,
            roleplay_id    INT REFERENCES roleplays(roleplay_id) ON DELETE CASCADE,
            PRIMARY KEY (from_id, to_id));
                           
        CREATE TABLE IF NOT EXISTS characters (
            character_id   INT NOT NULL PRIMARY KEY,
            location_id    INT REFERENCES locations(location_id) ON DELETE RESTRICT,
            roleplay_id    INT REFERENCES roleplays(roleplay_id) ON DELETE CASCADE,
            eaves_target   INT REFERENCES locations(location_id) ON DELETE SET NULL,
            name           TEXT NOT NULL,
            description    TEXT,
            reference      TEXT);

        CREATE INDEX IF NOT EXISTS idx_characters_location ON characters(location_id);
    
    """)

    await db.commit()
    
    return

async def close_db() -> None:

    global _db
    if _db:
        await _db.close()
        _db = None
        
    return

class CommitResult(StrEnum):
    UNKNOWN_ERR = "Unidentified error-- please report to owner!"
    SUCCESS = "Commit executed successfully."
    FOREIGN_KEY_FAIL = "Mismatch with one or more foreign keys."
    ROW_EXISTS = "Row with this primary key already exists!"
    ROW_MISSING = "No such row with this primary key exists!"
    NO_UPDATE = "Row not found or no change needed."

class _Unset:
    
    def __repr__(self) -> str: 
        return "<UNSET>"

UNSET: _Unset = _Unset()