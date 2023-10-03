

#Import-ant Libraries
from discord import ApplicationContext, Bot
from discord.ext import commands
from libraries.universal import mbd


#Classes
class OwnerCommands(commands.Cog):
    """
    Commands that only Lancaster can use.
    Maybe in the future I'll enforce that.
    """

    def __init__(self, bot: Bot):
        self.prox = bot

    # @commands.slash_command(
    #     description = 'Reloads all the cogs.',
    #     guild_ids = [1114005940392439899])
    # async def refresh(self, ctx: ApplicationContext):
    #
    #     loaded_cogs = list(self.prox.extensions.keys())
    #
    #     for cog in loaded_cogs:
    #
    #         self.prox.unload_extension(cog)
    #         self.prox.load_extension(cog)
    #
    #
    #     embed, _ = await mbd(
    #         'Refreshed cogs.',
    #         'Hopefully this is faster than just restarting.',
    #         'Or at least provides better continuity.')
    #     await ctx.respond(embed = embed, ephemeral = True)
    #     return

def setup(prox):
    prox.add_cog(OwnerCommands(prox), override = True)

