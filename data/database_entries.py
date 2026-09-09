from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import TypeVar, Generic, Type
from data.database_handler import get_db, CommitResult, UNSET
from sqlite3 import IntegrityError, OperationalError

@dataclass
class RoleplayData:
    roleplay_id: int
    name: str
    log_channel_id: int | None = None
    locations_cat: int | None = None
    characters_cat: int | None = None
    description: str | None = None
    reference: str | None = None
    character_limit: int = 10
    location_limit: int = 10
    creation_time: datetime | None = None          # server-assigned, see note below
    subscription_end: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=7))

@dataclass
class LocationData:
    location_id: int
    roleplay_id: int
    name: str
    description: str | None = None
    reference: str | None = None

@dataclass
class CharacterData:
    character_id: int
    location_id: int
    roleplay_id: int
    name: str
    eaves_target: int | None = None
    description: str | None = None
    reference: str | None = None

@dataclass
class RouteData:
    from_id: int
    to_id: int

EntryType = TypeVar("EntryType", RoleplayData, LocationData, CharacterData, RouteData)

class Repository(Generic[EntryType]):

    def __init__(self, 
        model: Type[EntryType], 
        table_name: str, 
        primary_key: str | tuple[str, ...]):

        self._model = model
        self._table_name = table_name
        self._primary_key = (primary_key,) if isinstance(primary_key, str) else primary_key

        return

    def _pk_where(self) -> str:
        return " AND ".join(f"{c} = ?" for c in self._primary_key)

    async def fetch(self, *pk_values: int) -> EntryType | CommitResult:

        db = await get_db()
        async with db.execute(
            f"SELECT * FROM {self._table_name} WHERE {self._pk_where()}", pk_values
        ) as cur:
            row = await cur.fetchone()

        return self._model(**row) if row else CommitResult.ROW_MISSING

    async def fetch_all(self, col_name: str, value) -> list[EntryType]:

        db = await get_db()
        async with db.execute(
            f"SELECT * FROM {self._table_name} WHERE {col_name} = ?", (value,)
        ) as cur:
            rows = await cur.fetchall()

        return [self._model(**row) for row in rows]

    async def exists(self, *pk_values: int) -> CommitResult:
        """Returns either SUCCESS or ROW_MISSING."""

        db = await get_db()
        async with db.execute(
            f"SELECT 1 FROM {self._table_name} WHERE {self._pk_where()}", pk_values
        ) as cur:
            return CommitResult.SUCCESS if await cur.fetchone() else CommitResult.ROW_MISSING

    async def create(self, entry: EntryType) -> CommitResult:

        db = await get_db()
        data = {k: v for k, v in asdict(entry).items() if v is not None} 
        cols = ", ".join(data)
        wildcards = ", ".join("?" * len(data))

        try:

            await db.execute(
                 f"INSERT INTO {self._table_name} ({cols}) VALUES ({wildcards})",
                tuple(data.values()))
            await db.commit()

        except (IntegrityError, OperationalError) as err:

            match err.sqlite_errorname:

                case "SQLITE_CONSTRAINT_PRIMARYKEY": 
                    return CommitResult.ROW_EXISTS
                case "SQLITE_CONSTRAINT_FOREIGNKEY": 
                    return CommitResult.FOREIGN_KEY_FAIL
                case _: 
                    return CommitResult.UNKNOWN_ERR
        
        return CommitResult.SUCCESS

    async def update(self, *pk_values: int, **changes) -> CommitResult:

        if not changes:
            return CommitResult.NO_UPDATE
        db = await get_db()
        set_clause = ", ".join(f"{c} = ?" for c in changes)

        try:
            async with db.execute(
                f"UPDATE {self._table_name} SET {set_clause} WHERE {self._pk_where()}",
                (*changes.values(), *pk_values)
            ) as cur:
                await db.commit()

        except (IntegrityError, OperationalError) as err:

            if "FOREIGN KEY constraint failed" in str(err):
                return CommitResult.FOREIGN_KEY_FAIL
            
            return CommitResult.UNKNOWN_ERR

        
        return CommitResult.SUCCESS if cur.rowcount else CommitResult.NO_UPDATE

    async def apply(self, entry: EntryType, **changes) -> CommitResult:
        """Persist `changes`; on success, mutate `entry` in place to match."""

        pk_values = tuple(getattr(entry, col) for col in self._primary_key)
        changes = {k: v for k, v in changes.items() if k is not UNSET}
        result = await self.update(*pk_values, **changes)

        if result is CommitResult.SUCCESS:
            for k, v in changes.items():
                setattr(entry, k, v)

        return result

    async def delete(self, *pk_values: int) -> CommitResult:

        db = await get_db()
        async with db.execute(
            f"DELETE FROM {self._table_name} WHERE {self._pk_where()}", pk_values
        ) as cur:
            await db.commit()
            return CommitResult.SUCCESS if cur.rowcount else CommitResult.NO_UPDATE

    async def count(self, col_name: str, value) -> int:

        db = await get_db()
        async with db.execute(
            f"SELECT COUNT(*) FROM {self._table_name} WHERE {col_name} = ?", (value,)
        ) as cur:
            return (await cur.fetchone())[0] # pyright: ignore[reportOptionalSubscript]

roleplay_repo: Repository[RoleplayData] = Repository(RoleplayData, "roleplays", "roleplay_id")
location_repo: Repository[LocationData] = Repository(LocationData, "locations", "location_id")
character_repo: Repository[CharacterData] = Repository(CharacterData, "characters", "character_id")
route_repo: Repository[RouteData] = Repository(RouteData, "routes", ("from_id", "to_id"))
