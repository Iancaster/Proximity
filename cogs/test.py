

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
#             'Welcome all.',
#             "Let's get this show on the road, eh?" + \
#                 " Now there's all sorts of improvements" + \
#                 " to the server to welcome new people" + \
#                 " in anticipation of some real growth.",
#             "It's about time.")
#
#         embed.add_field(name = '**General Info**', inline = False, value =
# """
# 1. <#1157385416320765952> is an annoucement channel you can follow in your own server.
# 2. <#1158457414589358170> now has tons of graphics and a rewritten explanation.
# 3. <#1158827576681300109> if you want.
# """)
#         embed.add_field(name = '**Better Dev Info**', inline = False, value =
# """
# 1. <#1158809778903072850> to see the past, what's been done.
# 2. <#1158809399486328866> to see the present, what I'm doing now.
# 3. <#1158808448499191841> to see future features, will soon be added.'
# """)
#         embed.add_field(name = '**Player Support**', inline = False, value =
# """
# 1. <#1157794246514982923> for support with your server running Proximity.
# 2. <#1158813808639361084> to contribute your ideas.
# 3. <#1158814020439134269> if you notice anything not quite right.
# """)
#
#         await ctx.respond(embed = embed)
#         return

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

