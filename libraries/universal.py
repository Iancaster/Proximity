
#Import-ant Libraries
from discord import Embed, File, Interaction, TextChannel, MISSING

from aiohttp import ClientSession, ClientTimeout
from typing import Callable
from io import BytesIO
from enum import IntEnum
from pathlib import Path

from libraries.formatting import *

#"Constants"
NO_AVATAR_URL = "https://i.imgur.com/A6qTjRc.jpeg"
ASSETS_DIR = Path().cwd() / "assets"
VALID_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"]

class ImageSource(IntEnum):
    ASSET = 0
    URL = 1
    BYTES = 2

def text_embed(
    title: str = "No Title", 
    description: str = "No description.", 
    footer: str = "No footer.",
    ) -> Embed:

    embed = Embed(
        title = title,
        description = description,
        color = 670869)
    embed.set_footer(text = footer)

    return embed

async def _validate_url(url: str) -> bool:
    # forgive me
    try:
        async with ClientSession() as session:
            async with session.head(url, timeout=ClientTimeout(5)) as response:
                content_type = response.headers.get("content-type", "") 
                return content_type in VALID_IMAGE_TYPES
            
    except Exception:
        return False

async def image_embed(
    title: str = "No Title", 
    description: str = "No description.", 
    footer: str = "No footer.",
    thumbnail: bool = True,
    source: ImageSource = ImageSource.ASSET,
    asset_str: str = "avatar.png",
    asset_bytes: BytesIO | None = None,
    ) -> tuple[Embed, File | None]:

    embed = text_embed(title, description, footer)
    file = None
    place_image = embed.set_thumbnail if thumbnail else embed.set_image

    if source == ImageSource.URL:

        if not await _validate_url(asset_str):
            asset_str = NO_AVATAR_URL

        file = None
        place_image(url = asset_str)                # pyright: ignore[reportCallIssue]

    elif source == ImageSource.BYTES:

        if asset_bytes is None:
            raise ValueError("Forgot to pass in a byte image.")
        
        file = File(asset_bytes, filename = "image.png")
        place_image(url = "attachment://image.png")  # pyright: ignore[reportCallIssue]
        
    else:
        asset_path = ASSETS_DIR / asset_str

        if not asset_path.exists():
            asset_str = "bad_link.png"
        else:
            asset_str = str(asset_path)

        file = File(asset_str, filename = "image.png")
        place_image(url = "attachment://image.png")  # pyright: ignore[reportCallIssue]

    return embed, file

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

async def send_message(
    send_method: Callable, 
    embed: Embed, 
    view = None, 
    file: File | None = None, 
    **options):
    
    if file is not None: 
        options["file"] = file

    if view is None:
        await send_method(embed = embed, **options)
        return
    
    message = await send_method(embed = embed, view = view, **options)
    view.message = message        
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


# Guild
async def identify_place_channel(**args):
    return

async def identify_character_channel(
        characters: dict, 
        origin_channel_id: int = 0, 
        presented_character_name: str = '', 
        presented_character_id: int = 0):

    if not characters:  # No characters

        embed = text_embed(
            'Easy, bronco.',
            "You've got no characters yet.",
            'Make a /new place so you can add a /new character.')

        return embed

    elif presented_character_id:  # Character given (channel)

        if presented_character_id in characters:
            return {presented_character_id : characters[presented_character_id]}

        embed = text_embed(
            'What?',
            f"<#{presented_character_id}> isn't a character channel. Did" + \
                " you select the wrong one?",
            'Try calling the command again.')

        return embed

    elif presented_character_name:  # Character given (text)

        if presented_character_name in characters:

            return {ID : name for ID, name in characters.items() if \
                name == presented_character_name}.items()

        embed = text_embed(
            'What?',
            f"*{presented_character_name}* isn't a character. Did" + \
                " you select the wrong one?",
            'Try calling the command again.')

        return embed

    elif origin_channel_id in characters:  # Character channel
        return {origin_channel_id : characters[origin_channel_id]}

    return None

# Checks
async def no_redundancies(test, embed: Embed, interaction: Interaction, file: File = MISSING):

    if test:
        await interaction.delete_original_response()

    elif interaction.message is None:
        pass

    else:
        await interaction.followup.edit_message(
            message_id = interaction.message.id,
            embed = embed,
            file = file,
            view = None)

    return

