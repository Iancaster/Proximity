
from data.data_handler import get_db
from sqlite3 import Row

async def get_character(channel_id: int) -> Row | None:

    db = await get_db()
    async with db.execute(
        "SELECT * FROM characters WHERE channel_id = ?",
        (channel_id)
    ) as cursor:
        return await cursor.fetchone()

async def create_character(user_id: str, guild_id: str, name: str):
    db = await get_db()
    await db.execute(
        "INSERT INTO characters (user_id, guild_id, name) VALUES (?, ?, ?)",
        (user_id, guild_id, name)
    )
    await db.commit()

async def update_location(user_id: str, guild_id: str, location: str):
    db = await get_db()
    await db.execute(
        "UPDATE characters SET location = ? WHERE user_id = ? AND guild_id = ?",
        (location, user_id, guild_id)
    )
    await db.commit()