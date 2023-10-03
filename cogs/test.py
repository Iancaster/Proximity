

#Import-ant Libraries
from discord import ApplicationContext, Option
from discord.ext import commands
from libraries.universal import mbd


#Classes
class TestCommands(commands.Cog):

    pass

#     @commands.slash_command(
#         guild_ids = [1114005940392439899])
#     async def test(
#         self,
#         ctx: ApplicationContext):
#
#         embed, file = await mbd(
#             'Opening Source! (9/17/23)',
#             'Now all of the code is public. You can contribute,' + \
#                 ' take it for yourself, make your own version,' + \
#                 ' do whatever you want with it.',
#             "I also spent two weeks rewriting the code to be" + \
#                 " easily understood now that other people will" + \
#                 f" be looking at it. That took like 80% of the" + \
#                 " work and it barely makes a footnote because" + \
#                 " nobody knows what the hell a GitHub is.",
#             ('assets/avatar.png', 'full'))
#
#         embed.add_field(name = '**New Features**', inline = False, value =
# """
# 1. GitHub link is [here](https://github.com/Iancaster/Proximity)!
#  - Code is being rewritted once more for legibility and consistency.
#  - A brand-new README.md file for the description.
#  - Work begun on Proximity 2.0 with tons of new features.
# """)
#         embed.add_field(name = '**Fixes**', inline = False, value =
# """
# 1. Reorganizing the server.
# 2. Redesigned the crappy logo.
# """)
#         await ctx.respond(embed = embed, file = file)
#         return
#
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

