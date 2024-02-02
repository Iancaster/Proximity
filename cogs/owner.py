

#Import-ant Libraries
from discord import ApplicationContext, Bot, Option, File
from discord.ext import commands
from libraries.universal import *
from timeit import timeit
from libraries.new_classes import test_func, tester_func

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


		print(f'Finished in {timeit(test_func(ctx.author.id), number=10000)}')
		print(f'Finished in {timeit(tester_func(ctx), number=10000)}')

		return

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
			'Bug Fixes 3.0.1',
			"These won't be altogether uncommon.",
			"I would hope they would be, but.")

		embed.add_field(name = 'Dumb stuff, lol.', inline = False, value =
"""
  - Fixed a problem where you couldn't make a `/new character` from outside a Place Channel.
  - Fixed an error where you couldn't specify a name in `/review character`.
"""
)
		#file = File('3.png', filename = 'image.png')
		#embed.set_image(url = 'attachment://image.png')

		await ctx.respond(embed = embed)#, file = file)
		return


def setup(prox):
	prox.add_cog(OwnerCommands(prox), override = True)

