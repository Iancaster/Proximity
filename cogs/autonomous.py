

#Import-ant Libraries
from discord.ext import commands

#Classes
class AutoCommands(commands.Cog):
    pass


def setup(prox):
    prox.add_cog(AutoCommands(prox), override = True)
