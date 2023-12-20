

#Import-ant Libraries
from discord import ApplicationContext, Option, Interaction, Embed, MISSING
from discord.ext import commands
from discord.commands import SlashCommandGroup
from discord.utils import get

from libraries.classes import GuildData, DialogueView
from libraries.universal import mbd, loading, \
	identify_place_channel, no_redundancies, send_message
from libraries.formatting import unique_name, format_whitelist, \
	format_places, format_words, format_channels, format_colors
from libraries.autocomplete import complete_places
from data.listeners import to_direct_listeners, queue_refresh

from networkx import DiGraph, ego_graph, compose

#Classes
class ReviewCommands(commands.Cog):

	review_group = SlashCommandGroup(
		name = 'review',
		description = 'Review any part of the server, from places to people.',
		guild_only = True)

	@review_group.command(name = 'server', description = 'Change how the server works. Temporary content.')
	async def server(self, ctx: ApplicationContext):

		await ctx.defer(ephemeral = True)

		guild_data = GuildData(
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

		if guild_data.places:

			description = ''
			for index, place in enumerate(guild_data.places.values()):
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

		if guild_data.characters:
			embed.add_field(
				name = 'Characters:',
				value = f'\n• {await format_channels(guild_data.characters.keys())}',
				inline = False)
		else:
			embed.add_field(
				name = 'No characters.',
				value = 'You can add some new characters with `/new character`.',
				inline = False)

		if guild_data.roles:
			embed.add_field(
				name = 'Protected Roles:',
				value = f"\n• {await format_words([f'@&{ID}>' for ID in guild_data.roles])}" + \
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

	@review_group.command(name = 'place', description = 'View or revise the places.')
	async def place(self, ctx: ApplicationContext, given_place: Option(str, description = 'Which place?', name = 'place', autocomplete = complete_places, required = False)):

		await ctx.defer(ephemeral = True)

		guild_data = GuildData(ctx.guild_id, load_places = True)

		async def review_places(place_names: list):

			reviewing_places = await guild_data.filter_places(place_names)

			if len(reviewing_places) == 1:
				reviewing_place = list(reviewing_places.values())[0]
				title = f'Reviewing <#{reviewing_place.channel_ID}>'
				description = ''
			else:
				title = f'Reviewing {len(reviewing_places)} place(s).'
				description = f"• Selected places: {await format_places(reviewing_places.values())}"

			occupants = await guild_data.get_occupants(reviewing_places.values())
			description += f"\n• Occupants: {await format_channels(occupants) if occupants else 'No people here.'}"

			graph = await guild_data.to_graph()
			subgraph = DiGraph()
			for place in place_names:
				ego = ego_graph(graph, place, radius = 1)
				subgraph = compose(subgraph, ego)

			if len(subgraph.nodes) >= len(place_names):
				graph_view = (await guild_data.to_map(subgraph), 'full')
			else:
				description += "\n• Neighbors: There are no paths that connect this to other places."
				graph_view = None

			async def refresh():

				nonlocal description

				full_description = description
				if view.name():
					new_name = await unique_name(view.name(), guild_data.places.keys())
					full_description = f'• Renaming this place to {new_name}.\n{description}'

				full_description += await view.format_whitelist(reviewing_places.values())

				embed, _ = await mbd(
					title,
					full_description,
					'You can rename a place if you have only one selected.',
					graph_view)
				return embed, MISSING

			def checks():
				return not (view.roles() or view.characters() or view.name() or view.clearing)

			async def submit(interaction: Interaction):

				await loading(interaction)

				nonlocal reviewing_places
				new_name = await unique_name(view.name(), guild_data.places.keys())

				description = ''

				if view.clearing:
					description += '\n• Removed the whitelist(s).'
					for name, place in reviewing_places.items():

						await guild_data.places[name].clear_whitelist()
						embed, _ = await mbd(
							'Opening up.',
							'You somehow feel like this place just easier to get to.',
							'For better or for worse.')
						await to_direct_listeners(embed,
							interaction.guild,
							place.channel_ID,
							occupants_only = True)

				if view.roles() or view.characters():

					description += '\n• New whitelist: ' + \
						await format_whitelist(view.roles(), view.characters())

					embed, _ = await mbd(
						'Strange.',
						"There's a sense that this place just changed in some way.",
						"Only time will tell if you'll be able to return here as easily as you came.")

					for name, place in reviewing_places.items():
						await to_direct_listeners(embed,
							interaction.guild,
							place.channel_ID,
							occupants_only = True)

						await guild_data.places[name].set_roles(view.roles())
						await guild_data.places[name].set_players(view.players())

				await guild_data.save()

				if new_name:

					old_name = list(reviewing_places.keys())[0]
					place_data = guild_data.places[old_name]

					place_channel = get(interaction.guild.text_channels, id = place_data.channel_ID)
					await place_channel.edit(name = new_name)

					description += f"\n• Renamed **#{old_name}** to <#{place_data.channel_ID}>."


				await queue_refresh(interaction.guild)

				embed, _ = await mbd(
					'Edited.',
					description,
					'Another successful revision.')
				for place in reviewing_places.values():
					place_channel = get(interaction.guild.text_channels, id = place.channel_ID)
					await place_channel.send(embed = embed)

				return await no_redundancies(
					(interaction.channel.name in reviewing_places or interaction.channel.name == new_name),
					embed,
					interaction)

			view = DialogueView(refresh, checks)
			await view.add_roles()
			await view.add_characters(guild_data.characters)
			await view.add_submit(submit)
			if len(reviewing_places) == 1:
				await view.add_rename(place_names[0])
			if any(place.allowed_roles or place.allowed_characters for place in reviewing_places.values()):
				await view.add_clear()
			await view.add_cancel()
			embed, _ = await refresh()
			_, file = await mbd(image_details = graph_view)

			await send_message(ctx.respond, embed, view, file, ephemeral = True)
			return

		result = await identify_place_channel(guild_data.places.keys(), ctx.channel.name, given_place)
		match result:
			case _ if isinstance(result, Embed):
				await send_message(ctx.respond, result)
			case _ if isinstance(result, str):
				await review_places([result])
			case None:
				embed, _ = await mbd(
					'Review place(s)?',
					"You can review a place four ways:" + \
						"\n• Call this command inside of a place channel." + \
						"\n• Do `/review place review #place-channel`." + \
						"\n• Select one or more places with the list below." + \
						"\n• To rename a place, you can just rename the channel.",
					'This will allow you to view place details, like paths and whitelists.')

				async def submit_locations(interaction: Interaction):
					await ctx.delete()
					await review_places(view.places())
					return

				view = DialogueView()
				await view.add_places(guild_data.places.keys(), callback = submit_locations)
				await view.add_cancel()
				await send_message(ctx.respond, embed, view)

		return

	@review_group.command(name = 'path', description = 'Look at (or edit) paths.')
	async def path(self, ctx: ApplicationContext, given_place: Option(str, description = 'Which place to start from?', name = 'place', autocomplete = complete_places, required = False)):

		await ctx.defer(ephemeral = True)

		guild_data = GuildData(ctx.guild_id, load_places = True)

		async def review_paths(place_name: str):

			place_name = place_name
			origin_place = guild_data.places[place_name]
			neighbors = origin_place.neighbors
			if not neighbors:
				embed, _ = await mbd(
					'No paths.',
					f'<#{origin_place.channel_ID}> has no paths to review. It' + \
						" isn't connected to any other places.",
					'You can make some with /new path.')
				await send_message(ctx.respond, embed, ephemeral = True)
				return

			impacted_places = await guild_data.filter_places(list(neighbors.keys()) + [place_name])
			graph = await guild_data.to_graph(impacted_places)
			selected_paths = []
			graph_view = None

			async def refresh():

				nonlocal place_name, origin_place, selected_paths, graph_view
				full_description = f'• Selected place: <#{origin_place.channel_ID}>'

				if view.paths():
					full_description += '\n• Selected Path(s): See below.'
					revising_paths = [origin_place.neighbors[name] for name in view.paths()]
					full_description += await view.format_whitelist(revising_paths)
				else:
					full_description += '\n• Use the dropdown below to select one or more' + \
						' paths. You can look at the whitelists or overwrite them.'

				if view.paths() and view.paths != selected_paths:
					selected_paths = view.paths()
					path_colors = await format_colors(graph, place_name, view.paths(), 'blue')
					graph_view = (await guild_data.to_map(graph, path_colors), 'full')
				elif view.paths != selected_paths:
					selected_paths = view.paths()
					graph_view = (await guild_data.to_map(graph), 'full')

				embed, file = await mbd(
					'Review path(s)?',
					full_description,
					'You can change these back at any time.',
					graph_view)
				return embed, file

			def checks():
				return not (view.paths() and (view.roles() or view.characters() or view.clearing))

			async def submit(interaction: Interaction):

				await interaction.response.defer()

				if view.clearing:
					description = '\n• Removed the whitelist(s).'
					for neighbor_name in view.paths():
						await origin_place.neighbors[neighbor_name].clear_whitelist()
						await guild_data.places[neighbor_name].neighbors[place_name].clear_whitelist()

				else:
					revising_paths = [origin_place.neighbors[name] for name in view.paths()][0]
					description = await view.format_whitelist(revising_paths)
					description = f'\n• Changed the whitelist to: {await format_whitelist(view.roles(), view.characters())}'

					for neighbor_name in view.paths():
						origin_place.neighbors[neighbor_name].allowed_roles = view.roles()
						guild_data.places[neighbor_name].neighbors[place_name].allowed_characters = view.characters()

				await guild_data.save()

				#Inform neighbors occupants and neighbor locations
				neighbor_places = await guild_data.filter_places(view.paths())
				neighbor_mentions = await format_places(neighbor_places.values())
				player_embed, _ = await mbd(
					'Hm?',
					f"You feel like the way to **#{place_name}** changed somehow.",
					'Will it be easier to travel through, or harder?')
				place_embed, _ = await mbd(
					f'Path with <#{origin_place.channel_ID}> changed.',
					description,
					'You can view its details with /review path.')
				for place in neighbor_places.values():
					await to_direct_listeners(
						player_embed,
						interaction.guild,
						place.channel_ID,
						occupants_only = True)
					place_channel = get(interaction.guild.text_channels, id = place.channel_ID)
					await place_channel.send(embed = place_embed)

				#Inform edited location occupants
				player_embed, _ = await mbd(
					'Hm?',
					"You notice that there's been a change in the way this" + \
						f" place is connected to {neighbor_mentions}.",
					"Perhaps you're only imagining it.")
				await to_direct_listeners(
					player_embed,
					interaction.guild,
					origin_place.channel_ID,
					occupants_only = True)

				#Inform own location
				embed, _ = await mbd(
					f'Path(s) with {neighbor_mentions} changed.',
					description,
					'You can always undo these changes.')
				place_channel = get(interaction.guild.text_channels, id = origin_place.channel_ID)
				await place_channel.send(embed = embed)

				return await no_redundancies(
					(interaction.channel.name in view.paths() or interaction.channel.id == origin_place.channel_ID),
					embed,
					interaction)

			view = DialogueView(refresh, checks)
			await view.add_paths(neighbors)
			await view.add_roles()
			await view.add_characters(guild_data.characters)
			await view.add_submit(submit)
			if any(path.allowed_roles or path.allowed_characters for path in neighbors.values()):
				await view.add_clear()
			await view.add_cancel()
			embed, file = await refresh()

			await send_message(ctx.respond, embed, view, file, ephemeral = True)
			return

		result = await identify_place_channel(guild_data.places.keys(), ctx.channel.name, given_place)
		match result:
			case _ if isinstance(result, Embed):
				await send_message(ctx.respond, result)
			case _ if isinstance(result, str):
				await review_paths(result)
			case None:
				embed, _ = await mbd(
					'Review path(s)?',
					"You can review path whitelists three ways:" + \
						"\n• Call this command inside of a place channel." + \
						"\n• Do `/review path #place-channel`." + \
						"\n• Select a place with the list below.",
					"This is just to select the origin, you'll select which paths next.")

				async def submit_location(interaction: Interaction):
					await ctx.delete()
					await review_paths(list(view.places())[0])
					return

				view = DialogueView()
				await view.add_places(guild_data.places.keys(), callback = submit_location)
				await view.add_cancel()
				await send_message(ctx.respond, embed, view)

		return

def setup(prox):
	prox.add_cog(ReviewCommands(prox), override = True)
