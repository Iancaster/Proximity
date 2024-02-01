

#Import-ant Libraries
from discord import ApplicationContext, Option, Interaction, Embed
from discord.ext import commands
from discord.commands import SlashCommandGroup
from discord.utils import get_or_fetch

from libraries.new_classes import GuildData, ChannelManager, Path, Location, \
	DialogueView, Character, ListenerManager
from libraries.universal import mbd, loading, no_redundancies, \
	send_message, identify_place_channel, character_change
from libraries.formatting import format_words, discordify, unique_name, \
	format_whitelist, format_new_neighbors, embolden, \
	format_channels, format_roles, format_avatar
from libraries.autocomplete import complete_places, exclusionary_places
from data.listeners import direct_listeners, queue_refresh, \
	to_direct_listeners


#Classes
class NewCommands(commands.Cog):

	new_group = SlashCommandGroup(
		name = 'new',
		description = 'Create new locations, paths, and characters.',
		guild_only = True)

	@new_group.command(name = 'place', description = 'Create a new place.')
	async def place(self, ctx: ApplicationContext, name: Option(str, description = 'What should it be called?') = ''):

		await ctx.defer(ephemeral = True)

		GD = GuildData(
			ctx.guild_id,
			load_places = True,
			load_characters = True,
			load_roles = True)

		submitted_name = await discordify(name)
		name = submitted_name if submitted_name else 'new-place'

		async def refresh(interaction: Interaction = None):

			nonlocal name
			name = view.name() or name
			name = await discordify(name)
			name = await unique_name(name, GD.places.keys())

			description = f'Whitelist: {await format_whitelist(view.roles(), view.characters().keys())}'

			embed, file = await mbd(
				f'New location: {name}',
				description,
				'You can also create a whitelist to limit who can visit this place.')
			return embed, file

		async def submit(interaction: Interaction):

			await loading(interaction)

			CM = ChannelManager(interaction.guild)
			new_channel = await CM.create_channel('places', name)

			await GD.create_place(
				name = name,
				channel_ID = new_channel.id,
				role_IDs = view.roles(),
				char_IDs = view.characters())
			GD.roles |= view.roles()
			await GD.save()

			embed, _ = await mbd(
				 f'**{name.capitalize()}** created!',
				 f"Go check it out at {new_channel.mention}.",
				 "And remember to connect it using /new path.")
			await interaction.followup.edit_message(
				 message_id = interaction.message.id,
				 embed = embed,
				 view = None)

			whitelist = await format_whitelist(view.roles(), view.characters())
			embed, _ = await mbd(
				'Cool, new place.',
				f"{whitelist} If you want to change that, you can use `/review place`.",
				"Don't forget to connect this place to other places with /new path.")
			await new_channel.send(embed = embed)
			return

		view = DialogueView(refresh)
		await view.add_roles()
		await view.add_characters(GD.characters)
		await view.add_submit(submit)
		await view.add_rename(name)
		await view.add_cancel()

		embed, _ = await refresh()
		await send_message(ctx.respond, embed, view)
		return

	@new_group.command(name = 'path', description = 'Connect two places.')
	async def path(self, ctx: ApplicationContext, origin: Option(str, description = 'Which place to start from?', autocomplete = exclusionary_places) = ''):

		await ctx.defer(ephemeral = True)

		GD = GuildData(
			ctx.guild_id,
			load_places = True,
			load_characters = True,
			load_roles = True)
		CM = ChannelManager(GD = GD)

		async def create_paths(origin_place_name: str):

			origin_place_name = origin_place_name
			origin_place = GD.places[origin_place_name]
			destinations = set()

			async def refresh(interaction: Interaction = None):

				nonlocal destinations

				description = f'• Origin: <#{origin_place.channel_ID}>'

				destination_message, destinations = await format_new_neighbors(
					view.overwriting,
					origin_place,
					view.places(),
					GD)

				description += destination_message

				description += f"\n• Whitelist: {await format_whitelist(view.roles(), view.characters())}"

				match view.directionality:
					case 0:
						description += "\n• Directionality: **One-way** (<-) from" + \
							f" the destination(s) to <#{origin_place.channel_ID}>."
					case 1:
						description += "\n• Directionality: **Two-way** (<->), people will be able to travel" + \
							f" back and forth between <#{origin_place.channel_ID}> and the destination(s)."
					case 2:
						description += "\n• Directionality: **One-way** (->) to" + \
							f" <#{origin_place.channel_ID}> to the destination(s)."

				if origin_place.neighbors:
					if view.overwriting:
						description += "\n• **Overwriting** paths. Old paths will be erased where new one are laid."
					else:
						description += "\n• Will not overwrite paths. Click below to toggle."

				embed, file = await mbd(
					'New path(s).',
					description,
					'Which places are we hooking up?')

				return embed, file

			def checks():
				#nonlocal destinations
				return not destinations

			async def submit(interaction: Interaction):

				await loading(interaction)

				#nonlocal origin_place_name, destinations

				#Make paths
				path = Path(
					directionality = view.directionality,
					allowed_roles = view.roles(),
					allowed_characters = view.characters())
				existing_paths = 0
				for destination in destinations:

					if await GD.set_path(
						origin_place_name,
						destination,
						path,
						view.overwriting):

						existing_paths += 1

				await GD.save()
				neighbors_dict = await GD.filter_places(destinations)
				await queue_refresh(interaction.guild)

				whitelist = await format_whitelist(view.roles(), view.characters())

				#Inform neighbors occupants and neighbor places
				player_embed, _ = await mbd(
					'Hm?',
					f"You notice a way to get between this place and **#{origin_place_name}**. Has that always been there?",
					'And if so, has it always been like that?')
				place_embed, _ = await mbd(
					'Path created.',
					f'• Created a path between here and <#{origin_place.channel_ID}>.' + \
						f'\n• {whitelist}',
					'You can view its details with /review path.')
				for place in neighbors_dict.values():

					await to_direct_listeners(
						player_embed,
						interaction.guild,
						place.channel_ID,
						occupants_only = True)
					place_channel = await get_or_fetch(interaction.guild, 'channel', place.channel_ID)
					await place_channel.send(embed = place_embed)

				#Inform edited place occupants
				bold_neighbors = await embolden(destinations)
				player_embed, _ = await mbd(
					'Hm?',
					f"You notice that this place is connected to {bold_neighbors}. Something about that seems new.",
					"Perhaps you're only imagining it.")
				await to_direct_listeners(
					player_embed,
					interaction.guild,
					origin_place.channel_ID,
					occupants_only = True)

				#Inform own place
				description = f'\n• Connected <#{origin_place.channel_ID}>'
				match view.directionality:
					case 0:
						description += ' from <- '
					case 1:
						description += ' <-> back and forth to '
					case 2:
						description += ' to -> '
				destination_mentions = await format_channels({place.channel_ID for place in neighbors_dict.values()})
				description += f'{destination_mentions}.'

				if view.roles() or view.characters():
					description += f'\n• Imposed the whitelist: {whitelist}'

				if existing_paths:
					if view.overwriting:
						description += f'\n• Overwrote {existing_paths} path(s).'
					else:
						description += f"\n• Skipped {existing_paths} path(s) because" + \
							" the places were already connected. Enable overwriting to ignore."

				#Produce map of new paths
				neighbors_dict[origin_place_name] = origin_place
				subgraph = await GD.to_graph(neighbors_dict)
				graph_view = await GD.to_map(subgraph)
				embed, file = await mbd(
					'New path results.',
					description,
					'You can view all the places and paths with /server view.',
					(graph_view, 'full'))
				place_channel = await get_or_fetch(interaction.guild, 'channel', origin_place.channel_ID)
				await place_channel.send(embed = embed, file = file)

				return await no_redundancies(
					(interaction.channel.name in destinations \
					or interaction.channel.name == origin_place_name),
					embed,
					interaction)

			view = DialogueView(refresh, checks)
			await view.add_places(
				{name for name, place in GD.places.items() if place is not origin_place},
				singular = False)
			await view.add_roles()
			await view.add_characters(GD.characters)
			await view.add_submit(submit)
			await view.add_directionality()
			if origin_place.neighbors:
				await view.add_overwrite()
			await view.add_cancel()

			embed, _ = await refresh()
			await send_message(ctx.respond, embed, view, ephemeral = True)
			return

		async def select_menu():

			embed, _ = await mbd(
				'Connect places?',
				"You can create a new path three ways:" + \
					"\n• Call this command inside of a place channel." + \
					"\n• Do `/new place #place-channel`." + \
					"\n• Select a place channel with the list below.",
				"This is just to select the origin, you'll select the destination(s) next.")

			async def submit_locations(interaction: Interaction):
				await ctx.delete()
				await create_paths(list(view.places())[0])
				return

			view = DialogueView()
			await view.add_places(GD.places.keys(), callback = submit_locations)
			await view.add_cancel()
			await send_message(ctx.respond, embed, view)
			return

		if result := await CM.identify_place_channel(ctx, select_menu, origin):
			await create_paths(result)

		return

	@new_group.command(name = 'character', description = 'A new actor onstage.')
	async def character(self, ctx: ApplicationContext, name: Option(str, description = 'Give them a name here?') = ''):

		await ctx.defer(ephemeral = True)

		GD = GuildData(ctx.guild_id, load_places = True, load_characters = True)
		CM = ChannelManager(GD = GD)
		valid_url = False
		name = name[:24]
		allowed_people = None

		if result := await CM.identify_place_channel(ctx, presented_name = name) is None:
			return

		place_name = result

		async def refresh():

			nonlocal valid_url, name, place_name, allowed_people

			description = '\n• Character name: '
			name = view.name() or name
			description += f'*{name}*' if name else 'Not set yet. What will they be called?'

			description += '\n• Starting location: '
			if view.places():
				place_name = view.places()[0]

			if place_name:
				place = GD.places[place_name]
				description += f"<#{place.channel_ID}>"
			else:
				description += "Use the dropdown to choose where they'll join."

			description += '\n• Player(s): '
			if view.people():
				allowed_people = view.people()
				description += await format_words([person.mention for person in view.people()])
			else:
				allowed_people = [ctx.author]
				description += 'At a minimum, you and admins have access to this character.'

			description += '\n• Role(s): '
			if view.roles():
				description += await format_roles(view.roles())
			else:
				description += 'Use the dropdown to give the character some roles.'

			avatar, valid_url, avatar_message = await format_avatar(view.url())
			description += f'\n• Avatar: {avatar_message}'


			embed, file = await mbd(
				'New character?',
				description,
				"You can always change these things later with /review character.",
				(avatar, 'thumb'))
			return embed, file

		def checks():
			nonlocal name, place_name
			return not (name and place_name)

		async def submit(interaction: Interaction):

			await loading(interaction)

			nonlocal GD, valid_url, name, place_name, allowed_people

			#Inform character
			CM = ChannelManager(interaction.guild)
			character_channel = await CM.create_channel('characters', await discordify(name), allowed_people)

			embed, _ = await mbd(
				f'Welcome to your Character Channel, {name}.',
				"Roleplay with others by talking here. Nearby characters will hear." + \
				f"\n• Other people who can send messages here can also RP as {name}." + \
				f"\n• Start the message with `\\` if you don't want it to leave this chat." + \
				f"\n• You can `/look` around. {name} is at **#{place_name}** right now." + \
				"\n• Do `/move` to go to other places you can reach." + \
				"\n• You can `/eavesdrop` on nearby characters." + \
				"\n• Other people can't see your `/commands` directly..." + \
				"\n• ...Until you hit Submit, and start moving or eavesdropping.",
				'You can always type /help to get more help.')
			await character_channel.send(embed = embed)

			char_data = Character(character_channel.id)
			char_data.channel_ID = character_channel.id
			char_data.location = place_name
			char_data.roles = view.roles()
			char_data.name = name

			if view.url() and valid_url:
				char_data.avatar = view.url()

			await char_data.save()

			#Inform the node occupants
			place = GD.places[place_name]
			player_embed, _ = await mbd(
				'Someone new.',
				f"*{char_data.name}* is here.",
				'Perhaps you should greet them.',
				(char_data.avatar, 'thumb'))
			await to_direct_listeners(
				player_embed,
				interaction.guild,
				place.channel_ID,
				occupants_only = True)

			#Add the players to the guild nodes as occupants
			await GD.insert_character(char_data, place_name)
			GD.characters[char_data.id] = char_data.name
			await GD.save()

			await character_change(character_channel, char_data)

			#Inform admins node
			description = f"• Added <#{char_data.id}> as a character. " + \
				f"\n• They're starting at <#{place.channel_ID}>."
			if char_data.roles:
				description += f"\n• They have the role(s) of {await format_roles(char_data.roles)}"
			embed, _ = await mbd(
				f'Hello, **{char_data.name}**.',
				description,
				'You can view all characters and where they are with /review server.',
				(char_data.avatar, 'thumb'))
			place_channel = await get_or_fetch(interaction.guild, 'channel', place.channel_ID)
			await place_channel.send(embed = embed)

			LM = ListenerManager(interaction.guild, GD)
			await LM.load_channels()
			await LM.insert_character(char_data, skip_eaves = True)

			return await no_redundancies(
				(interaction.channel.name == place_name),
				embed,
				interaction)

		view = DialogueView(refresh, checks)
		await view.add_places(GD.places.keys())
		await view.add_people()
		await view.add_roles()
		await view.add_submit(submit)
		await view.add_rename()
		await view.add_URL()
		await view.add_cancel()
		embed, file = await refresh()
		await send_message(ctx.respond, embed, view, file)
		return

def setup(prox):
	prox.add_cog(NewCommands(prox), override = True)
