

#Import-ant Libraries
from discord import ApplicationContext#, Option
from discord.ext import commands
from libraries.universal import mbd


#Classes
class TestCommands(commands.Cog):

    @commands.slash_command(
        guild_ids = [1114005940392439899])
    async def announce(self, ctx: ApplicationContext):

        if ctx.author.id != 985699127742582846:
            await ctx.respond('I do not believe you are the one who is supposed to be using this command.', ephemeral = True)
            return


        embed, file = await mbd(
            'Version 2.0: Optimizations [2/5]',
            "People sleep on this part of bot development." + \
                " At least, until they realize how slow things get." + \
                " Really glad I prioritized it before that happened.",
            "Now to add 19 more features that bring it to a crawl.")

        embed.add_field(name = 'Command-Specific', inline = False, value =
"""
1. Revamped the `/help` menu page switcher!
  - Now, it can be used anywhere.
  - ...And it's much faster.
2. Optimized `/node delete` and `/node review`.
  - Plays nicely with the listeners that detect changes to protected channels.
  - Sends messages once, as it should.
""")
        embed.add_field(name = 'Throughout', inline = False, value =
"""
1. Granular imports! Only uses what it needs.
  - Improved startup time between reboots.
  - Decreased memory usage.
2. Detected unneccessary string-formatting.
  - Imperceptably faster commands all throughout.
  - Thanks, KATE.
""")
        #
        # from discord.ui import View, Select
        # from discord import ComponentType
        # view = View()
        # select_thing = Select(
        #     select_type = ComponentType.channel_select)
        # view.add_item(select_thing)
        await ctx.respond(embed = embed)
        return

#     @commands.slash_command(
#         description = 'Repeat something as an embed.',
#         guild_ids = [1114005940392439899])
#     async def say(
#         self,
#         ctx: ApplicationContext,
#         header: Option(
#             str,
#             description = 'What should the title be?',
#             default = None),
#         body: Option(
#             str,
#             description = 'What should the body be?',
#             default = None),
#         footer: Option(
#             str,
#             description = 'What should the footer be?',
#             default = None)):
#
#         embed, _ = await mbd(header, body, footer)
#         await ctx.respond(embed = embed)
#         return

def setup(prox):
    prox.add_cog(TestCommands(prox), override = True)

