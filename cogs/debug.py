

#Import-ant Libraries
from discord import ApplicationContext, Option, \
    SlashCommandGroup, Embed
from discord.ext import commands

from libraries.classes import RPServer
from libraries.user_interface import send_message, image_embed, ImageSource

#Classes
class DebugCommands(commands.Cog):
    """
    Commands that only Lancaster can use.
    Maybe in the future I'll enforce that.
    """


    debug_group = SlashCommandGroup(
        name = "debug",
        description = "For testers only! Lets you peer behind the veil.",
        guild_ids = [1111152704279035954])

    # @debug_group.command(name = 'listeners', description = 'See what channels proxy their messages to which others.')
    # async def listeners(self, ctx: ApplicationContext, listener_type: Option(str, description = 'Direct or indirect listeners?', name = 'type', choices = ['direct','indirect'], default = 'direct')):

    #     GD = GuildData(ctx.guild.id, load_places = True, load_characters = True)

    #     channels_to_check = {place.channel_ID : name for name, place in GD.places.items()}
    #     channels_to_check.update(GD.characters)

    #     if not channels_to_check:

    #         description = f'There are no {listener_type} listeners, which means no' + \
    #             ' messages will be relayed through this avenue.'

    #         if listener_type == 'direct':
    #             description += ' Direct communication occurs between a character' + \
    #                 ' and those nearby, as well as back and forth with the location.' + \
    #                 ' It also encompasses eavesdropping on others.'
    #         else:
    #             description += ' Indirect communication encompasses overhearing other' + \
    #                 'characters nearby, without actually eavesdropping on them.'

    #         embed, _ = await mbd(
    #             f"{listener_type.capitalize()} Listeners",
    #              description,
    #             'Listeners will appear as characters are made.')
    #         from discord import MISSING
    #         await send_message(ctx.respond, embed = embed, file = MISSING, ephemeral = True)
    #         return

    #     graph = DiGraph()
    #     silent_channels = set()
    #     listener_dict = direct_listeners if listener_type == 'direct' else indirect_listeners

    #     for channel_ID, name in channels_to_check.items():

    #         listeners = listener_dict.get(channel_ID, None)
    #         if not listeners:
    #             silent_channels.add(name)
    #             continue

    #         for listener_channel, _ in listeners:
    #             graph.add_edge(name, channels_to_check.get(listener_channel.id, 'Missing channel!'))


    #     if graph:
    #         listener_view = (await GD.to_map(graph), 'full')
    #     else:
    #         listener_view = None

    #     description = 'This is a full map of all the listeners in the server.' + \
    #         ' Messages go towards -> the places the arrows point.'

    #     if silent_channels:
    #         description += f'\n\nSkipped putting {await embolden(silent_channels)}' + \
    #             ' on the map because they have no channels listening to them.'

    #     embed, file = await mbd(
    #         f"{listener_type.capitalize()} Listeners",
    #         description,
    #         'Note: character channels should always show on the Direct Listeners map.',
    #         listener_view)

    #     await send_message(ctx.respond, embed = embed, file = file, ephemeral = True)
    #     return

    @debug_group.command(name = "server", description = "See what server info is saved in the database.")
    async def server(self, ctx: ApplicationContext):

        server = RPServer(ctx.guild_id)

        if await server.exists:

            await server.fetch()
            description = \
                (f"Server name: **{server.name}**" + 
                f"\nServer description: {server.description}")
            
            if server.reference is None:
                footer = "If this server had a reference photo, you could view it here."
                thumbnail = True
                source = ImageSource.ASSET
                asset_str = "logo.png"
            
            else:
                footer = "Server's reference photo seen above." 
                thumbnail = False
                source = ImageSource.URL
                asset_str = server.reference       

        else:
            description = \
                ("This server is not in the database." + 
                " You can use this dialogue to view information on" \
                " servers registered as Proximity Roleplays.")  
            footer = "Check back after this server gets registered!"
            thumbnail = True
            source = ImageSource.ASSET
            asset_str = "logo.png"                         

        embed, file = await image_embed(
            title = "Server debug.",
            description = description,
            footer = footer,
            thumbnail = thumbnail,
            source = source,
            asset_str =  asset_str)

        await send_message(ctx.interaction, embed, file = file, ephemeral = True)
        return

def setup(prox):
    prox.add_cog(DebugCommands(prox), override = True)

