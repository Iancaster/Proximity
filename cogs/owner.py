

#Import-ant Libraries
from discord import ApplicationContext, Bot, Option, File
from discord.ext import commands
from libraries.universal import mbd, send_message


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
			'Version 3 Forum!',
			"There's never been a bigger update to this bot, and you've got lots of questions." + \
				" This temporary channel should shed some light.",
			"Read up on it while you can!")

		embed.add_field(name = 'New Info!', inline = False, value =
"""
1. View how far along 3.0 is with <#1190733014557265930>.
  - See what commands are ready, and which ones are up next.
  - This will stay current as more commands get finished.
2. See the <#1190732367942389882>.
  - This has been moved from <#1158808448499191841>.
  - That channel is more of a checklist of things to get around to.
  - Meanwhile, this channel is a detailed look at what's confirmed.
3. Read up on the <#1190742719803424920>!
  - Talks about compatibility, features, and the timeline.
  - I'll add new questions on there and their answers, as they come.
""")
		#file = File('ghost.png', filename = 'image.png')
		#embed.set_image(url = 'attachment://image.png')

		await ctx.respond(embed = embed)#, file = file)
		return


def setup(prox):
	prox.add_cog(OwnerCommands(prox), override = True)

