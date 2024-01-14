

#Import-ant Libraries
from discord import ApplicationContext, Option, Interaction, Embed
from discord.ext import commands
from discord.commands import SlashCommandGroup
from discord.utils import get, get_or_fetch

from libraries.classes import *
from libraries.universal import *
from libraries.formatting import *
from libraries.autocomplete import *
from data.listeners import *


#Classes
class NewCommands(commands.Cog):

	new_group = SlashCommandGroup(
		name = 'new',
		description = 'Create new locations, paths, and characters.',
		guild_only = True)

	@new_group.command(name = 'place', description = 'Create a new place.')
	async def place(self, ctx: ApplicationContext, name: Option(str, description = 'What should it be called?') = ''):

		await ctx.defer(ephemeral = True)

		guild_data = GuildData(
			ctx.guild_id,
			load_places = True,
			load_characters = True,
			load_roles = True)

		submitted_name = await discordify(name)
		name = submitted_name if submitted_name else 'new-place'
		name = await discordify(name)
		name = await unique_name(name[:24], guild_data.places.keys())

		async def refresh(interaction: Interaction = None):

			nonlocal name
			name = view.name() if view.name() else name
			name = await discordify(name)
			name = await unique_name(name[:24], guild_data.places.keys())

			description = f'Whitelist: {await format_whitelist(view.roles(), view.characters().keys())}'

			embed, file = await mbd(
				f'New location: {name}',
				description,
				'You can also create a whitelist to limit who can visit this place.')
			return embed, file

		async def submit(interaction: Interaction):

			await loading(interaction)

			maker = ChannelMaker(interaction.guild, 'places')
			await maker.initialize()
			new_channel = await maker.create_channel(name)

			await guild_data.create_place(
				name = name,
				channel_ID = new_channel.id,
				role_IDs = view.roles(),
				char_IDs = view.characters())
			guild_data.roles |= view.roles()
			await guild_data.save()

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
		await view.add_characters(guild_data.characters)
		await view.add_submit(submit)
		await view.add_rename(name)
		await view.add_cancel()

		embed, _ = await refresh()
		await send_message(ctx.respond, embed, view)
		return

	@new_group.command(name = 'path', description = 'Connect two places.')
	async def path(self, ctx: ApplicationContext, origin: Option(str, description = 'Which place to start from?', autocomplete = complete_places) = ''):

		await ctx.defer(ephemeral = True)

		guild_data = GuildData(
			ctx.guild_id,
			load_places = True,
			load_characters = True,
			load_roles = True)

		async def create_paths(origin_place_name: str):

			origin_place_name = origin_place_name
			origin_place = guild_data.places[origin_place_name]
			destinations = set()

			async def refresh(interaction: Interaction = None):

				nonlocal destinations

				description = f'• Origin: <#{origin_place.channel_ID}>'

				destination_message, destinations = await format_new_neighbors(
					view.overwriting,
					origin_place,
					view.places(),
					guild_data)

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
				nonlocal destinations
				return not destinations

			async def submit(interaction: Interaction):

				await loading(interaction)

				nonlocal origin_place_name, destinations

				#Make paths
				path = Path(
					directionality = view.directionality,
					allowed_roles = view.roles(),
					allowed_characters = view.characters())
				existing_paths = 0
				for destination in destinations:

					if await guild_data.set_path(
						origin_place_name,
						destination,
						path,
						view.overwriting):

						existing_paths += 1

				await guild_data.save()
				neighbors_dict = await guild_data.filter_places(destinations)
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
				subgraph = await guild_data.to_graph(neighbors_dict)
				graph_view = await guild_data.to_map(subgraph)
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
				{name for name, place in guild_data.places.items() if place is not origin_place},
				singular = False)
			await view.add_roles()
			await view.add_characters(guild_data.characters)
			await view.add_submit(submit)
			await view.add_directionality()
			if origin_place.neighbors:
				await view.add_overwrite()
			await view.add_cancel()

			embed, _ = await refresh()
			await send_message(ctx.respond, embed, view, ephemeral = True)
			return

		result = await identify_place_channel(guild_data.places.keys(), ctx.channel.name, origin)
		match result:
			case _ if isinstance(result, Embed):
				await send_message(ctx.respond, result)
			case _ if isinstance(result, str):
				await create_paths(result)
			case None:
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
				await view.add_places(guild_data.places.keys(), callback = submit_locations)
				await view.add_cancel()
				await send_message(ctx.respond, embed, view)


		return

	@new_group.command(name = 'character', description = 'A new actor onstage.')
	async def character(self, ctx: ApplicationContext, name: Option(str, description = 'Give them a name here?') = ''):

		await ctx.defer(ephemeral = True)

		guild_data = GuildData(ctx.guild_id, load_places = True, load_characters = True)
		valid_url = False
		name = name[:24]
		allowed_people = None

		result = await identify_place_channel(guild_data.places.keys(), ctx.channel.name)
		match result:
			case _ if isinstance(result, Embed):
				await send_message(ctx.respond, result)
				return
			case _ if isinstance(result, str):
				place_name = result
			case None:
				place_name = None

		async def refresh():

			nonlocal guild_data, valid_url, name, place_name, allowed_people

			description = '\n• Character name: '
			name = view.name() or name
			description += f'*{name}*' if name else 'Not set yet. What will they be called?'

			description += '\n• Starting location: '
			if view.places():
				place_name = view.places()[0]

			if place_name:
				place = guild_data.places[place_name]
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

			nonlocal guild_data, valid_url, name, place_name, allowed_people

			#Inform character
			maker = ChannelMaker(interaction.guild, 'characters')
			await maker.initialize()
			character_channel = await maker.create_channel(await discordify(name), allowed_people)

			embed, _ = await mbd(
				f'Welcome to your Character Channel, {name}.',
				"Roleplay with others by talking here. Nearby characters will hear." + \
				f"\n• Other people who can send messages here can also RP as {name}." + \
				f"\n• Start the message with `\\` if you don't want it to leave this chat." + \
				f"\n• You can `/look` around. {name} is at **#{place_name}** right now." + \
				"\n• Do `/map` to see nearby places and `/move` to go there." + \
				"\n• You can `/eavesdrop` on characters in nearby places." + \
				"\n• Other people can't see your `/commands` directly..." + \
				"\n• ...Until you hit Submit, and start moving or eavesdropping.",
				'You can always type /help to get more help.')
			await character_channel.send(embed = embed)

			character_data = Character(character_channel.id)
			character_data.channel_ID = character_channel.id
			character_data.location = place_name
			character_data.roles = view.roles()
			character_data.name = name

			if view.url() and valid_url:
				character_data.avatar = view.url()

			await character_data.save()

			#Inform the node occupants
			place = guild_data.places[place_name]
			player_embed, _ = await mbd(
				'Someone new.',
				f"*{character_data.name}* is here.",
				'Perhaps you should greet them.',
				(character_data.avatar, 'thumb'))
			await to_direct_listeners(
				player_embed,
				interaction.guild,
				place.channel_ID,
				occupants_only = True)

			#Add the players to the guild nodes as occupants
			await place.add_occupants({character_data.id})
			guild_data.characters[character_data.id] = character_data.name
			await guild_data.save()

			await character_change(character_channel, character_data)

			#Inform admins node
			description = f"• Added <#{character_data.id}> as a character. " + \
				f"\n• They're starting at <#{place.channel_ID}>."
			if character_data.roles:
				description += f"\n• They have the role(s) of {await format_roles(character_data.roles)}"
			embed, _ = await mbd(
				f'Hello, **{character_data.name}**.',
				description,
				'You can view all characters and where they are with /review server.',
				(character_data.avatar, 'thumb'))
			place_channel = await get_or_fetch(interaction.guild, 'channel', place.channel_ID)
			await place_channel.send(embed = embed)

			await queue_refresh(interaction.guild)

			return await no_redundancies(
				(interaction.channel.name == place_name),
				embed,
				interaction)

		view = DialogueView(refresh, checks)
		await view.add_places(guild_data.places.keys())
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
