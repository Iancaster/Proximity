

#Import-ant Libraries
from discord import ApplicationContext, Bot, Option, File, \
	OptionChoice, SlashCommandGroup
from discord.ext import commands

from data.listeners import direct_listeners, indirect_listeners, \
	print_listeners
from libraries.classes import GuildData
from libraries.formatting import format_words, format_channels, \
	embolden
from libraries.universal import mbd, send_message

from networkx import DiGraph

#Classes
class DebugCommands(commands.Cog):
	"""
	Commands that only Lancaster can use.
	Maybe in the future I'll enforce that.
	"""


	debug_group = SlashCommandGroup(
		name = 'debug',
		description = 'For testers only! Lets you peer behind the veil.',
		guild_only = True,
		guild_ids = [1114005940392439899])

	@debug_group.command(name = 'listeners', description = 'See what channels proxy their messages to which others.')
	async def listeners(
		self,
		ctx: ApplicationContext,
		listener_type: Option(
			str,
			description = 'Direct or indirect listeners?',
			name = 'type',
			choices = ['direct','indirect'],
			default = 'direct')):

		guild_data = GuildData(ctx.guild.id, load_places = True, load_characters = True)

		channels_to_check = {place.channel_ID : name for name, place in guild_data.places.items()}
		channels_to_check.update(guild_data.characters)

		if not channels_to_check:

			description = f'There are no {listener_type} listeners, which means no' + \
				' messages will be relayed through this avenue.'

			if listener_type == 'direct':
				description += ' Direct communication occurs between a character' + \
					' and those nearby, as well as back and forth with the location.' + \
					' It also encompasses eavesdropping on others.'
			else:
				description += ' Indirect communication encompasses overhearing other' + \
					'characters nearby, without actually eavesdropping on them.'

			embed, _ = await mbd(
				f"{listener_type.capitalize()} Listeners",
				 description,
				'Listeners will appear as characters are made.')
			from discord import MISSING
			await send_message(ctx.respond, embed = embed, file = MISSING, ephemeral = True)
			return

		graph = DiGraph()
		silent_channels = set()
		listener_dict = direct_listeners if listener_type == 'direct' else indirect_listeners
		for channel_ID, name in channels_to_check.items():

			listeners = listener_dict.get(channel_ID, None)
			if not listeners:
				silent_channels.add(name)
				continue

			for listener_channel, _ in listeners:
				graph.add_edge(name, listener_channel.name)

		if graph:
			listener_view = (await guild_data.to_map(graph), 'full')
		else:
			listener_view = None

		description = 'This is a full map of all the listeners in the server.' + \
			' Messages go towards -> the places the arrows point.'

		if silent_channels:
			description += f'\n\nSkipped putting {await embolden(silent_channels)}' + \
				' on the map because they have no channels listening to them.'

		embed, file = await mbd(
			f"{listener_type.capitalize()} Listeners",
			description,
			'Note: character channels should always show on the Direct Listeners map.',
			listener_view)

		await send_message(ctx.respond, embed = embed, file = file, ephemeral = True)
		return


def setup(prox):
	prox.add_cog(DebugCommands(prox), override = True)

