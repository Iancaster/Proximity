
#Import-ant Libraries
from discord import Embed, File, Interaction, TextChannel

from requests import head
from os import path, getcwd
from io import BytesIO

from libraries.formatting import *

#"Constants"
NO_AVATAR_URL = 'https://i.imgur.com/A6qTjRc.jpeg'

#Dialogues
async def mbd(title: str = 'No Title', description: str = 'No description.', footer: str = 'No footer.', image_details = None):

	embed = Embed(
		title = title,
		description = description,
		color = 670869)
	embed.set_footer(text = footer)

	file = None

	match image_details:

		case _ if image_details is None:
			pass

		case _ if image_details[0] is None:
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

async def send_message(send_method: callable, embed: Embed, view = None, file = None, **options):

	if view:
		message = await send_method(embed = embed, view = view, file = file, **options)
		view.message = message
	else:
		await send_method(embed = embed, file = file, **options)
	return

async def character_change(channel: TextChannel, char_data):

	webhook = (await channel.webhooks())[0]
	character_message = "Good news! Your character details" + \
		" just got updated. This is how you'll appear" + \
		" to other characters. Also, you have the role(s)" + \
		f' of {await format_roles(char_data.roles)}.'
	if char_data.avatar:
		await webhook.send(
			character_message,
			username = char_data.name,
			avatar_url = char_data.avatar)
	else:
		await webhook.send(
			character_message,
			username = char_data.name,
			avatar_url = NO_AVATAR_URL)

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

	if not characters:  # No characters

		embed, _ = await mbd(
			'Easy, bronco.',
			"You've got no characters yet.",
			'Make a /new place so you can add a /new character.')

		return embed

	elif presented_character_id:  # Character given (channel)

		if presented_character_id in characters:
			return {presented_character_id : characters[presented_character_id]}

		embed, _ = await mbd(
			'What?',
			f"<#{presented_character_id}> isn't a character channel. Did" + \
				" you select the wrong one?",
			'Try calling the command again.')

		return embed

	elif presented_character_name:  # Character given (text)

		if presented_character_name in characters:

			return next({ID : name for ID, name in characters.items() if \
				name == presented_character_name}, None)

		embed, _ = await mbd(
			'What?',
			f"*{presented_character_name}* isn't a character. Did" + \
				" you select the wrong one?",
			'Try calling the command again.')

		return embed

	elif origin_channel_id in characters:  # Character channel
		return {origin_channel_id : characters[origin_channel_id]}

	return None

#Checks
async def no_redundancies(test, embed: Embed, interaction: Interaction, file = None):

	if test:
		await interaction.delete_original_response()

	else:
		await interaction.followup.edit_message(
			message_id = interaction.message.id,
			embed = embed,
			file = file,
			view = None)

	return

