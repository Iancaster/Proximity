

#Import-ant Libraries
from discord import ApplicationContext, Option, Interaction, Embed
from discord.ext import commands
from discord.commands import SlashCommandGroup
from discord.utils import get

from libraries.classes import GuildData, DialogueView, Edge
from libraries.universal import mbd, loading, identify_node_channel, \
    no_nodes_selected
from libraries.formatting import format_whitelist, \
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

            origin_node= guild_data.nodes[origin_node_name]
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
                    origin.channel_ID,
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
                neighbors_dict[origin_node_name] = origin
                subgraph = await guild_data.to_graph(neighbors_dict)
                graph_view = await guild_data.toMap(subgraph)
                embed, file = await mbd(
                    'New edge results.',
                    description,
                    'You can view all the nodes and edges with /server view.',
                    (graph_view, 'full'))
                node_channel = get(interaction.guild.text_channels, id = origin.channel_ID)
                await node_channel.send(embed = embed, file = file)

                if interaction.channel.name not in new_neighbors \
                    and interaction.channel.name != origin_node_name:
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed)
                return

            view = DialogueView(ctx.guild, refresh_embed)
            nodes = {name for name, node in guild_data.nodes.items() if node != origin}
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
                await view.add_nodes(guild_data.nodes, submit_nodes, manyNodes = False)
                await view.add_cancel()
                await ctx.respond(embed = embed, view = view)

        return

    # @edge.command(
    #     name = 'delete',
    #     description = 'Remove the connections of a given node.')
    # async def delete(
    #     self,
    #     ctx: ApplicationContext,
    #     origin: Option(
    #         str,
    #         'Either call this command inside a node or name it here.',
    #         autocomplete = complete_nodes,
    #         required = False)):
    #
    #     await ctx.defer(ephemeral = True)
    #
    #     guild_data = GuildData(ctx.guild_id)
    #
    #     async def deleteEdges(origin_node_name: str):
    #
    #         origin_node= guild_data.nodes[origin_node_name]
    #
    #         neighbors = origin.neighbors
    #         if not neighbors:
    #             embed, _ = await mbd(
    #                 'No edges.',
    #                 f'{origin_node.mention} has no edges to view.',
    #                 'So I suppose that answers your inquiry.')
    #             await ctx.respond(embed = embed, ephemeral = True)
    #             return
    #
    #         localNodes = await guild_data.filter_nodes(list(neighbors.keys()) + [origin_node_name])
    #         graph = await guild_data.to_graph(localNodes)
    #         description = f'{origin_node.mention} has these connections'
    #
    #         async def refresh_embed():
    #
    #             fullDescription = description
    #
    #             if not view.edges():
    #                 fullDescription += ':'
    #             else:
    #                 selectedNeighbors = {name : neighbors[name] for name in view.edges()}
    #                 fullDescription += ", but you'll be deleting the following:" + \
    #                     await guild_data.formatEdges(selectedNeighbors)
    #
    #
    #             edgeColors = await format_colors(graph, origin_node_name, view.edges(), 'red')
    #             graphImage = await guild_data.toMap(graph, edgeColors)
    #
    #             embed, file = await mbd(
    #                 'Delete edge(s)?',
    #                 fullDescription,
    #                 'This cannot be reversed.',
    #                 (graphImage, 'full'))
    #
    #             return embed, file
    #
    #         async def refreshMessage(interaction: Interaction):
    #             embed, file = await refresh_embed()
    #             await interaction.response.edit_message(embed = embed, file = file)
    #             return
    #
    #         async def confirmDelete(interaction: Interaction):
    #
    #             await loading(interaction)
    #
    #             for neighbor in view.edges():
    #                 await guild_data.deleteEdge(origin_node_name, neighbor)
    #
    #             await guild_data.save()
    #
    #             await queue_refresh(interaction.guild)
    #
    #             deletedNeighbors = await guild_data.filter_nodes(view.edges())
    #
    #             #Inform neighbors occupants and neighbor nodes
    #             player_embed, _ = await mbd(
    #                 'Hm?',
    #                 f"The path between here and **#{origin_node_name}** just closed.",
    #                 'Just like that...')
    #             node_embed, _ = await mbd(
    #                 'Edge deleted.',
    #                 f'Removed an edge between here and {origin_node.mention}.',
    #                 'You can view the remaining edges with /node review.')
    #             for node in deletedNeighbors.values():
    #                 await to_direct_listeners(
    #                     player_embed,
    #                     interaction.guild,
    #                     node.channel_ID,
    #                     occupants_only = True)
    #                 node_channel = get(interaction.guild.text_channels, id = node.channel_ID)
    #                 await node_channel.send(embed = node_embed)
    #
    #             #Inform edited node occupants
    #             boldDeleted = await embolden(view.edges())
    #             player_embed, _ = await mbd(
    #                 'Hm?',
    #                 f"This place just lost access to {boldDeleted}.",
    #                 "Will that path ever be restored?")
    #             await to_direct_listeners(
    #                 player_embed,
    #                 interaction.guild,
    #                 origin.channel_ID,
    #                 occupants_only = True)
    #
    #             #Inform own node
    #             deletedMentions = await format_nodes(deletedNeighbors.values())
    #             embed, _ = await mbd(
    #                 'Edges deleted.',
    #                 f'Removed the edge(s) to {deletedMentions}.',
    #                 'You can always make some new ones with /edge new.')
    #             node_channel = get(interaction.guild.text_channels, name = origin_node_name)
    #             await node_channel.send(embed = embed)
    #
    #             if interaction.channel.name == origin_node_name:
    #                 await interaction.followup.delete_message(message_id = interaction.message.id)
    #             else:
    #                 await interaction.followup.edit_message(
    #                     message_id = interaction.message.id,
    #                     embed = embed,
    #                     attachments = [],
    #                     view = None)
    #             return
    #
    #         view = DialogueView()
    #         await view.addEdges(neighbors, callback = refreshMessage)
    #         await view.addEvilConfirm(confirmDelete)
    #         await view.add_cancel()
    #         embed, file = await refresh_embed()
    #
    #         await ctx.respond(
    #             embed = embed,
    #             file = file,
    #             view = view,
    #             ephemeral = True)
    #         return
    #
    #     result = await identify_node_channel(guild_data.nodes, ctx.channel.name, origin)
    #     match result:
    #         case _ if isinstance(result, Embed):
    #             await ctx.respond(embed = result)
    #         case _ if isinstance(result, str):
    #             await deleteEdges(result)
    #         case None:
    #
    #             embed, _ = await mbd(
    #                 'Delete edges?',
    #                 "You can delete edges three ways:" + \
    #                     "\n• Call this command inside of a node channel." + \
    #                     "\n• Do `/edge delete #node-channel`." + \
    #                     "\n• Select a node channel with the list below.",
    #                 "This is just to select the origin, you'll see the edges next.")
    #
    #             async def submit_nodes(interaction: Interaction):
    #                 await ctx.delete()
    #                 await deleteEdges(view.nodes())
    #                 return
    #
    #             view = DialogueView()
    #             await view.add_nodes(guild_data.nodes.keys(), submit_nodes, manyNodes = False)
    #             await view.add_cancel()
    #             await ctx.respond(embed = embed, view = view)
    #
    #     return
    #
    # @edge.command(
    #     name = 'allow',
    #     description = 'Choose who is allowed in an edge.')
    # async def allow(
    #     self,
    #     ctx: ApplicationContext,
    #     origin: Option(
    #         str,
    #         'Either call this command inside a node or name it here.',
    #         autocomplete = complete_nodes,
    #         required = False)):
    #
    #     await ctx.defer(ephemeral = True)
    #
    #     guild_data = GuildData(ctx.guild_id)
    #
    #     async def revisePermissions(origin_node_name: str):
    #
    #         origin_node= guild_data.nodes[origin_node_name]
    #
    #         if not origin.neighbors:
    #             embed, _ = await mbd(
    #                 'No edges.',
    #                 f'{origin_node.mention} has no edges to modify.',
    #                 "So...that's that.")
    #             await ctx.respond(embed = embed, ephemeral = True)
    #             return
    #
    #         description = f'• Selected node: {origin_node.mention}'
    #
    #         localNodes = await guild_data.filter_nodes([origin_node_name] + list(origin.neighbors.keys()))
    #         subgraph = await guild_data.to_graph(localNodes)
    #
    #         hasWhitelist = any(edge.allowed_roles or edge.allowed_players for edge in origin.neighbors.values())
    #
    #         async def refresh_embed():
    #
    #             fullDescription = description
    #
    #             if view.edges():
    #                 fullDescription += f"\n• Selected Edges: See below."
    #                 revisingEdges = [origin.neighbors[name] for name in view.edges()]
    #                 fullDescription += await view.whitelist(revisingEdges)
    #
    #             else:
    #                 fullDescription += '\n• Selected Edges: None yet. Use the dropdown below to pick one or more.'
    #
    #             edgeColors = await format_colors(subgraph, origin_node_name, view.edges(), 'blue')
    #             graphImage = await guild_data.toMap(subgraph, edgeColors)
    #
    #             embed, file = await mbd(
    #                 'Change whitelists?',
    #                 fullDescription,
    #                 'This can always be reversed.',
    #                 (graphImage, 'full'))
    #
    #             return embed, file
    #
    #         async def refreshMessage(interaction: Interaction):
    #             embed, file = await refresh_embed()
    #             await interaction.response.edit_message(
    #                 embed = embed,
    #                 file = file)
    #             return
    #
    #         async def confirmEdges(interaction: Interaction):
    #
    #             await interaction.response.defer()
    #
    #             #Screen for invalid submissions
    #             if not view.edges():
    #                 await fn.noEdges(interaction)
    #                 return
    #
    #             if not any([view.roles(), view.players(), view.clearing]):
    #                 await fn.no_changes(interaction)
    #                 return
    #
    #             if view.clearing:
    #                 description = '\n• Removed the whitelist(s).'
    #                 for neighborName in view.edges():
    #                     await origin.neighbors[neighborName].clearWhitelist()
    #                     await guild_data.nodes[neighborName].neighbors[origin_node_name].clearWhitelist()
    #
    #             else:
    #                 description = ''
    #
    #                 if view.roles():
    #                     description += '\n• Edited the whitelist(s).'
    #
    #                 for neighborName in view.edges():
    #                     origin.neighbors[neighborName].allowed_roles = view.roles()
    #                     guild_data.nodes[neighborName].neighbors[origin_node_name].allowed_players = view.players()
    #
    #             await guild_data.save()
    #
    #             #Inform neighbors occupants and neighbor nodes
    #             neighborNodes = await guild_data.filter_nodes(view.edges())
    #             neighborMentions = await format_nodes(neighborNodes.values())
    #             player_embed, _ = await mbd(
    #                 'Hm?',
    #                 f"You feel like the way to **#{origin_node_name}** changed somehow.",
    #                 'Will it be easier to travel through, or harder?')
    #             node_embed, _ = await mbd(
    #                 f'Edge with {origin_node.mention} changed.',
    #                 description,
    #                 'You can view its details with /edge allow.')
    #             for node in neighborNodes.values():
    #                 await to_direct_listeners(
    #                     player_embed,
    #                     interaction.guild,
    #                     node.channel_ID,
    #                     occupants_only = True)
    #                 node_channel = get(interaction.guild.text_channels, id = node.channel_ID)
    #                 await node_channel.send(embed = node_embed)
    #
    #             #Inform edited node occupants
    #             player_embed, _ = await mbd(
    #                 'Hm?',
    #                 "You notice that there's been a change in the way this" + \
    #                     f" place is connected to {neighborMentions}.",
    #                 "Perhaps you're only imagining it.")
    #             await to_direct_listeners(
    #                 player_embed,
    #                 interaction.guild,
    #                 origin.channel_ID,
    #                 occupants_only = True)
    #
    #             #Inform own node
    #             embed, _ = await mbd(
    #                 f'Edge(s) with {neighborMentions} changed.',
    #                 description,
    #                 'You can always undo these changes.')
    #             node_channel = get(interaction.guild.text_channels, id = origin.channel_ID)
    #             await node_channel.send(embed = embed)
    #
    #             if interaction.channel.name in view.edges() or interaction.channel.id == origin.channel_ID:
    #                 await interaction.delete_original_response()
    #             else:
    #                 await interaction.followup.edit_message(
    #                     message_id = interaction.message.id,
    #                     embed = embed,
    #                     view = None)
    #             return
    #
    #         view = DialogueView(ctx.guild)
    #         await view.addEdges(origin.neighbors, False, callback = refreshMessage)
    #         await view.add_roles(callback = refreshMessage)
    #         await view.add_players(guild_data.players, callback = refreshMessage)
    #         await view.add_submit(confirmEdges)
    #         if hasWhitelist:
    #             await view.addClear(refreshMessage)
    #         await view.add_cancel()
    #
    #         embed, file = await refresh_embed()
    #         await ctx.respond(
    #             embed = embed,
    #             file = file,
    #             view = view,
    #             ephemeral = True)
    #         return
    #
    #     result = await identify_node_channel(guild_data.nodes, ctx.channel.name, origin)
    #     match result:
    #         case _ if isinstance(result, Embed):
    #             await ctx.respond(embed = result)
    #         case _ if isinstance(result, str):
    #             await revisePermissions(result)
    #         case None:
    #
    #             embed, _ = await mbd(
    #                 'Change allowances?',
    #                 "You can review edge whitelists three ways:\n\
    #                 • Call this command inside of a node channel.\n\
    #                 • Do `/edge allow #node-channel`.\n\
    #                 • Select a node channel with the list below.",
    #                 "This is just to select the origin, you'll see the edges next.")
    #
    #             async def submit_nodes(interaction: Interaction):
    #                 await ctx.delete()
    #                 await revisePermissions(view.nodes())
    #                 return
    #
    #             view = DialogueView()
    #             await view.add_nodes(guild_data.nodes.keys(), submit_nodes, manyNodes = False)
    #             await view.add_cancel()
    #             await ctx.respond(embed = embed, view = view)
    #
    #     return

def setup(prox):
    prox.add_cog(EdgeCommands(prox), override = True)
