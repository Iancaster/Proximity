

#Import-ant Libraries
from discord import ApplicationContext, Option, \
	SlashCommandGroup, Embed
from discord.ext import commands

from libraries.new_classes import GuildData, ChannelManager, ListenerManager
from libraries.universal import *
from libraries.formatting import *
from data.listeners import *

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
	async def listeners(self, ctx: ApplicationContext, listener_type: Option(str, description = 'Direct or indirect listeners?', name = 'type', choices = ['direct','indirect'], default = 'direct')):

		GD = GuildData(ctx.guild.id, load_places = True, load_characters = True)

		channels_to_check = {place.channel_ID : name for name, place in GD.places.items()}
		channels_to_check.update(GD.characters)

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
				graph.add_edge(name, channels_to_check.get(listener_channel.id, 'Missing channel!'))


		if graph:
			listener_view = (await GD.to_map(graph), 'full')
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

	@debug_group.command(name = 'server', description = 'Look into the data the server has.')
	async def server(self, ctx: ApplicationContext):

		await ctx.defer(ephemeral = True)

		GD = GuildData(
			ctx.guild_id,
			load_places = True,
			load_characters = True,
			load_roles = True)

		embed = Embed(
			title = 'Debug details.',
			description = 'A complete look into what the' + \
				' databases hold for this server.',
			color = 670869)

		embed.set_footer(text = 'Peer behind the veil.')

		if GD.places:

			description = ''
			for index, place in enumerate(GD.places.values()):
				description += f"\n{index}. <#{place.channel_ID}>"
				if place.allowed_roles or place.allowed_characters:
					description += "\n-- Whitelist:" + \
						f" {await format_whitelist(place.allowed_roles, place.allowed_characters)}"
				if place.occupants:
					occupant_mentions = await format_channels(place.occupants)
					description += f'\n-- Occupants: {occupant_mentions}.'
				if place.neighbors:
					neighbors = [f'**#{name}**' for name in place.neighbors.keys()]
					description += f'\n-- Neighbors: {await format_words(neighbors)}.'

			embed.add_field(
				name = 'Places:',
				value = description[:1500],
				inline = False)
		else:
			embed.add_field(
				name = 'No places.',
				value = 'You can make some places with `/new place`.',
				inline = False)

		if GD.characters:
			embed.add_field(
				name = 'Characters:',
				value = f'\n• {await format_channels(GD.characters.keys())}',
				inline = False)
		else:
			embed.add_field(
				name = 'No characters.',
				value = 'You can add some new characters with `/new character`.',
				inline = False)

		if GD.roles:
			embed.add_field(
				name = 'Protected Roles:',
				value = f"\n• {await format_words([f'<@&{ID}>' for ID in GD.roles])}" + \
					'\n\*Note: "Protected Roles" are roles that have been added to a whitelist' + \
					" and so there's a failsafe to prevent accidentally deleting that role.",
				inline = False)
		else:
			embed.add_field(
				name = 'No protected roles.',
				value = 'Roles become protected by being added to a whitelist.',
				inline = False)

		await send_message(ctx.respond, embed)
		return

def setup(prox):
	prox.add_cog(DebugCommands(prox), override = True)

