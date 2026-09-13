

#Import-ant Libraries
from discord import ApplicationContext, Option, \
    SlashCommandGroup, Embed, ButtonStyle, Interaction
from discord.ext import commands

from libraries.classes import Roleplay, Location
from data.database_entries import roleplay_repo, location_repo
from data.database_handler import CommitResult
from libraries.user_interface import ImageSource, LOGO, \
    send_message, image_embed, text_embed, Dialogue
from libraries.embed_templates import ErrorEmbeds

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

    @debug_group.command(name = "test", description = "Test out some logic.")
    async def test(self, ctx: ApplicationContext):


        rp = await Roleplay.load(ctx.guild_id)
        assert rp is not None

        await send_message(ctx.interaction, content = "boop", ephemeral = True)  

        graph = await rp.graph      
        print(graph.nodes[1547486058722361434])
        return

    @debug_group.command(name = "server", description = "See what server info is saved in the database.")
    async def server(self, ctx: ApplicationContext):

        rp = await Roleplay.load(ctx.guild.id)
        if rp is not None:

            description = \
                (f"Server name: **{rp.data.name}**" + 
                f"\nServer description: {rp.data.description}")
            
            if rp.data.reference is None:
                footer = "If this server had a reference photo, you could view it here."
                thumbnail = True
                asset_str = "logo.png"
            
            else:
                footer = "Server's reference photo seen above." 
                thumbnail = False
                asset_str = rp.data.reference       

        else:
            description = \
                ("This server is not in the database." 
                " You can use this dialogue to view information on" 
                " servers registered as Proximity Roleplays via"
                " `/create roleplay`.")  
            footer = "Check back after this server gets registered!"
            thumbnail = True
            asset_str = LOGO                         

        embed, file = await image_embed(
            title = "Server debug.",
            description = description,
            footer = footer,
            thumbnail = thumbnail,
            source = ImageSource.URL,
            asset_str =  asset_str)

        return await send_message(ctx.interaction, embed, file = file, ephemeral = True)

def setup(prox):
    prox.add_cog(DebugCommands(prox), override = True)

