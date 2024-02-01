

#Import-ant Libraries
from discord import ApplicationContext, Option, Interaction, Embed
from discord.ext import commands
from discord.commands import SlashCommandGroup
from discord.utils import get, get_or_fetch

from libraries.new_classes import GuildData, ChannelManager, \
	DialogueView, ListenerManager
from libraries.universal import *
from libraries.formatting import *
from libraries.autocomplete import *
from data.listeners import *

from asyncio import sleep

#Classes
class DeleteCommands(commands.Cog):

	delete_group = SlashCommandGroup(
		name = 'delete',
		description = 'Get rid of places, paths, or characters.',
		guild_only = True)

	@delete_group.command(name = 'place', description = 'Delete a place.')
	async def place(self, ctx: ApplicationContext, given_place: Option(str, description = 'Which place?', name = 'place', autocomplete = complete_places, required = False)):

		await ctx.defer(ephemeral = True)

		GD = GuildData(ctx.guild_id, load_places = True)
		CM = ChannelManager(GD = GD)

		async def delete_locations(condemned_place_names: list):

			condemned_places = await GD.filter_places(condemned_place_names)

			async def confirm_delete(interaction: Interaction):

				await loading(interaction)

				nonlocal condemned_places
				occupied_place_count = len(condemned_places)
				condemned_places = {name : place for name, place in condemned_places.items() if not place.occupants}
				occupied_place_count -= len(condemned_places)

				if not condemned_places:
					embed, _ = await mbd(
						'And leave them stranded?',
						"You can't delete places that have people still inside." + \
							" Either use `/review character` to move them somewhere" + \
							" else, or just `/delete character` so it's not a problem.",
						'Then you can do /delete place.')
					await interaction.followup.edit_message(
						message_id = interaction.message.id,
						embed = embed,
						view = None)
					await interaction.message.delete(delay = 15)
					return

				#Delete places
				for name, place in condemned_places.items():

					place_channel = await get_or_fetch(interaction.guild, 'channel', place.channel_ID, default = None)
					if place_channel:
						await place_channel.delete()
					else:
						await GD.delete_place(name)
						await GD.save()
						sleep(.5)

				if not GD.places:
					category = get(interaction.guild.categories, name = 'places')
					if category:
						await category.delete()

				if interaction.channel.name not in condemned_places.keys():

					bold_deleting = await embolden(condemned_places.keys())
					description = f'Successfully deleted the following things about {bold_deleting}:' + \
						"\n• The channel(s)." + \
						"\n• Any paths." + \
						"\n• The data, like location messages."

					if occupied_place_count:
						description += f"\n\nCouldn't delete {occupied_place_count}" + \
							" place(s) because there were still people inside."

					embed, _ = await mbd(
						'Cleared out.',
						description,
						'Making room for new places?')
					await interaction.followup.edit_message(
						message_id = interaction.message.id,
						embed = embed,
						view = None)
				return

			view = DialogueView()
			await view.add_confirm(confirm_delete)
			await view.add_cancel()

			condemned_IDs = {place.channel_ID for place in condemned_places.values()}
			embed, _ = await mbd(
				'Confirm deletion?',
				f"Delete {await format_channels(condemned_IDs)}?",
				'This will delete the channel, the paths, and data for the place itself.')
			await send_message(ctx.respond, embed, view, ephemeral = True)
			return

		async def select_menu():

			embed, _ = await mbd(
				'Delete place(s)?',
				"You can delete a location four ways:" + \
					"\n• Call this command inside of a place channel." + \
					"\n• Do `/delete place #place-channel`." + \
					"\n• Delete the #place-channel itself." + \
					"\n• Select one or more places from the dropdown below.",
				'This will delete the place, its paths, and its channel.')

			async def submit_locations(interaction: Interaction):
				await ctx.delete()
				await delete_locations(view.places())
				return

			view = DialogueView()
			await view.add_places(GD.places.keys(), singular = False, callback = submit_locations)
			await view.add_cancel()
			await send_message(ctx.respond, embed, view)

			return

		if result := await CM.identify_place_channel(ctx, select_menu, given_place):
			await delete_locations([result])

		return

	@delete_group.command(name = 'path', description = 'Seperate two or more places.')
	async def path(self, ctx: ApplicationContext, given_place: Option(str, description = 'Which place to start from?', name = 'place', autocomplete = complete_places, required = False)):

		await ctx.defer(ephemeral = True)

		GD = GuildData(ctx.guild_id, load_places = True)
		CM = ChannelManager(GD = GD)

		async def delete_paths(origin_place_name: str):

			origin_place = GD.places[origin_place_name]

			neighbors = origin_place.neighbors
			if not neighbors:
				embed, _ = await mbd(
					'No paths.',
					f'<#{origin_place.channel_ID}> has no paths to delete. It' + \
						" isn't connected to any other places.",
					'So...mission accomplished?')
				await send_message(ctx.respond, embed, ephemeral = True)
				return

			impacted_places = await GD.filter_places(list(neighbors.keys()) + [origin_place_name])
			graph = await GD.to_graph(impacted_places)
			description = f'<#{origin_place.channel_ID}> has these connections'
			graph_image = None

			async def refresh():

				nonlocal graph_image
				full_description = description

				if not view.paths():
					full_description += ':'
				else:
					selected_neighbors = {name : neighbors[name] for name in view.paths()}
					full_description += ", but you'll be deleting the following:" + \
						await GD.format_paths(selected_neighbors)

				path_colors = await format_colors(graph, origin_place_name, view.paths(), 'red')
				graph_image = await GD.to_map(graph, path_colors)

				embed, file = await mbd(
					'Delete paths(s)?',
					full_description,
					'This can only be reversed by remaking them.',
					(graph_image, 'full'))

				return embed, file

			def checks():
				return not view.paths()

			async def submit(interaction: Interaction):

				await loading(interaction)

				nonlocal graph_image

				for neighbor in view.paths():
					await GD.delete_path(origin_place_name, neighbor)

				await GD.save()

				await queue_refresh(interaction.guild)

				deleted_neighbors = await GD.filter_places(view.paths())

				#Inform neighbors occupants and neighbor nodes
				player_embed, _ = await mbd(
					'Hm?',
					f"The path between here and **#{origin_place_name}** just closed.",
					'Just like that...')
				node_embed, _ = await mbd(
					'Path deleted.',
					f'Removed an edge between here and <#{origin_place.channel_ID}>.',
					'You can view the remaining paths with /review paths.')
				for place in deleted_neighbors.values():
					await to_direct_listeners(
						player_embed,
						interaction.guild,
						place.channel_ID,
						occupants_only = True)
					place_channel = get(interaction.guild.text_channels, id = place.channel_ID)
					await place_channel.send(embed = node_embed)

				#Inform edited node occupants
				bold_deleted = await embolden(view.paths())
				player_embed, _ = await mbd(
					'Hm?',
					f"This place just lost access to {bold_deleted}.",
					"Will that path ever be restored?")
				await to_direct_listeners(
					player_embed,
					interaction.guild,
					origin_place.channel_ID,
					occupants_only = True)

				#Inform own node
				deleted_mentions = await format_channels(deleted_neighbors.keys())
				embed, file = await mbd(
					'Path(s) deleted.',
					f'Removed the path(s) to {deleted_mentions}.',
					'You can always make some new ones with /new path.',
					(graph_image, 'full'))
				node_channel = get(interaction.guild.text_channels, name = origin_place_name)
				await node_channel.send(embed = embed, file = file)

				await no_redundancies(
					(interaction.channel.name == origin_place_name),
					embed,
					interaction,
					file)
				return

			view = DialogueView(refresh, checks)
			await view.add_paths(neighbors)
			await view.add_submit(submit)
			await view.add_cancel()
			embed, file = await refresh()
			await send_message(ctx.respond, embed, view, file, ephemeral = True)

		async def select_menu():

			embed, _ = await mbd(
				'Delete path(s)?',
				"You can delete a path three ways:" + \
					"\n• Call this command inside of a place channel." + \
					"\n• Do `/delete path #place-channel`." + \
					"\n• Select a place from the dropdown below.",
				"This is to select the origin, you'll choose which paths to delete next.")

			async def submit_location(interaction: Interaction):
				await ctx.delete()
				await delete_paths(list(view.places())[0])
				return

			view = DialogueView()
			await view.add_places(GD.places.keys(), singular = True, callback = submit_location)
			await view.add_cancel()
			await send_message(ctx.respond, embed, view)

			return

		if result := await CM.identify_place_channel(ctx, select_menu, given_place):
			await delete_paths(result)

		return

	@delete_group.command(name = 'server', description = 'Delete all server data.')
	async def server(self, ctx: ApplicationContext):

		await ctx.defer(ephemeral = True)

		GD = GuildData(
			ctx.guild_id,
			load_places = True,
			load_characters = True,
			load_roles = True)

		if not (GD.places or GD.characters or GD.roles):

			embed, _ = await mbd(
				'Nothing to delete!',
				'Data is only made when you create new places or characters.',
				'So, wish granted? This is as deleted as it gets.')
			await send_message(ctx.respond, embed)
			return

		async def delete_data(interaction: Interaction):

			await loading(interaction)

			await GD.delete(interaction.guild)

			embed, _ = await mbd(
				'See you.',
				"The following has been deleted: \n• All places." + \
					"\n• All paths."
					"\n• All characters.\n• All the channels I made.",
				'You can always remake them if you want.')

			try:
				await interaction.followup.edit_message(
					message_id = interaction.message.id,
					embed = embed,
					view = None)
			except:
				pass

			return

		view = DialogueView()
		await view.add_confirm(delete_data)
		await view.add_cancel()
		embed, _ = await mbd(
			'Delete all data?',
			f"You're about to delete {len(GD.places)} places" +
				f" and {await GD.count_paths()} paths, alongside" +
				f" {len(GD.characters)} character(s).",
			'This will also delete associated channels from the server.')
		await send_message(ctx.respond, embed, view)
		return

	@delete_group.command(name = 'character', description = 'Delete a character.')
	async def character(self, ctx: ApplicationContext, given_character: Option(str, description = 'Which character?', name = 'character', autocomplete = complete_characters, required = False)):

		await ctx.defer(ephemeral = True)

		GD = GuildData(ctx.guild_id, load_places = True, load_characters = True)
		CM = ChannelManager(GD = GD)

		async def delete_characters(condemned_characters: dict):

			async def confirm_delete(interaction: Interaction):

				await loading(interaction)

				nonlocal condemned_characters

				for character_ID in condemned_characters.keys():

					character_channel = await get_or_fetch(interaction.guild, 'channel', character_ID, default = None)
					if character_channel:
						await character_channel.delete()
						await remove_speaker(character_channel)
					else:
						await GD.delete_character(character_ID)
						await GD.save()
						direct_listeners.pop(character_ID)
						indirect_listeners.pop(character_ID)
						sleep(.5)

				if not GD.characters:
					category = get(interaction.guild.categories, name = 'characters')
					if category:
						await category.delete()

				description = f'Deleted {await format_characters(condemned_characters.values())}.' + \
					"\n• Deleted their channel(s)." + \
					"\n• Removed them as occupants." + \
					"\n• Notified nearby characters.*"

				embed, _ = await mbd(
					'Cleared out.',
					description,
					'*Unless you already deleted their channel before this.')
				if interaction.channel.id not in condemned_characters:
					await interaction.followup.edit_message(
					message_id = interaction.message.id,
					embed = embed,
					view = None)
				return

			view = DialogueView()
			await view.add_confirm(confirm_delete)
			await view.add_cancel()

			description = "This command will do the following to" + \
				f" {await format_channels(condemned_characters.keys())}:" + \
				"\n• Delete their character channel(s).\n• Remove them as" + \
				" an occupant in the place they're in." + \
				"\n\nIt will **not**:\n• Delete their messages." + \
				"\n• Prevent you from recreating them later."

			embed, _ = await mbd(
				'Confirm deletion?',
				description,
				'Nearby characters will notice their disappearance.')
			await send_message(ctx.respond, embed, view, ephemeral = True)
			return

		async def select_menu():

			description = 'You can delete a character four ways:' + \
				'\n• Call this command inside of a character channel.' + \
				'\n• Do `/delete character character-name`.' + \
				'\n• Delete the **#character-channel** itself.' + \
				'\n• Select one or more characters from the dropdown below.'

			async def refresh():

				nonlocal description

				if view.character_select.values and not view.characters():
					description = 'Because you have more characters than can' + \
						' fit in a Text dropdown, this uses a Channel dropdown.' + \
						" It's almost the same, just choose the character channels" + \
						' instead of the character names. Non-character channels' + \
						' get ignored.'

				embed, _ = await mbd(
					'Delete character(s)?',
					description,
					"This will only select them, you'll be asked if you want to delete them for sure after this.")
				return embed, None

			def checks():
				return not view.characters()

			async def submit_characters(interaction: Interaction):
				await ctx.delete()
				await delete_characters(view.characters())
				return

			view = DialogueView()
			await view.add_characters(GD.characters, callback = submit_characters)
			await view.add_cancel()
			embed, _ = await refresh()
			await send_message(ctx.respond, embed, view)

			return

		if result := await CM.identify_character_channel(ctx, select_menu, given_character):
			await delete_characters(result)

		return

def setup(prox):
	prox.add_cog(DeleteCommands(prox), override = True)
