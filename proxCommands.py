import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
from discord.utils import get_or_fetch, get

import functions as fn
import databaseFunctions as db

import asyncio
import time
import networkx as nx

import oopFunctions as oop

# Please, dear Gray, do not judge me based on the fact i used global here,
# I swear it's for a good reason. Do as I say, not as I do, you
# must rise above my practices and code better than me padawan

global updatedGuilds, needingUpdate, directListeners, indirectListeners, proximity
proximity = None
updatedGuilds = set()
needingUpdate = set()
directListeners = {}
indirectListeners = {}

async def queueRefresh(guild: discord.Guild):

    return 

    updatedGuilds.discard(guild.id) #Indicate to Relay and postToDirect that this server is out of date
    needingUpdate.add(guild) #Give the updateListeners function enough info to update the listeners
    return

async def relay(msg: discord.Message):

    return

    if msg.author.id == 1114004384926421126: #Don't relay bot's own messages
        return

    if msg.guild.id not in updatedGuilds: #Listeners are out of date, wait for refresh
        
        needingUpdate.add(msg.guild)
        
        while msg.guild.id not in updatedGuilds:
            print(f'Waiting for updated listeners in server: {msg.guild.name}.')
            await asyncio.sleep(2)

    directs = directListeners.get(msg.channel.id, [])
    for channel, eavesdropping in directs:

        if eavesdropping:
            embed, _ = await fn.embed(
                msg.author.name,
                msg.content[:2000],
                'You hear every word that they say.')
            await channel.send(embed = embed)
            if len(msg.content) > 1999:
                embed, _ = await fn.embed(
                    'Continued',
                    msg.content[2000:4000],
                    'And wow, is that a lot to say.')
                await channel.send(embed = embed)

        else:
            webhook = (await channel.webhooks())[0]
            files = [attachment.to_file() for attachment in msg.attachments]
            await webhook.send(
                msg.content[:2000], 
                username = msg.author.display_name, 
                avatar_url = msg.author.avatar.url,
                files = files)
            if len(msg.content) > 1999:
                await webhook.send(
                    msg.content[2000:4000], 
                    username = msg.author.display_name, 
                    avatar_url = msg.author.avatar.url)

    indirects = indirectListeners.get(msg.channel.id, [])
    for speakerLocation, channel in indirects:
        embed, _ = await fn.embed(
            f'Hm?',
            f"You think you hear {msg.author.mention} in **#{speakerLocation}**.",
            'Perhaps you can /move over to them.')
        await channel.send(embed = embed)

    # if directs or indirects:
    #     await msg.add_reaction('✔️')   
        
    return

async def postToDirects(    
    embed: discord.Embed,
    guild: discord.Interaction,
    channelID: int,
    exclude: int = 0,
    onlyOccs: bool = False):

    return

    if guild.id not in updatedGuilds:
    
        needingUpdate.add(guild)
        
        while guild.id not in updatedGuilds:
            print(f'Waiting for updated listeners in server: {guild.name}.')
            await asyncio.sleep(2)
    
    directs = directListeners.get(channelID, [])
    for channel, eavesdropping in directs:

        if channel.id == exclude: #Usually just to exclude the player who's performing the action
            continue

        if eavesdropping and onlyOccs: #To limit this message to only the direct listeners in the same room
            continue

        try:
            await channel.send(embed = embed)
        except: #Whenever this triggers it is NOT probably fine, don't fall for it Gray
            print(f"Tried to send a message to a channel without its webhook," + \
                f" #{channel.name} within {channel.guild.name}. It's probably fine.", \
                file = sys.stderr)

    return

class nodeCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    node = SlashCommandGroup(
        name = 'node',
        description = 'Manage the nodes of your graph.',
        guild_only = True)

    @node.command(
        name = 'new',
        description = 'Create a new node.')
    async def new(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(
            str,
            description = 'What should it be called?',
            default = 'new-node')):

        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        submittedName = oop.Format.discordify(name)
        name = submittedName if submittedName else 'new-node'

        async def refreshEmbed():

            nonlocal name
            name = view.name() if view.name() else name

            description = f'Whitelist: {await oop.Format.whitelist(view.roles(), view.players())}'

            #Formatting results
            embed, _ = await fn.embed(
                f'New node: {name}',
                description,
                'You can also create a whitelist to limit who can visit this node.')
            return embed

        async def submitNode(interaction: discord.Interaction):

            await fn.loading(interaction)

            nonlocal name

            if name in guildData.nodes:
                await fn.nodeExists(guildData.nodes[name], interaction)
                return
    
            maker = oop.ChannelMaker(interaction.guild, 'nodes')
            await maker.initialize()
            newChannel = await maker.newChannel(name)

            await guildData.newNode(
                name = name, 
                channelID = newChannel.id,
                allowedRoles = view.roles(),
                allowedPlayers = view.players())
            await guildData.save()

            embed, _ = await fn.embed(
                f'{newChannel.mention} created!',
                f"The permissions you requested are set-- just not in the channel's Discord" + \
                " settings.",
                "No worries, it's all being kept track of by me.")        
            await interaction.followup.edit_message(
                message_id = interaction.message.id,
                embed = embed,
                view = None)

            whitelist = await oop.Format.whitelist(view.roles(), view.players())
            embed, _ = await fn.embed(
                'Cool, new node.',
                f"**Important!** Don't mess with this channel!" + \
                    " Use `/node review` or else you'll need to use `/server fix`." + \
                    f"\n\nAnyways, here's who is allowed:\n{whitelist}" + \
                    "\n\nYou can change the whitelist with`/node review`.",
                "You can connect this to other nodes you make with /edge new.")         
            await newChannel.send(embed = embed)
            return

        view = oop.DialogueView(guild = ctx.guild, refresh = refreshEmbed)
        await view.addRoles()
        await view.addPlayers(guildData.players)
        await view.addSubmit(submitNode)
        await view.addName()
        await view.addCancel()
        
        embed = await refreshEmbed()
        await ctx.respond(embed = embed, view = view)
        return

    @node.command(
        name = 'delete',
        description = 'Delete a node.')
    async def delete(
        self,
        ctx: discord.ApplicationContext,
        node: discord.Option(
            str,
            'Call this command in a node (or name it) to narrow it down.',
            autocomplete = fn.autocompleteNodes,
            required = False)):
        
        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        async def deleteNodes(deletingNodeNames: list):

            deletingNodes = await guildData.filterNodes(deletingNodeNames)
            deletingMentions = await oop.Format.nodes(deletingNodes.values())
            
            async def confirmDelete(interaction: discord.Interaction):

                await fn.loading(interaction)

                nonlocal deletingNodes
                deletingNodes = {name : node for name, node in deletingNodes.items() if not node.occupants}

                if not deletingNodes:
                    embed, _ = await fn.embed(
                        'No nodes to delete.',
                        "You need to specify a node that doesn't have anyone inside.",
                        'You can always try the command again.')
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id, 
                        embed = embed, 
                        view = None)
                    return

                #Inform neighbor nodes and occupants that the node is deleted now
                neighbors = await guildData.neighbors(deletingNodes.keys())
                boldDeleting = await oop.Format.bold(deletingNodes.keys())
                for neighbor in neighbors:
                    embed, _ = await fn.embed(
                        'Misremembered?',
                        f"Could you be imagining {boldDeleting}? Strangely, there's no trace.",
                        "Whatever the case, it's gone now.")
                    await postToDirects(
                        embed, 
                        interaction.guild, 
                        neighbor.channelID,
                        onlyOccs = True)
                    
                    embed, _ = await fn.embed(
                        'Neighbor node(s) deleted.',
                        f'Deleted {boldDeleting}--this node now has fewer neighbors.',
                        "I'm sure it's for the best.")
                    neighborChannel = get(
                        interaction.guild.text_channels,
                        id = neighbor.channelID)
                    await neighborChannel.send(embed = embed)

                #Delete nodes and their edges
                for name, node in deletingNodes.items():

                    for neighbor in node.neighbors.keys():
                        await guildData.deleteEdge(name, neighbor)

                    await guildData.deleteNode(name, ctx.guild.text_channels)

                await guildData.save()

                if interaction.channel.name not in deletingNodes:

                    description = f'Successfully deleted the following things about {boldDeleting}:' + \
                        "\n• The node data in the database." + \
                        "\n• The node channels." + \
                        "\n• All edges to and from the node."

                    occupiedNodesCount = len(deletingNodeNames) - len(deletingNodes) 
                    if occupiedNodesCount:                        
                        description += f"\n\nCouldn't delete {occupiedNodesCount}" + \
                                " node(s) that were occupied. Use `/player tp` to move the player(s) inside."
                    
                    embed, _ = await fn.embed(
                        'Delete results',
                        description,
                        'Say goodbye.')
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id, 
                        embed = embed, 
                        view = None)
                return
         
            view = oop.DialogueView(guild = ctx.guild)
            await view.addEvilConfirm(confirmDelete)
            await view.addCancel()

            embed, _ = await fn.embed(
                'Confirm deletion?',
                f"Delete {deletingMentions}?",
                'This will also delete any edges connected to the node(s).')
            await ctx.respond(embed = embed, view = view, ephemeral = True)
            return

        result = await fn.identifyNodeChannel(guildData.nodes.keys(), ctx.channel.name, node)
        match result:
            case isMessage if isinstance(result, discord.Embed):
                await ctx.respond(embed = result)
            case isChannel if isinstance(result, str):
                await deleteNodes([result])
            case None:
                embed, _ = await fn.embed(
                    'Delete Node(s)?',
                    "You can delete a node three ways:" + \
                        "\n• Call this command inside of a node channel." + \
                        "\n• Do `/node delete #node-channel`." + \
                        "\n• Select multiple node channels with the list below.",
                    'This will remove the node(s), all its edges, and any corresponding channels.')

                async def submitNodes(interaction: discord.Interaction):
                    await ctx.delete()
                    await deleteNodes(view.nodes())
                    return

                view = oop.DialogueView(guild = ctx.guild)
                await view.addNodes(guildData.nodes.keys(), submitNodes)
                await view.addCancel()
                await ctx.respond(embed = embed, view = view)

        return

    @node.command(
        name = 'review',
        description = 'Inspect and/or edit one or more nodes.')
    async def review(
        self,
        ctx: discord.ApplicationContext,
        node: discord.Option(
            str,
            'Either call this command inside a node or name it here.',
            autocomplete = fn.autocompleteNodes,
            required = False)):
        
        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        async def reviseNodes(nodeNames: list):

            revisingNodes = await guildData.filterNodes(nodeNames)

            title = f'Reviewing {len(revisingNodes)} node(s).'
            intro = f"• Selected node(s): {await oop.Format.nodes(revisingNodes.values())}"

            occupants = await guildData.getUnifiedOccupants(revisingNodes.values())
            description = f"\n• Occupants: {await oop.Format.players(occupants) if occupants else 'There are no people here.'}"
              
            neighbors = await guildData.neighbors(revisingNodes.keys())
            if neighbors:
                subgraph = await guildData.toGraph(neighbors + nodeNames)
                description += '\n• Edges: See below.'
                graphView = (await fn.showGraph(subgraph), 'full')
            else:
                description += '\n• Edges: No other nodes are connected to the selected node(s).'
                graphView = None

            hasWhitelist = any(node.allowedRoles or node.allowedPlayers for node in revisingNodes.values())

            async def refreshEmbed():

                fullDescription = intro
                if view.name():
                    fullDescription += f', renaming to **#{view.name()}**.'
                fullDescription += description
                
                fullDescription += await view.whitelist(revisingNodes.values())

                embed, _ = await fn.embed(
                    title,
                    fullDescription,
                    'You can rename a node if you have only one selected.',
                    graphView)
                return embed

            async def submitNode(interaction: discord.Interaction):

                await fn.loading(interaction)

                nonlocal revisingNodes

                if view.name() in guildData.nodes:
                    await fn.nodeExists(guildData.nodes[view.name()], interaction)
                    return

                if await fn.noChanges((view.name() or view.roles() or view.players() or view.clearing), interaction):
                    return

                description = ''

                if view.clearing: 
                    description += '\n• Removed the whitelist(s).'
                    for name, node in revisingNodes.items():

                        await guildData.nodes[name].clearWhitelist()
                        embed, _ = await fn.embed(
                            'Opening up.',
                            'You somehow feel like this place just easier to get to.',
                            'For better or for worse.')
                        await postToDirects(embed, 
                            interaction.guild, 
                            node.channelID,
                            onlyOccs = True)

                if view.roles() or view.players():
                    if view.roles():
                        description += '\n• Edited the roles whitelist(s).'
                    if view.players():
                        description += '\n• Edited the people whitelist(s).'
                    
                    embed, _ = await fn.embed(
                        'Strange.',
                        "There's a sense that this place just changed in some way.",
                        "Only time will tell if you'll be able to return here as easily as you came.")

                    for name, node in revisingNodes.items():
                        await postToDirects(embed,
                            interaction.guild, 
                            node.channelID,
                            onlyOccs = True)

                        await guildData.nodes[name].setRoles(view.roles())
                        await guildData.nodes[name].setPlayers(view.players())
                    
                if view.name(): 

                    oldName = list(revisingNodes.keys())[0]
                    renamedNode = guildData.nodes.pop(oldName)
                    guildData.nodes[view.name()] = renamedNode
                    
                    description += f"\n• Renamed **#{oldName}** to {renamedNode.mention}."

                    #Correct locationName in player data
                    for occupantID in renamedNode.occupants:

                        player = oop.Player(occupantID, interaction.guild_id)
                        player.location = view.name()
                        await player.save()
                    
                    #Rename channel
                    nodeChannel = get(interaction.guild.text_channels, id = renamedNode.channelID)
                    await nodeChannel.edit(name = view.name())

                    #Rename edges
                    for node in guildData.nodes.values():
                        for neighbor in list(node.neighbors):
                            if neighbor == oldName:
                                node.neighbors[view.name()] = node.neighbors.pop(oldName)
                                
                await guildData.save()

                await queueRefresh(interaction.guild)
                
                embed, _ = await fn.embed(
                    'Edited.',
                    description,
                    'Another successful revision.')
                for node in revisingNodes.values():
                    nodeChannel = get(interaction.guild.text_channels, id = node.channelID)
                    await nodeChannel.send(embed = embed)  

                return await fn.noCopies(
                    (interaction.channel.name in revisingNodes or interaction.channel.name == view.name()),
                    embed,
                    interaction)              
            
            view = oop.DialogueView(ctx.guild, refreshEmbed)
            await view.addRoles()
            await view.addPlayers(guildData.players)
            await view.addSubmit(submitNode)
            if len(revisingNodes) == 1:
                await view.addName()
            if hasWhitelist:
                await view.addClear()
            await view.addCancel()
            embed = await refreshEmbed()
            _, file = await fn.embed(
                imageDetails = graphView)

            await ctx.respond(embed = embed, view = view, file = file, ephemeral = True)
            return

        result = await fn.identifyNodeChannel(guildData.nodes.keys(), ctx.channel.name, node)
        match result:
            case isMessage if isinstance(result, discord.Embed):
                await ctx.respond(embed = result)
            case isChannel if isinstance(result, str):
                await reviseNodes([result])
            case None:
            
                embed, _ = await fn.embed(
                    'Review node(s)?',
                    "You can revise a node three ways:" + \
                        "\n• Call this command inside of a node channel." + \
                        "\n• Do `/node review #node-channel`." + \
                        "\n• Select multiple node channels with the list below.",
                    'This will allow you to view the nodes, their edges, and their whitelists.')

                async def submitNodes(interaction: discord.Interaction):
                    await ctx.delete()
                    await reviseNodes(view.nodes())
                    return

                view = oop.DialogueView()     
                nodes = [name for name, node in guildData.nodes.items() if node.channelID != ctx.channel_id]
                await view.addNodes(nodes, submitNodes)
                await view.addCancel()
                await ctx.respond(embed = embed, view = view)

        return

    @commands.Cog.listener()
    async def on_guild_channel_delete(
        self,
        channel):

        guildData = oop.GuildData(channel.guild.id)

        for name, node in guildData.nodes.items():
            if channel.id == node.channelID:
                await guildData.deleteNode(name)
                directListeners.pop(node.channelID, None)
                await guildData.save()
                break

        return
    
    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        beforeChannel,
        afterChannel):

        guildData = oop.GuildData(beforeChannel.guild.id)

        foundNode = False
        for name, node in guildData.nodes.items():
            if beforeChannel.id == node.channelID:
                renamedNode = guildData.nodes.pop(beforeChannel.name)
                guildData.nodes[afterChannel.name] = renamedNode
                foundNode = True
                break
            
        if foundNode == False:
            return

        for node in guildData.nodes.values():
            for neighbor in list(node.neighbors):
                if neighbor == oldName:
                    node.neighbors[afterChannel.name] = node.neighbors.pop(beforeChannel.name)

        await guildData.save()
        return
    
class edgeCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    edge = SlashCommandGroup(
        name = 'edge',
        description = 'Manage edges between nodes.',
        guild_only = True)

    @edge.command(
        name = 'new',
        description = 'Connect nodes.')
    async def new(
        self,
        ctx: discord.ApplicationContext,
        origin: discord.Option(
            str,
            'Either call this command inside a node or name it here.',
            autocomplete = fn.autocompleteNodes,
            required = False)):
        
        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        async def createEdges(originName: str):

            origin = guildData.nodes[originName]
            originName = originName
            
            async def refreshEmbed():

                description = f'• Origin: {origin.mention}'

                if view.nodes():
                    destinations = await guildData.filterNodes(view.nodes())
                    destinationMentions = await oop.Format.nodes(destinations.values())
                    description += f'\n• Destination(s): {destinationMentions}.'
                else:
                    description += f"\n• Destination(s): None yet! Add some nodes to draw an edge to."

                description += f"\n• Whitelist: {await oop.Format.whitelist(view.roles(), view.players())}"

                match view.directionality:
                    case 0:
                        description += "\n• Directionality: These connections are **one-way** (<-) from" + \
                            f" the destination(s) to {origin.mention}."
                    case 1:
                        description += "\n• Directionality: **Two-way** (<->), people will be able to travel" + \
                            f" back and forth between {origin.mention} and the destination(s)."
                    case 2:
                        description += "\n• Directionality: These connections are **one-way** (->) from" + \
                            f" {origin.mention} to the destination(s)."

                if view.overwriting:
                    description += f"\n• **Overwriting** edges. Old edges will be erased where new one are laid."
                else:
                    description += f"\n• Will not overwrite edges. Click below to toggle."

                embed, _ = await fn.embed(
                    f'New edge(s)',
                    description,
                    'Which nodes are we hooking up?')
                return embed

            async def submitEdges(interaction: discord.Interaction):

                await fn.loading(interaction)

                nonlocal originName
                    
                if not view.nodes():
                    await fn.noNodes(interaction)
                    return

                #Make edges          
                edge = oop.Edge(
                    directionality = view.directionality,
                    allowedRoles = view.roles(),
                    allowedPlayers = view.players())
                existingEdges = 0
                newNeighbors = set()
                for destination in view.nodes():
                    
                    if await guildData.setEdge(
                        originName,
                        destination,
                        edge,
                        view.overwriting):

                        existingEdges += 1
                    
                    else:
                        newNeighbors.add(destination)

                if len(newNeighbors) == 0:
                    embed, _ = await fn.embed(
                        'No new neighbors?',
                        "I couldn't make any new edges--there's already an edge" + \
                            " present for all the nodes you want to connect.",
                        'Enable overwriting to make the edges you want regardless.')
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        view = None)
                    return

                await guildData.save()
                neighborsDict = await guildData.filterNodes(newNeighbors)
                await queueRefresh(interaction.guild)
                    
                #Inform neighbors occupants and neighbor nodes
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"You notice a way to get between this place and **#{originName}**. Has that always been there?",
                    'And if so, has it always been like that?')
                nodeEmbed, _ = await fn.embed(
                    'Edge created.',
                    f'Created an edge between here and {origin.mention}.',
                    'You can view its details with /node review.')
                for node in neighborsDict.values():
                    await postToDirects(
                        playersEmbed, 
                        interaction.guild, 
                        node.channelID,
                        onlyOccs = True)
                    nodeChannel = get(interaction.guild.text_channels, id = node.channelID)
                    await nodeChannel.send(embed = nodeEmbed)

                #Inform edited node occupants
                boldNeighbors = await oop.Format.bold(newNeighbors)
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"You notice that this place is connected to {boldNeighbors}. Something about that seems new.",
                    "Perhaps you're only imagining it.")         
                await postToDirects(
                    playersEmbed, 
                    interaction.guild, 
                    origin.channelID,
                    onlyOccs = True)

                #Inform own node
                description = f'\n• Connected {origin.mention}'
                match view.directionality:
                    case 0:
                        description += ' from <- '
                    case 1:
                        description += ' <-> back and forth to '
                    case 2:
                        description += ' to -> '
                destinationMentions = await oop.Format.nodes(neighborsDict.values())
                description += f'{destinationMentions}.'
                
                if view.roles() or view.players():
                    description += f'\n• Imposed the whitelist: {await oop.Format.whitelist(view.roles(), view.players())}'
                
                if existingEdges:
                    if view.overwriting:
                        description += f'\n• Overwrote {existingEdges} edge(s).'
                    else:
                        description += f"\n• Skipped {existingEdges} edge(s) because" + \
                            f" the nodes were already connected. Enable overwriting to ignore."

                #Produce map of new edges
                graph = await guildData.toGraph()
                subgraph = nx.ego_graph(graph, originName, radius = 99)
                graphView = await fn.showGraph(subgraph)
                embed, file = await fn.embed(
                    'New edge results.',
                    description,
                    'You can view all the nodes and edges with /server view.',
                    (graphView, 'full'))        
                nodeChannel = get(interaction.guild.text_channels, id = origin.channelID)
                await nodeChannel.send(embed = embed, file = file)

                if interaction.channel.name not in newNeighbors and interaction.channel.name != originName:
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed)    
                return

            view = oop.DialogueView(ctx.guild, refreshEmbed)
            nodes = {name for name, node in guildData.nodes.items() if node != origin}
            await view.addNodes(nodes)
            await view.addRoles()
            await view.addPlayers(guildData.players)
            await view.addSubmit(submitEdges)
            await view.addDirectionality()
            await view.addOverwrite()
            await view.addCancel()
            embed = await refreshEmbed()
            await ctx.respond(embed = embed, view = view, ephemeral = True)
            return

        result = await fn.identifyNodeChannel(guildData.nodes.keys(), ctx.channel.name, origin)
        match result:
            case isMessage if isinstance(result, discord.Embed):
                await ctx.respond(embed = result)
            case isChannel if isinstance(result, str):
                await createEdges(result)
            case None:
            
                embed, _ = await fn.embed(
                    'Connect nodes?',
                    "You can create a new edge three ways:" + \
                        "\n• Call this command inside of a node channel." + \
                        "\n• Do `/edge new #node-channel`." + \
                        "\n• Select a node channel with the list below.",
                    "This is just to select the origin, you'll select the destinations next.")

                async def submitNodes(interaction: discord.Interaction):
                    await ctx.delete()
                    await createEdges(view.nodes()[0])
                    return

                view = oop.DialogueView(ctx.guild)          
                await view.addNodes(guildData.nodes, submitNodes, manyNodes = False)
                await view.addCancel()
                await ctx.respond(embed = embed, view = view)

        return

    @edge.command(
        name = 'delete',
        description = 'Remove the connections of a given node.')
    async def delete(
        self,
        ctx: discord.ApplicationContext,
        origin: discord.Option(
            str,
            'Either call this command inside a node or name it here.',
            autocomplete = fn.autocompleteNodes,
            required = False)):
        
        await ctx.defer(ephemeral = True)

        guildData = db.gd(ctx.guild_id)

        async def deleteEdges(originName: str):

            originMention = f"<#{guildData['nodes'][originName]['channelID']}>"

            graph = await fn.makeGraph(guildData)
            ancestors, mutuals, successors = await fn.getConnections(graph, [originName], True)
            allNeighbors = ancestors + mutuals + successors
            if not allNeighbors:
                embed, _ = await fn.embed(
                    'No edges.',
                    f'{originMention} has no edges to view.',
                    'So I suppose that answers your inquiry.')
                await ctx.respond(embed = embed, ephemeral = True)
                return

            subgraph = graph.subgraph(allNeighbors + [originName])
            description = f'{originMention} has the following connections'

            deletedEdges = []
            graphImage = None

            async def refreshEmbed():

                fullDescription = description

                if not deletedEdges:
                    fullDescription += ':'
                else:
                    deletingAncestors = [ancestor for ancestor in ancestors if ancestor in addEdges.values]
                    deletingMutuals = [mutual for mutual in mutuals if mutual in addEdges.values]
                    deletingSuccessors = [successor for successor in successors if successor in addEdges.values]

                    fullDescription += ", but you'll be deleting the following:" + \
                        await fn.formatEdges(
                            guildData['nodes'],
                            deletingAncestors,
                            deletingMutuals,
                            deletingSuccessors)

                embed, _ = await fn.embed(
                    'Delete edge(s)?',
                    fullDescription,
                    'This cannot be reversed.',
                    (graphImage, 'full'))
                
                return embed

            async def updateFile():

                nonlocal graphImage, deletedEdges

                deletedEdges = addEdges.values
                edgeColors = await fn.colorEdges(subgraph, originName, deletedEdges, 'red')
                graphImage = await fn.showGraph(subgraph, edgeColors)

                return

            async def refreshFile(interaction: discord.Interaction):   
                await updateFile()
                await interaction.response.edit_message(
                    file = discord.File(graphImage, filename = 'image.png'))
                return

            async def confirmDelete(interaction: discord.Interaction):

                await fn.loading(interaction)

                for neighbor in deletedEdges:
                    guildData['edges'].pop((neighbor, originName), None)
                    guildData['edges'].pop((originName, neighbor), None)

                con = db.connectToGuild()
                db.updateGuild(con, guildData, interaction.guild_id)
                con.close()

                await queueRefresh(interaction.guild)

                deletedNeighbors = await fn.filterNodes(guildData['nodes'], deletedEdges)

                #Inform neighbors occupants and neighbor nodes
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"The path between here and **#{originName}** just closed.",
                    'Just like that...')
                nodeEmbed, _ = await fn.embed(
                    'Edge deleted.',
                    f'Removed an edge between here and {originMention}.',
                    'You can view the remaining edges with /node review.')
                for data in deletedNeighbors.values():
                    await postToDirects(
                        playersEmbed, 
                        interaction.guild, 
                        data['channelID'],
                        onlyOccs = True)
                    nodeChannel = get(interaction.guild.text_channels, id = data['channelID'])
                    await nodeChannel.send(embed = nodeEmbed)

                #Inform edited node occupants
                boldDeleted = await fn.boldNodes(addEdges.values)
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"This place just lost access to {boldDeleted}.",
                    "Will that path ever be restored?")         
                await postToDirects(
                    playersEmbed, 
                    interaction.guild, 
                    guildData['nodes'][originName]['channelID'],
                    onlyOccs = True)

                #Inform own node            
                deletedMentions = await fn.mentionNodes(deletedNeighbors.values())
                embed, _ = await fn.embed(
                    'Edges deleted.',
                    f'Removed the edge(s) to {deletedMentions}.',
                    'You can always make some new ones with /edge new.')   
                nodeChannel = get(interaction.guild.text_channels, name = originName)
                await nodeChannel.send(embed = embed)

                if interaction.channel.name == originName:
                    await interaction.followup.delete_message(message_id = interaction.message.id)
                else:
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        attachments = [],
                        view = None)    
                return

            view = discord.ui.View()
            view, addEdges = await fn.addEdges(ancestors, mutuals, successors, view, callback = refreshFile)
            view, confirm = await fn.addEvilConfirm(view, confirmDelete)
            view, cancel = await fn.addCancel(view)

            await updateFile()
            embed = await refreshEmbed()

            await ctx.respond(embed = embed,
                file = discord.File(graphImage, filename='image.png'),
                view = view,
                ephemeral = True)
            return

        result = await fn.identifyNodeChannel(guildData['nodes'], ctx.channel.name, origin)
        match result:
            case isMessage if isinstance(result, discord.Embed):
                await ctx.respond(embed = result)
            case isChannel if isinstance(result, str):
                await deleteEdges(result)
            case None:
    
                embed, _ = await fn.embed(
                    'Delete edges?',
                    "You can delete edges three ways:\n\
                    • Call this command inside of a node channel.\n\
                    • Do `/edge delete #node-channel`.\n\
                    • Select a node channel with the list below.",
                    "This is just to select the origin, you'll see the edges next.")

                async def submitNodes(interaction: discord.Interaction):
                    await ctx.delete()
                    await deleteEdges(addNodes.values[0])
                    return

                view = discord.ui.View()      
                view, addNodes = await fn.addNodes(view, guildData['nodes'].keys(), submitNodes, manyNodes = False)
                view, cancel = await fn.addCancel(view)
                await ctx.respond(embed = embed, view = view)

        return

    @edge.command(
        name = 'allow',
        description = 'Choose who is allowed in an edge.')
    async def allow(
        self,
        ctx: discord.ApplicationContext,
        origin: discord.Option(
            str,
            'Either call this command inside a node or name it here.',
            autocomplete = fn.autocompleteNodes,
            required = False)):
        
        await ctx.defer(ephemeral = True)

        guildData, members = db.mag(ctx.guild_id)

        async def revisePermissions(originName: str):

            originMention = f"<#{guildData['nodes'][originName]['channelID']}>"

            graph = await fn.makeGraph(guildData)
            ancestors, mutuals, successors = await fn.getConnections(graph, [originName], True)
            edgeData = [graph.edges[edge] for edge in (graph.in_edges(originName) or graph.out_edges(originName))]
            if not edgeData:
                embed, _ = await fn.embed(
                    'No edges.',
                    f'{originMention} has no edges of which to modify the whitelists.',
                    'So I suppose that answers your inquiry.')
                await ctx.respond(embed = embed, ephemeral = True)
                return

            subgraph = nx.ego_graph(graph, originName, radius = 99)
            description = f'• Selected node: {originMention}'

            hasWhitelist = await fn.hasWhitelist(edgeData)

            clearing = False
            graphImage = None

            async def refreshEmbed():

                fullDescription = description

                if addEdges.values:
                    fullDescription += f"\n• Selected Edges: See below."   
                    components = []
                    for destination in addEdges.values:
                        toNeighbor = guildData['edges'].get((originName, destination), {})
                        fromNeighbor = guildData['edges'].get((destination, originName), {})
                        toNeighbor.update(fromNeighbor)
                        components.append(toNeighbor)

                    fullDescription += await fn.determineWhitelist(
                        clearing,
                        addRoles.values,
                        addPlayers.values,
                        components)                   
                
                else:
                    fullDescription += '\n• Selected Edges: None yet. Use the dropdown below to pick one or more.'
                    fullDescription += '\n• Whitelist: Selected edges will have their whitelists appear here.'
                                    
                edgeColors = await fn.colorEdges(subgraph, originName, addEdges.values, 'blue')
                graphImage = await fn.showGraph(subgraph, edgeColors)
                embed, _ = await fn.embed(
                    'Change whitelists?',
                    fullDescription,
                    'This can always be reversed.',
                    (graphImage, 'full'))

                return embed

            async def updateFile():

                nonlocal graphImage
                
                edgeColors = await fn.colorEdges(subgraph, originName, addEdges.values, 'blue')
                graphImage = await fn.showGraph(subgraph, edgeColors)
                return
            
            async def refreshMessage(interaction: discord.Interaction):
                
                await updateFile()
                embed = await refreshEmbed()
                await interaction.response.edit_message(
                    embed = embed,
                    file = discord.File(graphImage, filename = 'image.png'))

                return
            
            async def clearWhitelist(interaction: discord.Interaction):
                nonlocal clearing
                clearing = not clearing
                embed = await refreshEmbed()
                await interaction.response.edit_message(embed = embed)
                return 

            async def confirmEdges(interaction: discord.Interaction):

                await interaction.response.defer()

                #Screen for invalid submissions
                if await fn.noEdges(addEdges.values, interaction):
                    return

                if await fn.noChanges((addRoles.values or addPlayers.values or clearing), interaction):
                    return

                editedEdges = {}
                for destination in addEdges.values:
                    toNeighbor = guildData['edges'].pop((originName, destination), None)
                    fromNeighbor = guildData['edges'].pop((destination, originName), None)
                    if toNeighbor != None:
                        editedEdges[(originName, destination)] = {}
                    if fromNeighbor != None:
                        editedEdges[(destination, originName)] = {}
                
                if clearing:
                    description = '\n• Removed the whitelist(s).'
                    
                else:
                    
                    description = ''

                    if addRoles.values:
                        description += '\n• Edited the roles whitelist(s).'
                    if addPlayers.values:
                        description += '\n• Edited the people whitelist(s).'

                    allowedRoles = [role.id for role in addRoles.values]

                    for edgeName in editedEdges.keys():
                        if allowedRoles:
                            editedEdges[edgeName]['allowedRoles'] = allowedRoles
                            
                        if addPlayers.values:
                            editedEdges[edgeName]['allowedPeople'] = [int(ID) for ID in addPlayers.values]

                con = db.connectToGuild()
                guildData['edges'].update(editedEdges)
                db.updateGuild(con, guildData, interaction.guild_id)
                con.close()

                #Inform neighbors occupants and neighbor nodes
                neighborNodes = await fn.filterNodes(guildData['nodes'], addEdges.values)
                neighborMentions = await fn.mentionNodes(neighborNodes.values())
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"You feel like the way to **#{originName}** changed somehow.",
                    'Will it be easier to travel through, or harder?')
                nodeEmbed, _ = await fn.embed(
                    f'Edge with {originMention} changed.',
                    description,
                    'You can view its details with /edge allow.')
                for neighbor in neighborNodes.values():
                    await postToDirects(
                        playersEmbed, 
                        interaction.guild, 
                        neighbor['channelID'],
                        onlyOccs = True)
                    nodeChannel = get(interaction.guild.text_channels, id = neighbor['channelID'])
                    await nodeChannel.send(embed = nodeEmbed)

                #Inform edited node occupants
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"You notice that there's been in change in the way this place is connected to {neighborMentions}.",
                    "Perhaps you're only imagining it.")         
                await postToDirects(
                    playersEmbed, 
                    interaction.guild, 
                    guildData['nodes'][originName]['channelID'],
                    onlyOccs = True)

                #Inform own node                
                embed, _ = await fn.embed(
                    f'Edge(s) with {neighborMentions} changed.',
                    description,
                    'You can always undo these changes.') 
                nodeChannel = get(interaction.guild.text_channels, id = guildData['nodes'][originName]['channelID'])
                await nodeChannel.send(embed = embed)

                if interaction.channel.name in addEdges.values or interaction.channel.name == originName:
                    await interaction.delete_original_response()
                else:
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        view = None)    
                return

            view = discord.ui.View()
            view, addEdges = await fn.addEdges(ancestors, mutuals, successors, view, False, callback = refreshMessage)
            view, addRoles = await fn.addRoles(view, len(ctx.guild.roles), refresh = refreshEmbed)
            view, addPlayers = await fn.addPlayers(view, ctx.guild.members, members, refresh = refreshEmbed)
            view, submit = await fn.addSubmit(view, confirmEdges)
            if hasWhitelist:
                view, clear = await fn.addClear(view, clearWhitelist)
            view, cancel = await fn.addCancel(view)
            embed = await refreshEmbed()
            await updateFile()

            await ctx.respond(embed = embed,
                file = discord.File(graphImage, filename='image.png'),
                view = view,
                ephemeral = True)
            return
    
        result = await fn.identifyNodeChannel(guildData['nodes'], ctx.channel.name, origin)
        match result:
            case isMessage if isinstance(result, discord.Embed):
                await ctx.respond(embed = result)
            case isChannel if isinstance(result, str):
                await revisePermissions(result)
            case None:
    
                embed, _ = await fn.embed(
                    'Change allowances?',
                    "You can review edge whitelists three ways:\n\
                    • Call this command inside of a node channel.\n\
                    • Do `/edge allow #node-channel`.\n\
                    • Select a node channel with the list below.",
                    "This is just to select the origin, you'll see the edges next.")

                async def submitNodes(interaction: discord.Interaction):
                    await ctx.delete()
                    await revisePermissions(addNodes.values[0])
                    return

                view = discord.ui.View()    
                view, addNodes = await fn.addNodes(view, guildData['nodes'].keys(), submitNodes, manyNodes = False)
                view, cancel = await fn.addCancel(view)
                await ctx.respond(embed = embed, view = view)

        return

class serverCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    server = SlashCommandGroup(
        name = 'server',
        description = 'Manage the server as a whole.',
        guild_only = True)

    @server.command(
        name = 'clear',
        description = 'Delete all server data.')
    async def clear(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)
        
        guildData = oop.GuildData(ctx.guild_id)

        if not (guildData.nodes or guildData.players):
            
            embed, _ = await fn.embed(
                'No data to delete!',
                'Data is only made when you edit the graph or player count.',
                'Wish granted?')
            await ctx.respond(embed = embed)
            return
 
        async def deleteData(interaction: discord.Interaction):

            await fn.loading(interaction)

            global directListeners, indirectListeners

            directListeners, indirectListeners = await guildData.clear(
                ctx.guild,
                directListeners,
                indirectListeners)

            embed, _ = await fn.embed(
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

        view = oop.DialogueView()
        await view.addEvilConfirm(deleteData)
        await view.addCancel()
        embed, _ = await fn.embed(
            'Delete all data?',
            f"You're about to delete {len(guildData.nodes)} nodes" + \
                f" and {await guildData.edgeCount()} edges, alongside player data for {len(guildData.players)} people.",
            'This will also delete associated channels from the server.')

        await ctx.respond(embed = embed, view = view)
        return
    
    @server.command(
        name = 'view',
        description = 'View the entire graph or just a portion.')
    async def view(
        self,
        ctx: discord.ApplicationContext,
        node: discord.Option(
            str,
            'Specify a node to highlight?',
            autocomplete = fn.autocompleteNodes,
            required = False)):
        
        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        async def viewEgo(guildData: dict, centerName: str = None):

            graph = await guildData.toDict()

            #Nothing provided
            if not centerName:
                graphView = await guildData.toDict()
                embed, file = await fn.embed(
                    'Complete graph',
                    'Here is a view of every node and edge.',
                    'To view only a single node and its neighbors, use /server view #node.',
                    (graphView, 'full'))

                await ctx.respond(embed = embed, file = file, ephemeral = True)
                return

            #If something provided
            subgraph = nx.ego_graph(graph, centerName, radius = 99)
            graphView = await fn.showGraph(subgraph)

            nodeMention = f"<#{guildData['nodes'][centerName]['channelID']}>"
            embed, file = await fn.embed(
                f"{nodeMention}'s neighbors",
                "Here is the node, plus any neighbors.",
                'To view every node and edge, call /server view without the #node.',
                (graphView, 'full'))

            await ctx.respond(embed = embed, file = file, ephemeral = True)
            return
              
        result = await fn.identifyNodeChannel(guildData.nodes.keys(), node)
        match result:
            case isMessage if isinstance(result, discord.Embed):
                await ctx.respond(embed = result)
            case isChannel if isinstance(result, str):
                await viewEgo(guildData, result)
            case None:
                await viewEgo(guildData)

        return

    @server.command(
        name = 'fix',
        description = 'Fix certain issues with the server.')
    async def fix(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        allowedChannels = ['function', 'information', 'road-map', 'discussion', 'chat']
        deletingChannels = [channel for channel in ctx.guild.channels if channel.name not in allowedChannels]
        [await channel.delete() for channel in deletingChannels]

        return
    
        guildData, members = db.mag(ctx.guild_id)

        description = ''

        channelIDs = [channel.id for channel in ctx.guild.text_channels]
        channelNames = [channel.name for channel in ctx.guild.text_channels]

        ghostNodeMentions = []
        misnomerNodeMentions = []
        incorrectWebhooks = []

        if guildData['nodes']:
            nodesCategory = await fn.assertCategory(ctx.guild, 'nodes')
        for nodeName, nodeData in guildData['nodes'].items(): #Fix node issues

            if nodeData['channelID'] not in channelIDs: #Node was deleted in server only

                newNodeChannel = await fn.newChannel(ctx.guild, nodeName, nodesCategory)
                ghostNodeMentions.append(newNodeChannel.mention)
                guildData['nodes'][nodeName]['channelID'] = newNodeChannel.id

                whitelist = await fn.formatWhitelist(guildData['nodes'][nodeName].get('allowedRoles', []),
                    guildData['nodes'][nodeName].get('allowedPeople', []))
                embed, _ = await fn.embed(
                'Cool, new node...again.',
                f"**Important!** Don't mess with the settings for this channel! \
                    That means no editing the permissions, the name, and **no deleting** it. Use \
                    `/node delete`, or your network will (once more) be broken! \
                    \n\nAnyways, here's who is allowed:\n{whitelist}\n\n Of course, this can change \
                    with `/node review`, which lets you view/change the whitelist, among other things.",
                "You can also set the location message for this node by doing /node message while you're here.")         
                await newNodeChannel.send(embed = embed)
                continue

            newName = None
            if nodeName not in channelNames: #Node was renamed in server only
                
                nodeChannel = get(ctx.guild.text_channels, id = guildData['nodes'][nodeName]['channelID'])
                oldName = nodeName
                newName = nodeChannel.name

                misnomerNodeMentions.append(nodeChannel.mention)

                guildData['nodes'][newName] = guildData['nodes'].pop(oldName)
                for origin, destination in list(guildData['edges']):
                    if origin == oldName:
                        guildData['edges'][(newName, destination)] = guildData['edges'].pop((origin, destination))
                    if destination == oldName:
                        guildData['edges'][(origin, newName)] = guildData['edges'].pop((origin, destination))
            

            if newName:
                nodeChannel = get(ctx.guild.text_channels, id = guildData['nodes'][newName]['channelID'])
            else:
                nodeChannel = get(ctx.guild.text_channels, id = guildData['nodes'][nodeName]['channelID'])
            nodeWebhooks = await nodeChannel.webhooks()
            if len(nodeWebhooks) != 1:

                for webhook in nodeWebhooks:
                    await webhook.delete()

                await nodeChannel.create_webhook(name = 'Proximity')
                incorrectWebhooks.append(nodeChannel.mention)

        if ghostNodeMentions:
            description += f'\n• These nodes were deleted without using `/node delete`,\
            but were just regenerated: {await fn.listWords(ghostNodeMentions)}.'

        if misnomerNodeMentions:
            description += f'\n• Corrected the name(s) of the following channel(s) that were\
            renamed not using `/node review`: {await fn.listWords(misnomerNodeMentions)}.' 

        if incorrectWebhooks:
            description += f'\n• Fixed the webhook(s) for the following node channel(s):\
            {await fn.listWords(incorrectWebhooks)}.' 

        #Identify dead ends and isolates
        graph = await fn.makeGraph(guildData)
        noExits = {node for node, out_degree in graph.out_degree() if out_degree == 0}
        noEntrances = {node for node, in_degree in graph.in_degree() if in_degree == 0}

        noAccess = noExits.intersection(noEntrances)
        noExits -= noAccess
        noEntrances -= noAccess

        if noAccess:
            noAccessMentions = await fn.mentionNodes([guildData['nodes'][node] for node in noAccess])
            description += "\n• The following nodes have no edges for entry or exit, meaning" + \
                f" **players can only come or go through** `/player tp`**:** {noAccessMentions}."

        if noExits:
            noExitsMentions = await fn.mentionNodes([guildData['nodes'][node] for node in noExits])
            description += "\n• The following nodes have no edges for exiting, meaning" + \
                f" **players can get trapped:** {noExitsMentions}."

        if noEntrances:
            noEntrancesMentions = await fn.mentionNodes([guildData['nodes'][node] for node in noEntrances])
            description += "\n• The following nodes have no edges as entrances, meaning" + \
                f" **players will never enter:** {noEntrancesMentions}."

        con = db.connectToGuild()
        playerCon = db.connectToPlayer()
        noChannelMentions = []
        missingPlayers = []
        wrongWebhooks = []
        if members:
            playerCategory = await fn.assertCategory(ctx.guild, 'players')
        for member in list(members): #Identify player issues

            playerData = db.getPlayer(playerCon, member)
            serverData = playerData[str(ctx.guild_id)] 

            player = get(ctx.guild.members, id = member)
            if not player: #User left the server but is still considered a player
                oldChannel = await fn.deleteChannel(ctx.guild.text_channels, serverData['channelID'])
                if oldChannel:
                    missingPlayers.append(oldChannel.name)
                else:
                    missingPlayers.append('Channel-less Ex-player')

                lastLocation = serverData['locationName']
                lastKnownLocation = guildData['nodes'].get(lastLocation, None)
                if lastKnownLocation:
                    occupants = guildData['nodes'][lastLocation].get('occupants', None)
                    if occupants:
                        guildData['nodes']['locationName']['occupants'].pop(member)
                        if not guildData['nodes']['locationName']['occupants']:
                            del guildData['nodes']['locationName']['occupants']
                
                del playerData[str(ctx.guild_id)]
                db.updatePlayer(playerCon, playerData, member)

                members.remove(member)
                continue

            if serverData['channelID'] not in channelIDs: #User is missing their channel
                noChannelMentions.append(player.mention)

                newPlayerChannel = await fn.newChannel(ctx.guild, player.display_name, playerCategory, player)
                playerData[str(ctx.guild_id)]['channelID'] = newPlayerChannel.id
                db.updatePlayer(con, playerData, member)

                locationName = playerData[str(ctx.guild_id)]['locationName']
                
                embed, _ = await fn.embed(
                    f'Welcome.',
                    f"This is your very own channel, again, {player.mention}." + \
                    "\n• Speak to others by just talking in this chat. Anyone who can hear you" + \
                    " will see your messages pop up in their own player channel." + \
                    f"\n• You can `/look` around. You're at **{locationName}** right now." + \
                    "\n• Do `/map` to see the other places you can go." + \
                    "\n• ...And `/move` to go there." + \
                    "\n• You can`/eavesdrop` on people nearby room." + \
                    "\n• Other people can't see your `/commands`." + \
                    "\n• Tell the host not to accidentally delete your channel again.",
                    'You can always type /help to get more help.')
                await newPlayerChannel.send(embed = embed)
            
            playerChannel = get(ctx.guild.text_channels, id = serverData['channelID'])
            playerWebhooks = await playerChannel.webhooks()
            if len(playerWebhooks) != 1:

                for webhook in playerWebhooks:
                    await webhook.delete()

                await playerChannel.create_webhook(name = 'Proximity')
                wrongWebhooks.append(playerChannel.mention)

        db.updateGuild(con, guildData, ctx.guild_id)
        db.updateMembers(con, members, ctx.guild_id)
        con.close()
        playerCon.close()
        
        await queueRefresh(ctx.guild)

        if noChannelMentions:
            description += "\n• The following players got back their deleted player channels:" + \
                f" {await fn.listWords(noChannelMentions)}."

        if missingPlayers:
            description += f"\n• Deleted data and any remaining player channelsfor {len(missingPlayers)}" + \
                " players who left the server without ever being officially removed as players. My best guess" + \
                f" for the name(s) of those who left is {await fn.listWords(missingPlayers)}."

        if wrongWebhooks:
            description += "\n• Fixed the webhook(s) for the following player channel(s):" + \
                f" {await fn.listWords(wrongWebhooks)}."
     
        if not description:
            description += "Congratulations! This server has no detectable issues." + \
                "\n• There are no nodes missing a channel, none have been renamed" + \
                " improperly, and none are missing their webhook.\n• No dead end nodes" + \
                " or isolated nodes.\n• No players left the server and left behind data" + \
                " or a channel.\n• No players missing a channel or their webhook."

        embed, _ = await fn.embed(
        f'Server fix',
        description,
        'Be sure to check this whenever you have issues.')
        await ctx.respond(embed = embed)
        return
    
    @server.command(
        name = 'debug',
        description = 'View debug info for the server.')
    async def debug(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        embed = discord.Embed(
            title = 'Debug details',
            description = '(Mostly) complete look into what the databases hold.',
            color = discord.Color.from_rgb(67, 8, 69))

        embed.set_footer(text = 'Peer behind the veil.')

        guildDescription = ''
        guildDescription += f"\n• Guild ID: {ctx.guild_id}"
        guildDescription += f"\n• Nodes: "
        for index, node in enumerate(guildData.nodes.values()):
            guildDescription += f"\n{index}. {node.mention}"
            if node.allowedRoles or node.allowedPlayers:
                guildDescription += "\n-- Whitelist:" + \
                    f" {await oop.Format.whitelist(node.allowedRoles, node.allowedPlayers)}"
            if node.occupants:
                occupantMentions = await oop.Format.players(node.occupants)
                guildDescription += f'\n-- Occupants: {occupantMentions}'
            for neighbor in node.neighbors.keys():
                guildDescription += f'\n-- Neighbors: **#{neighbor}**'


        visitedNodes = set()
        for name, node in guildData.nodes.items():
            
            for neighbor, edge in node.neighbors.items():

                if neighbor in visitedNodes:
                    continue

                match edge.directionality:
                    case 0:
                        guildDescription += f"\n• {name} -> {neighbor}"
                        visited

                    case 1:
                        guildDescription += f"\n• {name} <-> {neighbor}"
                    
                    case 2:
                        guildDescription += f"\n• {neighbor} -> {name}"
                
            visitedNodes.add(name)

        embed.add_field(
            name = 'Server Data: guilds.guilds.db',
            value = guildDescription[:1000],
            inline = False)        
            
        memberDescription = f'\n• Players: {await oop.Format.players(guildData.players)}'

        embed.add_field(
            name = 'Player List: guilds.members.db',
            value = memberDescription,
            inline = False)
            
        
        player = oop.Player(ctx.author.id, ctx.guild_id)

        playerDescription = f'• Your User ID: {player.id}'
        playerDescription += f"\n• Server **{ctx.guild.name}**:"
        playerDescription += f"\n- Channel: {player.channelID}"
        playerDescription += f"\n- Location: {player.location}"
        playerDescription += f"\n- Eavesdropping: {player.eavesdropping}"

        embed.add_field(
            name = 'Player Data: players.db',
            value = playerDescription,
            inline = False)

        await ctx.respond(embed = embed)
        return
    
    @server.command(
        name = 'quick',
        description = 'Create a quick example graph.')
    async def quick(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        exampleNodes = ['the-kitchen', 'the-living-room', 'the-dining-room', 'the-bedroom']
                
        maker = oop.ChannelMaker(ctx.guild, 'nodes')
        await maker.initialize()
        for name in exampleNodes:

            if name in guildData.nodes:
                await guildData.deleteNode(name, ctx.guild.text_channels)

            newChannel = await maker.newChannel(name)
            await guildData.newNode(name, newChannel.id)


        newEdges = {
            ('the-kitchen', 'the-dining-room') : {},
            ('the-dining-room', 'the-kitchen') : {},
            ('the-living-room', 'the-dining-room') : {},
            ('the-dining-room', 'the-living-room') : {},
            ('the-dining-room', 'the-kitchen') : {},
            ('the-kitchen', 'the-dining-room') : {},
            ('the-living-room', 'the-bedroom') : {},
            ('the-bedroom', 'the-living-room') : {}}
        guildData['edges'].update(newEdges)
        db.updateGuild(con, guildData, ctx.guild_id)
        con.close()

        await guildData.save()

        embed, _ = await fn.embed(
            'Done.',
            "Made an example graph composed of a household layout. If there were any" + \
                " nodes/edges that were already present from a previous `/server quick` call," + \
                " they've been overwritten.",
            'Your other data is untouched.')

        await ctx.respond(embed = embed)
        return

class playerCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    player = SlashCommandGroup(
        name = 'player',
        description = "Manage players.",
        guild_only = True)

    @player.command(
        name = 'new',
        description = 'Add a new player to the server.')
    async def new(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        members = db.getMembers(con, ctx.guild_id)
        con.close()

        async def refreshEmbed():

            if addPeople.values:
                playerMentions = [person.mention for person in addPeople.values]
                description = f'Add {await fn.listWords(playerMentions)} to '
            else:
                description = 'Add who as a new player to '

            if addNodes.values:
                nodeName = addNodes.values[0]
                nodeData = guildData['nodes'][nodeName]
                description += f"<#{nodeData['channelID']}>?"
            else:
                description += 'which node?'

            embed, _ = await fn.embed(
                'New players?',
                description,
                "Just tell me where to put who.")
            return embed

        async def submitPlayers(interaction: discord.Interaction):

            nonlocal guildData

            await fn.loading(interaction)

            newPlayers = [person for person in addPeople.values if person.id not in members]

            if await fn.noNodes(addNodes.values, interaction):
                return

            if await fn.noPeople(newPlayers, interaction):
                return
                
            nodeName = addNodes.values[0]    
            playerCon = db.connectToPlayer()
            playerCategory = await fn.assertCategory(interaction.guild, 'players')
            for person in newPlayers:

                newPlayerChannel = await fn.newChannel(interaction.guild, person.name, playerCategory, person)
                embed, _ = await fn.embed(
                    f'Welcome.',
                    f"This is your very own channel, {person.mention}." + \
                    "\n• Speak to others by just talking in this chat. Anyone who can hear you" + \
                        "will see your messages pop up in their own player channel." + \
                    f"\n• You can `/look` around. You're at **#{nodeName}** right now." + \
                    "\n• Do `/map` to see the other places you can go." + \
                    "\n• ...And `/move` to go there." + \
                    "\n• You can`/eavesdrop` on people nearby room." + \
                    "\n• Other people can't ever see your `/commands`.",
                    'You can always type /help to get more help.')
                await newPlayerChannel.send(embed = embed)

                playerData = db.getPlayer(playerCon, person.id)
                playerData[str(interaction.guild_id)] = {
                    'channelID' : newPlayerChannel.id,
                    'locationName' : nodeName}
                db.updatePlayer(playerCon, playerData, person.id)
                members.append(person.id)
            playerCon.close()

            #Add the players to the guild nodes as occupants
            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)
            playerIDs = [player.id for player in newPlayers]
            guildData = await fn.addOccupants(
                guildData, 
                nodeName, 
                playerIDs)
            db.updateGuild(con, guildData, interaction.guild_id)
            db.updateMembers(con, members, interaction.guild_id)
            con.close()

            #Inform the node occupants
            playerMentions = await fn.mentionPlayers(playerIDs)
            playersEmbed, _ = await fn.embed(
                'A fresh face.',
                f"{playerMentions} is here.",
                'Perhaps you should greet them.')         
            await postToDirects(
                playersEmbed, 
                interaction.guild, 
                guildData['nodes'][nodeName]['channelID'],
                onlyOccs = True)

            #Inform own node                
            embed, _ = await fn.embed(
                'New player(s).',
                f'Added {playerMentions} to this node to begin their journey.',
                'You can view all players and where they are with /player find.') 
            nodeChannel = get(interaction.guild.text_channels, id = guildData['nodes'][nodeName]['channelID'])
            await nodeChannel.send(embed = embed)

            await queueRefresh(interaction.guild)

            description = f"Successfully added {playerMentions} to this server," + \
                    f" starting their journey at <#{guildData['nodes'][nodeName]['channelID']}>."

            existingPlayers = len(addPeople.values) - len(newPlayers)
            if existingPlayers:
                description += f"\n\nYou provided {existingPlayers} person(s) that are already in," + \
                    " so they got skipped. They're all players now, either way."          

            embed, _ = await fn.embed(
                'New player results.',
                description,
                'The more the merrier.')
            if interaction.channel.name == nodeName:
                await ctx.delete()
            else:
                await ctx.edit(
                    embed = embed,
                    view = None)
            return

        view = discord.ui.View() 
        view, addPeople = await fn.addPeople(view, ctx.guild.member_count, refresh = refreshEmbed)
        view, addNodes = await fn.addNodes(view, guildData['nodes'].keys(), refresh = refreshEmbed, manyNodes = False)
        view, submit = await fn.addSubmit(view, submitPlayers)
        view, cancel = await fn.addCancel(view)
        embed = await refreshEmbed()

        await ctx.respond(embed = embed, view = view)
        return
    
    @player.command(
        name = 'delete',
        description = 'Remove a player from the game (but not the server).')
    async def delete( #Rework this so it's like /tp such that it only sends one message per node
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData, members = db.mag(ctx.guild_id)

        async def refreshEmbed():

            if addPlayers.values:
                playerMentions = [f'<@{player}>' for player in addPlayers.values]
                description = f'Remove {await fn.listWords(playerMentions)} from the game?'
            else:
                description = "For all the players you list, this command will:" + \
                "\n• Delete their player channel(s).\n• Remove them as occupants in" + \
                " the locations they're in.\n• Remove their ability to play, returning" + \
                " them to the state they were in before they were added as a player." + \
                "\n\nIt will not:\n• Kick or ban them from the server.\n• Delete their" + \
                " messages."

            embed, _ = await fn.embed(
                'Delete player(s)?',
                description,
                "This won't remove them from the server.")
            return embed

        async def deletePlayers(interaction: discord.Interaction):

            await interaction.response.defer()

            if await fn.noPeople(addPlayers.values, interaction):
                return
                
            con = db.connectToGuild()

            #Screen players
            members = db.getMembers(con, interaction.guild_id)
            thinnerMembers = [member for member in members if str(member) not in addPlayers.values]
            db.updateMembers(con, thinnerMembers, interaction.guild_id)

            #Remove the players from the guild nodes as occupants
            guildData = db.getGuild(con, interaction.guild_id)

            playerCon = db.connectToPlayer()
            for playerID in addPlayers.values:
                playerID = int(playerID)
                playerData = db.getPlayer(playerCon, playerID)

                serverData = playerData[str(interaction.guild_id)]
                occupiedNode = serverData['locationName']
                
                guildData['nodes'][occupiedNode]['occupants'].remove(playerID)
                playerMention = f'<@{playerID}>'
                playerEmbed, _ = await fn.embed(
                    'Where did they go?',
                    f"You look around, but {playerMention} seems to have vanished into thin air.",
                    "You get the impression you won't be seeing them again.")         
                await postToDirects(playerEmbed, interaction.guild, guildData['nodes'][occupiedNode]['channelID'])

                #Inform own node                
                embed, _ = await fn.embed(
                    'Player deleted.',
                    f'{playerMention} has been removed from the game.',
                    'You can view all remaining players with /player find.') 
                nodeChannel = get(interaction.guild.text_channels, id = guildData['nodes'][occupiedNode]['channelID'])
                await nodeChannel.send(embed = embed)

                await fn.deleteChannel(interaction.guild.text_channels, serverData['channelID'])

                del playerData[str(interaction.guild_id)]
                db.updatePlayer(playerCon, playerData, playerID)
            playerCon.close()

            db.updateGuild(con, guildData, interaction.guild_id)
            con.close()

            await queueRefresh(interaction.guild)

            actualMentions = [f'<@{playerID}>' for playerID in addPlayers.values]
            description = f"Successfully removed {await fn.listWords(actualMentions)} from the game."

            embed, _ = await fn.embed(
                'Delete player results.',
                description,
                'Hasta la vista.')
            try:
                await interaction.followup.edit_message(
                    message_id = interaction.message.id,
                    embed = embed,
                    view = None)
            except:
                pass
            return

        view = discord.ui.View() 
        view, addPlayers = await fn.addPlayers(view, ctx.guild.members, members, refresh = refreshEmbed)
        view, confirm = await fn.addEvilConfirm(view, deletePlayers)
        view, cancel = await fn.addCancel(view)
        embed = await refreshEmbed()

        await ctx.respond(embed = embed, view = view)
        return
    
    @player.command(
        name = 'review',
        description = 'Change some player-specific data.')
    async def review(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData, members = db.mag(ctx.guild_id)

        if not members:
            embed, _ = await fn.embed(
            'But nobody came.',
            'There are no players, so nobody to locate.',
            'The title of this embed is a reference, by the way.')
            await ctx.respond(embed = embed)
            return

        if player:
            if player in members:
                playerIDs = [player.id]
            else:
                embed, _ = await embed(
                    f'{player.mention}?',
                    "But they aren't a player.",
                    'So how can they be located?')
                await ctx.edit(
                    embed = embed,
                    view = None)
                return
        else:
            playerIDs = members
                
        description = ''

        occupiedNodes = await fn.getOccupants(guildData['nodes'])
        for nodeName, occupantIDs in occupiedNodes.items():
            occupantMentions = [f'<@{occupantID}>' for occupantID in occupantIDs if occupantID in playerIDs]
            if occupantMentions:
                description += f"\n• <#{guildData['nodes'][nodeName]['channelID']}>: {await fn.listWords(occupantMentions)}"
                
        if not description:
            description = "• No players found. That's a big problem. Run `/server fix`."

        embed, _ = await fn.embed(
            'Find results',
            description,
            'Looked high and low.')
        await ctx.respond(embed = embed)
        return
    
    @player.command(
        name = 'find',
        description = 'Locate the players.')
    async def find(
        self,
        ctx: discord.ApplicationContext,
        player: discord.Option(
            discord.Member,
            description = 'Find anyone in particular?',
            default = None)):

        await ctx.defer(ephemeral = True)

        guildData, members = db.mag(ctx.guild_id)

        if not members:
            embed, _ = await fn.embed(
            'But nobody came.',
            'There are no players, so nobody to locate.',
            'The title of this embed is a reference, by the way.')
            await ctx.respond(embed = embed)
            return

        if player:
            if player in members:
                playerIDs = [player.id]
            else:
                embed, _ = await embed(
                    f'{player.mention}?',
                    "But they aren't a player.",
                    'So how can they be located?')
                await ctx.edit(
                    embed = embed,
                    view = None)
                return
        else:
            playerIDs = members
                
        description = ''

        occupiedNodes = await fn.getOccupants(guildData['nodes'])
        for nodeName, occupantIDs in occupiedNodes.items():
            occupantMentions = [f'<@{occupantID}>' for occupantID in occupantIDs if occupantID in playerIDs]
            if occupantMentions:
                description += f"\n• <#{guildData['nodes'][nodeName]['channelID']}>: {await fn.listWords(occupantMentions)}"
                
        if not description:
            description = "• No players found. That's a big problem. Run `/server fix`."

        embed, _ = await fn.embed(
            'Find results',
            description,
            'Looked high and low.')
        await ctx.respond(embed = embed)
        return
    
    @player.command(
        name = 'tp',
        description = 'Teleport the players.')
    async def teleport(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData, members = db.mag(ctx.guild_id)

        async def refreshEmbed():

            if addPlayers.values:
                playerMentions = [f'<@{ID}>' for ID in addPlayers.values]
                description = f'Teleport {await fn.listWords(playerMentions)} to '
            else:
                description = 'Teleport who to '

            if addNodes.values:
                nodeName = addNodes.values[0]
                nodeData = guildData['nodes'][nodeName]
                description += f"<#{nodeData['channelID']}>?"
            else:
                description += 'which node?'

            embed, _ = await fn.embed(
                'Teleport player(s)?',
                description,
                "Just tell me where to put who.")
            return embed

        async def teleportPlayers(interaction: discord.Interaction):

            await fn.waitForRefresh(interaction)

            nonlocal guildData

            if await fn.noNodes(addNodes.values, interaction, True):
                return
            
            if await fn.noPeople(addPlayers.values, interaction):
                return
                
            nodeName = addNodes.values[0]

            description = ''
            teleportingMentions = await fn.listWords([f'<@{ID}>' for ID in addPlayers.values])
            description += f"• Teleported {teleportingMentions} to" + \
                    f" <#{guildData['nodes'][nodeName]['channelID']}>."

            playerCon = db.connectToPlayer()
            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)

            exitingNodes = {}
            for ID in addPlayers.values:
                ID = int(ID)
                playerData = db.getPlayer(playerCon, ID)

                oldLocation = playerData[str(interaction.guild_id)]['locationName']
                guildData = await fn.removeOccupant(guildData, oldLocation, ID)

                oldChannelID = guildData['nodes'][oldLocation]['channelID']

                alreadyMoving = exitingNodes.setdefault(oldChannelID, [])
                exitingNodes[oldChannelID].append(ID)

                playerData[str(interaction.guild_id)]['locationName'] = nodeName
                playerData[str(interaction.guild_id)].pop('eavesdropping', None)
                db.updatePlayer(playerCon, playerData, ID)

            playerCon.close()

            #Add players to new location
            guildData = await fn.addOccupants(guildData, nodeName, [int(ID) for ID in addPlayers.values])
            db.updateGuild(con, guildData, interaction.guild_id)
            con.close()

            await queueRefresh(interaction.guild)

            for channelID, exitingPlayerIDs in exitingNodes.items():

                #Inform old location occupants
                playerMentions = await fn.mentionPlayers(exitingPlayerIDs)
                playersEmbed, _ = await fn.embed(
                    'Gone in a flash.',
                    f"{playerMentions} disappeared somewhere.",
                    "But where?")         
                await postToDirects(playersEmbed, interaction.guild, channelID, onlyOccs = True)

                #Inform old node                
                embed, _ = await fn.embed(
                    'Teleported player(s).',
                    f"Teleported {playerMentions} to **#{nodeName}**.",
                    'You can view all players and where they are with /player find.') 
                nodeChannel = get(interaction.guild.text_channels, id = channelID)
                await nodeChannel.send(embed = embed)
        
            #Inform new location occupants
            playersEmbed, _ = await fn.embed(
                'Woah.',
                f"{teleportingMentions} appeared in <#{guildData['nodes'][nodeName]['channelID']}>.",
                "Must have been relocated by someone else.")         
            await postToDirects(playersEmbed, interaction.guild, guildData['nodes'][nodeName]['channelID'])

            #Inform new node                
            embed, _ = await fn.embed(
                'Teleported player(s).',
                f"Teleported {playerMentions} to <#{guildData['nodes'][nodeName]['channelID']}>.",
                'You can view all players and where they are with /player find.') 
            nodeChannel = get(interaction.guild.text_channels, id = guildData['nodes'][nodeName]['channelID'])
            webhook = (await nodeChannel.webhooks())[0]
            await webhook.send(embed = embed)

            embed, _ = await fn.embed(
                'Teleport results.',
                description,
                'Woosh.')
            await interaction.followup.edit_message(
                message_id = interaction.message.id,
                embed = embed,
                view = None)
            return

        view = discord.ui.View()
        view, addPlayers = await fn.addPlayers(view, ctx.guild.members, members, refresh = refreshEmbed)
        view, addNodes = await fn.addNodes(view, guildData['nodes'].keys(), refresh = refreshEmbed, manyNodes = False)
        view, submit = await fn.addSubmit(view, teleportPlayers)
        view, cancel = await fn.addCancel(view)
        embed = await refreshEmbed()
        await ctx.respond(embed = embed, view = view)
        return

class freeCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot
        self.updateListeners.start()

    def cog_unload(self):
        self.updateListeners.cancel()

    @commands.slash_command(
        name = 'help',
        description = 'Basic help.')
    async def help(
        self,
        ctx: discord.ApplicationContext,
        word: discord.Option(
            str,
            'Get help on a specific term?',
            required = False)):

        await ctx.defer(ephemeral = True)
        word = word.lower() if word else ''
        if word:

            allHelp = {
                'graph' : "A __graph__ (a.k.a. __network__), is a math thing: basically, there's\
                    dots (__nodes__) and there may or may not be connections between those dots\
                    (__edges__). That's basically it.\n\nFor us, though, all that matters is that\
                    __nodes__ are __locations__ and __edges__ are connections between them.",
                'network' : "See __graph__.",
                'node' : "A __node__ is a dot on a __graph__. If it's connected to any other\
                __node__s, that's called an __edge__. For us, a \"__node__\" has a couple things--\
                the __location__ is represents, the __permissions__ for it, and the Discord channel\
                for that __node__, which isn't visible to the players.",
                'location' : "The actual place represented by a __node__, like a kitchen. These\
                must be big enough to fit the __player__s, and small enough that anyone in one part of\
                the node can reasonably be expected to hear/see anything in any other part of the\
                __location__. Every __player__ is located in some __location__ at any point in time.",
                'permissions' : "Who's allowed to travel into/through a __node__ or an __edge__.\
                This mostly affects __movement__, where a __player__ is denied access to a place\
                because there's no route to their destination after accounting for their __permissions__.",
                'edges' : "Connections between __node__s on a __graph__. Any time two __locations__ are\
                connected for __movement__ or __sound__, an __edge__ should exist. Usually a door,\
                but it can be a hallway, bridge, elevator, portal... Can only let people through who\
                satisfy the __permissions__, but sound can travel freely.",
                'movement' : "The way that __player__s change which __location__ along the __graph__\
                their __presence__ is in. When they try to move to a new __location__, they need a\
                path along the __edges__ from where they are to their destination __node__, such that\
                they have permission to access every node and edge along the way.",
                'presence' : "The __location__ that a __player__ will hear all __sound__ in. Anytime\
                someone speaks in the same __location__, the __player__s who are present will hear.\
                __Presence__ also means that you'll see everyone in a room when you walk in, and\
                they'll see you.",
                'sound' : "Everything that __player__s are notified of. Includes everything spoken\
                by a __player__ in the same __location__, but may include __indirect__ sound from\
                __neighbor__ __node__s. Note that you trasmit all the same kind of noise as they do.",
                'indirect' : "As opposed to __sound__ that is __direct__, __indirect__ sound can only\
                by faintly made out, and only voices or small segments of the speech may be heard.\
                __Indirect__ sound is usually heard through __edges__ to __neighbor__ __nodes__,\
                and can be heard __direct__ly by __eavesdropping__.",
                'direct' : "As opposed to __sound__ that is __indirect__, __direct__ sound can be\
                fully heard, including identifying the speaker and what they're saying. Usually heard\
                through the __player__ being in the same __location__ as the speaker, or by __eavesdropping__.",
                'neighbor' : "A __node__ that is connected to another __node__ along one of its __edges__.\
                Fun fact: if a __node__ has an edge that points *to* another one, and it's only one-way,\
                they're not technically neighbors (even though this `/help` command defines them as such).\
                Instead, the origin would be the \"ancestor\" and the destination would be its \"successor.\"",
                'player' : 'People who have __presence__ at a __location__, can hear __sound__ from __node__s\
                they __neighbor__ as well as from other people in the same place. Capable of __movement__\
                and __eavesdropping__. In short, everyone who is placed in the __graph__.',
                'underlined' : "What-- no, \"__underlined__\" was so you can see what an __underlined__\
                word looked like, you're not supposed to actually search it. Goof."}
            
            if word in allHelp:
                embed, _ = await fn.embed(
                f'Help for "{word}"',
                allHelp[word],
                "Clear things up, I hope?")
            else:
                embed, _ = await fn.embed(
                f'What was that?',
                f"I'm sorry. I have a glossay for {len(allHelp)} words, but not for that.\
                Perhaps start with the tutorials with just a standard `/help` and go from there.",
                "Sorry I couldn't do more.")

                await ctx.respond(embed = embed)
                return

        tutorialName = None
        tutorialData = None
        tutorialPictures = {}

        async def playerTutorial(interaction: discord.Interaction):
            nonlocal tutorialName, tutorialData
            tutorialName = 'Player Tutorial, Page'
            tutorialData = {'Intro' : "Welcome, this guide" + \
                                    " will tell you everything you need to know as" + \
                                    " a player. Let's begin.",
                            'Player Channels': "Players have their own channel" + \
                                    " for roleplaying. All speech and movement, etc, is" + \
                                    " done through there.",
                            'Locations': "Your character exists in some location." + \
                                    " You can check where you are with `/look`.",
                            'Movement': "You can `/move` to a new place. Certain" + \
                                    " places or routes might have limits on who's allowed" + \
                                    " in.",
                            'Visibility': "You're able to see people in the same" + \
                                    " location as you, even if they're only passing by.",
                            'Sound': "Normally, you can only hear people in the" + \
                                    " same location as you, and vice versa.",
                            'Eavesdropping': "If you want, you can `/eavesdrop` on" + \
                                    " people in a location next to you to hear what's going on.",
                            'Fin': "And that's about it! Enjoy the game."}
            
            if interaction.guild_id:
                guildData = db.gd(interaction.guild_id)
                con = db.connectToPlayer()
                playerData = db.getPlayer(con, interaction.user.id)
                con.close()
                serverData = playerData.get(str(interaction.guild_id), None)
                if serverData:
                    tutorialData['Player Channels'] += f" You're a" + \
                        " player in this server, so you'll use" + \
                        f" <#{serverData['channelID']}>."
                    tutorialData['Locations'] += f" Right now, you're" + \
                        f" in **#{serverData['locationName']}**."
                
            await displayTutorial(interaction = interaction)
            return
        
        async def hostTutorial(interaction: discord.Interaction):
            nonlocal tutorialName, tutorialData, tutorialPictures
            tutorialName = 'Host Tutorial, Page'
            tutorialData = {'Intro': "Buckle up, this guide is" + \
                                " a little longer than the Player one. I trust" + \
                                " you brought snacks. Let's begin.",
                            'The Goal': "I let the players move around" + \
                                    " between places, so your job is to tell me" + \
                                    " what the places are and how players can" + \
                                    " move around between them.",
                            'Nodes': "Locations that the players" + \
                                " can go inside are called nodes. Nodes should" + \
                                " be about the size of a room. Use `/node new`" + \
                                " to make them.",
                            'Edges': "Edges are the connections between nodes." + \
                                " An edge just means that there is a direct path" + \
                                " between two nodes that you can walk through. Maybe it's" + \
                                " a doorway or a bridge. Use `/edge new` to connect nodes.",
                            'Graph': "You can view a map of every node and the" + \
                                " edges between them. That's called a 'graph'. Nodes" + \
                                " are shown as just their name and the edges are" + \
                                " shown as arrows between them. Look at the graph" + \
                                " with `/server view`.",
                            'Quick Start': "If you want an example of a graph," + \
                                    " you can do `/server quick` to make a little house." + \
                                    " You can clear out the graph and the player data with" + \
                                    " `/server clear`.",
                            'Players': "Once you have somewhere to put the players," + \
                                " use `/player new` to add them to the game. You can also" + \
                                " move them with `/player tp` or find them with `/player find`.",
                            'Fixing': "If you mess with the channels, or if players leave," + \
                                " if might break the bot causing certain features not to work. Use" + \
                                " `/server fix` to automatically fix common issues.",
                            'Fin': "That's about all--you can figure the rest out. If you" + \
                                " have any issues or improvements to suggest, just let **davidlancaster**" + \
                                " know. Enjoy! :)"}
            tutorialPictures = {}
                # 'The Goal' : 'assets/overview.png',
                # 'Nodes' : 'assets/nodeExample.png',
                # 'Edges' : 'assets/edgeExample.png',
                # 'Graph' : 'assets/edgeIllustrated.png'}
            
            await displayTutorial(interaction = interaction)
            return

        async def displayTutorial(interaction: discord.Interaction):

            await interaction.response.defer()

            pageCount = 0

            async def refreshEmbed():

                nonlocal pageCount

                totalPages = len(tutorialData)
                embedTitle = interaction.message.embeds[0].title
                if embedTitle == 'Hello!':
                    pass
                else:
                    pageCount = embedTitle.split()[3]

                pages = list(tutorialData.items())

                title = f'{tutorialName} {pageCount + 1}: {pages[pageCount][0]}'

                description = pages[pageCount][1]

                picture = tutorialPictures.get(pages[pageCount][0], None)
                pictureView = (picture, 'full') if picture else None

                embed, file = await fn.embed(
                    title,
                    description,
                    'Use the buttons below to flip the page.',
                    pictureView)

                return embed, file
            
            async def refreshMessage(interaction: discord.Interaction):

                embed, file = await refreshEmbed()    
                totalPages = len(tutorialData)

                async def calculateLit(pageNumber: int):

                    leftLit = False
                    if pageNumber > 0:
                        leftLit = True

                    rightLit = False
                    if pageNumber < totalPages - 1:
                        rightLit = True

                    return leftLit, rightLit

                leftLit, rightLit = await calculateLit(pageCount)
                leftCallback = reducePageCount if leftLit else None
                rightCallback = increasePageCount if rightLit else None

                if pageCount < 1:
                    lastLeft, lastRight = True, totalPages > 1
                elif pageCount == totalPages - 2:
                    lastLeft, lastRight = pageCount < 1, False
                else:
                    lastLeft, lastRight = await calculateLit(pageCount - 1)
                leftChanged = lastLeft != leftLit
                rightChanged = lastRight != rightLit
                
                if leftChanged or rightChanged:
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        file = file if file else discord.MISSING,
                        view = await fn.addArrows(leftCallback, rightCallback))
                else:
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        attachments = discord.MISSING)
                    
                return

            async def increasePageCount(interaction: discord.Interaction):

                await interaction.response.defer()

                nonlocal pageCount
                pageCount += 1
                await refreshMessage(interaction)
                return
            
            async def reducePageCount(interaction: discord.Interaction):

                await interaction.response.defer()

                nonlocal pageCount
                pageCount -= 1
                await refreshMessage(interaction)
                return
            
            await refreshMessage(interaction = interaction)
            return

        embed, _ = await fn.embed(
        'Hello!',
        "This command will help you learn what the bot does and how it" + \
            " can be used. Additionally, if you want to learn more about any" + \
            " __underlined__ words I use, just say `/help (underlined word)`.",
        "I'll be here if/when you need me.")

        view = discord.ui.View()
        playerHelp = discord.ui.Button(
            label = 'Help for Players',
            style = discord.ButtonStyle.success)
        playerHelp.callback = playerTutorial
        view.add_item(playerHelp)
        hostHelp = discord.ui.Button(
            label = 'Help for Hosts',
            style = discord.ButtonStyle.success)
        hostHelp.callback = hostTutorial
        view.add_item(hostHelp)

        await ctx.respond(embed = embed, view = view)
        return

    # @commands.slash_command(
    #     name = 'inventory',
    #     description = 'Here.')
    # async def inventory(
    #     self,
    #     ctx: discord.ApplicationContext):

    #     embed, file = await fn.embed(
    #         'Inventory',
    #         "Looks like you have a lot of room for items.",
    #         "Just as an example.",
    #         ('assets/mockup.png', 'full'))

    #     view = discord.ui.View()
    #     button = discord.ui.Button(
    #         label = '.',
    #         style = discord.ButtonStyle.secondary,
    #         disabled = True)
    #     view.add_item(button)
    #     button = discord.ui.Button(
    #         label = '^',
    #         style = discord.ButtonStyle.secondary)
    #     view.add_item(button)
    #     button = discord.ui.Button(
    #         label = '.',
    #         style = discord.ButtonStyle.secondary,
    #         disabled = True)
    #     view.add_item(button)
    #     button = discord.ui.Button(
    #         label = '↪️',
    #         style = discord.ButtonStyle.secondary)
    #     view.add_item(button)
    #     button = discord.ui.Button(
    #         label = '↩️',
    #         style = discord.ButtonStyle.secondary)
    #     view.add_item(button)

    #     button = discord.ui.Button(
    #         label = '<',
    #         style = discord.ButtonStyle.secondary)
    #     view.add_item(button)
    #     button = discord.ui.Button(
    #         label = '🟢',
    #         style = discord.ButtonStyle.secondary)
    #     view.add_item(button)
    #     button = discord.ui.Button(
    #         label = '>',
    #         style = discord.ButtonStyle.secondary)
    #     view.add_item(button)
    #     button = discord.ui.Button(
    #         label = '.',
    #         style = discord.ButtonStyle.secondary,
    #         disabled = True)
    #     view.add_item(button)
    #     button = discord.ui.Button(
    #         label = '.',
    #         style = discord.ButtonStyle.secondary,
    #         disabled = True)
    #     view.add_item(button)

    #     button = discord.ui.Button(
    #         label = '.',
    #         style = discord.ButtonStyle.secondary,
    #         disabled = True)
    #     view.add_item(button)
    #     button = discord.ui.Button(
    #         label = 'v',
    #         style = discord.ButtonStyle.secondary)
    #     view.add_item(button)
    #     button = discord.ui.Button(
    #         label = '.',
    #         style = discord.ButtonStyle.secondary,
    #         disabled = True)
    #     view.add_item(button)
    #     button = discord.ui.Button(
    #         label = '✅',
    #         style = discord.ButtonStyle.secondary)
    #     view.add_item(button)
    #     button = discord.ui.Button(
    #         label = '❌',
    #         style = discord.ButtonStyle.secondary)
    #     view.add_item(button)

    #     await ctx.respond(embed = embed, view = view, file = file, ephemeral = True)
    #     return


    @tasks.loop(seconds = 5.0)
    async def updateListeners(self):

        return

        con = None
        if needingUpdate:
            con = db.connectToGuild()
        # else:
        #     print(f'No change to {len(directListeners)} directs and {len(indirectListeners)} indirects.')

        for guild in list(needingUpdate):

            guildStartTime = time.time()
            
            guildData = db.getGuild(con, guild.id)
            members = db.getMembers(con, guild.id)
            graph = await fn.makeGraph(guildData)
            guildListeners = {}
            guildIndirects = {}

            cachedChannelReferences = {}
            cachedPlayerData = {}

            async def addListener(speaker: int, listener: discord.TextChannel, eavesdropping: bool = False):

                allListeners = guildListeners.get(speaker, [])
                allListeners.append((listener, eavesdropping))
                guildListeners[speaker] = allListeners
                return
            
            async def addIndirect(speaker: int, speakerLocation: str, listener: discord.TextChannel):

                allListeners = guildIndirects.get(speaker, [])
                allListeners.append((speakerLocation, listener))
                guildIndirects[speaker] = allListeners
                return

            async def channelLoad(channelID: int):

                if channelID in cachedChannelReferences:
                    channel = cachedChannelReferences[channelID]
                else:
                    channel = await get_or_fetch(guild, 'channel', channelID)
                    cachedChannelReferences[channelID] = channel

                return channel

            async def playerLoad(playerID: int):

                if playerID in cachedPlayerData:
                    serverData = cachedPlayerData[playerID]

                else:
                    playerData = db.getPlayer(playerCon, playerID)
                    serverData = playerData[str(guild.id)]
                    cachedPlayerData[playerID] = serverData

                return serverData

            playerCon = db.connectToPlayer()
            
            for member in members:

                playerData = await playerLoad(member)
                playerChannelID = playerData['channelID']
                directListeners.pop(playerChannelID, None)
                indirectListeners.pop(playerChannelID, None)

            for nodeName, nodeData in guildData['nodes'].items(): #For every node in the graph

                #Get node channel
                nodeChannelID = nodeData['channelID']
                nodeChannel = await channelLoad(nodeData['channelID'])

                #Get node neighbors
                neighborNodes = await fn.getConnections(graph, [nodeName])

                for ID in nodeData.get('occupants', []): #For each occupant...

                    playerData = await playerLoad(ID)
                    await addListener(playerData['channelID'], nodeChannel) #Add node channel as listeners to occupant

                    playerChannel = await channelLoad(playerData['channelID'])
                    await addListener(nodeData['channelID'], playerChannel) #Add occupant as listeners to own node

                    for occupant in nodeData['occupants']: #For every occupant...

                        if occupant != ID: #That isn't yourself...
                            occData = await playerLoad(occupant)
                            await addListener(occData['channelID'], playerChannel) #Add them as a listener to you.

                    for neighborName in neighborNodes: #For every neighbor node...

                        neighborOccupants = guildData['nodes'][neighborName].get('occupants', [])

                        for neighborOccupant in neighborOccupants: #For every person in the neighbor node...

                            NOdata = await playerLoad(neighborOccupant)
                            NOchannel = await channelLoad(NOdata['channelID'])

                            if NOdata.get('eavesdropping', None) == nodeName: #If they're eavesdropping on us...
                                await addListener(playerData['channelID'], NOchannel, True)
                                await addListener(nodeData['channelID'], NOchannel, True)
                            else: #Otherwise...
                                await addIndirect(playerData['channelID'], playerData['locationName'], NOchannel)

            directListeners.update(guildListeners)
            indirectListeners.update(guildIndirects)

            needingUpdate.remove(guild)
            updatedGuilds.add(guild.id)
            print(f"Updated {guild.name}'s listeners in {time.time() - guildStartTime} seconds.")

        if con:

            #import json
            #printableListeners = {speakerID : [channel.name for channel, _ in listeners] 
            #    for speakerID, listeners in directListeners.items()}
            #print(f"Direct listeners: {json.dumps(printableListeners, indent = 4)}")

            con.close()

        return

class guildCommands(commands.Cog): 

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    @commands.slash_command(
        name = 'look',
        description = 'Look around your location.',
        guild_only = True)
    async def look(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData, members = db.mag(ctx.guild_id)

        if await fn.notPlayer(ctx, members):
            return

        con = db.connectToPlayer()
        playerData = db.getPlayer(con, ctx.author.id)
        con.close()

        nodeName = playerData[str(ctx.guild_id)]['locationName']
        nodeData = guildData['nodes'][nodeName]

        description = ''

        nodeData['occupants'].remove(ctx.author.id)
        if nodeData['occupants']:
            occupantMentions = [f'<@{occupant}>' for occupant in nodeData['occupants']]
            description += f"There's {await fn.listWords(occupantMentions)} with you inside **#{nodeName}**."
        else:
            description += f"You're by yourself inside **#{nodeName}**. "

        graph = await fn.makeGraph(guildData)
        ancestors, mutuals, successors = await fn.getConnections(graph, [nodeName], True)

        if ancestors:
            if len(ancestors) > 1:
                boldedNodes = await fn.boldNodes(ancestors)
                description += f" There are one-way routes from (<-) {boldedNodes}. "
            else:
                description += f" There's a one-way route from (<-) **#{ancestors[0]}**. "

        if successors:
            if len(successors) > 1:
                boldedNodes = await fn.boldNodes(successors)
                description += f" There are one-way routes to (->) {boldedNodes}. "
            else:
                description += f" There's a one-way route to (->) **#{successors[0]}**. "

        if mutuals:
            if len(mutuals) > 1:
                boldedNodes = await fn.boldNodes(mutuals)
                description += f" There's ways to {boldedNodes} from here. "
            else:
                description += f" There's a way to get to **#{mutuals[0]}** from here. "
        
        if not (ancestors or mutuals or successors):
            description += "There's no way in or out of here."

        embed, _ = await fn.embed(
            'Looking around...',
            description,
            'You can /eavesdrop on a nearby location.')
        await ctx.respond(embed = embed)
        return

    @commands.slash_command(
        name = 'eavesdrop',
        description = 'Listen in on a nearby location.',
        guild_only = True)
    async def eavesdrop(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData, members = db.mag(ctx.guild_id)

        if await fn.notPlayer(ctx, members):
            return
        
        con = db.connectToPlayer()
        playerData = db.getPlayer(con, ctx.author.id)
        serverData = playerData[str(ctx.guild_id)]
        con.close()

        eavesdroppingNode = serverData.get('eavesdropping', None)
        if eavesdroppingNode: #Breaking glitch here if the node you're eavesdropping on is deleted!
            occupants = guildData['nodes'][eavesdroppingNode].get('occupants', False)
            if occupants:
                occupantMentions = await fn.listWords([f'<@{ID}>' for ID in occupants])
                description = f"You're eavesdropping on {occupantMentions} in **#{eavesdroppingNode}**."
            else:
                description = f"You're eavesdropping on **#{eavesdroppingNode}**, but you think nobody is there."

            async def stopEavesdropping(interaction: discord.Interaction):

                await fn.waitForRefresh(interaction)
                
                con = db.connectToPlayer()
                del playerData[str(ctx.guild_id)]['eavesdropping']
                db.updatePlayer(con, playerData, ctx.author.id)
                con.close()

                await queueRefresh(interaction.guild)

                embed, _ = await fn.embed(
                    'Saw that.',
                    f"You notice {ctx.author.mention} play it off like they weren't just listening in on **#{eavesdroppingNode}**.",
                    'Do with that what you will.')
                await postToDirects(
                    embed, 
                    interaction.guild, 
                    guildData['nodes'][serverData['locationName']]['channelID'], 
                    serverData['channelID'],
                    onlyOccs = True)

                embed, _ = await fn.embed(
                    'All done.',
                    "You're minding your own business, for now.",
                    'You can always choose to eavesdrop again later.')
                await ctx.edit(embed = embed, view = None)
                return

            view = discord.ui.View()
            view, confirm = await fn.addEvilConfirm(view, callback = stopEavesdropping)
            view, cancel = await fn.addCancel(view)
            embed, _ = await fn.embed(
                'Nosy.',
                description,
                'Would you like to stop eavesdropping?')
            await ctx.respond(embed = embed, view = view)
            return

        graph = await fn.makeGraph(guildData)
        nodeName = playerData[str(ctx.guild_id)]['locationName']
        neighbors = await fn.getConnections(graph, [nodeName])
        selectedNode = None
        userNodes = None

        if neighbors:
            neighborNodes = await fn.filterNodes(guildData['nodes'], neighbors)
            occupiedNeighbors = await fn.getOccupants(neighborNodes)
            if occupiedNeighbors:
                description = 'Listening closely, you think that you can hear '
                fullList = []
                for neighborNodeName, occupants in occupiedNeighbors.items():
                    occupantMentions = await fn.listWords([f'<@{ID}>' for ID in occupants])
                    fullList.append(f'{occupantMentions} in **#{neighborNodeName}**')
                description += f'{await fn.listWords(fullList)}. '
                unoccupiedNeighbors = [neighbor for neighbor in neighbors if neighbor not in occupiedNeighbors]
                if unoccupiedNeighbors:
                    boldedUnoccupied = await fn.boldNodes(unoccupiedNeighbors)
                    description += f"You can also listen in on {boldedUnoccupied}, but it sounds like nobody is in there."
            else:
                boldedNeighbors = await fn.boldNodes(neighbors)
                description = f"You're able to listen in on {boldedNeighbors} from here," + \
                    " but you don't hear anyone over there. "
        else:
            description = "If there was someplace nearby, you could listen in on it, but" + \
                " there's nowhere nearby here. Wait, does that mean you're stuck here?"

        async def refreshEmbed():

            nonlocal selectedNode, description

            if userNodes.values:
                selectedNode = userNodes.values[0]
            else:
                selectedNode = None

            fullDescription = description
            if selectedNode:
                fullDescription = f'Eavesdrop on **#{selectedNode}**?'

            embed, _ = await fn.embed(
                'Eavesdrop?',
                fullDescription,
                'You can listen in on any place near you.')

            return embed

        async def submitEavesdrop(interaction: discord.Interaction):

            await fn.waitForRefresh(interaction)

            if not userNodes.values:
                embed, _ = await fn.embed(
                    'Eavesdrop where?',
                    'You have to tell me where you would like to eavesdrop.',
                    'Try calling /eavesdrop again.')
                await interaction.followup.edit_message(
                    message_id = interaction.message.id,
                    embed = embed,
                    view = None)
                return
                
            con = db.connectToPlayer()
            playerData[str(ctx.guild_id)]['eavesdropping'] = userNodes.values[0]
            db.updatePlayer(con, playerData, ctx.author.id)
            con.close()

            await queueRefresh(interaction.guild)

            embed, _ = await fn.embed(
                'Sneaky.',
                f"You notice {ctx.author.mention} start to listen in on **#{userNodes.values[0]}**.",
                'Do with that what you will.')
            await postToDirects(embed, interaction.guild, guildData['nodes'][nodeName]['channelID'], serverData['channelID'])

            embed, _ = await fn.embed(
                'Listening close...',
                f"Let's hear what's going on over there in **#{userNodes.values[0]}**, shall we?",
                "Be mindful that people can see that you're doing this.")
            await interaction.followup.edit_message(
                message_id = interaction.message.id,
                embed = embed,
                view = None)
            return

        view = discord.ui.View()
        if neighbors:
            view, userNodes = await fn.addUserNodes(view, neighbors, refresh = refreshEmbed)
            view, submit = await fn.addSubmit(view, submitEavesdrop)
            view, cancel = await fn.addCancel(view)
        embed = await refreshEmbed()
        await ctx.respond(embed = embed, view = view)
        return

    @commands.slash_command(
        name = 'map',
        description = 'See where you can go.',
        guild_only = True)
    async def map(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData, members = db.mag(ctx.guild_id)

        if await fn.notPlayer(ctx, members):
            return
        
        con = db.connectToPlayer()
        playerData = db.getPlayer(con, ctx.author.id)
        serverData = playerData[str(ctx.guild_id)]
        con.close()

        playerRoleIDs = [role.id for role in ctx.author.roles]

        playerGraph = await fn.filterMap(
            guildData, 
            ctx.author.roles, 
            ctx.author.id, 
            serverData['locationName'])
        playerMap = await fn.showGraph(playerGraph)

        embed, file = await fn.embed(
            'Map',
            f"Here are all the places you can reach from **#{serverData['locationName']}**." + \
                " You can travel along the arrows that point to where you want to go. ",
            "Use /move to go there.",
            (playerMap, 'full'))
        
        await ctx.respond(embed = embed, file = file)
        return

    @commands.slash_command(
        name = 'move',
        description = 'Go someplace new.',
        guild_only = True)
    async def move(
        self,
        ctx: discord.ApplicationContext,
        node: discord.Option(
            str,
            "Name where you would like to go?",
            autocomplete = fn.autocompleteMap,
            required = False)):

        await ctx.defer(ephemeral = True)

        guildData, members = db.mag(ctx.guild_id)

        if await fn.notPlayer(ctx, members):
            return

        con = db.connectToPlayer()
        playerData = db.getPlayer(con, ctx.author.id)
        serverData = playerData[str(ctx.guild_id)]
        con.close()

        playerRoleIDs = [role.id for role in ctx.author.roles]
        playerGraph = await fn.filterMap(
            guildData,
            ctx.author.roles,
            ctx.author.id,
            serverData['locationName'])

        description = f"Move from **#{serverData['locationName']}**"
        userNodes = None
        selectedNode = node if node and node != serverData['locationName'] else None

        async def refreshMessage():

            nonlocal userNodes, selectedNode

            view = discord.ui.View()

            fullDescription = description
            if userNodes:
                view.add_item(userNodes)
                selectedNode = userNodes.values[0]
            else:
                view, userNodes = await fn.addUserNodes(
                    view, 
                    [node for node in playerGraph.nodes if node != serverData['locationName']], 
                    callback = callRefresh)
            
            if selectedNode:
                fullDescription += f' to **#{selectedNode}**?'
                view, submit = await fn.addSubmit(view, submitDestination)
                view, cancel = await fn.addCancel(view)
            else:
                fullDescription += f'? Where would you like to go?'

            embed, _ = await fn.embed(
                'Move?',
                fullDescription,
                "Bear in mind that others will notice.")
            return embed, view

        async def callRefresh(interaction: discord.Interaction):
            embed, view = await refreshMessage()
            await interaction.response.edit_message(embed = embed, view = view)
            return

        async def submitDestination(interaction: discord.Interaction):

            await fn.waitForRefresh(interaction)

            nonlocal serverData, playerData, guildData

            path = nx.shortest_path(playerGraph,
                source = serverData['locationName'],
                target = selectedNode)

            graph = await fn.makeGraph(guildData)
            allAdjacents = await fn.getConnections(graph, path)
            nonPathAdjacents = [nodeName for nodeName in allAdjacents if nodeName not in path]
            nonPathAdjNodes = await fn.filterNodes(guildData['nodes'], nonPathAdjacents)
            nearbyOccs = await fn.getUnifiedOccupants(nonPathAdjNodes.values())

            playerCon = db.connectToPlayer()
            for occupant in nearbyOccs:
                eavesPlayer = db.getPlayer(playerCon, occupant)
                eavesData = eavesPlayer[str(interaction.guild_id)]
                eavesDroppingName = eavesData.get('eavesdropping', None)
                if eavesDroppingName in path:
                    whichPart = path.index(eavesDroppingName)
                    eavesdropperChannel = get(interaction.guild.text_channels, id = eavesData['channelID'])

                    match whichPart:

                        case 0:
                            embed, _ = await fn.embed(
                                'Someone got moving.',
                                f"You can hear someone in **#{path[whichPart]}** start" + \
                                    f" to go towards **#{path[whichPart + 1]}**.",
                                'Who could it be?')
                            await eavesdropperChannel.send(embed = embed)

                        case halfway if whichPart < len(path):
                            embed, _ = await fn.embed(
                                'Someone passed through.',
                                f"You can hear someone go through **#{path[whichPart]}**,\
                                from **#{path[whichPart - 1]}** to **#{path[whichPart + 1]}**.",
                                'On the move.')
                            await eavesdropperChannel.send(embed = embed)

                        case ending if whichPart == len(path) - 1:
                            embed, _ = await fn.embed(
                                'Someone stopped by.',
                                f"You can hear someone come from **#{path[whichPart - 1]}**" +
                                    f" and stop at **#{path[whichPart + 1]}**.",
                                'Wonder why they chose here.')
                            await eavesdropperChannel.send(embed = embed)
            playerCon.close()

            #Inform origin occupants
            embed, _ = await fn.embed(
                'Departing.',
                f"You notice {ctx.author.mention} leave, heading towards **#{path[1]}**.",
                'Maybe you can follow them?')
            await postToDirects(
                embed, 
                interaction.guild, 
                guildData['nodes'][path[0]]['channelID'], 
                serverData['channelID'],
                True)

            #Inform destination occupants
            embed, _ = await fn.embed(
                'Arrived.',
                f"You notice {ctx.author.mention} arrive from the direction of **#{path[-2]}**.",
                'Say hello.')
            await postToDirects(embed, 
                interaction.guild, 
                guildData['nodes'][path[-1]]['channelID'],
                serverData['channelID'],
                True)

            #Inform intermediary nodes + their occupants
            for index, midwayName in enumerate(path[1:-1]): 
                embed, _ = await fn.embed(
                    'Passing through.',
                    f"You notice {interaction.user.mention} come in from the direction of **#{path[index]}**\
                    before continuing on their way towards **#{path[index+2]}**.",
                    'Like two ships in the night.')
                await postToDirects(embed, 
                    interaction.guild, 
                    guildData['nodes'][midwayName]['channelID'],
                    True)

                nodeChannel = get(interaction.guild.text_channels, name = midwayName)
                embed, _ = await fn.embed(
                    'Transit.',
                    f"{interaction.user.mention} passed through here when traveling from" + \
                        f"**#{path[0]}>** to + **#{path[-1]}**.",
                    f"They went from {' -> '.join(path)}.")
                await nodeChannel.send(embed = embed)

            visitedNodes = await fn.filterNodes(guildData['nodes'], path)
            visitedNodes[path[0]]['occupants'].remove(interaction.user.id)
            occupantsData = await fn.getOccupants(visitedNodes)

            #Calculate who they saw on the way
            fullMessage = []
            for nodeName, occupantsList in occupantsData.items():

                if occupantsList:
                    occupantsMention = await fn.listWords([f"<@{ID}>" for ID in occupantsList])
                    fullMessage.append(f'{occupantsMention} in **#{nodeName}**')

            #Inform player of who they saw and what path they took
            if fullMessage:
                description = f'Along the way, you saw (and were seen by) {await fn.listWords(fullMessage)}.'
            else:
                description = "You didn't see anyone along the way."

            #Change occupants
            con = db.connectToGuild()
            guildData = await fn.addOccupants(guildData, path[-1], [interaction.user.id])
            db.updateGuild(con, guildData, interaction.guild_id)
            con.close()

            #Update location and eavesdropping
            playerCon = db.connectToPlayer()
            playerData[str(ctx.guild_id)]['locationName'] = path[-1]
            playerData[str(ctx.guild_id)].pop('eavesdropping', None)
            db.updatePlayer(playerCon, playerData, ctx.author.id)
            playerCon.close()        

            await queueRefresh(interaction.guild)

            #Tell player
            embed, _ = await fn.embed(
                'Movement',
                description,
                f"The path you traveled was {' -> '.join(path)}.")
            playerChannel = get(interaction.guild.text_channels, id = serverData['channelID'])
            await playerChannel.send(embed = embed)
            await interaction.followup.delete_message(message_id = interaction.message.id)
            return

        embed, view = await refreshMessage()        
        await ctx.respond(embed = embed, view = view)
        return

    @commands.Cog.listener()
    async def on_guild_remove(
        self,
        guild: discord.Guild):
 
        global directListeners, indirectListeners

        directListeners, indirectListeners = await fn.deleteServer(
            guild,
            directListeners,
            indirectListeners)

        if needingUpdate:
            needingUpdate.discard(guild)
        if updatedGuilds:
            updatedGuilds.discard(guild.id)

        guildData = oop.GuildData(guild.id)
        await guildData.clear(guild, directListeners, indirectListeners)        
        return

    @commands.Cog.listener()
    async def on_ready(self):

        # con = db.connectToGuild()
        # for guild in self.prox.guilds:
        #     needingUpdate.add(guild)
        #     print(f'Added {guild.name} to the queue of servers needing updated listeners.')

        #     guildData = db.getGuild(con, guild.id)
            

        
        # con.close()

        return
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if not message.webhook_id:
            await relay(message)

        return

def setup(prox):

    global proximity
    proximity = prox

    prox.add_cog(nodeCommands(prox), override = True)
    prox.add_cog(edgeCommands(prox), override = True)
    prox.add_cog(serverCommands(prox), override = True)
    prox.add_cog(playerCommands(prox), override = True)
    prox.add_cog(freeCommands(prox), override = True)
    prox.add_cog(guildCommands(prox), override = True)

