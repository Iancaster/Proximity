

# Import-ant Libraries
from discord import Guild
from discord.utils import get_or_fetch, get

from libraries.classes import GuildData, ChannelMaker, Path
from libraries.formatting import unique_name, format_words, \
	format_whitelist
from libraries.universal import mbd

# Functions
async def create_location(guild: Guild, location_name: str = 'test-location'):

	guild_data = GuildData(guild.id, load_places = True)

	original_place_count = len(guild_data.places)

	name = await unique_name(location_name, guild_data.places)

	maker = ChannelMaker(guild, 'places')
	await maker.initialize()
	new_channel = await maker.create_channel(name)

	await guild_data.create_place(
		name = name,
		channel_ID = new_channel.id,
		role_IDs = set(),
		char_IDs = set())
	#guild_data.roles |= view.roles()
	await guild_data.save()

	whitelist = await format_whitelist(set(), set())
	embed, _ = await mbd(
		'Cool, new place.',
		f"{whitelist} If you want to change that, you can use `/review place`.",
		"Don't forget to connect this place to other places with /new path.")
	await new_channel.send(embed = embed)

	verify_channel = await get_or_fetch(guild, 'channel', new_channel.id, default = None)

	if not verify_channel:
		return ['channel was not made']

	flaws = []

	if verify_channel.name != 'test-channel':
		flaws.append('name was incorrectly set')

	if verify_channel.category == None:
		flaws.append('channel was not placed into a category')
	elif verify_channel.category.name != 'places':
		flaws.append('channel was not placed into the correct category')

	guild_data = GuildData(guild.id, load_places = True)
	verify_location = guild_data.places.get('test', None)

	if not verify_location:
		return flaws.append('data was not written')

	if len(guild_data.places) <= original_place_count:
		flaws.append('place overwrote existing location')

	return flaws

async def delete_location_channel(guild: Guild, location_name: str):

	guild_data = GuildData(guild.id, load_places = True)
	place = guild_data.places.get(location_name, None)

	flaws = []

	if not place:
		flaws.append('place did not exist in the guild_data')
		return flaws


	place_channel = await get_or_fetch(guild, 'channel', place.channel_ID, default = None)
	if place_channel:
		await place_channel.delete()
	else:
		flaws.append('could not locate the location channel to delete')

	if len(guild_data.places) == 1:
		category = get(guild.categories, name = 'places')
		if category:
			await category.delete()

	return flaws

async def create_path(guild: Guild, path_data: tuple[str, str]):

	path = Path(
		directionality = 1,
		allowed_roles = set(),
		allowed_characters = set())

	guild_data = GuildData(guild.id, load_places = True)

	await guild_data.set_path(
		path_data[0],
		path_data[1],
		path,
		False)

	await guild_data.save()

	return

async def tests(tests_checklist: dict, test_guild: Guild, only_severe: bool = False):

	total_tests = sum(len(tests) for test_category, tests in tests_checklist.items())
	print(f'Running {total_tests} tests.')

	for category, tests in tests_checklist.items():

		print(f'{category}:')
		category_results = []

		for test_count, test_data in enumerate(tests):

			test_name, test_additional = test_data

			results = None
			severity = 'Severe'

			match test_name:

				case 'Create Location':

					flaws = await create_location(test_guild, test_additional)
					description = f'Creates a location with a blank whitelist named "{test_additional}"'
					if flaws:
						results = f'The {await format_words(flaws)}.'

				case 'Delete Location':

					# await delete_location_channel(test_guild, test_additional)

					# description = f'Deletes one location named {test_additional}'
					# severity = 'Utility'

					flaws = await delete_location_channel(test_guild, test_additional)
					description = f'Deletes the location named {test_additional}'
					if flaws:
						results = f'The {await format_words(flaws)}.'
					else:
						severity = 'Utility'

				case 'Create Path':

					flaws = await create_path(test_guild, test_additional)
					description = f'Creates a new path between {test_additional[0]} and {test_additional[1]}'
					if flaws:
						results = f'The {await format_words(flaws)}.'

				case _:

					print(f'Unrecognized test name: {test_name}')
					continue

			category_results.append((
						test_name,
						description,
						results,
						severity))

		if only_severe:
				category_results = [data for data in category_results if data[2] == 'severe']

		for test_count, result in enumerate(category_results):

			print(f'\n  {test_count + 1}. \033[1;33;40m {result[0]}' + \
				f'\033[1;37;40m: {result[1]}.' + \
				'\n    Result: ', end = '')
			if result[2]:
				print('\033[1;31;40m Failure. \033[1;37;40m')
				print(f'    - Impact: {result[3]}' + \
					f'\n    - Details: {result[2]}')
			else:
				print('\033[1;32m Success! \033[0;37;40m')

	return
