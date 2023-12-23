

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
	async def repeat(self, ctx: ApplicationContext, header: Option( str, description = 'What should the title be?', default = None), body: Option( str, description = 'What should the body be?', default = None), footer: Option( str, description = 'What should the footer be?', default = None)):

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
			'3.0 Upgrades: Multiple OCs!',
			"Way back when, in ye olde days of 2.0 and before, you could only have" + \
				" one character per person. It was a 'player channel', not a 'character" + \
				" channel', after all. This was the main reason that inspired me to do" + \
				" a version 3.0 at all, actually, was to correct that limitation.",
			"You would not *believe* just how much needed to be redone to make this happen.")

		embed.add_field(name = 'No More Player Channels', inline = False, value =
"""
1. People are no longer "players" or not, they just have access to characters or not.
  - You can roleplay as a character if you can send messages in their channel.
  - You can have access to as many characters channels as the host(s) like.
  - Multiple people can have access to the same character, if desired.
  - You can still see *who* is the one controlling the character.
  - ...Just look at who sent the message in the character channel.
2. Character cap removed!
  - If there's less than 25 characters, the dropdowns are text-selects.
  - If there's more than that, it's a channel-select.
  - Just select the character channel corresponding to the character.
  - This type of select-menu has a search bar built in. :)
  - It's a Discord thing, they won't let you do more than 25 with text.
  - It's just with the menus in the commands, everything else runs the same.
""")
		#file = File('ghost.png', filename = 'image.png')
		#embed.set_image(url = 'attachment://image.png')

		await ctx.respond(embed = embed)#, file = file)
		return


def setup(prox):
	prox.add_cog(OwnerCommands(prox), override = True)

