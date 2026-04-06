
#Import-ant Libraries
from discord import Embed, File, Interaction, TextChannel, MISSING

from typing import Callable


from libraries.formatting import *


async def loading(interaction: Interaction):

    embed = text_embed(
        'Loading...',
        'Recalculating listeners.',
        'Usually takes less than five seconds.')
    await interaction.response.edit_message(
        embed = embed,
        view = None,
        attachments = [])
    return

async def moving(interaction: Interaction):

    embed = text_embed(
        'Moving...',
        'Getting into position.',
        'Usually takes less than five seconds.')
    await interaction.response.edit_message(
        embed = embed,
        view = None,
        attachments = [])
    return

async def character_change(channel: TextChannel, char_data):

    webhook = (await channel.webhooks())[0]
    character_message = "Good news! Your character details" + \
        " just got updated. This is how you'll appear" + \
        " to other characters."

    if char_data.roles:
        character_message += " Also, you have the role(s)" + \
            f' of {await format_roles({char_data.roles})}.'
    else:
        character_message += " You don't have any roles."

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

# # Guild
# async def identify_place_channel(**args):
#     return

# async def identify_character_channel(
#         characters: dict, 
#         origin_channel_id: int = 0, 
#         presented_character_name: str = '', 
#         presented_character_id: int = 0):

#     if not characters:  # No characters

#         embed = text_embed(
#             'Easy, bronco.',
#             "You've got no characters yet.",
#             'Make a /new place so you can add a /new character.')

#         return embed

#     elif presented_character_id:  # Character given (channel)

#         if presented_character_id in characters:
#             return {presented_character_id : characters[presented_character_id]}

#         embed = text_embed(
#             'What?',
#             f"<#{presented_character_id}> isn't a character channel. Did" + \
#                 " you select the wrong one?",
#             'Try calling the command again.')

#         return embed

#     elif presented_character_name:  # Character given (text)

#         if presented_character_name in characters:

#             return {ID : name for ID, name in characters.items() if \
#                 name == presented_character_name}.items()

#         embed = text_embed(
#             'What?',
#             f"*{presented_character_name}* isn't a character. Did" + \
#                 " you select the wrong one?",
#             'Try calling the command again.')

#         return embed

#     elif origin_channel_id in characters:  # Character channel
#         return {origin_channel_id : characters[origin_channel_id]}

#     return None

# # Checks
# async def no_redundancies(test, embed: Embed, interaction: Interaction, file: File = MISSING):

#     if test:
#         await interaction.delete_original_response()

#     elif interaction.message is None:
#         pass

#     else:
#         await interaction.followup.edit_message(
#             message_id = interaction.message.id,
#             embed = embed,
#             file = file,
#             view = None)

#     return

