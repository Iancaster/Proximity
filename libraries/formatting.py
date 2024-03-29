

# Import-ant Libraries
from networkx import DiGraph
from re import search, sub
from random import randrange
from requests import head

# Functions
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

async def get_names(character_IDs: iter, characters: dict):
	return {name for ID, name in characters.items() if ID in character_IDs}

async def format_characters(characters: iter):
	return await format_words([f'*{name}*' for name in characters])

async def format_channels(channel_IDs: iter):
	return await format_words([f'<#{ID}>' for ID in channel_IDs])

async def format_places(places: iter):
	return await format_words([f'**#{place}**' for place in places])

async def format_new_neighbors(overwriting: bool, origin_place, places: set, GD):

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
		destinations = await GD.filter_places(new_neighbors)
		destination_mentions = await format_channels(place.channel_ID for place in destinations.values())
		destination_comments.append(destination_mentions)

	if existing_neighbors:

		if overwriting:
			destination_comments.append(
				f'{len(existing_neighbors)} existing paths that will be overwritten')
			new_neighbors.append(existing_neighbors)
		else:
			destination_comments.append(
				f'{len(existing_neighbors)} existing paths that are getting skipped.' +
					' Enable overwriting below if you want these to be overwritten')

	return f'{description}{await format_words(destination_comments)}.', new_neighbors

async def embolden(place_names: iter):
	return await format_words([f"**#{name}**" for name in place_names])

async def format_whitelist(allowed_roles: iter = set(), allowed_characters: iter = set()):

	if not allowed_roles and not allowed_characters:
		return 'Everyone will be allowed to travel to/through here.'

	role_mentions = await format_roles(allowed_roles)
	character_mentions = await format_channels(allowed_characters)

	if allowed_roles and not allowed_characters:
		return f'Only people with these roles are allowed: ({role_mentions}).'

	elif allowed_characters and not allowed_roles:
		return f'Only these characters are allowed: ({character_mentions}).'

	roles_description = f'any of these roles: ({role_mentions})' \
		if allowed_roles else 'any role'

	character_description = f'any of these people: ({character_mentions})' \
		if allowed_characters else 'everyone else'

	return f'People with {roles_description} will be allowed,' + \
		f' as well as {character_description}.'

async def discordify(text: str):

	sanitized = ''.join(character.lower() for character in text if
		(character.isalnum() or character.isspace() or character == '-'))
	spaceless = '-'.join(sanitized.split())
	trimmed = spaceless.strip()
	result = '-'.join(part for part in trimmed.split('-') if part)

	return result[:24]

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

async def format_avatar(presented_url: str):

	if not presented_url:
		return 'no_profile_pic.webp', \
			False, \
			"You can set the character's profile pic" + \
			" by uploading a picture URL. It's better for it to be" + \
			" a permanent one like Imgur, but it can be URL, really."

	try:
		response = head(presented_url)
		if response.headers["content-type"] in {"image/png", "image/jpeg", "image/jpg"}:
			return presented_url, True, 'Set!'
		else:
			return 'bad_link.png', \
				False, \
				'**Error,** avatars have to be a still image.' + \
					' PNG, JPEG, or JPG, please.'

	except:
		return 'bad_link.png', False, '**Error,** that URL is broken somehow. Try another one?'

async def omit_segments(sentence: str):

	words = sentence.split()

	heard_word_count = max(len(words) // 6, 2)

	heard_words_indexes = set()
	while heard_word_count > 0:
		insertion_point = randrange(len(words))

		for cluster_index in range(randrange(1, 3)):
			heard_words_indexes.add(insertion_point + cluster_index)
			heard_word_count -= 1

	for word_index in range(len(words)):

		if word_index in heard_words_indexes:
			continue

		word = words[word_index]
		if word == word.upper():
			continue
		else:
			words[word_index] = '...'

	return ' '.join(words)
