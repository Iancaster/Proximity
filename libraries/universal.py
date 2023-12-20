
#Import-ant Libraries
from discord import Embed, MISSING, File, Interaction, Member
from discord.ui import View
from requests import head
from os import path, getcwd
from io import BytesIO


#"Constants"
NO_AVATAR_URL = 'https://i.imgur.com/A6qTjRc.jpeg'

#Dialogues
async def mbd(title: str = 'No Title', description: str = 'No description.', footer: str = 'No footer.', image_details = None):

	embed = Embed(
		title = title,
		description = description,
		color = 670869)
	embed.set_footer(text = footer)

	file = MISSING

	match image_details:

		case None:
			pass

		case _ if image_details[1] == 'thumb':

			match image_details[0]:

				case _ if isinstance(image_details[0], BytesIO):
					file = File(image_details[0], filename = 'image.png')
					embed.set_thumbnail(url = 'attachment://image.png')

				case _ if 'http' in image_details[0]:

					try:
						response = head(image_details[0])
						if response.headers["content-type"] in {"image/png", "image/jpeg", "image/jpg"}:
							embed.set_thumbnail(url = image_details[0])
					except:
						pass

				case _ if path.isfile(path.join(getcwd(), 'assets', image_details[0])):
					file = File(path.join(getcwd(), 'assets', image_details[0]), filename = 'image.png')
					embed.set_thumbnail(url = 'attachment://image.png')

		case _ if image_details[1] == 'full':
			file = File(image_details[0], filename = 'image.png')
			embed.set_image(url = 'attachment://image.png')

	return embed, file

async def loading(interaction: Interaction):

	embed, _ = await mbd(
		'Loading...',
		'Recalculating listeners.',
		'Usually takes less than five seconds.')
	await interaction.response.edit_message(
		embed = embed,
		view = None,
		attachments = [])
	return

async def moving(interaction: Interaction):

	embed, _ = await mbd(
		'Moving...',
		'Getting into position.',
		'Usually takes less than five seconds.')
	await interaction.response.edit_message(
		embed = embed,
		view = None,
		attachments = [])
	return

async def send_message(send_method: callable, embed: Embed, view: View = MISSING, file = MISSING, **options):
	message = await send_method(embed = embed, view = view, file = file, **options)
	view.message = message
	return


#Guild
async def identify_place_channel(place_names: dict, origin_channel_name: str = '', presented_channel_name: str = ''):

	if not place_names:

		embed, _ = await mbd(
			'Easy, bronco.',
			"You've got no places to work with.",
			'Make some first with /new place.')

		return embed

	elif presented_channel_name:

		if presented_channel_name in place_names:
			return presented_channel_name

		else:

			embed, _ = await mbd(
				'What?',
				f"**#{presented_channel_name}** isn't a place channel. Did" + \
					" you select the wrong one?",
				'Try calling the command again.')

			return embed

	if origin_channel_name in place_names:
		return origin_channel_name

	else:
		return None

async def identify_character_channel(characters: dict, origin_channel_id: int = 0, presented_character_name: str = '', presented_character_id: int = 0):

	if not characters: #No characters

		embed, _ = await mbd(
			'Easy, bronco.',
			"You've got no characters yet.",
			'Make a /new place so you can add a /new character.')

		return embed

	elif presented_character_id: #Character given (channel)

		if presented_character_id in characters:
			return {presented_character_id : characters[presented_character_id]}

		embed, _ = await mbd(
			'What?',
			f"<#{presented_character_id}> isn't a character channel. Did" + \
				" you select the wrong one?",
			'Try calling the command again.')

		return embed

	elif presented_character_name: #Character given (text)

		if presented_character_name in characters:

			return next({ID : name for ID, name in characters.items() if \
				name == presented_character_name}, None)

		embed, _ = await mbd(
			'What?',
			f"*{presented_character_name}* isn't a character. Did" + \
				" you select the wrong one?",
			'Try calling the command again.')

		return embed

	elif origin_channel_id in characters: #Character channel
		return {origin_channel_id : characters[origin_channel_id]}

	return None



#Checks
async def no_changes(interaction: Interaction):

	embed, _ = await mbd(
		'Success?',
		"You didn't make any changes.",
		"Unsure what the point of that was.")
	await interaction.followup.edit_message(
		message_id = interaction.message.id,
		embed = embed,
		view = None,
		attachments = [])
	return

async def no_redundancies(test, embed: Embed, interaction: Interaction, file = MISSING):

	if test:
		await interaction.delete_original_response()

	else:
		await interaction.followup.edit_message(
			message_id = interaction.message.id,
			embed = embed,
			file = file,
			view = None)

	return

async def no_places_selected(interaction: Interaction, singular: bool = False):

	embed, _ = await mbd(
		'No places selected!',
		'Please select a valid place first.' if singular else \
			"You've got to select some.",
		'Try calling the command again.')
	await interaction.followup.edit_message(
		message_id = interaction.message.id,
		embed = embed,
		view = None,
		attachments = [])
	return

async def no_paths_selected(interaction: Interaction):
	embed, _ = await mbd(
		'No paths!',
		"You've got to select at least one.",
		'Try calling the command again.')
	await interaction.followup.edit_message(
		message_id = interaction.message.id,
		embed = embed,
		view = None,
		attachments = [])
	return

async def no_people_selected(interaction: Interaction):

	embed, _ = await mbd(
		'Who?',
		"You didn't select any valid people.",
		'You can call the command again and specify someone new.')
	await interaction.followup.edit_message(
		message_id = interaction.message.id,
		embed = embed,
		view = None)
	return

# async def no_membership(ctx: ApplicationContext):
#
# 	embed, _ = await mbd(
# 		'Easy there.',
# 		"You're not a player in this server, so you're not able to do this.",
# 		'You can ask the server owner to make you a player?')
# 	await send_message(ctx.respond, embed)
# 	return
