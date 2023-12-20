

#Import-ant Libraries
from discord import AutocompleteContext
from libraries.classes import GuildData


#Functions
async def complete_places(ctx: AutocompleteContext):

	guild_data = GuildData(ctx.interaction.guild_id, load_places = True)

	if not guild_data.places:
		return ['No places!']

	return guild_data.places.keys()

async def complete_map(ctx: AutocompleteContext):

	player = None#Player(ctx.interaction.user.id, ctx.interaction.guild_id)

	if not player.location:
		return ["Only players can use this command."]

	guild_data = GuildData(ctx.interaction.guild_id)

	guild_map = await guild_data.accessible_locations(
		[ID for ID in ctx.interaction.user.roles],
		ctx.interaction.user.id,
		player.location)

	return guild_map.places

async def complete_characters(ctx: AutocompleteContext):

	guild_data = GuildData(ctx.interaction.guild_id, load_characters = True)

	if not guild_data.places:
		return ['No characters!']

	return list(set(guild_data.characters.values()))
