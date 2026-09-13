

#Import-ant Libraries
from discord import ApplicationContext, Interaction, MISSING, \
    InteractionContextType, InputTextStyle, ButtonStyle
from discord.ext import commands
from discord.commands import SlashCommandGroup
from libraries.classes import in_text_channel, is_administrator, in_prox_rp, \
    get_channel, Roleplay, Location, Character, Route
from data.database_handler import CommitResult
from data.database_entries import (
    roleplay_repo, location_repo, character_repo, route_repo,
    RoleplayData, LocationData, CharacterData, RouteData)
from libraries.user_interface import text_embed, send_message, \
    image_embed, reference_validator, ImageSource, Dialogue, Popup, \
    LOGO
from libraries.embed_templates import notify_log, RoleplayEmbeds

# Classes
class ReviewCommands(commands.Cog):

    review_group = SlashCommandGroup(
        name = "review",
        description = "Review any part of the server, from places to people.",
        contexts = [InteractionContextType.guild],
        checks = [in_text_channel, is_administrator, in_prox_rp])

    @review_group.command(name = "location", description = "Examine or change the details of a Location.")
    async def location(self, ctx: ApplicationContext):

        location = await Location.load(ctx.channel_id)
        rp = await Roleplay.load(ctx.guild_id)
        assert rp is not None, "tf"

        async def add_components(curr_location: Location, curr_dialogue: Dialogue) -> None:

            details_popup = Popup(title = "Review Location details")

            details_popup.add_text(
                label = "Name",
                placeholder = "What should the Location be renamed?",
                value = curr_location.data.name,
                min_length = 1,
                max_length = 100)

            details_popup.add_text(
                label = "Description",
                placeholder = "Share some lore, maybe, or the sounds or scents of a scene?",
                value = curr_location.data.description,
                min_length = 0,
                max_length = 300,
                required = False,
                style = InputTextStyle.paragraph)

            details_popup.add_text(
                label = "Reference",
                placeholder = "Right click an Imgur image and select 'Copy Link'.",
                value = curr_location.data.reference,
                min_length = 1,
                max_length = 300,
                required = False,
                style = InputTextStyle.paragraph)

            details_button = curr_dialogue.add_button(label = "Review Location details", style = ButtonStyle.blurple)
            curr_dialogue.add_modal(details_popup, details_button)

            submit_button = curr_dialogue.add_button(label = "Submit edits", style = ButtonStyle.success)
            submit_button.should_disable = lambda : not curr_dialogue.is_valid
            curr_dialogue.add_close()

            async def submit(interaction: Interaction):

                nonlocal curr_dialogue, curr_location

                url =  curr_dialogue._fields["Reference"].get_value()
                url_result = await reference_validator(url)
                if url_result != CommitResult.SUCCESS:
                    url = None

                await curr_location.update(
                    name = curr_dialogue._fields["Name"].get_value(),
                    description = curr_dialogue._fields["Description"].get_value(),
                    reference = url)

                curr_dialogue = await review_location(curr_location, curr_dialogue)   
                curr_dialogue.view.clear_items()
                await add_components(curr_location, curr_dialogue)
                await curr_dialogue.refresh(interaction)

            submit_button.callback = submit
            curr_dialogue = await review_location(curr_location, curr_dialogue)
            return

        async def review_location(
            curr_location: Location, 
            curr_dialogue: Dialogue | None = None
        ) -> Dialogue:

            if occupants := await curr_location.occupants:
                occupants = ", ".join([f"<#{c.character_id}>" for c in occupants])
            else:
                occupants = "No one is here at the moment."

            if curr_location.data.description:
                loc_description = "See below.\n>>> " + curr_location.data.description
            else:
                loc_description = "No description yet."

            neighbors_text = ""
            inlet_ids = [data.from_id for data in await curr_location.inlet_routes]
            outlet_ids = [data.to_id for data in await curr_location.outlet_routes]

            for id in inlet_ids:

                if id in outlet_ids:
                    outlet_ids.remove(id)
                    neighbors_text += f"\n - <#{id}> <-> Here"

                else:
                    neighbors_text += f"\n - <#{id}> -> Here"

            for id in outlet_ids:
                neighbors_text += f"\n - Here -> <#{id}>"
                
            embed, file = await image_embed(
                f"Reviewing {curr_location.data.mention}",
                (f"**Occupants:** {occupants}" +
                f"\n**Neighbors:** {neighbors_text or "None-- consider `/create Route`."}" + 
                f"\n**Reference:** " +
                    ("See below." if curr_location.data.reference else "None (yet). You should add one!") +
                "**\nDescription:** " + loc_description),
                "Would you perhaps like to change any of these things?",
                thumbnail = False,
                source = ImageSource.URL,
                asset_str = curr_location.data.reference)

            if curr_dialogue is None:
                curr_dialogue = Dialogue(embed, file)
                await add_components(curr_location, curr_dialogue)
            else:
                curr_dialogue.current_embed = embed
                curr_dialogue.current_file = file

            await curr_dialogue.view.refresh_children()
            return curr_dialogue

        if location is None:

            embed = text_embed(
                "Which Location?",
                ("Please select a Location channel from the dropdown below" +
                    " to review its details. You can also call this command" +
                    " in a Location channel to select it automatically."),
                "This will show you everything about the place.")

            dialogue = Dialogue(embed)

            channel_select = dialogue.add_channel_select(
                label = "Pick a Location to review.",
                purpose = "Location Choice",
                placeholder = "#the-castle",
                min_values = 1)

            submit_button = dialogue.add_button("Select Location", ButtonStyle.primary)

            async def select(interaction: Interaction):
                nonlocal dialogue, location
                location = await Location.load(channel_select.values[0].id)
                dialogue.view.clear_items()
                dialogue = await review_location(location, dialogue) # pyright: ignore[reportArgumentType]
                await add_components(location, dialogue) # pyright: ignore[reportArgumentType]
                await dialogue.refresh(interaction)
                return

            submit_button.callback = select
            location_ids = [loc.location_id for loc in await rp.locations]
            submit_button.should_disable = (lambda : not channel_select.is_valid() or
                channel_select.values[0].id not in location_ids)
            
            dialogue.add_close()

        else:
            dialogue = await review_location(curr_location = location, curr_dialogue = None)

        await send_message(ctx.interaction,
            dialogue.current_embed,
            dialogue.view,
            ephemeral = True)

        return

    # @review_group.command(name = 'path', description = 'Look at (or edit) paths.')
    # async def path(self, ctx: ApplicationContext, given_place: Option(str, description = 'Which place to start from?', name = 'place', autocomplete = complete_places, required = False)):

    # 	await ctx.defer(ephemeral = True)

    # 	GD = GuildData(ctx.guild_id, load_places = True)
    # 	CM = ChannelManager(GD = GD)

    # 	async def review_paths(place_name: str):

    # 		place_name = place_name
    # 		origin_place = GD.places[place_name]
    # 		neighbors = origin_place.neighbors
    # 		if not neighbors:
    # 			embed, _ = await mbd(
    # 				'No paths.',
    # 				f'<#{origin_place.channel_ID}> has no paths to review. It' + \
    # 					" isn't connected to any other places.",
    # 				'You can make some with /createpath.')
    # 			await send_message(ctx.respond, embed, ephemeral = True)
    # 			return

    # 		impacted_places = await GD.filter_places(list(neighbors.keys()) + [place_name])
    # 		graph = await GD.to_graph(impacted_places)
    # 		selected_paths = []
    # 		graph_view = None

    # 		async def refresh():

    # 			nonlocal place_name, origin_place, selected_paths, graph_view
    # 			full_description = f'• Selected place: <#{origin_place.channel_ID}>'

    # 			if view.paths():
    # 				full_description += '\n• Selected Path(s): See below.'
    # 				revising_paths = [origin_place.neighbors[name] for name in view.paths()]
    # 				full_description += await view.format_whitelist(revising_paths)
    # 			else:
    # 				full_description += '\n• Use the dropdown below to select one or more' + \
    # 					' paths. You can look at the whitelists or overwrite them.'

    # 			if view.paths() and view.paths != selected_paths:
    # 				selected_paths = view.paths()
    # 				path_colors = await format_colors(graph, place_name, view.paths(), 'blue')
    # 				graph_view = (await GD.to_map(graph, path_colors), 'full')
    # 			elif view.paths != selected_paths:
    # 				selected_paths = view.paths()
    # 				graph_view = (await GD.to_map(graph), 'full')

    # 			embed, file = await mbd(
    # 				'Review path(s)?',
    # 				full_description,
    # 				'You can change these back at any time.',
    # 				graph_view)
    # 			return embed, file

    # 		def checks():
    # 			return not (view.paths() and (view.roles() or view.characters() or view.clearing))

    # 		async def submit(interaction: Interaction):

    # 			await interaction.response.defer()

    # 			if view.clearing:
    # 				description = '\n• Removed the whitelist(s).'
    # 				for neighbor_name in view.paths():
    # 					await origin_place.neighbors[neighbor_name].clear_whitelist()
    # 					await GD.places[neighbor_name].neighbors[place_name].clear_whitelist()

    # 			else:
    # 				revising_paths = [origin_place.neighbors[name] for name in view.paths()][0]
    # 				description = await view.format_whitelist(revising_paths)
    # 				description = f'\n• Changed the whitelist to: {await format_whitelist(view.roles(), view.characters())}'

    # 				for neighbor_name in view.paths():
    # 					origin_place.neighbors[neighbor_name].allowed_roles = view.roles()
    # 					GD.places[neighbor_name].neighbors[place_name].allowed_characters = view.characters()

    # 			await GD.save()

    # 			#Inform neighbors occupants and neighbor locations
    # 			neighbor_places = await GD.filter_places(view.paths())
    # 			neighbor_mentions = await format_channels({place.channel_ID for place in neighbor_places.values()})
    # 			player_embed, _ = await mbd(
    # 				'Hm?',
    # 				f"You feel like the way to **#{place_name}** changed somehow.",
    # 				'Will it be easier to travel through, or harder?')
    # 			place_embed, _ = await mbd(
    # 				f'Path with <#{origin_place.channel_ID}> changed.',
    # 				description,
    # 				'You can view its details with /review path.')
    # 			for place in neighbor_places.values():
    # 				await to_direct_listeners(
    # 					player_embed,
    # 					interaction.guild,
    # 					place.channel_ID,
    # 					occupants_only = True)
    # 				place_channel = get(interaction.guild.text_channels, id = place.channel_ID)
    # 				await place_channel.send(embed = place_embed)

    # 			#Inform edited location occupants
    # 			player_embed, _ = await mbd(
    # 				'Hm?',
    # 				"You notice that there's been a change in the way this" + \
    # 					f" place is connected to {neighbor_mentions}.",
    # 				"Perhaps you're only imagining it.")
    # 			await to_direct_listeners(
    # 				player_embed,
    # 				interaction.guild,
    # 				origin_place.channel_ID,
    # 				occupants_only = True)

    # 			#Inform own location
    # 			embed, _ = await mbd(
    # 				f'Path(s) with {neighbor_mentions} changed.',
    # 				description,
    # 				'You can always undo these changes.')
    # 			place_channel = get(interaction.guild.text_channels, id = origin_place.channel_ID)
    # 			await place_channel.send(embed = embed)

    # 			return await no_redundancies(
    # 				(interaction.channel.name in view.paths() or interaction.channel.id == origin_place.channel_ID),
    # 				embed,
    # 				interaction)

    # 		view = DialogueView(refresh, checks)
    # 		await view.add_paths(neighbors)
    # 		await view.add_roles()
    # 		await view.add_characters(GD.characters)
    # 		await view.add_submit(submit)
    # 		if any(path.allowed_roles or path.allowed_characters for path in neighbors.values()):
    # 			await view.add_clear()
    # 		await view.add_cancel()
    # 		embed, file = await refresh()

    # 		await send_message(ctx.respond, embed, view, file, ephemeral = True)
    # 		return

    # 	async def select_menu():
    # 		embed, _ = await mbd(
    # 			'Review path(s)?',
    # 			"You can review path whitelists three ways:" + \
    # 				"\n• Call this command inside of a place channel." + \
    # 				"\n• Do `/review path #place-channel`." + \
    # 				"\n• Select a place with the list below.",
    # 			"This is just to select the origin, you'll select which paths next.")

    # 		async def submit_location(interaction: Interaction):
    # 			await ctx.delete()
    # 			await review_paths(list(view.places())[0])
    # 			return

    # 		view = DialogueView()
    # 		await view.add_places(GD.places.keys(), callback = submit_location)
    # 		await view.add_cancel()
    # 		await send_message(ctx.respond, embed, view)
    # 		return

    # 	if result := await CM.identify_place_channel(ctx, select_menu, given_place):
    # 		await review_paths(result)

    # 	return

    # @review_group.command(name = 'character', description = 'Review a character.')
    # async def character(self, ctx: ApplicationContext, given_character: Option(str, description = 'Which character?', name = 'character', autocomplete = complete_characters, required = False)):

    # 	await ctx.defer(ephemeral = True)

    # 	GD = GuildData(ctx.guild_id, load_places = True, load_characters = True)
    # 	CM = ChannelManager(GD = GD)

    # 	async def review_character(reviewing_characters: dict):

    # 		characters_dict = {char_ID : Character(char_ID) for char_ID in reviewing_characters.keys()}
    # 		valid_url = False
    # 		if len(reviewing_characters) == 1:
    # 			char_ID, char_name = list(reviewing_characters.items())[0]
    # 			char_data = list(characters_dict.values())[0]
    # 		else:
    # 			existing_locations = {character.location for character in characters_dict.values()}
    # 			existing_roles = {role for character in characters_dict.values() for role in character.roles}

    # 		async def singular_refresh():

    # 			nonlocal valid_url

    # 			if view.name():
    # 				description = f'• Name: ~~{char_name}~~, renaming to *{view.name()}*'
    # 			else:
    # 				description = f'• Name: *{char_name}*'

    # 			if view.places():
    # 				description += f'\n• Location: ~~#{char_data.location}~~, relocating to **#{view.places()[0]}**'
    # 			else:
    # 				description += f'\n• Location: **#{char_data.location}**'

    # 			if view.clearing:
    # 				description += '\n• Roles: Being cleared!'
    # 			elif view.roles():
    # 				description += f'\n• Roles: Being set to {await format_roles(view.roles())}.'
    # 			elif char_data.roles:
    # 				description += f'\n• Roles: {await format_roles(char_data.roles)}'

    # 			if char_data.eavesdropping and GD.eavesdropping_allowed:
    # 				description += f'\n• Eavesdropping on: **#{char_data.eavesdropping}**'

    # 			if view.url():
    # 				avatar, valid_url, avatar_message = await format_avatar(view.url())
    # 				description += f'\n• Avatar: {avatar_message}'
    # 			else:
    # 				avatar, valid_url = None, False

    # 			embed, file = await mbd(
    # 				f'Reviewing <#{char_ID}>',
    # 				description,
    # 				'You can rename them, relocate them, and change their roles.',
    # 				(avatar, 'thumb'))
    # 			return embed, file

    # 		async def multiple_refresh():

    # 			description = f'• Names: {await format_characters(reviewing_characters.values())}'

    # 			if view.places():
    # 				description += f'\n• Location: Relocating characters to **#{view.places()[0]}**'
    # 			else:
    # 				description += f'\n• Location(s): {await format_places(existing_locations)}'

    # 			if view.clearing:
    # 				description += '\n• Roles: Being cleared!'
    # 			elif view.roles():
    # 				description += f'\n• Roles: Being set to {await format_roles(view.roles())}.'
    # 			elif existing_roles:
    # 				description += f'\n• Roles: {await format_roles(existing_roles)}'

    # 			embed, _ = await mbd(
    # 				f'Reviewing {len(reviewing_characters)} Characters',
    # 				description,
    # 				'Select only one character to change their avatar or name.')

    # 			return embed, _

    # 		def checks():
    # 			return not (valid_url or view.places() or view.roles() or view.name() or view.clearing)

    # 		async def submit(interaction: Interaction):

    # 			await loading(interaction)

    # 			nonlocal char_data

    # 			LM = ListenerManager(interaction.guild, GD)
    # 			await LM.load_channels()

    # 			character_channels = {char_ID : await get_or_fetch(interaction.guild, 'channel', char_ID) for char_ID in reviewing_characters}

    # 			description = ''
    # 			image_view = None
    # 			if len(reviewing_characters) == 1:

    # 				if view.name():
    # 					description += f"• Changed *{char_name}*'s name to *{view.name()}*."
    # 					char_data.name = view.name()
    # 					await character_channels[char_ID].edit(name = view.name())

    # 				if view.url() and valid_url:
    # 					description += f"• Changed *{char_data.name}*'s avatar to [this]({view.url()})."
    # 					char_data.avatar = view.url()
    # 					image_view = (view.url(), 'thumb')

    # 				if view.name() or view.url():
    # 					await character_change(character_channels[char_ID], char_data)

    # 				title = f'Reviewed {char_data.name}.'

    # 			else:
    # 				title = f'Reviewed {len(reviewing_characters)} Characters.'
    # 				description += f"• Did the following to {await format_channels(reviewing_characters.keys())}."

    # 			if view.clearing:
    # 				description += "• Removed their role(s)."
    # 				for role_char in characters_dict.values():
    # 					role_char.roles = ''

    # 			elif view.roles():

    # 				description += f"• Changed their role(s) to {await format_roles(view.roles())}."
    # 				for character in characters_dict.values():
    # 					character.roles = view.roles()

    # 			informed_channels = set()
    # 			if view.places():

    # 				LM = ListenerManager(ctx.guild, GD)
    # 				await LM.load_channels()

    # 				dest_name = view.places()[0]

    # 				vacating_places = {char_data.location : \
    # 					dict().setdefault(char_data.location, set()).union({char_ID}) \
    # 					for char_ID, char_data in characters_dict.items()}

    # 				destination_place = GD.places[dest_name]
    # 				description += f"\n• Relocated them to <#{destination_place.channel_ID}>."

    # 				informed_channels.add(await LM._load_channel(destination_place.channel_ID))

    # 				for location, moving_people in vacating_places.items():

    # 					moving_names = {GD.characters[char_ID] for char_ID in moving_people}
    # 					place = GD.places[location]

    # 					# Remove people from place
    # 					for moving_ID in moving_people:

    # 						moving_char = characters_dict[moving_ID]
    # 						await GD.evict_character(moving_char)
    # 						await LM.remove_channel(moving_ID)

    # 					# Inform occs
    # 					embed, _ = await mbd(
    # 						'Poof.',
    # 						f'{await format_characters(moving_names)} just got whisked away.',
    # 						"But to where?")
    # 					await to_direct_listeners(
    # 						embed,
    # 						interaction.guild,
    # 						place.channel_ID)

    # 					# Inform place
    # 					embed, _ = await mbd(
    # 						'Teleported.',
    # 						f'Relocated {await format_channels(moving_people)} to' +
    # 							f' <#{place.channel_ID}>.',
    # 						'You can further relocate them with /review player.')
    # 					origin_channel = await LM._load_channel(place.channel_ID)
    # 					await origin_channel.send(embed = embed)

    # 					if view.clearing or view.roles():
    # 						informed_channels.add(origin_channel)

    # 					# Put them back
    # 					for moving_ID in moving_people:

    # 						moving_char = characters_dict[moving_ID]
    # 						await GD.insert_character(moving_char, dest_name)
    # 						await moving_char.save()
    # 						await LM.insert_character(moving_char, skip_eaves = True)

    # 						embed, _ = await mbd(
    # 							'How...What?',
    # 							f'You find yourself now at **#{dest_name}**.',
    # 							'Better find your bearings.')
    # 						moving_channel = await LM._load_channel(moving_ID)
    # 						await moving_channel.send(embed = embed)

    # 					await GD.save()

    # 					embed, _ = await mbd(
    # 						'Whoosh.',
    # 						f'{await format_characters(moving_names)} just appeared here at **#{dest_name}**.',
    # 						"How strange.")
    # 					await to_direct_listeners(
    # 						embed,
    # 						interaction.guild,
    # 						destination_place.channel_ID)

    # 					embed, _ = await mbd(
    # 						'New arrival(s).',
    # 						f'{await format_channels(moving_people)} got teleported here.',
    # 						"You can move them again using /review player.")
    # 					destination_channel = await LM._load_channel(destination_place.channel_ID)
    # 					await destination_channel.send(embed = embed)


    # 			for character in characters_dict.values():
    # 				their_place = GD.places[character.location]
    # 				informed_channels.add(await LM._load_channel(their_place.channel_ID))
    # 				await character.save()

    # 			embed, file = await mbd(
    # 				title,
    # 				description,
    # 				'You can always undo your changes by calling /review player again.',
    # 				image_view)

    # 			if view.clearing or view.roles():

    # 				for channel in character_channels.values():
    # 					affected_char = characters_dict[channel.id]
    # 					await character_change(channel, affected_char)

    # 				for channel in informed_channels:
    # 					await channel.send(embed = embed, file = file)

    # 			return await no_redundancies(
    # 				(interaction.channel.id in reviewing_characters or interaction.channel in informed_channels),
    # 				embed,
    # 				interaction,
    # 				file)


    # 		if len(reviewing_characters) == 1:
    # 			view = DialogueView(singular_refresh, checks)
    # 			other_places = set(GD.places.keys())
    # 			other_places.remove(char_data.location)
    # 			await view.add_places(other_places)
    # 			await view.add_roles()
    # 			await view.add_submit(submit)
    # 			await view.add_rename(char_name[:24])
    # 			await view.add_URL()
    # 			if char_data.roles:
    # 				await view.add_clear()
    # 			embed, file = await singular_refresh()
    # 		else:
    # 			view = DialogueView(multiple_refresh, checks)
    # 			await view.add_places(GD.places.keys())
    # 			await view.add_roles()
    # 			await view.add_submit(submit)
    # 			if existing_roles:
    # 				await view.add_clear()
    # 			embed, file = await multiple_refresh()

    # 		await view.add_cancel()

    # 		await send_message(ctx.respond, embed, view, ephemeral = True)
    # 		return

    # 	async def select_menu():
    # 		description = 'You can review a character three ways:' + \
    # 			'\n• Call this command inside of a character channel.' + \
    # 			'\n• Do `/review character character-name`.' + \
    # 			'\n• Select a character from the dropdown below.'

    # 		async def refresh():

    # 			nonlocal description

    # 			if view.character_select.values and not view.characters():
    # 				description = 'Because you have more characters than can' + \
    # 					' fit in a Text dropdown, this uses a Channel dropdown.' + \
    # 					" It's almost the same, just choose the character channels" + \
    # 					' instead of the character names. Non-character channels' + \
    # 					' get ignored.'

    # 			embed, _ = await mbd(
    # 				'Review character?',
    # 				description,
    # 				"This will only select them, you'll see their details after this.")
    # 			return embed, None

    # 		def checks():
    # 			return not view.characters()

    # 		async def submit_characters(interaction: Interaction):
    # 			await ctx.delete()
    # 			await review_character(view.characters())
    # 			return

    # 		view = DialogueView()
    # 		await view.add_characters(GD.characters, callback = submit_characters)
    # 		await view.add_cancel()
    # 		embed, _ = await refresh()
    # 		await send_message(ctx.respond, embed, view)
    # 		return

    # 	if result := await CM.identify_character_channel(ctx, select_menu, given_character):
    # 		await review_character(result)

    # 	return

    @review_group.command(name = "roleplay", description = "Look over the details of this roleplay.")
    async def roleplay(self, ctx: ApplicationContext):

        rp = await Roleplay.load(ctx.guild_id)
        assert rp is not None, "This server is not a roleplay server. Please set it up first."

        embed, file = await image_embed(
            f"Reviewing {rp.data.name}",
            f"**Character Count:** {await rp.character_count} / {rp.data.character_limit}"
                f"\n**Character Category:** " +
                    (f"{rp.data.char_mention}" if rp.data.characters_cat is not None else "None yet.") +
                f"\n**Location Count:** {await rp.location_count} / {rp.data.location_limit}"
                f"\n**Location Category:** " +
                    (f"{rp.data.loc_mention}" if rp.data.locations_cat is not None else "None yet.") +
                f"\n**Log Channel:** {rp.data.log_mention}"
                f"\n**Description:** {rp.data.description}"
                "\n**Reference:** " +
                    ("See below." if rp.data.reference else "None (yet). You should add one!"),
            "Would you perhaps like to change these things?",
            thumbnail = rp.data.reference is None,
            source = ImageSource.URL if rp.data.reference is not None else ImageSource.ASSET,
            asset_str = rp.data.reference or "")

        dialogue = Dialogue(embed, file, disable_timeout = True)
        details_popup = Popup(title = "Roleplay details")

        dialogue.add_channel_select(
            label = "logging",
            purpose = " for admin logs",
            placeholder = "Change the log channel?",
            min_values = 0)

        details_popup.add_text(
            label = "Title",
            placeholder = "What should the roleplay be renamed to?",
            min_length = 1,
            max_length = 64,
            value = rp.data.name)

        details_popup.add_text(
            label = "Description",
            placeholder = "Have you got a better description in mind?",
            min_length = 0,
            max_length = 300,
            required = False,
            value = rp.data.description,
            style = InputTextStyle.paragraph)

        details_popup.add_text(
            label = "Reference photo URL",
            placeholder = "You can paste an Imgur link for your reference art or advert.",
            min_length = 1,
            max_length = 300,
            required = False,
            value = rp.data.reference,
            style = InputTextStyle.paragraph)

        details_popup.add_text(
            label = "Maximum player count",
            placeholder = "10 - Subscribe to increase this limit!",
            required = False)

        details_popup.add_text(
            label = "Maximum location count",
            placeholder = "10 - Subscribe to increase this limit!",
            required = False)

        details_button = dialogue.add_button(label = "Edit roleplay details", style = ButtonStyle.blurple)
        dialogue.add_modal(details_popup, details_button)

        proposals = {
            "log_channel_id" : dialogue._fields["logging"].get_value(),
            "name" : dialogue._fields["Title"].get_value(),
            "description" : dialogue._fields["Description"].get_value(),
            "reference" : dialogue._fields["Reference photo URL"].get_value()}
        
        async def submit(interaction: Interaction):

            url_results = await reference_validator(proposals["reference"])
            if url_results != CommitResult.SUCCESS:
                proposals["reference"] = None

            old_rp_data = RoleplayData(**rp.data.__dict__.copy())
            await rp.update(**proposals)

            embed, file = await RoleplayEmbeds.update.user(
                old_rp_data,
                proposals,
                rp.data)

            await notify_log(rp.data, embed, file)
            
            dialogue.current_embed, dialogue.current_file = embed, file
            dialogue.view.clear_items()
            await dialogue.refresh(interaction)

            return

        submit_button = dialogue.add_button(label = "Submit", style = ButtonStyle.success)

        def should_disable():

            nonlocal proposals
            proposals = {
                "log_channel_id" : dialogue._fields["logging"].get_value(),
                "name" : dialogue._fields["Title"].get_value(),
                "description" : dialogue._fields["Description"].get_value(),
                "reference" : dialogue._fields["Reference photo URL"].get_value()}

            if not dialogue.is_valid:
                return True

            changes_proposed = {k : v for k, v in proposals.items() if v != getattr(rp.data, k)}
            return not len(changes_proposed) > 0
        
        submit_button.should_disable = lambda : not dialogue.is_valid

        submit_button.callback = submit
        submit_button.should_disable = should_disable
        dialogue.add_close()

        await dialogue.view.refresh_children()
        await send_message(
            ctx.interaction,
            embed,
            dialogue.view,
            file = file,
            ephemeral = True)

        return

def setup(prox):
    prox.add_cog(ReviewCommands(prox), override = True)
