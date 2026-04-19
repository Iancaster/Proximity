#!/usr/bin/python3

from data.database_handler import initialize_db, close_db
from discord import Bot, Game, Intents, ApplicationContext, CheckFailure, NotFound
from asyncio import run
from time import time
from dotenv import load_dotenv
from config.cfg_parser import cfg
from os import environ

boot_time: float = time()

intents = Intents.none()
intents.guilds = True
intents.guild_messages = True
intents.members = True
intents.message_content = True
intents.webhooks = True

load_dotenv()


async def main():

    if not (token := environ.get("TOKEN")):
        raise RuntimeError("Have you forgotten the .env?")
    
    bot = Bot(intents = intents, owner_id = cfg("account", "owner_id"))
    await initialize_db()	
    
    @bot.listen()
    async def on_ready():

        if bot.user is None:
            raise RuntimeError("Bot has no user!")
        
        await bot.change_presence(activity = Game(str(cfg("account", "activity")) or " with someone's heart."))
        print(f"{bot.user.name} woke up in {time() - boot_time:.2f} seconds.")

    @bot.listen()
    async def on_close():
        await close_db()

    @bot.event
    async def on_application_command_error(ctx: ApplicationContext, error: Exception):

        if isinstance(error, CheckFailure):
            pass # Handled by the check.

        elif isinstance(error, NotFound):
            pass

        else:
            raise error
        
    bot.load_extensions(
        "cogs.owner", 
        "cogs.debug", 
        "cogs.new", 
        "cogs.delete", 
        "cogs.review",
        "cogs.autonomous")
    await bot.start(token)
    return

if __name__ == "__main__":
    run(main())
