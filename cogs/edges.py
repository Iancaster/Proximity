

#Import-ant Libraries
from discord import ApplicationContext, Option, Interaction, Embed
from discord.ext import commands
from discord.commands import SlashCommandGroup
from discord.utils import get

from libraries.classes import GuildData, DialogueView, Edge
from libraries.universal import mbd, loading, identify_node_channel, \
    no_nodes_selected, no_edges_selected, no_changes, no_redundancies
from libraries.formatting import format_whitelist, format_colors, \
    format_nodes, embolden
from libraries.autocomplete import complete_nodes
from data.listeners import queue_refresh, to_direct_listeners

#Classes
class EdgeCommands(commands.Cog):

    edge = SlashCommandGroup(
        name = 'edge',
        description = 'Manage edges between nodes.',
        guild_only = True)

    @edge.command(name = 'new', description = 'Connect nodes.')
    async def new(self, ctx: ApplicationContext, origin: Option(str, description = 'Either call this command inside a node or name it here.', autocomplete = complete_nodes, required = False)):
        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def create_edges(origin_node_name: str):

            origin_node = guild_data.nodes[origin_node_name]
            origin_node_name = origin_node_name

            async def refresh_embed():

                description = f'• Origin: {origin_node.mention}'

                if view.nodes():
                    destinations = await guild_data.filter_nodes(view.nodes())
                    destination_mentions = await format_nodes(destinations.values())
                    description += f'\n• Destination(s): {destination_mentions}.'
                else:
                    description += "\n• Destination(s): None yet! Choose some nodes to connect to this one."

                description += f"\n• Whitelist: {await format_whitelist(view.roles(), view.players())}"

                match view.directionality:
                    case 0:
                        description += "\n• Directionality: **One-way** (<-) from" + \
                            f" the destination(s) to {origin_node.mention}."
                    case 1:
                        description += "\n• Directionality: **Two-way** (<->), people will be able to travel" + \
                            f" back and forth between {origin_node.mention} and the destination(s)."
                    case 2:
                        description += "\n• Directionality: **One-way** (->) to" + \
                            f" {origin_node.mention} to the destination(s)."

                if view.overwriting:
                    description += "\n• **Overwriting** edges. Old edges will be erased where new one are laid."
                else:
                    description += "\n• Will not overwrite edges. Click below to toggle."

                embed, _ = await mbd(
                    'New edge(s)',
                    description,
                    'Which nodes are we hooking up?')
                return embed

            async def submit_edges(interaction: Interaction):

                await loading(interaction)

                nonlocal origin_node_name

                if not view.nodes():
                    await no_nodes_selected(interaction)
                    return

                #Make edges
                edge = Edge(
                    directionality = view.directionality,
                    allowed_roles = view.roles(),
                    allowed_players = view.players())
                existing_edges = 0
                new_neighbors = set()
                for destination in view.nodes():

                    if await guild_data.set_edge(
                        origin_node_name,
                        destination,
                        edge,
                        view.overwriting):

                        existing_edges += 1

                        if not view.overwriting:
                            continue

                    new_neighbors.add(destination)

                if len(new_neighbors) == 0:
                    embed, _ = await mbd(
                        'No new neighbors?',
                        "I couldn't make any new edges--there's already an edge" + \
                            " present for all the nodes you want to connect.",
                        'Enable overwriting to make the edges you want regardless.')
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        view = None)
                    return

                await guild_data.save()
                neighbors_dict = await guild_data.filter_nodes(new_neighbors)
                await queue_refresh(interaction.guild)

                #Inform neighbors occupants and neighbor nodes
                player_embed, _ = await mbd(
                    'Hm?',
                    f"You notice a way to get between this place and **#{origin_node_name}**. Has that always been there?",
                    'And if so, has it always been like that?')
                node_embed, _ = await mbd(
                    'Edge created.',
                    f'Created an edge between here and {origin_node.mention}.',
                    'You can view its details with /node review.')
                for node in neighbors_dict.values():
                    await to_direct_listeners(
                        player_embed,
                        interaction.guild,
                        node.channel_ID,
                        occupants_only = True)
                    node_channel = get(interaction.guild.text_channels, id = node.channel_ID)
                    await node_channel.send(embed = node_embed)

                #Inform edited node occupants
                bold_neighbors = await embolden(new_neighbors)
                player_embed, _ = await mbd(
                    'Hm?',
                    f"You notice that this place is connected to {bold_neighbors}. Something about that seems new.",
                    "Perhaps you're only imagining it.")
                await to_direct_listeners(
                    player_embed,
                    interaction.guild,
                    origin_node.channel_ID,
                    occupants_only = True)

                #Inform own node
                description = f'\n• Connected {origin_node.mention}'
                match view.directionality:
                    case 0:
                        description += ' from <- '
                    case 1:
                        description += ' <-> back and forth to '
                    case 2:
                        description += ' to -> '
                destination_mentions = await format_nodes(neighbors_dict.values())
                description += f'{destination_mentions}.'

                if view.roles() or view.players():
                    description += f'\n• Imposed the whitelist: {await format_whitelist(view.roles(), view.players())}'

                if existing_edges:
                    if view.overwriting:
                        description += f'\n• Overwrote {existing_edges} edge(s).'
                    else:
                        description += f"\n• Skipped {existing_edges} edge(s) because" + \
                            " the nodes were already connected. Enable overwriting to ignore."

                #Produce map of new edges
                neighbors_dict[origin_node_name] = origin_node
                subgraph = await guild_data.to_graph(neighbors_dict)
                graph_view = await guild_data.to_map(subgraph)
                embed, file = await mbd(
                    'New edge results.',
                    description,
                    'You can view all the nodes and edges with /server view.',
                    (graph_view, 'full'))
                node_channel = get(interaction.guild.text_channels, id = origin_node.channel_ID)
                await node_channel.send(embed = embed, file = file)

                return await no_redundancies(
                    (interaction.channel.name not in new_neighbors \
                    and interaction.channel.name != origin_node_name),
                    embed,
                    interaction)

            view = DialogueView(ctx.guild, refresh_embed)
            nodes = {name for name, node in guild_data.nodes.items() if node != origin_node}
            await view.add_nodes(nodes)
            await view.add_roles()
            await view.add_players(guild_data.players)
            await view.add_submit(submit_edges)
            await view.add_directionality()
            await view.add_overwrite()
            await view.add_cancel()
            embed = await refresh_embed()
            await ctx.respond(embed = embed, view = view, ephemeral = True)
            return

        result = await identify_node_channel(guild_data.nodes.keys(), ctx.channel.name, origin)
        match result:
            case _ if isinstance(result, Embed):
                await ctx.respond(embed = result)
            case _ if isinstance(result, str):
                await create_edges(result)
            case None:

                embed, _ = await mbd(
                    'Connect nodes?',
                    "You can create a new edge three ways:" + \
                        "\n• Call this command inside of a node channel." + \
                        "\n• Do `/edge new #node-channel`." + \
                        "\n• Select a node channel with the list below.",
                    "This is just to select the origin, you'll select the destinations next.")

                async def submit_nodes(interaction: Interaction):
                    await ctx.delete()
                    await create_edges(view.nodes()[0])
                    return

                view = DialogueView(ctx.guild)
                await view.add_nodes(guild_data.nodes, submit_nodes, select_multiple = False)
                await view.add_cancel()
                await ctx.respond(embed = embed, view = view)

        return

    @edge.command(name = 'delete', description = 'Remove the connections of a given node.')
    async def delete(self, ctx: ApplicationContext, origin: Option(str, description = 'Either call this command inside a node or name it here.', autocomplete = complete_nodes, required = False)):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def delete_edges(origin_node_name: str):

            origin_node= guild_data.nodes[origin_node_name]

            neighbors = origin_node.neighbors
            if not neighbors:
                embed, _ = await mbd(
                    'No edges.',
                    f'{origin_node.mention} has no edges to view.',
                    'So I suppose that answers your inquiry.')
                await ctx.respond(embed = embed, ephemeral = True)
                return

            impacted_nodes = await guild_data.filter_nodes(list(neighbors.keys()) + [origin_node_name])
            graph = await guild_data.to_graph(impacted_nodes)
            description = f'{origin_node.mention} has these connections'

            async def refresh_embed():

                full_description = description

                if not view.edges():
                    full_description += ':'
                else:
                    selected_neighbors = {name : neighbors[name] for name in view.edges()}
                    full_description += ", but you'll be deleting the following:" + \
                        await guild_data.format_edges(selected_neighbors)


                edge_colors = await format_colors(graph, origin_node_name, view.edges(), 'red')
                graph_image = await guild_data.to_map(graph, edge_colors)

                embed, file = await mbd(
                    'Delete edge(s)?',
                    full_description,
                    'This cannot be reversed.',
                    (graph_image, 'full'))

                return embed, file

            async def refresh_message(interaction: Interaction):
                embed, file = await refresh_embed()
                await interaction.response.edit_message(embed = embed, file = file)
                return

            async def confirm_delete(interaction: Interaction):

                await loading(interaction)

                for neighbor in view.edges():
                    await guild_data.delete_edge(origin_node_name, neighbor)

                await guild_data.save()

                await queue_refresh(interaction.guild)

                deleted_neighbors = await guild_data.filter_nodes(view.edges())

                #Inform neighbors occupants and neighbor nodes
                player_embed, _ = await mbd(
                    'Hm?',
                    f"The path between here and **#{origin_node_name}** just closed.",
                    'Just like that...')
                node_embed, _ = await mbd(
                    'Edge deleted.',
                    f'Removed an edge between here and {origin_node.mention}.',
                    'You can view the remaining edges with /node review.')
                for node in deleted_neighbors.values():
                    await to_direct_listeners(
                        player_embed,
                        interaction.guild,
                        node.channel_ID,
                        occupants_only = True)
                    node_channel = get(interaction.guild.text_channels, id = node.channel_ID)
                    await node_channel.send(embed = node_embed)

                #Inform edited node occupants
                bold_deleted = await embolden(view.edges())
                player_embed, _ = await mbd(
                    'Hm?',
                    f"This place just lost access to {bold_deleted}.",
                    "Will that path ever be restored?")
                await to_direct_listeners(
                    player_embed,
                    interaction.guild,
                    origin_node.channel_ID,
                    occupants_only = True)

                #Inform own node
                deleted_mentions = await format_nodes(deleted_neighbors.values())
                embed, _ = await mbd(
                    'Edges deleted.',
                    f'Removed the edge(s) to {deleted_mentions}.',
                    'You can always make some new ones with /edge new.')
                node_channel = get(interaction.guild.text_channels, name = origin_node_name)
                await node_channel.send(embed = embed)

                if interaction.channel.name == origin_node_name:
                    await interaction.followup.delete_message(message_id = interaction.message.id)
                else:
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        attachments = [],
                        view = None)
                return

            view = DialogueView()
            await view.add_edges(neighbors, callback = refresh_message)
            await view.add_confirm(confirm_delete)
            await view.add_cancel()
            embed, file = await refresh_embed()

            await ctx.respond(
                embed = embed,
                file = file,
                view = view,
                ephemeral = True)
            return

        result = await identify_node_channel(guild_data.nodes, ctx.channel.name, origin)
        match result:
            case _ if isinstance(result, Embed):
                await ctx.respond(embed = result)
            case _ if isinstance(result, str):
                await delete_edges(result)
            case None:

                embed, _ = await mbd(
                    'Delete edges?',
                    "You can delete edges three ways:" + \
                        "\n• Call this command inside of a node channel." + \
                        "\n• Do `/edge delete #node-channel`." + \
                        "\n• Select a node channel with the list below.",
                    "This is just to select the origin, you'll see the edges next.")

                async def submit_nodes(interaction: Interaction):
                    await ctx.delete()
                    await delete_edges(view.nodes())
                    return

                view = DialogueView()
                await view.add_nodes(guild_data.nodes.keys(), submit_nodes, select_multiple = False)
                await view.add_cancel()
                await ctx.respond(embed = embed, view = view)

        return

    @edge.command(name = 'review', description = 'Choose who is allowed in an edge.')
    async def review(self, ctx: ApplicationContext, origin: Option(str, description = 'Either call this command inside a node or name it here.', autocomplete = complete_nodes, required = False)):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def review_permissions(origin_node_name: str):

            origin_node = guild_data.nodes[origin_node_name]

            if not origin_node.neighbors:
                embed, _ = await mbd(
                    'No edges.',
                    f'{origin_node.mention} has no edges to modify.',
                    "You can make some with /edge new.")
                await ctx.respond(embed = embed, ephemeral = True)
                return

            description = f'• Selected node: {origin_node.mention}'

            impacted_nodes = await guild_data.filter_nodes([origin_node_name] + list(origin_node.neighbors.keys()))
            subgraph = await guild_data.to_graph(impacted_nodes)

            whitelist_exists = any(edge.allowed_roles or edge.allowed_players for edge in origin_node.neighbors.values())

            async def refresh_embed():

                full_description = description

                if view.edges():
                    full_description += '\n• Selected Edges: See below.'
                    revising_edges = [origin_node.neighbors[name] for name in view.edges()]
                    full_description += await view.format_whitelist(revising_edges)

                else:
                    full_description += '\n• Selected Edges: None yet. Use the dropdown below to pick one or more.'

                edge_colors = await format_colors(subgraph, origin_node_name, view.edges(), 'blue')
                graph_image = await guild_data.to_map(subgraph, edge_colors)

                embed, file = await mbd(
                    'Change whitelists?',
                    full_description,
                    'This can always be reversed.',
                    (graph_image, 'full'))

                return embed, file

            async def refresh_message(interaction: Interaction):
                embed, file = await refresh_embed()
                await interaction.response.edit_message(
                    embed = embed,
                    file = file)
                return

            async def confirm_edges(interaction: Interaction):

                await interaction.response.defer()

                #Screen for invalid submissions
                if not view.edges():
                    await no_edges_selected(interaction)
                    return

                if not any([view.roles(), view.players(), view.clearing]):
                    await no_changes(interaction)
                    return

                if view.clearing:
                    description = '\n• Removed the whitelist(s).'
                    for neighbor_name in view.edges():
                        await origin_node.neighbors[neighbor_name].clear_whitelist()
                        await guild_data.nodes[neighbor_name].neighbors[origin_node_name].clear_whitelist()

                else:
                    revising_edges = [origin_node.neighbors[name] for name in view.edges()][0]
                    description = await view.format_whitelist(revising_edges)

                    for neighbor_name in view.edges():
                        origin_node.neighbors[neighbor_name].allowed_roles = view.roles()
                        guild_data.nodes[neighbor_name].neighbors[origin_node_name].allowed_players = view.players()

                await guild_data.save()

                #Inform neighbors occupants and neighbor nodes
                neighbor_nodes = await guild_data.filter_nodes(view.edges())
                neighbor_mentions = await format_nodes(neighbor_nodes.values())
                player_embed, _ = await mbd(
                    'Hm?',
                    f"You feel like the way to **#{origin_node_name}** changed somehow.",
                    'Will it be easier to travel through, or harder?')
                node_embed, _ = await mbd(
                    f'Edge with {origin_node.mention} changed.',
                    description,
                    'You can view its details with /edge allow.')
                for node in neighbor_nodes.values():
                    await to_direct_listeners(
                        player_embed,
                        interaction.guild,
                        node.channel_ID,
                        occupants_only = True)
                    node_channel = get(interaction.guild.text_channels, id = node.channel_ID)
                    await node_channel.send(embed = node_embed)

                #Inform edited node occupants
                player_embed, _ = await mbd(
                    'Hm?',
                    "You notice that there's been a change in the way this" + \
                        f" place is connected to {neighbor_mentions}.",
                    "Perhaps you're only imagining it.")
                await to_direct_listeners(
                    player_embed,
                    interaction.guild,
                    origin_node.channel_ID,
                    occupants_only = True)

                #Inform own node
                embed, _ = await mbd(
                    f'Edge(s) with {neighbor_mentions} changed.',
                    description,
                    'You can always undo these changes.')
                node_channel = get(interaction.guild.text_channels, id = origin_node.channel_ID)
                await node_channel.send(embed = embed)

                if interaction.channel.name in view.edges() or interaction.channel.id == origin_node.channel_ID:
                    await interaction.delete_original_response()
                else:
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        view = None)
                return

            view = DialogueView(ctx.guild)
            await view.add_edges(origin_node.neighbors, callback = refresh_message)
            await view.add_roles(callback = refresh_message)
            await view.add_players(guild_data.players, callback = refresh_message)
            await view.add_submit(confirm_edges)
            if whitelist_exists:
                await view.add_clear(refresh_message)
            await view.add_cancel()

            embed, file = await refresh_embed()
            await ctx.respond(
                embed = embed,
                file = file,
                view = view,
                ephemeral = True)
            return

        result = await identify_node_channel(guild_data.nodes, ctx.channel.name, origin)
        match result:
            case _ if isinstance(result, Embed):
                await ctx.respond(embed = result)
            case _ if isinstance(result, str):
                await review_permissions(result)
            case None:

                embed, _ = await mbd(
                    'Review edges?',
                    "You can review edge whitelists three ways:\n\
                    • Call this command inside of a node channel.\n\
                    • Do `/edge allow #node-channel`.\n\
                    • Select a node with the list below.",
                    "This is just to select the origin, you'll see the edges next.")

                async def submit_nodes(interaction: Interaction):
                    await ctx.delete()
                    await review_permissions(view.nodes())
                    return

                view = DialogueView()
                await view.add_nodes(guild_data.nodes.keys(), submit_nodes, select_multiple = False)
                await view.add_cancel()
                await ctx.respond(embed = embed, view = view)

        return

def setup(prox):
    prox.add_cog(EdgeCommands(prox), override = True)
