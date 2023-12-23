

# Import-ant Libraries
from discord import Guild
from discord.utils import get_or_fetch, get

from libraries.classes import GuildData, ChannelMaker
from libraries.formatting import unique_name, format_words, \
	format_whitelist
from libraries.universal import mbd

# Functions
async def make_location(guild: Guild):

	guild_data = GuildData(guild.id, load_places = True)

	original_place_count = len(guild_data.places)

	maker = ChannelMaker(guild, 'places')
	await maker.initialize()
	new_channel = await maker.create_channel('Test Channel')

	name = await unique_name('test-channel', guild_data.places)
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

async def delete_test_channel(guild: Guild):

	guild_data = GuildData(guild.id, load_places = True)
	place = guild_data.places['test-channel']

	place_channel = await get_or_fetch(guild, 'channel', place.channel_ID, default = None)
	if place_channel:
		await place_channel.delete()

	if not guild_data.places:
		category = get(guild.categories, name = 'places')
		if category:
			await category.delete()

	return


async def tests(tests_checklist: dict, test_guild: Guild, only_severe: bool = False):

	print(f'Running {len(tests_checklist)} tests.')

	for category, tests in tests_checklist.items():

		print(f'{category}:')
		category_results = []

		for test_count, test_name in enumerate(tests):

			results = None
			severity = 'Severe'

			match test_name:

				case 'New Location':

					flaws = await make_location(test_guild)
					description = 'Creates a location with a blank whitelist named "test-channel"'
					if flaws:
						results = f'The {await format_words(flaws)}.'

				case 'Delete Test Channel':

					await delete_test_channel(test_guild)

					description = 'Deletes one test channel'
					severity = 'Utility'

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

			print(f'  {test_count + 1}. \033[1;33;40m {result[0]}' + \
				f'\033[1;37;40m: {result[1]}.' + \
				'\n    Result: ', end = '')
			if result[2]:
				print('\033[1;31;40m Failure. \033[1;37;40m')
				print(f'\n    - Impact: {result[3]}' + \
					f'\n    - Details: {result[2]}')
			else:
				print('\033[1;32m Success! \033[0;37;40m')

	return
