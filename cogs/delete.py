


from discord import ApplicationContext, Interaction, InteractionContextType, ButtonStyle
from discord.ext import commands
from discord.commands import SlashCommandGroup
from discord.utils import get_or_fetch

from libraries.classes import in_text_channel, is_administrator, in_prox_rp, RPServer, Location
from libraries.user_interface import Dialogue, ImageSource, text_embed, image_embed, send_message

from asyncio import create_task

class DeleteCommands(commands.Cog):

    delete_group = SlashCommandGroup(
        name = "delete",
        description = "Get rid of Locations, Routes, or Characters. Or the RP itself.",
        contexts = [InteractionContextType.guild],
        checks = [in_text_channel, is_administrator, in_prox_rp])

    @delete_group.command(name = "location", description = "Delete a location.")
    async def location(self, ctx: ApplicationContext):
 
        async def delete_location(interaction: Interaction):

            if await location.character_count != 0:

                embed = text_embed(
                    "Can't delete this location.",
                    f"<#{location.id}> still has characters in it. Please move"
                        " them somewhere else first with `/review character`.",
                    "This is to prevent characters from being stranded in a nonexistant location.")
                dialogue.current_embed = embed
                dialogue.view.clear_items()
                return await dialogue.refresh(interaction)
                
            if calling_from_location_channel:
                await interaction.respond("Sure thing!", ephemeral = True)

            log_channel = await server.get_logging_channel(interaction.guild)
            await location.fetch()
            await location.delete(log_channel = log_channel, guild = interaction.guild)

            if not calling_from_location_channel:
                embed = text_embed(
                    "Location deleted.",
                    f"Deleted **{location.name}** and all routes connected to it.",
                    "This can't be undone, but you can always make a new location.")
                    
                dialogue.current_embed = embed
                dialogue.view.clear_items()
                await dialogue.refresh(interaction)
                
            return

        server = RPServer(ctx.guild_id)
        await server.fetch()
        location = Location(ctx.channel_id)   
        calling_from_location_channel = await location.exists

        if calling_from_location_channel:

            embed = text_embed(
                "Delete this location?",
                f"You're about to delete <#{location.id}> and all routes to and from it.",
                "This is irreversible, so make sure you really want to do this.")
            
        else:
            
            embed = text_embed(
                "Which location?",
                ("Please select a location channel from the dropdown below"
                    " to delete the location. You can also call this command"
                    " in a location channel to select it automatically."),
                "This will delete the location, its channel, and all" + 
                    " routes to and from it.")
            
        dialogue = Dialogue(embed) 

        if calling_from_location_channel:
            
            submit_button = dialogue.add_button("Select for deletion", ButtonStyle.danger)
            submit_button.callback = delete_location     

        else:

            channel_select = dialogue.add_channel_select(
                label = "Select a location to delete.",
                purpose = "Location choice",
                placeholder = "#the-castle",
                min_values = 1)
            
            submit_button = dialogue.add_button("Select for deletion", ButtonStyle.danger)

            async def select(interaction: Interaction):
                nonlocal location
                location = Location(channel_select.values[0].id) # pyright: ignore[reportPossiblyUnboundVariable]
                await delete_location(interaction)
                return
            
            submit_button.callback = select

            location_ids = [loc.id for loc in await server.locations]
            submit_button.should_disable = (lambda : not channel_select.is_valid() or # pyright: ignore[reportPossiblyUnboundVariable]
                channel_select.values[0].id not in location_ids) # pyright: ignore[reportPossiblyUnboundVariable]
            
            await dialogue.view.refresh_children()

        dialogue.add_close()
        return await send_message(ctx.interaction, embed, dialogue.view, ephemeral = True)

    # @delete_group.command(name = 'path', description = 'Seperate two or more places.')
    # async def path(self, ctx: ApplicationContext, given_place: Option(str, description = 'Which place to start from?', name = 'place', autocomplete = complete_places, required = False)):

    # 	await ctx.defer(ephemeral = True)

    # 	GD = GuildData(ctx.guild_id, load_places = True)
    # 	CM = ChannelManager(GD = GD)

    # 	async def delete_paths(origin_place_name: str):

    # 		origin_place = GD.places[origin_place_name]

    # 		neighbors = origin_place.neighbors
    # 		if not neighbors:
    # 			embed, _ = await mbd(
    # 				'No paths.',
    # 				f'<#{origin_place.channel_ID}> has no paths to delete. It' + \
    # 					" isn't connected to any other places.",
    # 				'So...mission accomplished?')
    # 			await send_message(ctx.respond, embed, ephemeral = True)
    # 			return

    # 		impacted_places = await GD.filter_places(list(neighbors.keys()) + [origin_place_name])
    # 		graph = await GD.to_graph(impacted_places)
    # 		description = f'<#{origin_place.channel_ID}> has these connections'
    # 		graph_image = None

    # 		async def refresh():

    # 			nonlocal graph_image
    # 			full_description = description

    # 			if not view.paths():
    # 				full_description += ':'
    # 			else:
    # 				selected_neighbors = {name : neighbors[name] for name in view.paths()}
    # 				full_description += ", but you'll be deleting the following:" + \
    # 					await GD.format_paths(selected_neighbors)

    # 			path_colors = await format_colors(graph, origin_place_name, view.paths(), 'red')
    # 			graph_image = await GD.to_map(graph, path_colors)

    # 			embed, file = await mbd(
    # 				'Delete paths(s)?',
    # 				full_description,
    # 				'This can only be reversed by remaking them.',
    # 				(graph_image, 'full'))

    # 			return embed, file

    # 		def checks():
    # 			return not view.paths()

    # 		async def submit(interaction: Interaction):

    # 			await loading(interaction)

    # 			nonlocal graph_image

    # 			for neighbor in view.paths():
    # 				await GD.delete_path(origin_place_name, neighbor)

    # 			await GD.save()

    # 			await queue_refresh(interaction.guild)

    # 			deleted_neighbors = await GD.filter_places(view.paths())

    # 			#Inform neighbors occupants and neighbor nodes
    # 			player_embed, _ = await mbd(
    # 				'Hm?',
    # 				f"The path between here and **#{origin_place_name}** just closed.",
    # 				'Just like that...')
    # 			node_embed, _ = await mbd(
    # 				'Path deleted.',
    # 				f'Removed an edge between here and <#{origin_place.channel_ID}>.',
    # 				'You can view the remaining paths with /review paths.')
    # 			for place in deleted_neighbors.values():
    # 				await to_direct_listeners(
    # 					player_embed,
    # 					interaction.guild,
    # 					place.channel_ID,
    # 					occupants_only = True)
    # 				place_channel = get(interaction.guild.text_channels, id = place.channel_ID)
    # 				await place_channel.send(embed = node_embed)

    # 			#Inform edited node occupants
    # 			bold_deleted = await embolden(view.paths())
    # 			player_embed, _ = await mbd(
    # 				'Hm?',
    # 				f"This place just lost access to {bold_deleted}.",
    # 				"Will that path ever be restored?")
    # 			await to_direct_listeners(
    # 				player_embed,
    # 				interaction.guild,
    # 				origin_place.channel_ID,
    # 				occupants_only = True)

    # 			#Inform own node
    # 			deleted_mentions = await format_channels(deleted_neighbors.keys())
    # 			embed, file = await mbd(
    # 				'Path(s) deleted.',
    # 				f'Removed the path(s) to {deleted_mentions}.',
    # 				'You can always make some new ones with /new path.',
    # 				(graph_image, 'full'))
    # 			node_channel = get(interaction.guild.text_channels, name = origin_place_name)
    # 			await node_channel.send(embed = embed, file = file)

    # 			await no_redundancies(
    # 				(interaction.channel.name == origin_place_name),
    # 				embed,
    # 				interaction,
    # 				file)
    # 			return

    # 		view = DialogueView(refresh, checks)
    # 		await view.add_paths(neighbors)
    # 		await view.add_submit(submit)
    # 		await view.add_cancel()
    # 		embed, file = await refresh()
    # 		await send_message(ctx.respond, embed, view, file, ephemeral = True)

    # 	async def select_menu():

    # 		embed, _ = await mbd(
    # 			'Delete path(s)?',
    # 			"You can delete a path three ways:" + \
    # 				"\n• Call this command inside of a place channel." + \
    # 				"\n• Do `/delete path #place-channel`." + \
    # 				"\n• Select a place from the dropdown below.",
    # 			"This is to select the origin, you'll choose which paths to delete next.")

    # 		async def submit_location(interaction: Interaction):
    # 			await ctx.delete()
    # 			await delete_paths(list(view.places())[0])
    # 			return

    # 		view = DialogueView()
    # 		await view.add_places(GD.places.keys(), singular = True, callback = submit_location)
    # 		await view.add_cancel()
    # 		await send_message(ctx.respond, embed, view)

    # 		return

    # 	if result := await CM.identify_place_channel(ctx, select_menu, given_place):
    # 		await delete_paths(result)

    # 	return

    # @delete_group.command(name = 'character', description = 'Delete a character.')
    # async def character(self, ctx: ApplicationContext, given_character: Option(str, description = 'Which character?', name = 'character', autocomplete = complete_characters, required = False)):

    # 	await ctx.defer(ephemeral = True)

    # 	GD = GuildData(ctx.guild_id, load_places = True, load_characters = True)
    # 	CM = ChannelManager(GD = GD)

    # 	async def delete_characters(condemned_characters: dict):

    # 		async def confirm_delete(interaction: Interaction):

    # 			await loading(interaction)

    # 			nonlocal condemned_characters

    # 			for character_ID in condemned_characters.keys():

    # 				character_channel = await get_or_fetch(interaction.guild, 'channel', character_ID, default = None)
    # 				if character_channel:
    # 					await character_channel.delete()
    # 					await remove_speaker(character_channel)
    # 				else:
    # 					await GD.delete_character(character_ID)
    # 					await GD.save()
    # 					direct_listeners.pop(character_ID)
    # 					indirect_listeners.pop(character_ID)
    # 					sleep(.5)

    # 			if not GD.characters:
    # 				category = get(interaction.guild.categories, name = 'characters')
    # 				if category:
    # 					await category.delete()

    # 			description = f'Deleted {await format_characters(condemned_characters.values())}.' + \
    # 				"\n• Deleted their channel(s)." + \
    # 				"\n• Removed them as occupants." + \
    # 				"\n• Notified nearby characters.*"

    # 			embed, _ = await mbd(
    # 				'Cleared out.',
    # 				description,
    # 				'*Unless you already deleted their channel before this.')
    # 			if interaction.channel.id not in condemned_characters:
    # 				await interaction.followup.edit_message(
    # 				message_id = interaction.message.id,
    # 				embed = embed,
    # 				view = None)
    # 			return

    # 		view = DialogueView()
    # 		await view.add_confirm(confirm_delete)
    # 		await view.add_cancel()

    # 		description = "This command will do the following to" + \
    # 			f" {await format_channels(condemned_characters.keys())}:" + \
    # 			"\n• Delete their character channel(s).\n• Remove them as" + \
    # 			" an occupant in the place they're in." + \
    # 			"\n\nIt will **not**:\n• Delete their messages." + \
    # 			"\n• Prevent you from recreating them later."

    # 		embed, _ = await mbd(
    # 			'Confirm deletion?',
    # 			description,
    # 			'Nearby characters will notice their disappearance.')
    # 		await send_message(ctx.respond, embed, view, ephemeral = True)
    # 		return

    # 	async def select_menu():

    # 		description = 'You can delete a character four ways:' + \
    # 			'\n• Call this command inside of a character channel.' + \
    # 			'\n• Do `/delete character character-name`.' + \
    # 			'\n• Delete the **#character-channel** itself.' + \
    # 			'\n• Select one or more characters from the dropdown below.'

    # 		async def refresh():

    # 			nonlocal description

    # 			if view.character_select.values and not view.characters():
    # 				description = 'Because you have more characters than can' + \
    # 					' fit in a Text dropdown, this uses a Channel dropdown.' + \
    # 					" It's almost the same, just choose the character channels" + \
    # 					' instead of the character names. Non-character channels' + \
    # 					' get ignored.'

    # 			embed, _ = await mbd(
    # 				'Delete character(s)?',
    # 				description,
    # 				"This will only select them, you'll be asked if you want to delete them for sure after this.")
    # 			return embed, None

    # 		def checks():
    # 			return not view.characters()

    # 		async def submit_characters(interaction: Interaction):
    # 			await ctx.delete()
    # 			await delete_characters(view.characters())
    # 			return

    # 		view = DialogueView()
    # 		await view.add_characters(GD.characters, callback = submit_characters)
    # 		await view.add_cancel()
    # 		embed, _ = await refresh()
    # 		await send_message(ctx.respond, embed, view)

    # 		return

    # 	if result := await CM.identify_character_channel(ctx, select_menu, given_character):
    # 		await delete_characters(result)

    # 	return

    @delete_group.command(name = "roleplay", description = "Delete all RP data and channels. Use with caution.")
    async def roleplay(self, ctx: ApplicationContext):

        server = RPServer(ctx.guild_id)
        async def delete_data(interaction: Interaction):

            await server.fetch()
            logging_channel = await server.get_logging_channel(interaction.guild)
            await server.delete(logging_channel)

            embed, file = await image_embed(
                f"Roleplay Deleted: {server.name}",
                "The following has been deleted: " 
                    "\n - All server data (name, description, reference, etc)."
                    "\n - All Locations, their channels, and all Routes between them."
                    "\n - All Characters and their location channels.",
                "Sorry to see you go.",
                thumbnail = True,
                source = ImageSource.URL if server.reference else ImageSource.ASSET,
                asset_str = server.reference or "")

            dialogue.current_embed, dialogue.current_file = embed, file
            dialogue.view.clear_items()
            return await dialogue.refresh(interaction)

        embed = text_embed(
            "Delete all data?",
            "You're about to delete all server data, including"
                " all Locations and Characters. Any associated" 
                " channels will also be deleted, except for the"
                " log channel you set when you registered the server.",
            "This is irreversible, so make sure you really want to do this.")

        dialogue = Dialogue(embed)
        delete_button = dialogue.add_button("Delete all data", ButtonStyle.danger)
        delete_button.callback = delete_data
        dialogue.add_close()
    
        return await send_message(ctx.interaction, embed, dialogue.view, ephemeral = True)

def setup(prox):
    prox.add_cog(DeleteCommands(prox), override = True)
