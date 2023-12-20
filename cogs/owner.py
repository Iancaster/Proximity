

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
		 description = 'Repeat something as an embed.',
		 guild_ids = [1114005940392439899])
	async def repeat(
		self,
		ctx: ApplicationContext,
		header: Option(
			 str,
			 description = 'What should the title be?',
			 default = None),
		body: Option(
			 str,
			 description = 'What should the body be?',
			 default = None),
		footer: Option(
			 str,
			 description = 'What should the footer be?',
			 default = None)):

		embed, _ = await mbd(header, body, footer)
		await ctx.respond(embed = embed)
		return

	@commands.slash_command(
		 description = 'Custom embed.',
		 guild_ids = [1114005940392439899])
	async def say(self, ctx: ApplicationContext):

		if ctx.author.id != 985699127742582846:
			await ctx.respond('I do not believe you are the one who is supposed to be using this command.', ephemeral = True)
			return


		embed, file = await mbd(
			'3.0 Upgrades: No more wrong answers!',
			"In the early days, if you tried to press 'Submit' without putting" + \
				" in the right info, it would bug. Then, I made it so it would" + \
				" recognize when you gave it conflicting information (or not enough)," + \
				" and tell you what to fix. Now it's even better than that!",
			"The ultimate form of input sanitation...")

		embed.add_field(name = 'Sensitive Submit Buttons', inline = False, value =
"""
1. Submit buttons only turn on when they're ready.
  - It starts off grey and disabled.
  - Once you put in enough info, it'll turn green and clickable.
  - No more invalid submissions, and then having to redo it.
  - Some buttons are green right away, like `/delete server`.
  - ...But stuff like `/new path` has you define a destination first, for example.
""")
		#file = File('ghost.png', filename = 'image.png')
		#embed.set_image(url = 'attachment://image.png')

		await ctx.respond(embed = embed)#, file = file)
		return


def setup(prox):
	prox.add_cog(OwnerCommands(prox), override = True)

