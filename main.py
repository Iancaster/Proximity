#!/usr/bin/python3

from data.database_handler import initialize_db, close_db
from discord import Bot, Game, Intents
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

    token = environ.get("TOKEN")
    if not token:
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
        
    bot.load_extensions("cogs.owner", "cogs.debug", "cogs.new", "cogs.delete")
    await bot.start(token)
    return

if __name__ == "__main__":
    run(main())

    # tests_checklist = {
    # 	'Location Tests' : [
    # 			#('Delete Location', 'the-gardens'),
    # 			('Create Location', 'the-gardens'),
    # 			('Create Location', 'the-courtyard'),
    # 			('Create Character', ('Cylian', 'the-courtyard')),
    # 			('Create Character', ('Theo', 'the-gardens')),
    # 			('Create Location', 'the-village-outskirts'),
    # 			#('Delete Location', 'the-courtyard'),
    # 			#('Delete Location', 'the-village-outskirts'),
    # 			('Create Path', ('the-courtyard', 'the-gardens')),
    # 			('Create Path', ('the-courtyard', 'the-village-outskirts')
    # 			)
    # 		]
    # 	}

    #test_guild = await bot.fetch_guild(1114005940392439899)

    #from libraries.classes import Character
    #my_guy = Character(1196173831610564708)
    #from helpers.tests import tests
    #await tests(tests_checklist, test_guild)

    #print('Exiting.')
    #exit()
