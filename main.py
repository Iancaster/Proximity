# Import-ant Libraries
import discord
from discord.ext import commands
import databaseFunctions as db
import time

bootTime = time.time()

# Setup
intents = discord.Intents.none()
intents.guilds = True
intents.guild_messages = True
intents.members = True
intents.message_content = True
prox = discord.Bot(intents = intents, owner_id = 985699127742582846)

@prox.listen()
async def on_connect():

    import test
    await test.main()

    await prox.change_presence(
        activity = discord.Game('the angles.'),
        status = discord.Status.online)
    
    print(f'{prox.user.name} woke up in {time.time() - bootTime} seconds.')
    return

prox.load_extension('proxCommands')
prox.run('MTExNDAwNDM4NDkyNjQyMTEyNg.GDXRZV.yUSnxv3Ak6Ws3GdN0QzrZj50ln-znrS7SdoBGs')