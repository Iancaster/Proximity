

#Import-ant Libraries
from discord import ApplicationContext#, Option
from discord.ext import commands
from libraries.universal import mbd


#Classes
class TestCommands(commands.Cog):

    @commands.slash_command(
        guild_ids = [1114005940392439899])
    async def test(self, ctx: ApplicationContext):

        if ctx.author.id != 985699127742582846:
            await ctx.respond('I do not believe you are the one who is supposed to be using this command.', ephemeral = True)
            return


        embed, file = await mbd(
            'Version 2.0: Bug Fixes [1/5]',
            "So many things updated that it won't fit into just one" + \
                " message! This section is dedicated to discussing all" + \
                " the bugs that were fixed, with Optimizations, Overhauls," + \
                " and New Features coming next-- and some reworks that just make sense.",
            "I swear this is gonna jinx it. Watch me find ten more bugs tonight.")

        embed.add_field(name = '**"You" Problems**', inline = False, value =
"""
1. Caught typos so bad they would have broken a few different features.
2. Fixed how renaming a node channel in Discord would just create a new node.
3. Squashed a bug where deleting a channel would delete it twice. (???)
""")
        embed.add_field(name = '**"Me" Problems**', inline = False, value =
"""
1. Fixed a memory leak where deleted nodes would still be listening for messages.
2. As well as deleted players. Ghost players listening to you. Spooky.
3. Benign error when overwriting old edges. Didn't *seem* bad but I got it anyhow.
""")

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

