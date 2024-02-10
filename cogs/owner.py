

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
		guild_ids = [1114005940392439899])
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

		embed, file = await mbd(
			'Update 3.0.3',
			"From now on, testers are named when their bug is fixed." +
				" Consider it a lil' credit for a job well done.",
			"You guys are doing great, keep it up.")

		embed.add_field(name = 'Bug Fixes.', inline = False, value =
"""
- <@757315397463572570>: Making a new channel no longer requires that the bot have that permission in the category the channel is going in.
- <@727901914401865829>: Moving is now un-broken! (Turns out it was a problem with the listeners getting mixed up).
"""
)
		#file = File('3.png', filename = 'image.png')
		#embed.set_image(url = 'attachment://image.png')

		await ctx.respond(embed = embed)#, file = file)
		return


def setup(prox):
	prox.add_cog(OwnerCommands(prox), override = True)

