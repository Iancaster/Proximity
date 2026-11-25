#!/usr/bin/python3

from asyncio import run
from time import time
from dotenv import load_dotenv
from os import environ
from typing import Coroutine

from discord import Bot, Game, Intents, ApplicationContext, CheckFailure, NotFound

from data.database_handler import initialize_db, close_db
from libraries.user_interface import set_bot
from libraries.logger import get_logger
from config.cfg_parser import cfg


boot_time: float = time()

intents = Intents.none()
intents.guilds = True
intents.guild_messages = True
intents.members = True
intents.message_content = True
intents.webhooks = True

load_dotenv()

post_ready: Coroutine | None = None
logger = get_logger("Main")

def set_post_ready(coro: Coroutine):
    global post_ready
    post_ready = coro
    return

async def main():

    if not (token := environ.get("TOKEN")):
        raise RuntimeError("Have you forgotten the .env?")

    bot = Bot(
        intents = intents, 
        owner_id = cfg("account", "owner_id")
    ) #debug_guilds = [1111152704279035954])
    set_bot(bot)
    await initialize_db()	
    
    @bot.listen()
    async def on_ready():

        if bot.user is None:
            raise RuntimeError("Bot has no user!")
        
        await bot.change_presence(activity = Game(str(cfg("account", "activity")) or " with someone's heart."))

        logger.info(f"{bot.user.name} woke up in {time() - boot_time:.2f} seconds.")

        if post_ready is not None:
            await post_ready() # pyright: ignore[reportCallIssue]

        return

    @bot.listen()
    async def on_close():
        await close_db()
        return

    @bot.event
    async def on_application_command_error(ctx: ApplicationContext, error: Exception):

        if isinstance(error, CheckFailure):
            pass # Handled by the check.

        elif isinstance(error, NotFound):
            pass

        else:
            raise error

        return
        
    bot.load_extensions("cogs")
    await bot.start(token)
    return

if __name__ == "__main__":
    run(main())

## Cleanup candidates

# - Inline `text_embed` calls in `delete.py` (to move into `embed_templates.py`).
# - Unused imports (`LOGO`, `CharEmbeds`, `Route`, `get_channel`, `CharacterData`, `route_repo`, and others).
# - Trailing whitespace across most files.
# - Unreachable code after the `return` in `autonomous.py::on_guild_channel_delete`.