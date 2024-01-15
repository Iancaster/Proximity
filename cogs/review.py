

#Import-ant Libraries
from discord import ApplicationContext, Option, Interaction, Embed
from discord.ext import commands
from discord.commands import SlashCommandGroup
from discord.utils import get, get_or_fetch

from libraries.classes import GuildData, DialogueView, Character
from libraries.universal import mbd, loading, no_redundancies, \
	send_message, identify_place_channel, character_change, \
	identify_character_channel
from libraries.formatting import format_channels, discordify, \
	unique_name, format_whitelist, format_colors, format_roles, \
	format_avatar, format_places, format_characters
from libraries.autocomplete import complete_places, complete_characters
from data.listeners import to_direct_listeners, queue_refresh

from networkx import DiGraph, ego_graph, compose

# Classes
class ReviewCommands(commands.Cog):

	review_group = SlashCommandGroup(
		name = 'review',
		description = 'Review any part of the server, from places to people.',
		guild_only = True)


	@review_group.command(name = 'place', description = 'View or revise the places.')
	async def place(self, ctx: ApplicationContext, given_place: Option(str, description = 'Which place?', name = 'place', autocomplete = complete_places, required = False)):

		await ctx.defer(ephemeral = True)

		guild_data = GuildData(ctx.guild_id, load_places = True, load_characters = True)

		async def review_places(place_names: list):

			reviewing_places = await guild_data.filter_places(place_names)

			if len(reviewing_places) == 1:
				reviewing_place = list(reviewing_places.values())[0]
				title = f'Reviewing <#{reviewing_place.channel_ID}>'
				description = ''
			else:
				title = f'Reviewing {len(reviewing_places)} place(s).'
				description = f"• Selected places: {await format_channels({place.channel_ID for place in reviewing_places.values()})}"

			occupants = await guild_data.get_occupants(reviewing_places.values())
			description += f"\n• Occupants: {await format_channels(occupants) if occupants else 'No people here.'}"

			graph = await guild_data.to_graph()
			subgraph = DiGraph()
			for place in place_names:
				ego = ego_graph(graph, place, radius = 1)
				subgraph = compose(subgraph, ego)

			if subgraph.edges:
				graph_view = (await guild_data.to_map(subgraph), 'full')
			else:
				description += "\n• Neighbors: There are no paths connected to any of the places you gave."
				graph_view = None

			new_name = None

			async def refresh():

				nonlocal description, new_name

				full_description = description
				if view.name():
					new_name = await discordify(view.name())
					new_name = await unique_name(new_name, guild_data.places.keys())
					full_description = f'• Renaming this place to {new_name}.\n{description}'
				else:
					new_name = None

				full_description += await view.format_whitelist(reviewing_places.values())

				embed, _ = await mbd(
					title,
					full_description,
					'You can rename a place if you have only one selected.',
					graph_view)
				return embed, None

			def checks():
				nonlocal new_name
				return not (view.roles() or view.characters() or new_name or view.clearing)

			async def submit(interaction: Interaction):

				await loading(interaction)

				nonlocal reviewing_places, new_name

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
						await guild_data.places[name].set_characters(view.characters())

				if new_name:

					old_name = list(reviewing_places.keys())[0]
					place_data = guild_data.places.pop(old_name)
					guild_data.places[new_name] = place_data

					place_channel = get(interaction.guild.text_channels, id = place_data.channel_ID)
					await place_channel.edit(name = new_name)

					description += f"\n• Renamed **#{old_name}** to <#{place_data.channel_ID}>."

				await guild_data.save()

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
					"You can review a place four ways:" +
						"\n• Call this command inside of a place channel." +
						"\n• Do `/review place review #place-channel`." +
						"\n• Select one or more places with the list below." +
						"\n• To rename a place, you can just rename the channel.",
					'This will allow you to view place details, like paths and whitelists.')

				async def submit_locations(interaction: Interaction):
					await ctx.delete()
					await review_places(view.places())
					return

				view = DialogueView()
				await view.add_places(guild_data.places.keys(), singular = False, callback = submit_locations)
				await view.add_cancel()
				await send_message(ctx.respond, embed, view = view)

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
				neighbor_mentions = await format_channels({place.channel_ID for place in neighbor_places.values()})
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

	@review_group.command(name = 'character', description = 'Review a character.')
	async def character(self, ctx: ApplicationContext, given_character: Option(str, description = 'Which character?', name = 'character', autocomplete = complete_characters, required = False)):

		await ctx.defer(ephemeral = True)

		guild_data = GuildData(ctx.guild_id, load_places = True, load_characters = True)

		async def review_character(reviewing_characters: dict):

			characters_dict = {char_ID : Character(char_ID) for char_ID in reviewing_characters.keys()}
			if len(reviewing_characters) == 1:
				char_ID, char_name = list(reviewing_characters.items())[0]
				char_data = Character(char_ID)
				valid_url = False
			else:
				existing_locations = {character.location for character in characters_dict.values()}
				existing_roles = {role for character in characters_dict.values() for role in character.roles}


			async def singular_refresh():

				nonlocal valid_url

				if view.name():
					description = f'• Name: ~~{char_name}~~, renaming to *{view.name()}*'
				else:
					description = f'• Name: *{char_name}*'

				if view.places():
					description += f'\n• Location: ~~#{char_data.location}~~, relocating to **#{view.places()[0]}**'
				else:
					description += f'\n• Location: **#{char_data.location}**'

				if view.clearing:
					description += '\n• Roles: Being cleared!'
				elif view.roles():
					description += f'\n• Roles: Being set to {await format_roles(view.roles())}.'
				elif char_data.roles:
					description += f'\n• Roles: {await format_roles(char_data.roles)}'

				if char_data.eavesdropping and guild_data.eavesdropping_allowed:
					description += f'\n• Eavesdropping on: **#{char_data.eavesdropping}**'

				if view.url():
					avatar, valid_url, avatar_message = await format_avatar(view.url())
					description += f'\n• Avatar: {avatar_message}'
				else:
					avatar, valid_url = None, False

				embed, file = await mbd(
					f'Reviewing <#{char_ID}>',
					description,
					'You can rename them, relocate them, and change their roles.',
					(avatar, 'thumb'))
				return embed, file

			async def multiple_refresh():

				description = f'• Names: {await format_characters(reviewing_characters.values())}'

				if view.places():
					description += f'\n• Location: Relocating characters to **#{view.places()[0]}**'
				else:
					description += f'\n• Location(s): {await format_places(existing_locations)}'

				if view.clearing:
					description += '\n• Roles: Being cleared!'
				elif view.roles():
					description += f'\n• Roles: Being set to {await format_roles(view.roles())}.'
				elif existing_roles:
					description += f'\n• Roles: {await format_roles(existing_roles)}'

				embed, _ = await mbd(
					f'Reviewing {len(reviewing_characters)} Characters',
					description,
					'Select only one character to change their avatar or name.')

				return embed, _

			def checks():
				return not (view.places() or view.roles() or view.name() or view.clearing)

			async def submit(interaction: Interaction):

				await loading(interaction)

				character_channels = {char_ID : await get_or_fetch('channel', interaction.guild, char_ID) for char_ID in reviewing_characters}

				description = ''
				if len(reviewing_characters) == 1:

					if view.name():
						description += f"• Changed *{char_name}*'s name to *{view.name()}*."
						char_data.name = view.name()
						await character_channels[char_ID].edit(name = view.name())

					if view.url() and valid_url:
						description += f"• Changed *{char_data.name}*'s avatar to *{view.url()}*."
						char_data.avatar = view.url()

					if view.name() or view.url():
						await character_change(character_channels[char_ID], char_data)

					title = f'Reviewed {char_data.name}'

				else:
					title = f'Reviewed {len(reviewing_characters)} Characters.'
					description += f"• Did the following to {await format_channels(reviewing_characters.keys())}."

				if view.clearing:
					description += "• Removed their role(s)."
					for character in characters_dict.values():
						character.roles = set()

				elif view.roles():

					description += f"• Changed their role(s) to {await format_roles(view.roles())}."
					for character in characters_dict.values():
						character.roles = view.roles()

				if view.places():

					destination_name = view.places()[0]
					destination_place = guild_data.places[destination_name]
					description += f"• Relocated them to <#{destination_place.channel_ID}>."

					vacating_places = {char_data.location : \
						{}.setdefault(char_data.location, set()).union({char_ID}) \
						for char_ID, char_data in characters_dict.items()}

					for location, moving_people in vacating_places.items():

						moving_names = {guild_data.characters[char_ID] for char_ID in moving_people}
						place = guild_data.places[location]
						place.remove_occupants(moving_people)

						embed, _ = await mbd(
							'Poof.',
							f'{await format_characters(moving_names)} just got whisked away.',
							"But to where?")
						await to_direct_listeners(
							embed,
							interaction.guild,
							place.channel_ID)

						embed, _ = await mbd(
							'Teleported.',
							f'Relocated {await format_channels(moving_people)} to' +
								f' <#{place.channel_ID}>.',
							'You can further relocate them with /review player.')
						origin_channel = await get_or_fetch('channel', interaction.guild, place.channel_ID)
						await origin_channel.send(embed = embed)

					for character_data in characters_dict.items():
						character_data.location = destination_name

					destination_place.add_occupants(characters_dict.keys())
					await guild_data.save()

					await queue_refresh(interaction.guild)

					embed, _ = await mbd(
						'Whoosh.',
						f'{await format_characters(moving_names)} just appeared here at **#{destination_name}**.',
						"How strange.")
					await to_direct_listeners(
						embed,
						interaction.guild,
						destination_place.channel_ID)

					embed, _ = await mbd(
						'New arrival(s).',
						f'{await format_characters(reviewing_characters.values())} got teleported here.',
						"You can move them again using /review player.")
					destination_channel = await get_or_fetch('channel', interaction.guild, destination_place.channel_ID)

				embed, _ = await mbd(
					title,
					description,
					'You can always undo your changes by calling /review player again.')
				return await no_redundancies(
					(interaction.channel.id in reviewing_characters),
					embed,
					interaction)





			if len(reviewing_characters) == 1:
				view = DialogueView(singular_refresh, checks)
				other_places = set(guild_data.places.keys())
				other_places.remove(char_data.location)
				await view.add_places(other_places)
				await view.add_roles()
				await view.add_submit(submit)
				await view.add_rename(char_name[:24])
				await view.add_URL()
				if char_data.roles:
					await view.add_clear()
				embed, file = await singular_refresh()
			else:
				view = DialogueView(multiple_refresh, checks)
				await view.add_places(guild_data.places.keys())
				await view.add_roles()
				await view.add_submit(submit)
				if existing_roles:
					await view.add_clear()
				embed, file = await multiple_refresh()

			await view.add_cancel()

			await send_message(ctx.respond, embed, view, ephemeral = True)
			return

		result = await identify_character_channel(guild_data.characters, ctx.channel.id, given_character)
		match result:
			case _ if isinstance(result, Embed):
				await send_message(ctx.respond, result)
			case _ if isinstance(result, dict):
				await review_character(result)
			case None:

				description = 'You can review a character three ways:' + \
					'\n• Call this command inside of a character channel.' + \
					'\n• Do `/review character character-name`.' + \
					'\n• Select a character from the dropdown below.'

				async def refresh():

					nonlocal description

					if view.character_select.values and not view.characters():
						description = 'Because you have more characters than can' + \
							' fit in a Text dropdown, this uses a Channel dropdown.' + \
							" It's almost the same, just choose the character channels" + \
							' instead of the character names. Non-character channels' + \
							' get ignored.'

					embed, _ = await mbd(
						'Review character?',
						description,
						"This will only select them, you'll see their details after this.")
					return embed, None

				def checks():
					return not view.characters()

				async def submit_characters(interaction: Interaction):
					await ctx.delete()
					await review_character(view.characters())
					return

				view = DialogueView()
				await view.add_characters(guild_data.characters, callback = submit_characters)
				await view.add_cancel()
				embed, _ = await refresh()
				await send_message(ctx.respond, embed, view)

		return

def setup(prox):
	prox.add_cog(ReviewCommands(prox), override = True)
