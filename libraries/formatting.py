

#Import-ant Libraries
from networkx import DiGraph
from re import search, sub


#Functions
async def format_words(words: iter):

	if not words:
		return ''

	word_list = list(words)

	if len(words) == 1:
		return word_list[0]

	elif len(words) == 2:
		return f'{word_list[0]} and {word_list[1]}'

	formatted_words = ', '.join(word_list[:-1])
	formatted_words += f', and {word_list[-1]}'

	return formatted_words

async def format_roles(role_IDs: iter):
	return await format_words([f'<@&{ID}>' for ID in role_IDs])

async def format_characters(characters: iter):
	return await format_words([f'**{name}**' for name in characters])

async def format_channels(channel_IDs: iter):
	return await format_words([f'<#{ID}>' for ID in channel_IDs])

async def format_places(places: iter):
	return await format_words([f'<#{place.channel_ID}>' for place in places])

async def format_new_neighbors(overwriting: bool, origin_place, places: set, guild_data):

	description = '\n• Destination(s): '

	if overwriting:
		new_neighbors = set(places)
	else:
		new_neighbors = {place for place in places if place not in origin_place.neighbors}
	existing_neighbors = {place for place in places if place not in new_neighbors}

	destination_comments = []

	if not (new_neighbors or existing_neighbors):
		return description + 'Add some places to draw new paths to using the dropdown below.', set()

	if new_neighbors:
		destinations = await guild_data.filter_places(new_neighbors)
		destination_mentions = await format_places(destinations.values())
		destination_comments.append(destination_mentions)

	if existing_neighbors:

		if overwriting:
			destination_comments.append(
				f'{len(existing_neighbors)} existing paths that will be overwritten')
			new_neighbors.append(existing_neighbors)
		else:
			destination_comments.append(
				f'{len(existing_neighbors)} existing paths that are getting skipped' +
					' Enable overwriting below if you want these to be overwritten')

	return f'{description}{await format_words(destination_comments)}.', new_neighbors

async def embolden(place_names: iter):
	return await format_words([f"**#{name}**" for name in place_names])

async def format_whitelist(allowed_roles: iter = set(), allowed_characters: iter = set()):

	if not allowed_roles and not allowed_characters:
		return 'Everyone will be allowed to travel to/through this place.'

	role_mentions = await format_roles(allowed_roles)
	character_mentions = await format_characters(allowed_characters)

	if allowed_roles and not allowed_characters:
		return f'Only people with these roles are allowed through this place: ({role_mentions}).'

	elif allowed_characters and not allowed_roles:
		return f'Only these characters are allowed through this place: ({character_mentions}).'

	roles_description = f'any of these roles: ({role_mentions})' if allowed_roles else 'any role'

	character_description = f'any of these people: ({character_mentions})' if allowed_characters else 'everyone else'

	return f'People with {roles_description} will be allowed to come here as well as {character_description}.'

async def discordify(text: str):

	sanitized = ''.join(character.lower() for character in \
						text if (character.isalnum() or character.isspace() or character == '-'))
	spaceless = '-'.join(sanitized.split())

	return spaceless[:19]

async def format_colors(graph: DiGraph, origin_name: str, colored_neighbors: list, color: str):

	path_colors = []
	for origin, destination in graph.edges:
		if origin in colored_neighbors and destination == origin_name:
			path_colors.append(color)
		elif origin == origin_name and destination in colored_neighbors:
			path_colors.append(color)
		else:
			path_colors.append('black')

	return path_colors

async def unique_name(candidate_name: str, places: iter):

	async def get_index(name):
		match = search(r'\d+$', name)
		if match:
			return int(match.group())
		return 0

	while candidate_name in places:
		suffix = await get_index(candidate_name)
		if suffix > 0:
			candidate_name = sub(r'\d+$', str(suffix + 1), candidate_name)
		else:
			candidate_name = f"{candidate_name}-2"

	return candidate_name

