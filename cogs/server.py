

#Import-ant Libraries
from discord import ApplicationContext, Embed, Interaction, Option
from discord.ext import commands
from discord.commands import SlashCommandGroup

from libraries.classes import GuildData, Player, DialogueView, \
    ChannelMaker, Edge
from libraries.formatting import format_whitelist, format_players
from libraries.universal import mbd, loading, identify_node_channel
from libraries.autocomplete import complete_nodes

#Classes
class ServerCommands(commands.Cog):
    """
    Commands related to managing
    broad aspects of a server, like
    clearing all data for example.
    """

    server = SlashCommandGroup(
        name = 'server',
        description = 'Manage the server as a whole.',
        guild_only = True,
        guild_ids = [1114005940392439899])

    @server.command(name = 'debug', description = 'View debug info for the server.')
    async def debug(self, ctx: ApplicationContext):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        embed = Embed(
            title = 'Debug details',
            description = '(Mostly) complete look into what the databases hold.',
            color = 670869)

        embed.set_footer(text = 'Peer behind the veil.')

        description = ''
        description += f"\n• Guild ID: {ctx.guild_id}"
        description += "\n• Nodes: "
        for index, node in enumerate(guild_data.nodes.values()):
            description += f"\n{index}. {node.mention}"
            if node.allowed_roles or node.allowed_players:
                description += "\n-- Whitelist:" + \
                    f" {await format_whitelist(node.allowed_roles, node.allowed_players)}"
            if node.occupants:
                occupant_mentions = await format_players(node.occupants)
                description += f'\n-- Occupants: {occupant_mentions}'
            for neighbor in node.neighbors.keys():
                description += f'\n-- Neighbors: **#{neighbor}**'


        embed.add_field(
            name = 'Server Data: guilds.guilds.db',
            value = description[:1500],
            inline = False)

        players_description = f'\n• Players: {await format_players(guild_data.players)}'

        embed.add_field(
            name = 'Player List: guilds.members.db',
            value = players_description,
            inline = False)

        player = Player(ctx.author.id, ctx.guild_id)

        self_description = f'• Your User ID: {player.id}'
        self_description += f"\n• Server **{ctx.guild.name}**:"
        self_description += f"\n- Channel: {player.channel_ID}"
        self_description += f"\n- Location: {player.location}"
        self_description += f"\n- Eavesdropping: {player.eavesdropping}"

        embed.add_field(
            name = 'Your Data: players.db',
            value = self_description,
            inline = False)

        await ctx.respond(embed = embed)
        return

    @server.command(name = 'clear', description = 'Delete all server data.')
    async def clear(self, ctx: ApplicationContext):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        # import helpers.databaseInitialization as db
        # db.create_guild_db()

        if not (guild_data.nodes or guild_data.players):

            embed, _ = await mbd(
                'No data to delete!',
                'Data is only made when you edit the graph or player count.',
                'Wish granted?')
            await ctx.respond(embed = embed)
            return

        async def delete_data(interaction: Interaction):

            await loading(interaction)

            await guild_data.clear(ctx.guild)

            embed, _ = await mbd(
                'See you.',
                "The following has been deleted: \n• All guild data.\n• All nodes and their channels." + \
                    "\n• All location messages.\n• All edges.\n• All player info and their channels.",
                'You can always make them again if you change your mind.')

            try:
                await interaction.followup.edit_message(
                    message_id = interaction.message.id,
                    embed = embed,
                    view = None)
            except:
                pass

            return

        view = DialogueView()
        await view.add_confirm(delete_data)
        await view.add_cancel()
        embed, _ = await mbd(
            'Delete all data?',
            f"You're about to delete {len(guild_data.nodes)} nodes" + \
                f" and {await guild_data.count_edges()} edges, alongside" + \
                f" player data for {len(guild_data.players)} people.",
            'This will also delete associated channels from the server.')

        await ctx.respond(embed = embed, view = view)
        return

    @server.command(name = 'view', description = 'View the entire graph or just a portion.')
    async def view(self, ctx: ApplicationContext, node: Option(str, description = 'Specify a node to highlight?', autocomplete = complete_nodes, required = False)):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def view_ego_graph(guild_data: dict, center_node_name: str = None):

            #Nothing provided
            if not center_node_name:
                server_map = await guild_data.to_map()
                embed, file = await mbd(
                    'Complete graph',
                    'Here is a view of every node and edge.',
                    'To view only a single node and its neighbors, use /server view #node.',
                    (server_map, 'full'))

                await ctx.respond(embed = embed, file = file, ephemeral = True)
                return

            #If something provided
            center_node = guild_data.nodes[center_node_name]
            included = list(center_node.neighbors.keys()) + [center_node_name]
            graph = await guild_data.to_graph(included)
            server_map = await guild_data.to_map(graph)

            embed, file = await mbd(
                f"{center_node.mention}'s neighbors",
                "Here is the node, plus any neighbors.",
                'To view every node and edge, call /server view, without the #node.',
                (server_map, 'full'))

            await ctx.respond(embed = embed, file = file, ephemeral = True)
            return

        result = await identify_node_channel(guild_data.nodes.keys(), node)
        match result:
            case _ if isinstance(result, Embed):
                await ctx.respond(embed = result)
            case _ if isinstance(result, str):
                await view_ego_graph(guild_data, result)
            case None:
                await view_ego_graph(guild_data)

        return

    @server.command(name = 'quick', description = 'Create a quick example graph.')
    async def quick(self, ctx: ApplicationContext):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        both_ways = Edge(
            directionality = 1,
            allowed_roles = set(),
            allowed_players = set())

        node_data = {
            'the-kitchen' : {
                'the-dining-room' : both_ways},
            'the-dining-room' : {
                'the-kitchen' : both_ways,
                'the-living-room' : both_ways},
            'the-living-room' : {
                'the-dining-room' : both_ways,
                'the-bedroom' : both_ways},
            'the-bedroom' : {
                'the-living-room' : both_ways}}

        maker = ChannelMaker(ctx.guild, 'nodes')
        await maker.initialize()
        for node_name, node_edges in node_data.items():

            if node_name in guild_data.nodes:
                await guild_data.delete_node(node_name, ctx.guild.text_channels)

            node_channel = await maker.create_channel(node_name)
            await guild_data.create_node(node_name, node_channel.id)

            embed, _ = await mbd(
                'Cool, example node.',
                'This node was just made to demonstrate what' + \
                    " a server's graph might look like, but apart" + \
                    " from this message, it's exactly the same.",
                "So you can still change the whitelist with /node review.")
            await node_channel.send(embed = embed)



        for node_name, node_edges in node_data.items():

            for neighbor_name, edge_data in node_edges.items():

                await guild_data.set_edge(node_name, neighbor_name, edge_data)

        await guild_data.save()

        embed, _ = await mbd(
            'Done.',
            "Made an example graph composed of a household layout. If there were any" + \
                " nodes/edges that were already present from a previous `/server quick` call," + \
                " they've been overwritten.",
            'Your other data is untouched.')

        await ctx.respond(embed = embed)
        return

    # @server.command(
    #     name = 'settings',
    #     description = 'Review server options.')
    # async def settings(
    #     self,
    #     ctx: ApplicationContext):
    #
    #     await ctx.defer(ephemeral = True)
    #
    #     guild_data = GuildData(ctx.guild_id)
    #
    #     if not (guild_data.nodes or guild_data.players):
    #
    #         embed, _ = await mbd(
    #             'No settings.',
    #             'You can edit settings once you make some nodes or add some players.',
    #             'You know where to find me once that happens.')
    #         await ctx.respond(embed = embed)
    #         return
    #
    #     async def delete_data(interaction: Interaction):
    #
    #         await loading(interaction)
    #
    #         global directListeners, indirectListeners
    #
    #         directListeners, indirectListeners = await guild_data.clear(
    #             ctx.guild,
    #             directListeners,
    #             indirectListeners)
    #
    #         embed, _ = await mbd(
    #             'See you.',
    #             "The following has been deleted: \n• All guild data.\n• All nodes and their channel_IDs." + \
    #                 "\n• All location messages.\n• All edges.\n• All player info and their channel_IDs.",
    #             'You can always make them again if you change your mind.')
    #
    #         try:
    #             await interaction.followup.edit_message(
    #                 message_id = interaction.message.id,
    #                 embed = embed,
    #                 view = None)
    #         except:
    #             pass
    #
    #         return
    #
    #     view = DialogueView()
    #     await view.add_confirm(delete_data)
    #     await view.add_cancel()
    #     embed, _ = await mbd(
    #         'Delete all data?',
    #         f"You're about to delete {len(guild_data.nodes)} nodes" + \
    #             f" and {await guild_data.count_edges()} edges, alongside" + \
    #             f" player data for {len(guild_data.players)} people.",
    #         'This will also delete associated channel_IDs from the server.')
    #
    #     await ctx.respond(embed = embed, view = view)
    #     return
    #

    # @server.command(
    #     name = 'fix',
    #     description = 'Fix certain issues with the server.')
    # async def fix(
    #     self,
    #     ctx: ApplicationContext):
    #
    #     await ctx.defer(ephemeral = True)
    #
    #     # allowedChannels = ['function', 'information', 'road-map', 'discussion', 'chat']
    #     # deletingChannels = [channel_ID for channel_ID in ctx.guild.channel_IDs if channel_ID.name not in allowedChannels]
    #     # [await channel_ID.delete() for channel_ID in deletingChannels]
    #
    #     # return
    #
    #     guild_data = GuildData(ctx.guild_id)
    #
    #     description = ''
    #
    #     channel_IDs = [channel_ID.id for channel_ID in ctx.guild.text_channel_IDs]
    #     channel_IDNames = [channel_ID.name for channel_ID in ctx.guild.text_channel_IDs]
    #
    #     ghostNodeMentions = []
    #     misnomerNodeMentions = []
    #     incorrectWebhooks = []
    #
    #     if guild_data.nodes:
    #         maker = ChannelMaker(ctx.guild, 'nodes')
    #         await maker.initialize()
    #     for name, node in list(guild_data.nodes.items()): #Fix node issues
    #
    #         if node.channel_ID not in channel_IDs: #Node was deleted in server only
    #
    #             new_channel = await maker.create_channel(name)
    #             ghostNodeMentions.append(new_channel.mention)
    #             node.channel_ID = new_channel.id
    #
    #             whitelist = await format_whitelist(node.allowed_roles, node.allowed_players)
    #             embed, _ = await mbd(
    #             'Cool, new node...again.',
    #             f"**Important!** Don't delete this one!" + \
    #                 f"\n\nAnyways, here's who is allowed:\n{whitelist}",
    #             "Unfortunately, I couldn't save the edges this may have had.")
    #             await new_channel.send(embed = embed)
    #             continue
    #
    #         newName = None
    #         if name not in channel_IDNames: #Node was renamed in server only
    #
    #             channel_ID = get(ctx.guild.text_channel_IDs, id = node.channel_ID)
    #             oldName = name
    #             newName = channel_ID.name
    #
    #             misnomerNodeMentions.append(channel_ID.mention)
    #
    #             guild_data.nodes[newName] = guild_data.nodes.pop(oldName)
    #             for neighbor in node.neighbors.keys():
    #
    #                 guild_data.nodes[neighbor].neighbors[newName] = guild_data.nodes[neighbor].neighbors.pop(oldName)
    #
    #
    #         channel_ID = get(ctx.guild.text_channel_IDs, id = node.channel_ID)
    #         nodeWebhooks = await channel_ID.webhooks()
    #         if len(nodeWebhooks) != 1:
    #
    #             for webhook in nodeWebhooks:
    #                 await webhook.delete()
    #
    #             with open('assets/avatar.png', 'rb') as file:
    #                 avatar = file.read()
    #                 await channel_ID.create_webhook(name = 'Proximity', avatar = avatar)
    #
    #             incorrectWebhooks.append(channel_ID.mention)
    #
    #     if ghostNodeMentions:
    #         description += "\n• These nodes were deleted without using `/node delete`," + \
    #             f" but were just regenerated: {await format_words(ghostNodeMentions)}."
    #
    #     if misnomerNodeMentions:
    #         description += "\n• Corrected the name(s) of the following" + \
    #             " channel_ID(s) that were renamed not using `/node review`:" + \
    #             f" {await format_words(misnomerNodeMentions)}."
    #
    #     if incorrectWebhooks:
    #         description += "\n• Fixed the webhook(s) for the following" + \
    #         f" node channel_ID(s): {await format_words(incorrectWebhooks)}."
    #
    #     await guild_data.save()
    #
    #     #Identify dead ends and isolates
    #     noExits = {name : node for name, node in guild_data.nodes.items() \
    #         if not any(edge.directionality > 0 for edge in node.neighbors.values())}
    #     noEntrances = {name : node for name, node in guild_data.nodes.items() \
    #         if not any(edge.directionality < 2 for edge in node.neighbors.values())}
    #     noAccess = {name : node for name, node in noExits.items() if \
    #         name in noEntrances}
    #
    #     noEntrances = {name : node for name, node in noEntrances.items() \
    #         if name not in noAccess}
    #     noExits = {name : node for name, node in noExits.items() \
    #         if name not in noAccess}
    #
    #     if noAccess:
    #         noAccessMentions = await format_nodes(noAccess.values())
    #         description += "\n• The following nodes have no edges for entry or exit, meaning" + \
    #             f" **players can only come or go through** `/player tp`**:** {noAccessMentions}."
    #
    #     if noExits:
    #         noExitsMentions = await format_nodes(noExits.values())
    #         description += "\n• The following nodes have no edges for exiting, meaning" + \
    #             f" **players can get trapped:** {noExitsMentions}."
    #
    #     if noEntrances:
    #         noEntrancesMentions = await format_nodes(noEntrances.values())
    #         description += "\n• The following nodes have no edges or entrances, meaning" + \
    #             f" **players will never enter:** {noEntrancesMentions}."
    #
    #     noChannelMentions = []
    #     missingPlayers = []
    #     wrongWebhooks = []
    #     if guild_data.players:
    #         maker = ChannelMaker(ctx.guild, 'players')
    #         await maker.initialize()
    #     for player_ID in list(guild_data.players): #Identify player issues
    #
    #         player = Player(player_ID, ctx.guild_id)
    #
    #         member = get(ctx.guild.members, id = player_ID)
    #         if not member: #User left the server but is still considered a player
    #             oldChannel = get(ctx.guild.text_channel_IDs, id = player.channel_ID)
    #             if oldChannel:
    #                 missingPlayers.append(oldChannel.name)
    #             else:
    #                 missingPlayers.append('Channel-less Ex-player')
    #
    #             lastNode = guild_data.nodes.get(player.location, None)
    #             if lastNode:
    #                 if lastNode.occupants:
    #                     lastNode.remove_occupants({player_ID})
    #
    #             await player.delete()
    #             guild_data.players.pop(player_ID)
    #             continue
    #
    #         if player.channel_ID not in channel_IDs: #User is missing their channel_ID
    #             noChannelMentions.append(member.mention)
    #
    #             channel_ID = await maker.create_channel(member.display_name, member)
    #
    #             player.channel_ID = channel_ID.id
    #             await player.save()
    #
    #             embed, _ = await mbd(
    #                 f'Welcome.',
    #                 f"This is your very own channel_ID, again, {member.mention}." + \
    #                 "\n• Speak to others by just talking in this chat. Anyone who can hear you" + \
    #                 " will see your messages pop up in their own player channel_ID." + \
    #                 f"\n• You can `/look` around. You're at **{player.location}** right now." + \
    #                 "\n• Do `/map` to see the other places you can go." + \
    #                 "\n• ...And `/move` to go there." + \
    #                 "\n• You can`/eavesdrop` on people nearby room." + \
    #                 "\n• Other people can't see your `/commands`." + \
    #                 "\n• Tell the host not to accidentally delete your channel_ID again.",
    #                 'You can always type /help to get more help.')
    #             await channel_ID.send(embed = embed)
    #
    #         playerChannel = get(ctx.guild.text_channel_IDs, id = player.channel_ID)
    #         playerWebhooks = await playerChannel.webhooks()
    #         if len(playerWebhooks) != 1:
    #
    #             for webhook in playerWebhooks:
    #                 await webhook.delete()
    #
    #             with open('assets/avatar.png', 'rb') as file:
    #                 avatar = file.read()
    #                 await channel_ID.create_webhook(name = 'Proximity', avatar = avatar)
    #
    #             wrongWebhooks.append(playerChannel.mention)
    #
    #     await queue_refresh(ctx.guild)
    #
    #     if noChannelMentions:
    #         description += "\n• The following players got back" + \
    #         f" their deleted player channel_IDs: {await format_words(noChannelMentions)}."
    #
    #     if missingPlayers:
    #         description += f"\n• Deleted data and any remaining player" + \
    #             f" channel_IDs for {len(missingPlayers)} players who left" + \
    #             " the server without ever being officially removed as" + \
    #             " players. My best guess for the name(s) of those who" + \
    #             f" left is {await format_words(missingPlayers)}."
    #
    #     if wrongWebhooks:
    #         description += "\n• Fixed the webhook(s) for the following" + \
    #         f" player channel_ID(s: {await format_words(wrongWebhooks)}."
    #
    #     if not description:
    #         description += "Congratulations! This server has no detectable issues." + \
    #             "\n• There are no nodes missing a channel_ID, none have been renamed" + \
    #             " improperly, and none are missing their webhook.\n• No dead end nodes" + \
    #             " or isolated nodes.\n• No players left the server and left behind data" + \
    #             " or a channel_ID.\n• No players missing a channel_ID or their webhook."
    #
    #     embed, _ = await mbd(
    #     f'Server fix',
    #     description,
    #     'Be sure to check this whenever you have issues.')
    #     await ctx.respond(embed = embed)
    #     return



def setup(prox):
    prox.add_cog(ServerCommands(prox), override = True)
