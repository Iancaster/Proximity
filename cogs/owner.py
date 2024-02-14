

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
	async def update(self, ctx: ApplicationContext):

		embed, file = await mbd(
			'Update 3.1: The Missing Update!',
			"Okay, this one is all about things not being seen. First, I may or may not" +
				" have forgotten to add `/eavesdrop` before releasing" +
				" Version 3, where I (secondly) also forgot to dub the update" +
				" with a nickname. ||So I guess, *technically,* 3.1" +
				" should have been used on something like location" +
				" descriptions or something, but *whatever,* dude," +
				" it's coming, sheesh.||",
			"At least it isn't ALL stuff I was supposed to do already.")

		embed.add_field(name = 'Features and Fixes.', inline = False, value =
"""
1. Eavesdropping (again)!
  - Revamped menu to choose where you want to listen.
  - Just pick "Nowhere" in the dropdown to stop.
  - Nearby characters will notice when you start or stop.
  - New! Now characters see you snooping when they `/move`.
2. Messages look better!
  - When you eavesdrop, you see their messages look normal.
  - ...Except that it says (Eavesdropping) at the end.
  - ...Which means you can see their images they send now. :D
  - Indirectly overheard messages now say (Overheard).
  - ...And you actually catch parts of the sentence!
  - Not all of it though, gonna have to listen closer...
3. Fixed a few things.
  - `/move`ing into a new place wouldn't let others indirectly hear.
  - Optimized the way messages are sent when proxied.
  - As well as the way listeners are sorted into directness.
"""
)
		#file = File('3.png', filename = 'image.png')
		#embed.set_image(url = 'attachment://image.png')

		await ctx.respond(embed = embed)#, file = file)
		return


def setup(prox):
	prox.add_cog(OwnerCommands(prox), override = True)

