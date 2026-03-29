
from aiosqlite import Connection, connect, Row, IntegrityError
from enum import StrEnum
from pathlib import Path
from sqlite3 import Row
from abc import ABC

DB_PATH = Path(__file__).parent.resolve() / "bot_data.db"

_db: Connection | None = None
_PRAGMAS: tuple[str, ...] = (
    "journal_mode = WAL",
    "synchronous = NORMAL",
    "cache_size = -32000",
    "foreign_keys = ON",
    "busy_timeout = 5000")

async def get_db() -> Connection:

    global _db
    if _db is None:
        _db = await connect(DB_PATH)
        _db.row_factory = Row
        pragma_str = "PRAGMA " + ";\nPRAGMA ".join(_PRAGMAS) + ";"
        await _db.executescript(pragma_str)

    return _db

async def initialize_db():

    db = await get_db()
    await db.executescript("""

        CREATE TABLE IF NOT EXISTS servers (
            guild_id       INT PRIMARY KEY,
            log_channel_id INT NOT NULL,
            name           TEXT NOT NULL,
            description    TEXT NOT NULL,
            reference      TEXT);
                           
        CREATE TABLE IF NOT EXISTS locations (
            location_id     INT PRIMARY KEY,
            guild_id       INT NOT NULL REFERENCES servers(guild_id) ON DELETE CASCADE,
            name           TEXT NOT NULL,
            description    TEXT,
            reference      TEXT);
                           
        CREATE TABLE IF NOT EXISTS routes (
            from_id        INT NOT NULL REFERENCES locations(location_id) ON DELETE CASCADE,
            to_id          INT NOT NULL REFERENCES locations(location_id) ON DELETE CASCADE,
            PRIMARY KEY (from_id, to_id));
                           
        CREATE TABLE IF NOT EXISTS characters (
            character_id     INT PRIMARY KEY,
            guild_id       INT NOT NULL REFERENCES servers(guild_id) ON DELETE CASCADE,
            name           TEXT NOT NULL,
            location_id    INT NOT NULL REFERENCES locations(character_id),
            reference      TEXT);
    
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

class DatabaseEntry(ABC):
    table_name: str
    primary_key_col_name: str

    @classmethod
    async def get_entry(cls, id: int) -> Row | None:

        db = await get_db()
        async with db.execute(
            "SELECT * FROM ? WHERE ? = ?",
            (cls.table_name, cls.primary_key_col_name, id)
            ) as cursor:

            return await cursor.fetchone()
        
    @classmethod
    async def create(cls, id: int, *args: str | int, **kwargs: str | int) -> CommitResult:

        db = await get_db()
        values = (id, *args, *kwargs.values())
        wildcards = ", ".join("?" * len(values))

        try:

            await db.execute(
                f"INSERT INTO {cls.table_name} VALUES ({wildcards})",
                values)
            await db.commit()
            result = CommitResult.SUCCESS

        except IntegrityError as err:

            if "FOREIGN KEY constraint failed" in str(err):
                result = CommitResult.FOREIGN_KEY_FAIL
            else:
                result = CommitResult.UNKNOWN_ERR

        return result

    @classmethod
    async def update_entry(cls, id: int, **kwargs) -> CommitResult:

        db = await get_db()
    
        set_clause = ", ".join(f"{col} = ?" for col in kwargs)
        values = (*kwargs.values(), id)

        try:
        
            await db.execute(
                f"UPDATE {cls.table_name} SET {set_clause} WHERE {cls.primary_key_col_name} = ?",
                values)
            await db.commit()
            result = CommitResult.SUCCESS

        except IntegrityError as err:

            if "FOREIGN KEY constraint failed" in str(err):
                result = CommitResult.FOREIGN_KEY_FAIL
            else:
                result = CommitResult.UNKNOWN_ERR

        return result

    @classmethod
    async def delete_entry(cls, id: int) -> None:

        db = await get_db()
        
        await db.execute(
            f"DELETE FROM {cls.table_name} WHERE {cls.primary_key_col_name} = ?",
            (id,))
        await db.commit()

        return

class ServerEntry(DatabaseEntry):

    table_name: str = "servers"
    primary_key_col_name: str = "guild_id"

    @classmethod
    async def create(cls, 
        id: int, 
        log_channel_id: int,
        name: str, 
        description: str = "", 
        reference: str = "", 
        *args, 
        **kwargs
    ) -> CommitResult:
        
        return await super().create(
            id, 
            log_channel_id = log_channel_id,
            name = name, 
            description = description, 
            reference = reference,
            *args,
            **kwargs)  

class LocationEntry(DatabaseEntry):

    table_name: str = "locations"
    primary_key_col_name: str = "location_id"

    @classmethod
    async def create(cls, 
        id: int, 
        guild_id: int, 
        name: str, 
        description: str = "", 
        reference: str = "", 
        *args, 
        **kwargs
    ) -> CommitResult:
        
        return await super().create(
            id, 
            guild_id = guild_id, 
            name = name, 
            description = description, 
            reference = reference,
            *args,
            **kwargs)  

class CharacterEntry(DatabaseEntry):

    table_name: str = "characters"
    primary_key_col_name: str = "character_id"

    @classmethod
    async def create(cls, 
        id: int, 
        guild_id: int, 
        name: str, 
        location_id: int, 
        reference: str = "", 
        *args, 
        **kwargs
    ) -> CommitResult:
        
        return await super().create(
            id, 
            guild_id = guild_id, 
            name = name, 
            location_id = location_id, 
            reference = reference,
            *args,
            **kwargs)    
    

# async def update_location(character_id: int, location_id: int):

#     db = await get_db()
#     await db.execute(
#         "UPDATE locations SET location_id = ? WHERE user_id = ?",
#         (location_id, character_id))
    
#     await db.commit()

#     return


