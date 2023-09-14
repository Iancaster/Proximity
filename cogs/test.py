

#Import-ant Libraries
from discord import ApplicationContext
from discord.ext import commands
from libraries.universal import mbd


#Functions
class TestCommands(commands.Cog):

    @commands.slash_command(
        guild_ids = [1114005940392439899])
    async def test(
        self,
        ctx: ApplicationContext):

        embed, _ = await mbd()
        await ctx.respond(embed = embed)
        return

def setup(prox):
    prox.add_cog(TestCommands(prox), override = True)

