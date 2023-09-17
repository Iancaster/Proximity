

#Import-ant Libraries
from discord import AutocompleteContext
from libraries.classes import GuildData


#Functions
async def complete_nodes(self, ctx: AutocompleteContext):

    guild_data = GuildData(ctx.interaction.guild_id)

    if not guild_data.nodes:
        return ['No nodes!']

    return guild_data.nodes
