
#Import-ant Libraries
from discord import Embed, MISSING, File, Interaction
from requests import head


#Dialogues
async def mbd(
    title: str = 'No Title',
    description: str = 'No description.',
    footer: str = 'No footer.',
    image_details = None):

    embed = Embed(
        title = title,
        description = description,
        color = 670869)
    embed.set_footer(text = footer)

    match image_details:
        
        case None:
            file = MISSING

        case _ if image_details[0] == None:
            file = MISSING

        case _ if image_details[1] == 'thumb':

            file = File('/./assets/badLink.png', filename = 'image.png')
            embed.set_thumbnail(url = 'attachment://image.png')

            try:
                response = head(image_details[0])
                if response.headers["content-type"] in {"image/png", "image/jpeg", "image/jpg"}:
                    embed.set_thumbnail(url = image_details[0])
                    file = MISSING
                else:
                    pass
            except:
                pass
        
        case _ if image_details[1] == 'full':
            file = File(image_details[0], filename = 'image.png')
            embed.set_image(url = 'attachment://image.png')
            
        case _:
            print('Unrecognized image viewing mode in dialogue!')
            file = MISSING

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

#Guild
async def identify_node_channel(
    node_names: dict,
    origin_channel_name: str = '',
    presented_channel_name: str = ''):

    if not node_names:

        embed, _ = await mbd(
            'Easy, bronco.',
            "You've got no nodes to work with.",
            'Make some first with /node new.')

        return embed

    elif presented_channel_name:

        if presented_channel_name in node_names:
            return presented_channel_name

        else:

            embed, _ = await mbd(
                'What?',
                f"**#{presented_channel_name}** isn't a node channel. Did" + \
                    " you select the wrong one?",
                'Try calling the command again.')

            return embed

    if origin_channel_name in node_names:
        return origin_channel_name

    else:
        return None

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

async def prevent_spam(test, embed: Embed, interaction: Interaction):

    if test:
        await interaction.delete_original_response()

    else:
        await interaction.followup.edit_message(
            message_id = interaction.message.id,
            embed = embed,
            view = None)

    return
