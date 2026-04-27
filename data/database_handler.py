
from aiosqlite import Connection, connect, Row, IntegrityError, OperationalError
from typing import Iterable, Any
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
            guild_id           INT NOT NULL PRIMARY KEY,
            log_channel_id     INT,
            locations_cat      INT,
            characters_cat     INT,
            name               TEXT NOT NULL,
            description        TEXT,
            reference          TEXT,
            character_limit    INT NOT NULL DEFAULT 10,
            location_limit     INT NOT NULL DEFAULT 10,
            creation_time      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            subscription_end   TIMESTAMP DEFAULT (DATETIME('now', '+7 day')));
                           
        CREATE TABLE IF NOT EXISTS locations (
            location_id    INT NOT NULL PRIMARY KEY,
            guild_id       INT REFERENCES servers(guild_id) ON DELETE CASCADE,
            name           TEXT NOT NULL,
            description    TEXT,
            reference      TEXT);
                           
        CREATE TABLE IF NOT EXISTS routes (
            from_id        INT REFERENCES locations(location_id) ON DELETE CASCADE,
            to_id          INT REFERENCES locations(location_id) ON DELETE CASCADE,
            PRIMARY KEY (from_id, to_id));
                           
        CREATE TABLE IF NOT EXISTS characters (
            character_id   INT NOT NULL PRIMARY KEY,
            location_id    INT REFERENCES locations(location_id) ON DELETE RESTRICT,
            guild_id       INT REFERENCES servers(guild_id) ON DELETE RESTRICT,
            eaves_target   INT REFERENCES locations(location_id) ON DELETE SET NULL,
            name           TEXT NOT NULL,
            description    TEXT,
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
    secondary_key_col_name: str | None = None

    @classmethod
    async def fetch(cls, id: int, sec: int | None = None) -> Row | None:

        query = f"SELECT * FROM {cls.table_name} WHERE {cls.primary_key_col_name} = ?"
        values = (id, )

        if sec is not None:
            query += f" AND {cls.secondary_key_col_name} = ?"
            values = (id, sec)

        db = await get_db()
        async with db.execute(query, values) as cursor:
            return await cursor.fetchone()
        
    @classmethod
    async def fetch_all(cls, col_name: str, value: int | str) -> Iterable[Row]:
        
        db = await get_db()
        async with db.execute(
            f"SELECT * FROM {cls.table_name} WHERE {col_name} = ?",
            (value,)) as cursor:

            rows = await cursor.fetchall()

        return rows

    @classmethod
    async def exists(cls, id: int, sec: int | None = None) -> bool:

        query = f"SELECT 1 FROM {cls.table_name} WHERE {cls.primary_key_col_name} = ?"
        values = (id, )

        if sec is not None:
            query += f" AND {cls.secondary_key_col_name} = ?"
            values = (id, sec)

        db = await get_db()
        async with db.execute(query, values) as cursor:
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

        query = f"INSERT INTO {cls.table_name} ({cls.primary_key_col_name}, \
            {', '.join(kwargs.keys())}) VALUES ({wildcards})"

        try:

            await db.execute( query, values)
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

        if not kwargs:
            return CommitResult.NO_UPDATE
            
        db = await get_db()
    
        set_clause = ", ".join(f"{col} = ?" for col in kwargs)
        values = (*kwargs.values(), id)


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
    async def delete(cls, id: int, **kwargs) -> CommitResult:

        db = await get_db()

        query = f"DELETE FROM {cls.table_name} WHERE {cls.primary_key_col_name} = ?"
        values = (id, )

        if kwargs:
            conditions = " AND ".join(f"{col} = ?" for col in kwargs)
            query += f" AND {conditions}"
            values = (id, *kwargs.values())

        async with db.execute(query, values) as cursor:
            
            await db.commit()
            
            if cursor.rowcount > 0:
                result = CommitResult.SUCCESS
            else:
                result = CommitResult.NO_UPDATE
        
        return result

    @classmethod
    async def count(cls, col_name: str, value: int | str) -> int:
        """Counts how many rows have such a value in col_name."""

        db = await get_db()

        async with db.execute(
            f"SELECT COUNT(*) FROM {cls.table_name} WHERE {col_name} = ?",
            (value,)) as cursor:

            row = await cursor.fetchone()
            return row[0] # pyright: ignore[reportOptionalSubscript]

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
        location_limit: int | None = None,
        character_limit: int | None = None,
        subscription_end: int | None = None,
        *args, 
        **kwargs
    ) -> CommitResult:
        
        if subscription_end is not None:
            kwargs["subscription_end"] = subscription_end
        
        return await super().create(
            id, 
            log_channel_id = log_channel_id,
            name = name, 
            description = description, 
            reference = reference,
            location_limit = location_limit,
            character_limit = character_limit,
            *args,
            **kwargs)  

    @classmethod
    async def update(cls, 
        id: int, 
        log_channel_id: int | None = None,
        locations_cat: int | None = None,
        characters_cat: int | None = None,
        name: str | None = None, 
        description: str | None = None, 
        reference: str | None = None, 
        character_limit: int | None = None,
        location_limit: int | None = None,
        subscription_end: int | None = None,
        **kwargs
    ) -> CommitResult:
        
        updates = {}
        
        if log_channel_id is not None:
            updates["log_channel_id"] = log_channel_id

        if locations_cat is not None:
            updates["locations_cat"] = locations_cat if locations_cat else None

        if characters_cat is not None:
            updates["characters_cat"] = characters_cat if characters_cat else None
        
        if name is not None:
            updates["name"] = name
        
        if description is not None:
            updates["description"] = description if description else None

        if reference is not None:
            updates["reference"] = reference if reference else None

        if character_limit is not None:
            updates["character_limit"] = character_limit

        if location_limit is not None:
            updates["location_limit"] = location_limit

        if subscription_end is not None:
            updates["subscription_end"] = subscription_end if subscription_end else None
        
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

