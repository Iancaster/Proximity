

#Import-ant Libraries
from discord import ApplicationContext, Bot, Option, File
from discord.ext import commands
from libraries.universal import *
from timeit import timeit

#Classes
class OwnerCommands(commands.Cog):
	"""
	Commands that only Lancaster can use.
	Maybe in the future I'll enforce that.
	"""

	def __init__(self, bot: Bot):
		self.prox = bot

	@commands.slash_command(
		description = 'Reloads all the cogs.',
		guild_ids = [1111152704279035954])
	async def refresh(self, ctx: ApplicationContext):

		await ctx.defer(ephemeral = True)

		loaded_cogs = list(self.prox.extensions.keys())

		for cog in loaded_cogs:
			self.prox.unload_extension(cog)
			self.prox.load_extension(cog)

		embed, _ = await mbd(
			'Refreshed cogs.',
			'Hopefully this is faster than just restarting.',
			'Or at least provides better continuity.')
		await send_message(ctx.respond, embed)
		return

	@commands.slash_command(
		 description = 'Custom embed.',
		 guild_ids = [1114005940392439899])
	async def say(self, ctx: ApplicationContext):

		if ctx.author.id != 985699127742582846:
			await ctx.respond('I do not believe you are the one who is supposed to be using this command.', ephemeral = True)
			return


		embed, file = await mbd(
			'Update 3.0.2',
			"The `on_guild_channel_update()` function disappeared." +
				" It *disappeared.* I had to recreate it from scratch." +
				" How does that happen? Whatever, it's better than it",
			"I would hope they would be, but.")

		embed.add_field(name = 'Bug Fixes.', inline = False, value =
"""
- Resolved a problem where you couldn't make a `/new character` from outside a Place Channel.
- Fixed an error where you couldn't specify a name in `/review character`.
- Corrected a typo when doing `/move` where two words were smooshed together.
"""
)
		#file = File('3.png', filename = 'image.png')
		#embed.set_image(url = 'attachment://image.png')

		await ctx.respond(embed = embed)#, file = file)
		return


def setup(prox):
	prox.add_cog(OwnerCommands(prox), override = True)

