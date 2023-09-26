

#Import-ant Libraries
from discord import ApplicationContext, Option, Interaction, Embed
from discord.ext import commands
from discord.commands import SlashCommandGroup
from discord.utils import get

from libraries.classes import GuildData, DialogueView, ChannelMaker, Player
from libraries.universal import mbd, loading, identify_node_channel, \
    no_changes, prevent_spam
from libraries.formatting import discordify, unique_name, format_whitelist, \
    format_nodes, embolden, format_players
from libraries.autocomplete import complete_nodes
from data.listeners import to_direct_listeners, queue_refresh, \
    direct_listeners, broken_webhook_channels


#Classes
class NodeCommands(commands.Cog):
    """
    Commnds specific to nodes and their functions.
    Also includes listener functions that keep the
    bot syncronized with the server.
    """

    node = SlashCommandGroup(
        name = 'node',
        description = 'Manage the nodes of your graph.',
        guild_only = True,
        guild_ids = [1114005940392439899])

    @node.command(name = 'new', description = 'Create a new node.')
    async def new(self, ctx: ApplicationContext, name: Option(str, description = 'What should it be called?', default = 'new-node')):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        submitted_name = await discordify(name)
        name = submitted_name if submitted_name else 'new-node'
        name = await unique_name(name, guild_data.nodes.keys())

        async def refresh_embed():

            nonlocal name
            name = view.name() if view.name() else name
            name = await unique_name(name, guild_data.nodes.keys())

            description = f'Whitelist: {await format_whitelist(view.roles(), view.players())}'

            embed, _ = await mbd(
                f'New node: {name}',
                description,
                'You can also create a whitelist to limit who can visit this node.')
            return embed

        async def submit_node(interaction: Interaction):

            await loading(interaction)

            nonlocal name

            maker = ChannelMaker(interaction.guild, 'nodes')
            await maker.initialize()
            new_channel = await maker.create_channel(name)

            await guild_data.create_node(
                name = name,
                channel_ID = new_channel.id,
                allowed_roles = view.roles(),
                allowed_players = view.players())
            await guild_data.save()

            embed, _ = await mbd(
                f'{new_channel.mention} created!',
                "The permissions you requested are set-- just not in the channel's Discord" + \
                " settings.",
                "No worries, it's all being kept track of by me.")
            await interaction.followup.edit_message(
                message_id = interaction.message.id,
                embed = embed,
                view = None)

            whitelist = await format_whitelist(view.roles(), view.players())
            embed, _ = await mbd(
                'Cool, new node.',
                "Here's who's allowed:" + \
                    f"\n{whitelist}" + \
                    "\n\nDon't forget to connect it to other nodes with `/edge new`.",
                "You can also change the whitelist with /node review.")
            await new_channel.send(embed = embed)
            return

        view = DialogueView(guild = ctx.guild, refresh = refresh_embed)
        await view.add_roles()
        await view.add_players(guild_data.players)
        await view.add_submit(submit_node)
        await view.add_rename('new-node')
        await view.add_cancel()

        embed = await refresh_embed()
        await ctx.respond(embed = embed, view = view)
        return

    @node.command(name = 'delete', description = 'Delete a node.')
    async def delete(self, ctx: ApplicationContext, node: Option(str, description = 'Call this command in a node (or name it) to narrow it down.', autocomplete = complete_nodes, required = False)):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def delete_nodes(deleting_node_names: list):

            deleting_nodes = await guild_data.filter_nodes(deleting_node_names)
            deleting_mentions = await format_nodes(deleting_nodes.values())

            async def confirm_delete(interaction: Interaction):

                await loading(interaction)

                nonlocal deleting_nodes
                deleting_nodes = {name : node for name, node in deleting_nodes.items() if not node.occupants}

                if not deleting_nodes:
                    embed, _ = await mbd(
                        'No nodes to delete.',
                        "You need to specify at least one node that doesn't have anyone inside.",
                        'You can always try the command again.')
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        view = None)
                    return

                #Inform neighbor nodes and occupants that the node is deleted now
                neighbor_node_names = await guild_data.neighbors(deleting_nodes.keys())
                bold_deleting = await embolden(deleting_nodes.keys())
                for name in neighbor_node_names:
                    embed, _ = await mbd(
                        'Misremembered?',
                        f"Could you be imagining {bold_deleting}? Strangely, there's no trace.",
                        "Whatever the case, it's gone now.")
                    await to_direct_listeners(
                        embed,
                        interaction.guild,
                        guild_data.nodes[name].channel_ID,
                        occupants_only = True)

                    embed, _ = await mbd(
                        'Neighbor node(s) deleted.',
                        f'Deleted {bold_deleting}--this node now has fewer neighbors.',
                        "I'm sure it's for the best.")
                    neighbor_node_channel = get(
                        interaction.guild.text_channels,
                        id = guild_data.nodes[name].channel_ID)
                    await neighbor_node_channel.send(embed = embed)

                #Delete nodes and their edges
                for name, node in deleting_nodes.items():

                    for neighbor in list(node.neighbors.keys()):
                        await guild_data.delete_edge(name, neighbor)

                    await guild_data.delete_node(name, ctx.guild.text_channels)

                await guild_data.save()

                if interaction.channel.name not in deleting_nodes:

                    description = f'Successfully deleted the following things about {bold_deleting}:' + \
                        "\n• The node data in the database." + \
                        "\n• The node channels." + \
                        "\n• All edges to and from the node."

                    occupied_nodes_count = len(deleting_node_names) - len(deleting_nodes)
                    if occupied_nodes_count:
                        description += f"\n\nCouldn't delete {occupied_nodes_count}" + \
                                " node(s) that were occupied. Use `/player tp` to" + \
                                " move the player(s) inside."

                    embed, _ = await mbd(
                        'Delete results',
                        description,
                        'Say goodbye.')
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        view = None)
                return

            view = DialogueView(guild = ctx.guild)
            await view.add_confirm(confirm_delete)
            await view.add_cancel()

            embed, _ = await mbd(
                'Confirm deletion?',
                f"Delete {deleting_mentions}?",
                'This will also delete any edges connected to the node(s).')
            await ctx.respond(embed = embed, view = view, ephemeral = True)
            return

        result = await identify_node_channel(guild_data.nodes.keys(), ctx.channel.name, node)
        match result:
            case _ if isinstance(result, Embed):
                await ctx.respond(embed = result)
            case _ if isinstance(result, str):
                await delete_nodes([result])
            case None:
                embed, _ = await mbd(
                    'Delete Node(s)?',
                    "You can delete a node three ways:" + \
                        "\n• Call this command inside of a node channel." + \
                        "\n• Do `/node delete #node-channel`." + \
                        "\n• Select multiple nodes with the list below.",
                    'This will remove the node(s), all its edges, and any corresponding channels.')

                async def submit_nodes(interaction: Interaction):
                    await ctx.delete()
                    await delete_nodes(view.nodes())
                    return

                view = DialogueView(guild = ctx.guild)
                await view.add_nodes(guild_data.nodes.keys(), submit_nodes)
                await view.add_cancel()
                await ctx.respond(embed = embed, view = view)

        return

    @node.command(name = 'review', description = 'Inspect and/or edit one or more nodes.')
    async def review(self, ctx: ApplicationContext, node: Option(str, description = 'Either call this command inside a node or name it here.', autocomplete = complete_nodes, required = False)):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def revise_nodes(node_names: list):

            reviewing_nodes = await guild_data.filter_nodes(node_names)

            title = f'Reviewing {len(reviewing_nodes)} node(s).'
            intro = f"• Selected node(s): {await format_nodes(reviewing_nodes.values())}"

            occupants = await guild_data.get_all_occupants(reviewing_nodes.values())
            final_part = f"\n• Occupants: {await format_players(occupants) if occupants else 'There are no people here.'}"

            neighbors = await guild_data.neighbors(reviewing_nodes.keys())
            if neighbors:
                impacted_nodes = await guild_data.filter_nodes(list(neighbors) + node_names)
                subgraph = await guild_data.to_graph(impacted_nodes)
                graph_view = (await guild_data.to_map(subgraph), 'full')
            else:
                final_part += '\n• Edges: No other nodes are connected to the selected node(s).'
                graph_view = None

            has_whitelist = any(node.allowed_roles or node.allowed_players for node in reviewing_nodes.values())

            async def refresh_embed():

                description = intro
                if view.name():
                    new_name = await unique_name(view.name(), guild_data.nodes.keys())
                    description += f', renaming to **#{new_name}**.'
                description += final_part

                description += await view.format_whitelist(reviewing_nodes.values())

                embed, _ = await mbd(
                    title,
                    description,
                    'You can rename a node if you have only one selected.',
                    graph_view)
                return embed

            async def submit_node(interaction: Interaction):

                await loading(interaction)

                nonlocal reviewing_nodes
                new_name = await unique_name(view.name(), guild_data.nodes.keys())

                if not any([new_name, view.roles(), view.players(), view.clearing]):
                    await no_changes(interaction)
                    return

                description = ''

                if view.clearing:
                    description += '\n• Removed the whitelist(s).'
                    for name, node in reviewing_nodes.items():

                        await guild_data.nodes[name].clear_whitelist()
                        embed, _ = await mbd(
                            'Opening up.',
                            'You somehow feel like this place just easier to get to.',
                            'For better or for worse.')
                        await to_direct_listeners(embed,
                            interaction.guild,
                            node.channel_ID,
                            occupants_only = True)

                if view.roles() or view.players():

                    description += '\n• New whitelist: ' + \
                        await format_whitelist(view.roles(), view.players())

                    embed, _ = await mbd(
                        'Strange.',
                        "There's a sense that this place just changed in some way.",
                        "Only time will tell if you'll be able to return here as easily as you came.")

                    for name, node in reviewing_nodes.items():
                        await to_direct_listeners(embed,
                            interaction.guild,
                            node.channel_ID,
                            occupants_only = True)

                        await guild_data.nodes[name].set_roles(view.roles())
                        await guild_data.nodes[name].set_players(view.players())

                if new_name:

                    old_name = list(reviewing_nodes.keys())[0]
                    node_data = guild_data.nodes.pop(old_name)
                    guild_data.nodes[new_name] = node_data

                    description += f"\n• Renamed **#{old_name}** to {node_data.mention}."


                    #Correct locationName in player data
                    for ID in node_data.occupants:
                        player = Player(ID, interaction.channel.guild.id)
                        player.location = new_name
                        await player.save()

                    #Rename edges
                    for node in guild_data.nodes.values():
                        for neighbor in list(node.neighbors):
                            if neighbor == old_name:
                                node.neighbors[new_name] = node.neighbors.pop(old_name)

                await guild_data.save()

                if new_name: #Gotta save first sorry
                    node_channel = get(interaction.guild.text_channels, id = node_data.channel_ID)
                    await node_channel.edit(name = new_name)

                await queue_refresh(interaction.guild)

                embed, _ = await mbd(
                    'Edited.',
                    description,
                    'Another successful revision.')
                for node in reviewing_nodes.values():
                    node_channel = get(interaction.guild.text_channels, id = node.channel_ID)
                    await node_channel.send(embed = embed)

                return await prevent_spam(
                    (interaction.channel.name in reviewing_nodes or interaction.channel.name == new_name),
                    embed,
                    interaction)

            view = DialogueView(ctx.guild, refresh_embed)
            await view.add_roles()
            await view.add_players(guild_data.players)
            await view.add_submit(submit_node)
            if len(reviewing_nodes) == 1:
                await view.add_rename(node_names[0])
            if has_whitelist:
                await view.add_clear()
            await view.add_cancel()
            embed = await refresh_embed()
            _, file = await mbd(
                image_details = graph_view)

            await ctx.respond(embed = embed, view = view, file = file, ephemeral = True)
            return

        result = await identify_node_channel(guild_data.nodes.keys(), ctx.channel.name, node)
        match result:
            case _ if isinstance(result, Embed):
                await ctx.respond(embed = result)
            case _ if isinstance(result, str):
                await revise_nodes([result])
            case None:

                embed, _ = await mbd(
                    'Review node(s)?',
                    "You can revise a node three ways:" + \
                        "\n• Call this command inside of a node channel." + \
                        "\n• Do `/node review #node-channel`." + \
                        "\n• Select multiple node channels with the list below.",
                    'This will allow you to view the nodes, their edges, and their whitelists.')

                async def submit_nodes(interaction: Interaction):
                    await ctx.delete()
                    await revise_nodes(view.nodes())
                    return

                view = DialogueView()
                nodes = [name for name, node in guild_data.nodes.items() if node.channel_ID != ctx.channel_id]
                await view.add_nodes(nodes, submit_nodes)
                await view.add_cancel()
                await ctx.respond(embed = embed, view = view)

        return

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):

        guild_data = GuildData(channel.guild.id)

        for name, node in guild_data.nodes.items(): #Delete Node, if node

            if channel.id != node.channel_ID:
                continue

            if node.occupants:
                maker = ChannelMaker(channel.guild, 'nodes')
                await maker.initialize()
                remade_channel = await maker.create_channel(name)
                node.channel_ID = remade_channel.id
                await guild_data.save()

                await queue_refresh(channel.guild)

                embed, _ = await mbd(
                    'Not so fast.',
                    "There's still people inside this node:" + \
                        f" {await format_players(node.occupants)}" + \
                        " to be specific. Either delete them as players" + \
                        " with `/player delete` or move them out with " + \
                        " `/player tp`.",
                    'Either way, you can only delete empty nodes.')
                await remade_channel.send(embed = embed)
                return

            #Inform neighbor nodes and occupants that the node is deleted now
            for neighbor_node_name in list(node.neighbors.keys()):
                embed, _ = await mbd(
                    'Misremembered?',
                    f"Could you be imagining **#{name}**? Strangely, there's no trace.",
                    "Whatever the case, it's gone now.")
                await to_direct_listeners(
                    embed,
                    channel.guild,
                    guild_data.nodes[neighbor_node_name].channel_ID,
                    occupants_only = True)

                embed, _ = await mbd(
                    'Neighbor node(s) deleted.',
                    f'Deleted **#{name}**--this node now has fewer neighbors.',
                    "I'm sure it's for the best.")
                neighbor_node_channel = get(
                    channel.guild.text_channels,
                    id = guild_data.nodes[neighbor_node_name].channel_ID,)
                await neighbor_node_channel.send(embed = embed)

                await guild_data.delete_edge(name, neighbor_node_name)

            await guild_data.delete_node(name)
            direct_listeners.pop(node.channel_ID, None)
            await guild_data.save()
            await queue_refresh(channel.guild)
            return

        for ID in guild_data.players: #Delete Player, if player

            player = Player(ID, channel.guild.id)

            if player.channel_ID != channel.id:
                continue

            last_location = guild_data.nodes[player.location]
            await last_location.remove_occupants({ID})
            await player.delete()
            guild_data.players.discard(ID)
            await guild_data.save()

            await queue_refresh(channel.guild)

            player_embed, _ = await mbd(
                'Where did they go?',
                f"You look around, but <@{ID}> seems to have vanished into thin air.",
                "You get the impression you won't be seeing them again.")
            await to_direct_listeners(
                player_embed,
                channel.guild,
                last_location.channel_ID,
                occupants_only = True)

            node_embed, _ = await mbd(
                'Fewer players.',
                f'Removed <@{ID}> from the game (and this node).',
                'You can view all remaining players with /player find.')
            node_channel = get(channel.guild.channels, id = last_location.channel_ID)
            if node_channel:
                await node_channel.send(embed = node_embed)
            return

        await queue_refresh(channel.guild)

        return

    #"Optimized" node listener, needs work, CHATGPT sucks
    @commands.Cog.listener()
    async def on_guild_channel_update(self, old_version, new_version):

        if old_version.name == new_version.name: #Nothing to do
            return

        guild_data = GuildData(old_version.guild.id)

        old_name, node_data = next(
            ((name, node) for name, node in guild_data.nodes.items() \
                if node.channel_ID == old_version.id),
            (None, None))

        if not node_data: #Channel is not a node
            return

        #Check if the new name conflicts with existing nodes
        new_name = await unique_name(new_version.name, guild_data.nodes.keys())

        if new_name != new_version.name:
            await new_version.edit(name = new_name)
            return

        #Update the node name
        guild_data.nodes[new_name] = guild_data.nodes.pop(old_name)

        #Update occupants' location
        for ID in node_data.occupants:
            player = Player(ID, old_version.guild.id)
            player.location = new_name
            await player.save()

        # Update neighbors' references
        for node_data in guild_data.nodes.values():

            node_data.neighbors = {
                new_name if neighbor == old_version.name \
                    else neighbor: edge
                for neighbor, edge in node_data.neighbors.items()}

        await guild_data.save()

        embed, _ = await mbd(
            'Edited.',
            f'Renamed **#{old_version.name}** to {new_version.mention}.',
            'Another successful revision.')
        await new_version.send(embed=embed)
        return


    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):

        if channel in broken_webhook_channels:
            return

        guild_data = GuildData(channel.guild.id)

        if get(guild_data.nodes.values(), channel_ID = channel.id):
            broken_webhook_channels.add(channel)

        else:

            broken_webhook_channels.update(
                {channel for ID in guild_data.players \
                    if (_ := Player(ID, channel.guild.id)).channel_ID == channel.id})

        return

def setup(prox):
    prox.add_cog(NodeCommands(prox), override = True)
