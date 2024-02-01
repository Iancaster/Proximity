

#Import-ant Libraries
from discord import AutocompleteContext
from libraries.new_classes import GuildData, Character


#Functions
async def complete_places(ctx: AutocompleteContext):

	GD = GuildData(ctx.interaction.guild_id, load_places = True)

	if not GD.places:
		return ['No places!']

	return GD.places.keys()

async def exclusionary_places(ctx: AutocompleteContext):

	GD = GuildData(ctx.interaction.guild_id, load_places = True)

	if not GD.places:
		return ['No places!']

	other_places = set(GD.places.keys())
	other_places.discard(ctx.interaction.channel.name)

	if not other_places:
		return ['No other places!']

	return other_places

async def complete_map(ctx: AutocompleteContext):

	GD = GuildData(
		ctx.interaction.guild_id,
		load_places = True,
		load_characters = True)

	if not await GD.validate_membership(ctx.interaction.channel.id):
		return ['You can only call this command in a Character Channel.']

	char_data = Character(ctx.interaction.channel.id)

	access_places = await GD.accessible_locations(
		[char_data.roles],
		ctx.interaction.channel.id,
		char_data.location)

	access_places.discard(char_data.location)

	return access_places or ['There is nowhere nearby to move to.']

async def complete_characters(ctx: AutocompleteContext):

	GD = GuildData(ctx.interaction.guild_id, load_characters = True)

	if not GD.characters:
		return ['No characters!']

	return list(set(GD.characters.values()))

async def glossary(ctx: AutocompleteContext):

	return [
		'graph', 'network', 'path', 'place', 'audio',
		'direct', 'indirect', 'visible', 'move',
		'character', 'player', 'whitelist', 'neighbor']

