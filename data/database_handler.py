
from aiosqlite import Connection, connect, Row, IntegrityError, OperationalError
from enum import StrEnum
from pathlib import Path
from sqlite3 import Row
from abc import ABC
from libraries.logger import get_logger

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
            description    TEXT,
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
            location_id    INT NOT NULL REFERENCES locations(location_id),
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
    ROW_EXISTS = "Row with this primary key already exists!"
    ROW_MISSING = "No such row with this primary key exists!"
    NO_UPDATE = "Row not found or no change needed."

class DatabaseEntry(ABC):
    """Base class which handles all database queries/operations."""

    table_name: str
    primary_key_col_name: str

    @classmethod
    async def fetch(cls, id: int) -> Row | None:

        db = await get_db()
        async with db.execute(
            f"SELECT * FROM {cls.table_name} WHERE {cls.primary_key_col_name} = ?",
            (id, )) as cursor:

            return await cursor.fetchone()
        
    @classmethod
    async def exists(cls, id: int) -> bool:

        db = await get_db()
        async with db.execute(
            f"SELECT 1 FROM {cls.table_name} WHERE {cls.primary_key_col_name} = ?",
            (id, )) as cursor:

            return await cursor.fetchone() is not None 
        
    @classmethod
    async def create(cls, 
        id: int, 
        *args: str | int | None, 
        **kwargs: str | int | None
    ) -> CommitResult:

        db = await get_db()
        values = (id, *args, *kwargs.values())
        wildcards = ", ".join("?" * len(values))

        try:

            async with db.execute(
                f"INSERT INTO {cls.table_name} VALUES ({wildcards})",
                values) as cursor:
                
                await db.commit()
                result = CommitResult.SUCCESS

        except IntegrityError as err:

            #if "FOREIGN KEY constraint failed" in str(err):
                #result = CommitResult.FOREIGN_KEY_FAIL
            if err.sqlite_errorname == 'SQLITE_CONSTRAINT_PRIMARYKEY':
                result = CommitResult.ROW_EXISTS
            else:
                result = CommitResult.UNKNOWN_ERR

        return result

    @classmethod
    async def update(cls, id: int, **kwargs) -> CommitResult:

        db = await get_db()
    
        set_clause = ", ".join(f"{col} = ?" for col in kwargs)
        values = (*kwargs.values(), id)

        if not kwargs:
            return CommitResult.NO_UPDATE

        try:

            async with db.execute(
                f"UPDATE {cls.table_name} SET {set_clause} WHERE {cls.primary_key_col_name} = ?",
                values) as cursor:
                
                await db.commit()
                
                if cursor.rowcount == 1:
                    result = CommitResult.SUCCESS
                else:
                    result = CommitResult.NO_UPDATE

        except (IntegrityError, OperationalError) as err:

            if "FOREIGN KEY constraint failed" in str(err):
                result = CommitResult.FOREIGN_KEY_FAIL
            else:
                result = CommitResult.UNKNOWN_ERR

        return result

    @classmethod
    async def delete(cls, id: int) -> CommitResult:

        db = await get_db()

        async with db.execute(
            f"DELETE FROM {cls.table_name} WHERE {cls.primary_key_col_name} = ?",
            (id,)) as cursor:
            
            await db.commit()
            
            if cursor.rowcount == 1:
                result = CommitResult.SUCCESS
            else:
                result = CommitResult.NO_UPDATE
        
        return result

class ServerEntry(DatabaseEntry):

    table_name: str = "servers"
    primary_key_col_name: str = "guild_id"

    @classmethod
    async def create(cls, 
        id: int, 
        log_channel_id: int,
        name: str, 
        description: str | None = None, 
        reference: str | None = None, 
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

    @classmethod
    async def update(cls, 
        id: int, 
        log_channel_id: int | None = None,
        name: str | None = None, 
        description: str | None = None, 
        reference: str | None = None, 
        **kwargs
    ) -> CommitResult:
        
        updates = {}
        
        if log_channel_id is not None:
            updates["log_channel_id"] = log_channel_id
        
        if name is not None:
            updates["name"] = name
        
        if description is not None:
            updates["description"] = description if description else None

        if reference is not None:
            updates["reference"] = reference if reference else None
        
        return await super().update(id, **updates)  

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
        reference: str | None = None, 
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

class DatabaseMixin:
    """Inheritable class for objects which intend to store attributes equivalent to the fields in their table."""

    def __init__(self, 
        entry_class: type[DatabaseEntry], 
        id: int,
        console_level: int | None):

        self.id = id
        self.entry = entry_class
        self._logger = get_logger("DB Mixin", console_level = console_level)
        
        return

    async def fetch(self) -> CommitResult:

        result = await self.entry.fetch(self.id)

        if result is None:
            self._logger.warning(f"Tried to fetch {self.entry.table_name} data with ID #{self.id}, none exists.")
            return CommitResult.ROW_MISSING
        
        self.__dict__.update(dict(result))
        return CommitResult.SUCCESS

    async def delete(self) -> CommitResult:
        self._logger.info(f"Deleting record in {self.entry.table_name} with ID: {self.id}.")
        return await self.entry.delete(self.id)
     
    async def create(self, *_, **kwargs) -> CommitResult:
        """Registers this server as an RP one."""

        self._logger.info(f"New record made in {self.entry.table_name} table, ID: {self.id}.")
        self.__dict__.update(kwargs)

        return await self.entry.create(self.id, **kwargs)
       
    async def update(self, **kwargs) -> CommitResult:

        passed_kwargs = {k: v for k, v in kwargs if v is not None}
        self.__dict__.update(passed_kwargs)
        
        return await self.entry.update(self.id, **passed_kwargs)
    
    @property
    async def exists(self) -> bool:
        f"""True if the record is in the respective database."""
        return await self.entry.exists(self.id)  
    

# async def update_location(character_id: int, location_id: int):

#     db = await get_db()
#     await db.execute(
#         "UPDATE locations SET location_id = ? WHERE user_id = ?",
#         (location_id, character_id))
    
#     await db.commit()

#     return


