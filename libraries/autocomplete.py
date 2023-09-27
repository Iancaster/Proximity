

#Import-ant Libraries
from discord import AutocompleteContext
from libraries.classes import GuildData, Player


#Functions
async def complete_nodes(ctx: AutocompleteContext):

    guild_data = GuildData(ctx.interaction.guild_id)

    if not guild_data.nodes:
        return ['No nodes!']

    return guild_data.nodes

async def complete_map(ctx: AutocompleteContext):

    player = Player(ctx.interaction.user.id, ctx.interaction.guild_id)

    if not player.location:
        return ["Only players can use this command."]

    guild_data = GuildData(ctx.interaction.guild_id)

    guild_map = await guild_data.accessible_locations(
        [ID for ID in ctx.interaction.user.roles],
        ctx.interaction.user.id,
        player.location)

    return guild_map.nodes