class RouteEntry(DatabaseEntry):

    table_name: str = "routes"
    primary_key_col_name: str = "from_id"

    @classmethod
    async def create(cls, 
        from_id: int, 
        to_id: int, 
        *_, **__
    ) -> CommitResult:
        
        return await super().create(
            id = from_id,
            to_id = to_id,
            *_, **__)   

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
        id: int,
        entry_class: type[DatabaseEntry], 
        sec: int | None = None,
        console_level: int | None = None):

        self.id = id
        self.sec = sec
        self.entry = entry_class
        self._logger = get_logger("DB Mixin", console_level = console_level)
        
        return

    async def fetch(self) -> CommitResult:

        result = await self.entry.fetch(self.id)

        if result is None:
            self._logger.warning(f"Tried to fetch {self.entry.table_name} data with ID #{self.id}, none exists.")
            return CommitResult.ROW_MISSING
        
        result = dict(result)
        for key, val in result.items():
            if val == "":
                result[key] = None
        
        self.__dict__.update(result)
        return CommitResult.SUCCESS
    
    @staticmethod
    async def fetch_all(
        col_name: str, 
        value: int | str,
        entry_class: type[DatabaseEntry],
        final_class: Any,
        *_,
        **__
    ) -> Iterable[Any]:

        rows = await entry_class.fetch_all(col_name, value)
                
        entries = []
        for row in rows:

            curr_entry = final_class(
                id = row[entry_class.primary_key_col_name], 
                console_level = 20)

            row = dict(row)
            for key, val in row.items():
                if val == "":
                    row[key] = None
        
            curr_entry.__dict__.update(row) # pyright: ignore[reportAttributeAccessIssue]
            entries.append(curr_entry)

        return entries

    async def delete(self, **kwargs) -> CommitResult:
        self._logger.info(f"Deleting record in {self.entry.table_name} with primary ID: {self.id}.")
        return await self.entry.delete(self.id, **kwargs)
     
    async def create(self, *_, **kwargs) -> CommitResult:
        self._logger.info(f"New record made in {self.entry.table_name} table, ID: {self.id}.")
        self.__dict__.update(kwargs)

        return await self.entry.create(self.id, **kwargs)
       
    async def update(self, **kwargs) -> CommitResult:

        passed_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        self.__dict__.update(passed_kwargs)
        
        return await self.entry.update(self.id, **passed_kwargs)
    
    @property
    async def exists(self) -> bool:      
        return await self.entry.exists(self.id, self.sec)  
    


