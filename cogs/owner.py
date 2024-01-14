

#Import-ant Libraries
from discord import ApplicationContext, Bot, Option, File
from discord.ext import commands
from libraries.universal import *

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
			'Getting Off the Hook.',
			"The webhook, specifically. It's the technology that Tupper and Proximity" + \
				" both use in order to make characters talk. That's done, plus `/delete character`. :)",
			"Break it, I dare ya.")

		embed.add_field(name = 'Webhook, Line, and Sinker.', inline = False, value =
"""
1. Webhooks have been fixed and optimized.
  - Deleting a webhook does not break the bot!
  - It recreates it for both character channels as well as places.
  - This technically *was* a feature back before, but it was bugged.
  - It's now much faster as well, only deletes excess webhooks.
  - And only reproduces the webhook if needed.
2. `/delete character` is \*finished!-
  - \*Just needs to be tested...
  - Delete a character by deleting their channel.
  - Or by using the command, like with `/delete place`.
  - Guide to follow, once we burn through some of the others.
  - Now onto `/review character`...
""")
		#file = File('ghost.png', filename = 'image.png')
		#embed.set_image(url = 'attachment://image.png')

		await ctx.respond(embed = embed)#, file = file)
		return


def setup(prox):
	prox.add_cog(OwnerCommands(prox), override = True)

