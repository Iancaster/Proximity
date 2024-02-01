

#Import-ant Libraries
from discord import ApplicationContext, Option, \
	Interaction, Embed, ButtonStyle
from discord.ext import commands
from discord.commands import SlashCommandGroup
from discord.utils import get, get_or_fetch
from discord.ui import Button

from libraries.new_classes import GuildData, DialogueView, \
	Character, ListenerManager, Paginator
from libraries.universal import mbd, loading, no_redundancies, \
	send_message, identify_place_channel, character_change, \
	identify_character_channel, moving
from libraries.formatting import format_channels, discordify, \
	unique_name, format_whitelist, format_colors, format_roles, \
	format_avatar, format_places, format_characters
from libraries.autocomplete import complete_places, complete_characters, \
	complete_map, glossary
from data.listeners import to_direct_listeners, queue_refresh

from networkx import DiGraph, ego_graph, compose, shortest_path

# Classes
class CharacterCommands(commands.Cog):

	@commands.slash_command(name = 'look', description = 'Look around your location.', guild_only = True)
	async def look(self, ctx: ApplicationContext):

		await ctx.defer(ephemeral = True)

		GD = GuildData(ctx.guild_id, load_places = True, load_characters = True)

		if not await GD.validate_membership(ctx.channel.id, ctx):
			return

		#check for location desc. here and offer option to toggle view to that

		char_data = Character(ctx.channel.id)
		place_data = GD.places[char_data.location]

		async def refresh():

			if True:

				title = f'Looking around #{char_data.location}.'

				description = f"There's "

				if other_occs := {ID for ID in place_data.occupants if ID != ctx.channel.id}:
					char_names = {GD.characters[ID] for ID in other_occs}
					description += await format_characters(char_names)
				else:
					description += 'nobody else'
				description += ' here with you.'

				if place_data.neighbors:
					description += " This map shows you what's nearby."
					graph = await GD.to_graph()
					ego = ego_graph(graph, char_data.location, radius = 1)
					image_view = (await GD.to_map(ego), 'full')
					footer = 'You can /move to anywhere nearby.'
				else:
					footer = "Looks like you're stuck here."
					image_view = None

			embed, file = await mbd(
				title,
				description,
				footer,
				image_view)
			return embed, file

		embed, file = await refresh()

		await send_message(ctx.respond, embed, file = file, ephemeral = True)
		return

	@commands.slash_command(name = 'move', description = 'Go someplace else.', guild_only = True)
	async def move(self, ctx: ApplicationContext, given_dest: Option(str, "Where would you like to go?", name = 'destination', autocomplete = complete_map) = None):

		await ctx.defer(ephemeral = True)

		GD = GuildData(ctx.guild_id, load_places = True, load_characters = True)

		if not await GD.validate_membership(ctx.channel.id, ctx):
			return

		char_data = Character(ctx.channel.id)

		char_map = await GD.accessible_map(
			[char_data.roles],
			ctx.channel.id,
			char_data.location)

		dest_name = given_dest if given_dest in char_map else None

		if not dest_name and len(char_map.nodes) > 1:
			image_view = (await GD.to_map(char_map), 'full')
		else:
			image_view = None

		async def refresh():

			nonlocal dest_name

			if len(char_map.nodes) > 1:

				if view.places():
					dest_name = view.places()[0]

				if dest_name:
					description = f"Move to **#{dest_name}**?"
				else:
					description = "You can move anywhere on the map."

				footer = "You'll see people you pass by, and they'll see you."
			else:
				description = "There's no way out."
				footer = "What to do now?"

			embed, file = await mbd(
				f'Leave #{char_data.location}?',
				description,
				footer,
				image_view)
			return embed, file

		def checks():
			return not dest_name

		async def submit_location(interaction: Interaction):

			await moving(interaction)

			LM = ListenerManager(interaction.guild, GD)
			await LM.load_channels()

			path = shortest_path(
				char_map,
				source = char_data.location,
				target = dest_name)

			await GD.evict_character(char_data)

			char_channel = await get_or_fetch(
				ctx.guild,
				'channel',
				char_data.channel_ID,
				default = None)

			await LM.remove_channel(channel = char_channel)

			place_embed, place_file = await mbd(
				'Movement.',
				f"*{char_data.name}* went from <#{GD.places[path[0]].channel_ID}>" +
					f" to <#{GD.places[dest_name].channel_ID}>.",
				f"They went from {' -> '.join(path)}.",
				(char_data.avatar, 'thumb'))

			async def inform_segment(seg_name: str, adj_embed: Embed, occ_embed: Embed):

				# Inform place channel
				seg_place = GD.places[seg_name]
				seg_channel = await get_or_fetch(
					ctx.guild,
					'channel',
					seg_place.channel_ID,
					default = None)
				if seg_channel:
					await seg_channel.send(
						embed = place_embed,
						file = place_file)

				# Inform occupants
				await to_direct_listeners(
					occ_embed,
					interaction.guild,
					seg_place.channel_ID,
					occupants_only = True)

				# Inform adjacents
				relevant_neighbors = (neigh for neigh in seg_place.neighbors.keys() \
					if neigh not in path)
				for relevant_neighbor in relevant_neighbors:
					await to_direct_listeners(
						adj_embed,
						interaction.guild,
						GD.places[relevant_neighbor].channel_ID)
				return

			# Inform start
			start_adj, _ = await mbd(
				'Someone got moving.',
				"You can hear someone in" +
					f" **#{path[0]}** start towards" +
					f" **#{path[1]}**.",
				'Who could it be?')
			start_occ, _ = await mbd(
				'Departing.',
				f"You notice *{char_data.name}* leave, heading" +
					f"towards **#{path[1]}**.",
				'Maybe you can follow them?')
			await inform_segment(path[0], start_adj, start_occ)

			# Inform middling segments (if any)
			for index, seg_name in enumerate(path[1:-1]):

				mid_adj, _ = await mbd(
					'Someone passed through.',
					"You can hear someone head through" +
						f" **#{seg_name}**, coming" +
						f" from **#{path[index]}** and going" +
						f" to **#{path[index + 2]}**.",
					'On the move.')
				mid_occ, _ = await mbd(
					'And on they go.',
					f"You see *{char_data.name}* arrive from" +
						f" from **#{path[index]}** before" +
						f" coninueing to **#{path[index + 2]}**.",
					'No time to lose, evidently.')

				await inform_segment(seg_name, mid_adj, mid_occ)

			# Inform end segment
			end_adj, _ = await mbd(
				'Someone stopped by.',
				f"You heard someone come from **#{path[-2]}**" +
					f" and stop at **#{path[-1]}**.",
				'Wonder why they chose here.')
			end_occ, _ = await mbd(
				'An arrival.',
				f"You notice *{char_data.name}* arrive" +
					f" from the direction of **#{path[-2]}**.",
				'Say hello.')
			await inform_segment(path[-1], end_adj, end_occ)

			# Inform character
			seen_places = await GD.filter_places(path)
			seen_char_IDs = await GD.get_occupants(seen_places.values())

			await GD.insert_character(char_data, path[-1])
			await GD.save()
			await char_data.save()

			if seen_char_IDs:
				char_names = {GD.characters[ID] for ID in seen_char_IDs}
				seen_desc = "Along the way, you saw (and were seen" + \
					f" by) {await format_characters(char_names)}."
			else:
				seen_desc = "You didn't see anyone else along the way."

			seen_embed, _ = await mbd(
				'Arrived.',
				seen_desc,
				f"The path you traveled was {' -> '.join(path)}.")
			await char_channel.send(embed = seen_embed)

			await LM.insert_character(char_data, skip_eaves = True)

			await interaction.followup.delete_message(message_id = interaction.message.id)
			return

		view = DialogueView(refresh, checks)
		if other_places := {place for place in char_map.nodes if place != char_data.location}:
			await view.add_places(other_places)
		await view.add_submit(submit_location)
		await view.add_cancel()
		embed, file = await refresh()

		await send_message(ctx.respond, embed, view, file, ephemeral = True)
		return

	@commands.slash_command(name = 'help', description = 'Get your footing with the bot.')
	async def help_func(self, ctx: ApplicationContext, given_word: Option(str, "Look up a certain word?", name = 'word', autocomplete = glossary) = ''):

		await ctx.defer(ephemeral = True)

		if word := given_word.lower():

			glossary_terms = {
				'graph' : "A __graph__ is just a collection of __place__s that are" +
					" connected by __path__s. Technically, a __graph__ could have" +
					" only one __place__, or not even have any __path__s. It's a" +
					" whole branch of mathematics you can look up--__graph__ theory!",
				'network' : "A __network__ is another name for a __graph__. It's a" +
					" little confusing considering '__graph__' makes you think of" +
					" line __graph__s, and '__network__s' make you think of cell" +
					" phone coverage. For this bot, we'll just call it a __graph__.",
				'path' : "A __path__ is a connection between two __place__s" +
					" within a __graph__. Paths may be one-way only, so that" +
					" __character__s can only __move__ along it in one __direct__ion, or" +
					" it can be two way. __Character__s use __path__s for __move__ment" +
					" as well as for __audio__.",
				'place' : "A __place__ is a location within the roleplay world" +
					" that __character__s can __move__ to. They are represented with" +
					" a text channel, the __place__ date (like name and description)," +
					" and any __path__s that it may" +
					" share that connect it to other __place__s. Places are about" +
					" the size of a room and everyone who's inside is __visible__ to" +
					" everyone else, as well as within earshot of their __audio__.",
				'audio' : "When a __character__ speaks, every other __character__ in the" +
					" same __place__ can hear __direct__ly. Players in __neighbor__ing" +
					" __place__s can hear __indirect__ly...unless the listener is" +
					" currently eavesdropping on the speaker," +
					" in which case, they'll hear everything __direct__ly.",
				'direct' : "When a __character__ speaks, other occupants in the" +
					" same __place__ will __direct__ly hear, as well as occupants" +
					" in __neighbor__ing __place__s that are eavesdropping. These" +
					" __direct__ listeners will hear word-for-word what was said." +
					" Compare this to __indirect__ __audio__.",
				'indirect' : "When a __character__ speaks, other __character__s in" +
					" __neighbor__ing __place__s who are not eavesdropping on" +
					" that __character__'s __place__ will only __indirect__ly hear the speaker." +
					" These listeners will be able to identify the speaker, " +
					" and will be able to identify where it's coming from, but" +
					" will not be able to make out the content of what was said.",
				'visible' : "When a __character__ chooses to `/look` around their" +
					" current __place__, they see every other __character__ around." +
					" They also see (and are seen by) __character__s who enter" +
					" their __place__, they see them as they leave (and which" +
					" __direct__ion they go).",
				'move' : "Since __character__s have a presence inside their" +
					"__place__, they can't instantly teleport between where they" +
					" are and where they want to be. Instead, they '__move__' " +
					" along the shortest path between these places, and " +
					" __character__s along the way see the __character__ and where they " +
					" came from, along with where they went to.",
				'character' : "A __character__ is the fictional roleplay figure who" +
					" is acted out via a player's text messages. When a player's" +
					" texts are 'proxied' by the bot into other __character__ channels, it " +
					" is the __character__'s name and the __character__'s profile picture " +
					" that is displayed. Characters occupy a __place__ in the __graph__.",
				'player' : "A __player__ is the nonfictitous user who roleplays on" +
					" Discord. __Player__s are only privy to what their __character__" +
					" knows, and can `/move`, `/look`, and `/eavesdrop`," +
					" among other things.",
				'whitelist' : "__Place__s and __path__s can have restrictions on what" +
					" __character__s are allowed to __move__ through them on the __graph__." +
					" They can restrict based on a list of approved __character__s," +
					" approved roles, or both: anyone who's approved on" +
					" either list may pass.",
				'neighbor' : "A __neighbor__ing __place__ is one that's connected to a" +
					" given __place__ with a __path__. A __neighbor__ing __character__ is one that's" +
					" in a __neighbor__ __place__. Neighbors are usually talked about in" +
					" the context of eavesdropping for __direct__ listening, or so that" +
					" __neighbor__ __character__s are alerted when a __place__ gets deleted, for" +
					"example.",
				'underlined' : "🤨"}

			if word in glossary_terms:
				embed, _ = await mbd(
					f'{word.capitalize()} explanation:',
					glossary_terms[word],
					'You can also look up underlined words in this message, too.')

			else:
				embed, _ = await mbd(
					'What was that?',
					f"I'm sorry. I have a glossay for {len(glossary_terms)} words," + \
						" but not for that. Perhaps start with the tutorials with" + \
						" just a standard `/help` and go from there.",
					"Sorry I couldn't do more.")

			await send_message(ctx.respond, embed)
			return

		async def leatherbound(interaction, title_prefix, page_content): #Because it wraps the paginators haha

			await interaction.response.defer()

			paginator = Paginator(
				interaction,
				title_prefix,
				page_content)
			await paginator.refresh_embed()

			return

		async def player_tutorial(interaction: Interaction):

			title_prefix = 'Player Tutorial, Page'
			page_content = {
				'Intro' : "Welcome, this guide" +
					" will tell you everything you need to know as" +
					" a __player__. Let's begin.",
				'Character Channels': "Players have their own channel" +
					" for roleplaying. All speech and __move__ment, etc, is" +
					" done through there.",
				'Places': "Your __character__s exists in some __place__." +
					" You can check where you are with `/look`.",
				'Movement': "You can `/move` to a new place. Certain" +
					" __place__s or __path__s might have limits on who's allowed" +
					" in.",
				'Visibility': "You're able to see people in the same" +
					" __place__ as you, even if they're only passing by.",
				'Sound': "Normally, you can only hear people in the" +
					" same __place__ as you, and vice versa.",
				'Eavesdropping': "If you want, you can `/eavesdrop` on" +
					" people in a __place__ next to you to __direct__ly hear" +
					" what's going on.",
				'Fin': "And that's about it! Enjoy the game."}

			if not interaction.guild_id:
				return await leatherbound(interaction, title_prefix, page_content)

			char_data = Character(interaction.channel.id)
			if char_data.location:
				page_content['Character Channels'] += " That's the" + \
					" channel you're in right now! :)"
				page_content['Places'] += " Right now, you're" + \
					f" in **#{char_data.location}**."

			return await leatherbound(interaction, title_prefix, page_content)

		async def command_list(interaction: Interaction):
			title_prefix = 'Command List, Page'
			page_content = {
				'Intro' :
					"So, the first few pages will be for __player__s, the next" +
					" few go over administrator/Host commands, and then" +
					" there's some bonus commands at the end. Let's begin.",
				'Player' :
					"Meant to be used by the __player__s themselves." +
					" `/help` can be used by anyone, anywhere-- but the" +
					" rest of these can only be done in a __character__ channel."
					"**Limitations**" +
						"\n• You must be calling from a __character__ channel." +
					"\n\n**Commands**" +
						"\n• `/help`: I have a feeling you know what this one does."
						"\n• `/look`: Shows you nearby __character__s, __place__s," +
							" and the __place__ description (if one is set)."
						"\n• `/move <location>`: Move somewhere." +
							" If you specify a __place__ when calling the command," +
							" you can skip straight to the confirmation." +
						"\n• `/eavesdrop`: By itself, this will tell you who you" +
							" hear nearby. You can pick someplace" +
							" nearby to eavesdrop on. Walk away or call" +
							" it again to cancel.",
				'Place' :
					"**Limitations**" +
						"\n• Must be within a server." +
						"\n• You must be a Host." +
					"\n\n**Commands**" +
						"\n*These all have a <name> option, for you to " +
							" optionally name a __place__ as you call the command.*" +
						"\n\n• `/new place <name>`: Create a new __place__. If" +
							" no `<name>`, you'll can set one with the modal" +
							" dialogue. You can also set a __whitelist__." +
						"\n\n*If there's no `<name>` given, these next two commands" +
							" will check if you're in a __place__ channel and target that." +
							" If you're not, they will provide you a dropdown.*" +
						"\n\n• `/delete place <name>`: Delete a __place__ (if" +
							" no __character__s are inside)." +
						"\n• `/review place <name>`: Change a __place__'s" +
							" name and/or __whitelist__-- also shows you its occupants.",
				'Path' :
					"**Limitations**" +
						"\n• Must be within a server." +
						"\n• You must be a Host." +
						"\n• There must be more than one __place__." +
					"\n\n**Commands**" +
						"\n*Like before, you can <name> a __place__ to work on," +
							" call from within a __place__, or use the dropdown.*" +
						"\n\n• `/new path <name>`: Create new __path__s." +
							" You can set a __whitelist__, overwrite, and toggle" +
							" whether they're two-way or one-way." +
						"\n• `/delete path <name>`: Delete __path__ between" +
							" __place__s." +
						"\n• `/review path <name>`: View or change __whitelist__s.",
				'Character' :
					"Meant to be used by the Hosts to manage __Character__s, not to" +
					" be confused with the __Player__ commands that are used within" +
					" Character Channels." +
					"**Limitations**" +
						"\n• Must be within a server." +
						"\n• You must be a Host." +
					"\n\n**Commands**" +
						"\n*For these, you can <name> a __character__.*" +
						"\n\n• `/new character <name>`: Create a new __Character__" +
						" with the given <name>. Call from within a __place__ channel," +
							" or set the place with the modal dialogue in the menu." +
						"\n\n*These ones will give you the context-sensitivity" +
							" for calling from within a __character__ channel, like with __place__s." +
							" Otherwise, you can use the dropdown to select multiples.*" +
						"\n• `/delete character <name>`: Delete one or more __character__." +
						"\n• `/review character <name>`: See their __place__, name, avatar," +
							" eavesdropping target...Or change these things. You can even" +
							" teleport __character__s, in bulk, using this.",
				'Server' :
					"**Limitations**" +
						"\n• Must be within a server." +
						"\n• You must be a Host." +
					"\n\n**Commands**" +
						"\n• `/delete server`: Delete *everything*. Tread lightly.",
						#"\n• `/review server`: Adjust certain things about the" + \
						#	" server, change defaults and overrides." + \
						#"\n• `/server debug`: View all server data, written out.",
				'Debug' :
					"**Limitations**" +
						"\n• Must be within a server." +
						"\n• You must be an admin." +
					"\n\n**Commands**" +
						"\n• `/debug server`: Review all the server data." +
						"\n• `/debug listeners <direct or indirect>`: Review the listeners."}

			await leatherbound(interaction, title_prefix, page_content)

		async def host_setup(interaction: Interaction):

			title_prefix = 'Host Setup, Step'
			page_content = {
				'Intro' : "Welcome, this guide will walk you through" + \
					" using this bot to run your roleplay. It'll be a little" + \
					" more involved than using as a __character__, heads up.",
				'Server': "You can start with your own server, but" + \
					" if you want one that's already set up for you, you" + \
					" can use this [template](https://discord.new/4UXDgqfJ894a).",
				'Invite': "Once you have your server, invite me to it" + \
					" using the button in my profile bio.",
				'Switching': "Now that we've got the new server, it might be" + \
					" better if we switch to over there. Call `/help` in that" + \
					" server and we can pick up from there, so we don't have" + \
					" to hop back and forth.",
				'Permissions (pt. 1/2)' : "Before we go too much further, let's make" + \
					" sure nobody can mess with commands they shouldn't." + \
					" Go to Server Settings > Integrations (Second block, just" + \
					" under Apps) > Proximity, and then turn off slash command" + \
					" access for @everyone. ",
				'Permissions (pt. 2/2)' : "Now you'll want to turn back on" + \
					" the permissions __character__s should be allowed to access." + \
					" Click `/eavesdrop`, then 'Add Roles or Members', and" + \
					" select @everyone or @Player (your call.) Repeat this for" + \
					" `/help`, `/look`, `/map`, and `/move`. ",
				'Nodes': "Right, now let's start with making some __place__s." + \
					" Do `/node new` for each place you want __character__s to go." + \
					" Usually, these places are about the size of a large room.",
				'Edges': "Now, for places that are connected, do `/edge new`" + \
					" to connect them. This can be two rooms connected by a door" + \
					" or hallway, an island and a port connected by a ferry, or" + \
					" it can be the Northern half of a courtyard adjacent to" + \
					" the Southern half. Get creative with it.",
				'Players': "Once you're all ready, you can add __character__s with" + \
					" `/player new`. By the way, it won't add the Player role" + \
					" to them-- this bot doesn't actually use roles. But it's in the" + \
					" template server just in case you want to give them the role" + \
					" anyways.",
				'Watching' : "As the roleplay goes, you can follow along with" + \
					" everything that goes on by watching their __character__ channels" + \
					" (for following their POV), or the __place__ channels (for following" + \
					" the events in a __place__).",
				'NPCs' : "If someone wants to join the RP as extra, like a shop" + \
					" keeper or villian, you can add them (or even yourself) as a" + \
					" __character__. Speak in a __place__ channel to talk only to the people" + \
					" there, or speak in your __character__ channel for everyone in earshot" + \
					" to hear you.",
				'Fin': "And that's about it! Enjoy the game. If you even need to" + \
					" manage your __character__s, you can `/player find` them," + \
					" `/player review` for more details, `/player tp` to" + \
					" __move__ them around... Frees you up to do the *real* hosting."
				}
			# page_image = {
				# 'The Goal' : 'assets/overview.png',
				# 'Nodes' : 'assets/nodeExample.png',
				# 'Edges' : 'assets/edgeExample.png',
				# 'Graph' : 'assets/edgeIllustrated.png'}

			return await leatherbound(interaction, title_prefix, page_content)


		embed, _ = await mbd(
			'Hello!',
			"This command will help you learn what the bot does and how it" + \
				" can be used. Head [here](https://discord.gg/VSNExYkvsA)" + \
				" for support, updates, and more info." + \
				" Lastly, if you want to learn more about any" + \
				" __underlined__ words I use, just say `/help (underlined word)`.",
			"I'll be here if/when you need me.")

		buttons = {
			'Help for Players' : player_tutorial,
			'Commands' : command_list} #,
			#'Host Setup' : host_setup}

		view = DialogueView()
		for button_label, button_callback in buttons.items():

			button = Button(
				label = button_label,
				style = ButtonStyle.success)
			button.callback = button_callback
			view.add_item(button)

		await view.add_cancel()
		await send_message(ctx.respond, embed, view)
		return

def setup(prox):
	prox.add_cog(CharacterCommands(prox), override = True)
