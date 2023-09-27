
#Import-ant Libraries
from discord import Embed, MISSING, File, Interaction, Member, \
    ApplicationContext
from requests import head
from os import path, getcwd


#Dialogues
async def mbd(title: str = 'No Title', description: str = 'No description.', footer: str = 'No footer.', image_details = None):

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

            bad_link = path.join(getcwd(), 'assets', 'bad_link.png')


            file = File(bad_link, filename = 'image.png')
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

#Guild
async def identify_node_channel(node_names: dict, origin_channel_name: str = '', presented_channel_name: str = ''):

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

async def identify_player_id(player: Member, player_IDs: set, origin_channel_id: int = 0, guild_ID: int = 0):

    if not player_IDs:

        embed, _ = await mbd(
            'Easy, bronco.',
            "You've got no players to work with.",
            'Add some first with /player new.')

        return embed

    if player:

        if player.id in player_IDs:
            return player.id

        else:

            embed, _ = await mbd(
                'Who?',
                f"{player.mention} isn't a player.",
                'Maybe that was a typo.')

            return embed

    from libraries.classes import Player

    for ID in player_IDs:

        player = Player(ID, guild_ID)

        if origin_channel_id == player.channel_ID:

            return player.id

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

async def no_redundancies(test, embed: Embed, interaction: Interaction):

    if test:
        await interaction.delete_original_response()

    else:
        await interaction.followup.edit_message(
            message_id = interaction.message.id,
            embed = embed,
            view = None)

    return

async def no_nodes_selected(interaction: Interaction, singular: bool = False):

    embed, _ = await mbd(
        'No nodes selected!',
        'Please select a valid node first.' if singular else \
            "You've got to select some.",
        'Try calling the command again.')
    await interaction.followup.edit_message(
        message_id = interaction.message.id,
        embed = embed,
        view = None,
        attachments = [])
    return

async def no_edges_selected(interaction: Interaction):
    embed, _ = await mbd(
        'No edges!',
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

async def no_membership(ctx: ApplicationContext):

    embed, _ = await mbd(
        'Easy there.',
        "You're not a player in this server, so you're not able to do this.",
        'You can ask the server owner to make you a player?')
    await ctx.respond(embed = embed)
    return
