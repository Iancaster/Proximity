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

global updatedGuilds, needingUpdate, directListeners, indirectListeners
global proximity, brokenWebhooks
proximity = None
updatedGuilds = set()
needingUpdate = set()
directListeners = {}
indirectListeners = {}
brokenWebhooks = set()

async def queueRefresh(guild: discord.Guild):
    updatedGuilds.discard(guild.id)
    needingUpdate.add(guild)
    return

async def relay(msg: discord.Message):

    if msg.author.id == 1114004384926421126: #Don't relay Prox itself
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
                'You hear everything.')
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

    if guild.id not in updatedGuilds:
    
        needingUpdate.add(guild)
        while guild.id not in updatedGuilds:
            print(f'Waiting for updated listeners in server: {guild.name}.')
            await asyncio.sleep(1)
    
    directs = directListeners.get(channelID, [])
    for channel, eavesdropping in directs:

        if channel.id == exclude: #To prevent echos
            continue

        if eavesdropping and onlyOccs: #Cant be overheard
            continue

        try:
            await channel.send(embed = embed)
        except: #Whenever this triggers it is NOT probably fine, don't fall for it Gray

            if not channel.webhooks:
                print(f'#{channel.name} is missing its webhook!')
                continue

            raise ConnectionRefusedError(f"Tried to send a message to a channel" + \
                f" with some weird error, #{channel.name}, within" + \
                f" {channel.guild.name}. It's probably fine.")

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
        name = await oop.Format.newName(name, guildData.nodes.keys())

        async def refreshEmbed():

            nonlocal name
            name = view.name() if view.name() else name
            name = await oop.Format.newName(name, guildData.nodes.keys())

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
                "Here's who's allowed:" + \
                    f"\n{whitelist}" + \
                    "\n\nDon't forget to connect it to other nodes with `/edge new`.",
                "You can also change the whitelist with /node review.")         
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
            autocomplete = oop.Auto.nodes,
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
                        "You need to specify at least one node that doesn't have anyone inside.",
                        'You can always try the command again.')
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id, 
                        embed = embed, 
                        view = None)
                    return

                #Inform neighbor nodes and occupants that the node is deleted now
                neighborNames = await guildData.neighbors(deletingNodes.keys())
                boldDeleting = await oop.Format.bold(deletingNodes.keys())
                for name in neighborNames:
                    embed, _ = await fn.embed(
                        'Misremembered?',
                        f"Could you be imagining {boldDeleting}? Strangely, there's no trace.",
                        "Whatever the case, it's gone now.")
                    await postToDirects(
                        embed, 
                        interaction.guild, 
                        guildData.nodes[name].channelID,
                        onlyOccs = True)
                    
                    embed, _ = await fn.embed(
                        'Neighbor node(s) deleted.',
                        f'Deleted {boldDeleting}--this node now has fewer neighbors.',
                        "I'm sure it's for the best.")
                    neighborChannel = get(
                        interaction.guild.text_channels,
                        id = guildData.nodes[name].channelID)
                    await neighborChannel.send(embed = embed)

                #Delete nodes and their edges
                for name, node in deletingNodes.items():

                    for neighbor in list(node.neighbors.keys()):
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
                                " node(s) that were occupied. Use `/player tp` to" + \
                                " move the player(s) inside."
                    
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
            autocomplete = oop.Auto.nodes,
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
                localNodes = await guildData.filterNodes(list(neighbors) + nodeNames)
                subgraph = await guildData.toGraph(localNodes)
                graphView = (await guildData.toMap(subgraph), 'full')
            else:
                description += '\n• Edges: No other nodes are connected to the selected node(s).'
                graphView = None

            hasWhitelist = any(node.allowedRoles or node.allowedPlayers for node in revisingNodes.values())

            async def refreshEmbed():

                fullDescription = intro
                if view.name():
                    newName = await oop.Format.newName(view.name(), guildData.nodes.keys())
                    fullDescription += f', renaming to **#{newName}**.'
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
                newName = await oop.Format.newName(view.name(), guildData.nodes.keys())

                if await fn.noChanges((newName or view.roles() or view.players() or view.clearing), interaction):
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
                        description += '\n• Edited the player whitelist(s).'
                    
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
                    
                if newName: 

                    oldName = list(revisingNodes.keys())[0]
                    renamedNode = guildData.nodes.pop(oldName)
                    guildData.nodes[newName] = renamedNode
                    
                    description += f"\n• Renamed **#{oldName}** to {renamedNode.mention}."


                    #Correct locationName in player data
                    for ID in renamedNode.occupants:
                        player = oop.Player(ID, channel.guild.id)
                        player.location = newName
                        await player.save()
                    
                    #Rename edges
                    for node in guildData.nodes.values():
                        for neighbor in list(node.neighbors):
                            if neighbor == oldName:
                                node.neighbors[newName] = node.neighbors.pop(oldName)
                                
                await guildData.save()

                if newName: #Gotta save first sorry
                    nodeChannel = get(interaction.guild.text_channels, id = renamedNode.channelID)
                    await nodeChannel.edit(name = newName)

                await queueRefresh(interaction.guild)
                
                embed, _ = await fn.embed(
                    'Edited.',
                    description,
                    'Another successful revision.')
                for node in revisingNodes.values():
                    nodeChannel = get(interaction.guild.text_channels, id = node.channelID)
                    await nodeChannel.send(embed = embed)  

                return await fn.noCopies(
                    (interaction.channel.name in revisingNodes or interaction.channel.name == newName),
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

                if not node.occupants:

                    #Inform neighbor nodes and occupants that the node is deleted now
                    for neighborName in list(node.neighbors.keys()):
                        embed, _ = await fn.embed(
                            'Misremembered?',
                            f"Could you be imagining **#{name}**? Strangely, there's no trace.",
                            "Whatever the case, it's gone now.")
                        await postToDirects(
                            embed, 
                            channel.guild, 
                            guildData.nodes[neighborName].channelID,
                            onlyOccs = True)
                        
                        embed, _ = await fn.embed(
                            'Neighbor node(s) deleted.',
                            f'Deleted **#{name}**--this node now has fewer neighbors.',
                            "I'm sure it's for the best.")
                        neighborChannel = get(
                            channel.guild.text_channels,
                            id = guildData.nodes[neighborName].channelID,)
                        await neighborChannel.send(embed = embed)
                
                        await guildData.deleteEdge(name, neighborName)

                    await guildData.deleteNode(name)
                    directListeners.pop(node.channelID, None)
                    await guildData.save()
                    return

                maker = oop.ChannelMaker(channel.guild, 'nodes')
                await maker.initialize()
                newChannel = await maker.newChannel(name)
                node.channelID = newChannel.id
                await guildData.save()

                await queueRefresh(channel.guild)

                embed, _ = await fn.embed(
                    'Not so fast.',
                    "There's still people inside this node:" + \
                        f" {await oop.Format.players(node.occupants)}" + \
                        " to be specific. Either delete them as players" + \
                        " with `/player delete` or move them out with " + \
                        " `/player tp`.",
                    'Either way, you can only delete empty nodes.')
                await newChannel.send(embed = embed)
                return

        for ID in guildData.players:
            player = oop.Player(ID, channel.guild.id)
            if player.channelID == channel.id:

                oldNode = guildData.nodes[player.location]
                await oldNode.removeOccupants({ID})
                await player.delete()
                guildData.players.discard(ID)
                await guildData.save()

                await queueRefresh(channel.guild)

                playerEmbed, _ = await fn.embed(
                    'Where did they go?',
                    f"You look around, but <@{ID}> seems to have vanished into thin air.",
                    "You get the impression you won't be seeing them again.") 
                await postToDirects(
                    playerEmbed,
                    channel.guild,
                    oldNode.channelID,
                    onlyOccs = True)
                
                nodeEmbed, _ = await fn.embed(
                    'Fewer players.',
                    f'Removed <@{ID}> from the game (and this node).',
                    'You can view all remaining players with /player find.') 
                nodeChannel = get(channel.guild.channels, id = oldNode.channelID)
                await nodeChannel.send(embed = nodeEmbed)
                return

        return
    
    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        beforeChannel,
        afterChannel):

        guildData = oop.GuildData(beforeChannel.guild.id)

        foundNode = False
        for node in guildData.nodes.values():
            if beforeChannel.id == node.channelID:

                if beforeChannel.name not in guildData.nodes \
                    and afterChannel.name in guildData.nodes:
                    return #Already good

                newName = await oop.Format.newName(afterChannel.name, guildData.nodes.keys())

                if newName != afterChannel.name:
                    await afterChannel.edit(name = newName)
                    return

                oldName = next(name for name, candidate in guildData.nodes.items() if candidate is node)
                guildData.nodes[newName] = guildData.nodes.pop(oldName)

                #Correct location name for occupants
                for ID in node.occupants:
                    player = oop.Player(ID, channel.guild.id)
                    player.location = newName
                    await player.save()

                embed, _ = await fn.embed(
                    'Edited.',
                    f'Renamed **#{beforeChannel.name}** to {afterChannel.mention}.',
                    'Another successful revision.')
                await afterChannel.send(embed = embed)

                foundNode = True
                break
            
        if foundNode == False: #Channel wasn't even a node channel
            return

        for node in guildData.nodes.values(): 
            #Fix the edges too
            for neighbor in list(node.neighbors.keys()):
                if neighbor == beforeChannel.name:
                    node.neighbors[newName] = node.neighbors.pop(beforeChannel.name)

        await guildData.save()
        return
    
    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):

        if channel in brokenWebhooks:
            return

        guildData = oop.GuildData(channel.guild.id)

        if get(guildData.nodes.values(), channelID = channel.id):
            brokenWebhooks.add(channel)
        else:
            for ID in guildData.players:
                player = oop.Player(ID, channel.guild.id)
                if player.channelID == channel.id:
                    brokenWebhooks.add(channel)
                    break
                    
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
            autocomplete = oop.Auto.nodes,
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
                    description += f"\n• Destination(s): None yet! Choose some nodes to connect to this one."

                description += f"\n• Whitelist: {await oop.Format.whitelist(view.roles(), view.players())}"

                match view.directionality:
                    case 0:
                        description += "\n• Directionality: **One-way** (<-) from" + \
                            f" the destination(s) to {origin.mention}."
                    case 1:
                        description += "\n• Directionality: **Two-way** (<->), people will be able to travel" + \
                            f" back and forth between {origin.mention} and the destination(s)."
                    case 2:
                        description += "\n• Directionality: **One-way** (->) to" + \
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

                        if not view.overwriting:        
                            continue

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
                neighborsDict[originName] = origin
                subgraph = await guildData.toGraph(neighborsDict)
                graphView = await guildData.toMap(subgraph)
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
            autocomplete = oop.Auto.nodes,
            required = False)):
        
        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        async def deleteEdges(originName: str):

            origin = guildData.nodes[originName]

            neighbors = origin.neighbors
            if not neighbors:
                embed, _ = await fn.embed(
                    'No edges.',
                    f'{origin.mention} has no edges to view.',
                    'So I suppose that answers your inquiry.')
                await ctx.respond(embed = embed, ephemeral = True)
                return

            localNodes = await guildData.filterNodes(list(neighbors.keys()) + [originName])
            graph = await guildData.toGraph(localNodes)
            description = f'{origin.mention} has these connections'

            async def refreshEmbed():

                fullDescription = description

                if not view.edges():
                    fullDescription += ':'
                else:
                    selectedNeighbors = {name : neighbors[name] for name in view.edges()}
                    fullDescription += ", but you'll be deleting the following:" + \
                        await guildData.formatEdges(selectedNeighbors)
                    
                
                edgeColors = await oop.Format.colors(graph, originName, view.edges(), 'red')
                graphImage = await guildData.toMap(graph, edgeColors)

                embed, file = await fn.embed(
                    'Delete edge(s)?',
                    fullDescription,
                    'This cannot be reversed.',
                    (graphImage, 'full'))
                
                return embed, file

            async def refreshMessage(interaction: discord.Interaction):
                embed, file = await refreshEmbed()
                await interaction.response.edit_message(embed = embed, file = file)
                return

            async def confirmDelete(interaction: discord.Interaction):

                await fn.loading(interaction)

                for neighbor in view.edges():
                    await guildData.deleteEdge(originName, neighbor)

                await guildData.save()

                await queueRefresh(interaction.guild)

                deletedNeighbors = await guildData.filterNodes(view.edges())

                #Inform neighbors occupants and neighbor nodes
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"The path between here and **#{originName}** just closed.",
                    'Just like that...')
                nodeEmbed, _ = await fn.embed(
                    'Edge deleted.',
                    f'Removed an edge between here and {origin.mention}.',
                    'You can view the remaining edges with /node review.')
                for node in deletedNeighbors.values():
                    await postToDirects(
                        playersEmbed, 
                        interaction.guild, 
                        node.channelID,
                        onlyOccs = True)
                    nodeChannel = get(interaction.guild.text_channels, id = node.channelID)
                    await nodeChannel.send(embed = nodeEmbed)

                #Inform edited node occupants
                boldDeleted = await oop.Format.bold(view.edges())
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"This place just lost access to {boldDeleted}.",
                    "Will that path ever be restored?")         
                await postToDirects(
                    playersEmbed, 
                    interaction.guild, 
                    origin.channelID,
                    onlyOccs = True)

                #Inform own node            
                deletedMentions = await oop.Format.nodes(deletedNeighbors.values())
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

            view = oop.DialogueView()
            await view.addEdges(neighbors, callback = refreshMessage)
            await view.addEvilConfirm(confirmDelete)
            await view.addCancel()
            embed, file = await refreshEmbed()

            await ctx.respond(
                embed = embed,
                file = file,
                view = view,
                ephemeral = True)
            return

        result = await fn.identifyNodeChannel(guildData.nodes, ctx.channel.name, origin)
        match result:
            case isMessage if isinstance(result, discord.Embed):
                await ctx.respond(embed = result)
            case isChannel if isinstance(result, str):
                await deleteEdges(result)
            case None:
    
                embed, _ = await fn.embed(
                    'Delete edges?',
                    "You can delete edges three ways:" + \
                        "\n• Call this command inside of a node channel." + \
                        "\n• Do `/edge delete #node-channel`." + \
                        "\n• Select a node channel with the list below.",
                    "This is just to select the origin, you'll see the edges next.")

                async def submitNodes(interaction: discord.Interaction):
                    await ctx.delete()
                    await deleteEdges(view.nodes())
                    return

                view = oop.DialogueView()      
                await view.addNodes(guildData.nodes.keys(), submitNodes, manyNodes = False)
                await view.addCancel()
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
            autocomplete = oop.Auto.nodes,
            required = False)):
        
        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        async def revisePermissions(originName: str):

            origin = guildData.nodes[originName]

            if not origin.neighbors:
                embed, _ = await fn.embed(
                    'No edges.',
                    f'{origin.mention} has no edges to modify.',
                    "So...that's that.")
                await ctx.respond(embed = embed, ephemeral = True)
                return

            description = f'• Selected node: {origin.mention}'  

            localNodes = await guildData.filterNodes([originName] + list(origin.neighbors.keys()))
            subgraph = await guildData.toGraph(localNodes)

            hasWhitelist = any(edge.allowedRoles or edge.allowedPlayers for edge in origin.neighbors.values())

            async def refreshEmbed():

                fullDescription = description

                if view.edges():
                    fullDescription += f"\n• Selected Edges: See below." 
                    revisingEdges = [origin.neighbors[name] for name in view.edges()]
                    fullDescription += await view.whitelist(revisingEdges)                   
                
                else:
                    fullDescription += '\n• Selected Edges: None yet. Use the dropdown below to pick one or more.'
                
                edgeColors = await oop.Format.colors(subgraph, originName, view.edges(), 'blue')
                graphImage = await guildData.toMap(subgraph, edgeColors)

                embed, file = await fn.embed(
                    'Change whitelists?',
                    fullDescription,
                    'This can always be reversed.',
                    (graphImage, 'full'))

                return embed, file

            async def refreshMessage(interaction: discord.Interaction):
                embed, file = await refreshEmbed()
                await interaction.response.edit_message(
                    embed = embed,
                    file = file)
                return
            
            async def confirmEdges(interaction: discord.Interaction):

                await interaction.response.defer()

                #Screen for invalid submissions
                if not view.edges():
                    await fn.noEdges(interaction)
                    return

                if await fn.noChanges(any([view.roles(), view.players(), view.clearing]), interaction):
                    return
                
                if view.clearing:
                    description = '\n• Removed the whitelist(s).'
                    for neighborName in view.edges():
                        await origin.neighbors[neighborName].clearWhitelist()
                        await guildData.nodes[neighborName].neighbors[originName].clearWhitelist()
                    
                else:
                    description = ''

                    if view.roles():
                        description += '\n• Edited the whitelist(s).'

                    for neighborName in view.edges():
                        origin.neighbors[neighborName].allowedRoles = view.roles()
                        guildData.nodes[neighborName].neighbors[originName].allowedPlayers = view.players()

                await guildData.save()

                #Inform neighbors occupants and neighbor nodes
                neighborNodes = await guildData.filterNodes(view.edges())
                neighborMentions = await oop.Format.nodes(neighborNodes.values())
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"You feel like the way to **#{originName}** changed somehow.",
                    'Will it be easier to travel through, or harder?')
                nodeEmbed, _ = await fn.embed(
                    f'Edge with {origin.mention} changed.',
                    description,
                    'You can view its details with /edge allow.')
                for node in neighborNodes.values():
                    await postToDirects(
                        playersEmbed, 
                        interaction.guild, 
                        node.channelID,
                        onlyOccs = True)
                    nodeChannel = get(interaction.guild.text_channels, id = node.channelID)
                    await nodeChannel.send(embed = nodeEmbed)

                #Inform edited node occupants
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    "You notice that there's been a change in the way this" + \
                        f" place is connected to {neighborMentions}.",
                    "Perhaps you're only imagining it.")         
                await postToDirects(
                    playersEmbed, 
                    interaction.guild, 
                    origin.channelID,
                    onlyOccs = True)

                #Inform own node                
                embed, _ = await fn.embed(
                    f'Edge(s) with {neighborMentions} changed.',
                    description,
                    'You can always undo these changes.') 
                nodeChannel = get(interaction.guild.text_channels, id = origin.channelID)
                await nodeChannel.send(embed = embed)

                if interaction.channel.name in view.edges() or interaction.channel.id == origin.channelID:
                    await interaction.delete_original_response()
                else:
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        view = None)    
                return

            view = oop.DialogueView(ctx.guild)
            await view.addEdges(origin.neighbors, False, callback = refreshMessage)
            await view.addRoles(callback = refreshMessage)
            await view.addPlayers(guildData.players, callback = refreshMessage)
            await view.addSubmit(confirmEdges)
            if hasWhitelist:
                await view.addClear(refreshMessage)
            await view.addCancel()
            
            embed, file = await refreshEmbed()
            await ctx.respond(
                embed = embed,
                file = file,
                view = view,
                ephemeral = True)
            return
    
        result = await fn.identifyNodeChannel(guildData.nodes, ctx.channel.name, origin)
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
                    await revisePermissions(view.nodes())
                    return

                view = oop.DialogueView()    
                await view.addNodes(guildData.nodes.keys(), submitNodes, manyNodes = False)
                await view.addCancel()
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

        # db.newGuildDB()
        # db.newPlayerDB()

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
                f" and {await guildData.edgeCount()} edges, alongside" + \
                f" player data for {len(guildData.players)} people.",
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
            autocomplete = oop.Auto.nodes,
            required = False)):
        
        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        async def viewEgo(guildData: dict, centerName: str = None):

            #Nothing provided
            if not centerName:
                map = await guildData.toMap()
                embed, file = await fn.embed(
                    'Complete graph',
                    'Here is a view of every node and edge.',
                    'To view only a single node and its neighbors, use /server view #node.',
                    (map, 'full'))

                await ctx.respond(embed = embed, file = file, ephemeral = True)
                return

            #If something provided
            center = guildData.nodes[centerName]
            included = center.neighbors.keys() + [centerName]
            graph = await guildData.toGraph(included)
            map = await guildData.toMap(graph)

            embed, file = await fn.embed(
                f"{center.mention}'s neighbors",
                "Here is the node, plus any neighbors.",
                'To view every node and edge, call /server view without the #node.',
                (map, 'full'))

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

        # allowedChannels = ['function', 'information', 'road-map', 'discussion', 'chat']
        # deletingChannels = [channel for channel in ctx.guild.channels if channel.name not in allowedChannels]
        # [await channel.delete() for channel in deletingChannels]

        # return
    
        guildData = oop.GuildData(ctx.guild_id)

        description = ''

        channelIDs = [channel.id for channel in ctx.guild.text_channels]
        channelNames = [channel.name for channel in ctx.guild.text_channels]

        ghostNodeMentions = []
        misnomerNodeMentions = []
        incorrectWebhooks = []

        if guildData.nodes:
            maker = oop.ChannelMaker(ctx.guild, 'nodes')
            await maker.initialize()
        for name, node in list(guildData.nodes.items()): #Fix node issues

            if node.channelID not in channelIDs: #Node was deleted in server only

                newChannel = await maker.newChannel(name)
                ghostNodeMentions.append(newChannel.mention)
                node.channelID = newChannel.id

                whitelist = await oop.Format.whitelist(node.allowedRoles, node.allowedPlayers)
                embed, _ = await fn.embed(
                'Cool, new node...again.',
                f"**Important!** Don't delete this one!" + \
                    f"\n\nAnyways, here's who is allowed:\n{whitelist}", 
                "Unfortunately, I couldn't save the edges this may have had.")         
                await newChannel.send(embed = embed)
                continue

            newName = None
            if name not in channelNames: #Node was renamed in server only
                
                channel = get(ctx.guild.text_channels, id = node.channelID)
                oldName = name
                newName = channel.name

                misnomerNodeMentions.append(channel.mention)

                guildData.nodes[newName] = guildData.nodes.pop(oldName)
                for neighbor in node.neighbors.keys():

                    guildData.nodes[neighbor].neighbors[newName] = guildData.nodes[neighbor].neighbors.pop(oldName)
            

            channel = get(ctx.guild.text_channels, id = node.channelID)
            nodeWebhooks = await channel.webhooks()
            if len(nodeWebhooks) != 1:

                for webhook in nodeWebhooks:
                    await webhook.delete()

                with open('assets/avatar.png', 'rb') as file:
                    avatar = file.read()
                    await channel.create_webhook(name = 'Proximity', avatar = avatar)

                incorrectWebhooks.append(channel.mention)

        if ghostNodeMentions:
            description += "\n• These nodes were deleted without using `/node delete`," + \
                f" but were just regenerated: {await oop.Format.words(ghostNodeMentions)}."

        if misnomerNodeMentions:
            description += "\n• Corrected the name(s) of the following" + \
                " channel(s) that were renamed not using `/node review`:" + \
                f" {await oop.Format.words(misnomerNodeMentions)}." 

        if incorrectWebhooks:
            description += "\n• Fixed the webhook(s) for the following" + \
            f" node channel(s): {await oop.Format.words(incorrectWebhooks)}."

        await guildData.save()

        #Identify dead ends and isolates        
        noExits = {name : node for name, node in guildData.nodes.items() \
            if not any(edge.directionality > 0 for edge in node.neighbors.values())}      
        noEntrances = {name : node for name, node in guildData.nodes.items() \
            if not any(edge.directionality < 2 for edge in node.neighbors.values())}
        noAccess = {name : node for name, node in noExits.items() if \
            name in noEntrances}
        
        noEntrances = {name : node for name, node in noEntrances.items() \
            if name not in noAccess}        
        noExits = {name : node for name, node in noExits.items() \
            if name not in noAccess}

        if noAccess:
            noAccessMentions = await oop.Format.nodes(noAccess.values())
            description += "\n• The following nodes have no edges for entry or exit, meaning" + \
                f" **players can only come or go through** `/player tp`**:** {noAccessMentions}."

        if noExits:
            noExitsMentions = await oop.Format.nodes(noExits.values())
            description += "\n• The following nodes have no edges for exiting, meaning" + \
                f" **players can get trapped:** {noExitsMentions}."

        if noEntrances:
            noEntrancesMentions = await oop.Format.nodes(noEntrances.values())
            description += "\n• The following nodes have no edges or entrances, meaning" + \
                f" **players will never enter:** {noEntrancesMentions}."

        noChannelMentions = []
        missingPlayers = []
        wrongWebhooks = []
        if guildData.players:
            maker = oop.ChannelMaker(ctx.guild, 'players')
            await maker.initialize()
        for playerID in list(guildData.players): #Identify player issues

            player = oop.Player(playerID, ctx.guild_id)

            member = get(ctx.guild.members, id = playerID)
            if not member: #User left the server but is still considered a player
                oldChannel = get(ctx.guild.text_channels, id = player.channelID)
                if oldChannel:
                    missingPlayers.append(oldChannel.name)
                else:
                    missingPlayers.append('Channel-less Ex-player')

                lastNode = guildData.nodes.get(player.location, None)
                if lastNode:
                    if lastNode.occupants:
                        lastNode.removeOccupants({playerID})
                
                await player.delete()
                guildData.players.pop(playerID)
                continue

            if player.channelID not in channelIDs: #User is missing their channel
                noChannelMentions.append(member.mention)

                channel = await maker.newChannel(member.display_name, member)

                player.channelID = channel.id
                await player.save()
                
                embed, _ = await fn.embed(
                    f'Welcome.',
                    f"This is your very own channel, again, {member.mention}." + \
                    "\n• Speak to others by just talking in this chat. Anyone who can hear you" + \
                    " will see your messages pop up in their own player channel." + \
                    f"\n• You can `/look` around. You're at **{player.location}** right now." + \
                    "\n• Do `/map` to see the other places you can go." + \
                    "\n• ...And `/move` to go there." + \
                    "\n• You can`/eavesdrop` on people nearby room." + \
                    "\n• Other people can't see your `/commands`." + \
                    "\n• Tell the host not to accidentally delete your channel again.",
                    'You can always type /help to get more help.')
                await channel.send(embed = embed)
            
            playerChannel = get(ctx.guild.text_channels, id = player.channelID)
            playerWebhooks = await playerChannel.webhooks()
            if len(playerWebhooks) != 1:

                for webhook in playerWebhooks:
                    await webhook.delete()

                with open('assets/avatar.png', 'rb') as file:
                    avatar = file.read()
                    await channel.create_webhook(name = 'Proximity', avatar = avatar)

                wrongWebhooks.append(playerChannel.mention)
        
        await queueRefresh(ctx.guild)

        if noChannelMentions:
            description += "\n• The following players got back" + \
            f" their deleted player channels: {await oop.Format.words(noChannelMentions)}."

        if missingPlayers:
            description += f"\n• Deleted data and any remaining player" + \
                f" channels for {len(missingPlayers)} players who left" + \
                " the server without ever being officially removed as" + \
                " players. My best guess for the name(s) of those who" + \
                f" left is {await oop.Format.words(missingPlayers)}."

        if wrongWebhooks:
            description += "\n• Fixed the webhook(s) for the following" + \
            f" player channel(s: {await oop.Format.words(wrongWebhooks)}."
     
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
                        guildDescription += f"\n• {neighbor} -> {name}"

                    case 1:
                        guildDescription += f"\n• {name} <-> {neighbor}"
                    
                    case 2:
                        guildDescription += f"\n• {name} -> {neighbor}"
                
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
    
    # @server.command(
    #     name = 'quick',
    #     description = 'Create a quick example graph.')
    # async def quick(
    #     self,
    #     ctx: discord.ApplicationContext):

    #     await ctx.defer(ephemeral = True)

    #     guildData = oop.GuildData(ctx.guild_id)

    #     exampleNodes = ['the-kitchen', 'the-living-room', 'the-dining-room', 'the-bedroom']
                
    #     maker = oop.ChannelMaker(ctx.guild, 'nodes')
    #     await maker.initialize()
    #     for name in exampleNodes:

    #         if name in guildData.nodes:
    #             await guildData.deleteNode(name, ctx.guild.text_channels)

    #         newChannel = await maker.newChannel(name)
    #         await guildData.newNode(name, newChannel.id)


    #     newEdges = {
    #         ('the-kitchen', 'the-dining-room') : {},
    #         ('the-dining-room', 'the-kitchen') : {},
    #         ('the-living-room', 'the-dining-room') : {},
    #         ('the-dining-room', 'the-living-room') : {},
    #         ('the-dining-room', 'the-kitchen') : {},
    #         ('the-kitchen', 'the-dining-room') : {},
    #         ('the-living-room', 'the-bedroom') : {},
    #         ('the-bedroom', 'the-living-room') : {}}
    #     guildData['edges'].update(newEdges)
    #     db.updateGuild(con, guildData, ctx.guild_id)
    #     con.close()

    #     await guildData.save()

    #     embed, _ = await fn.embed(
    #         'Done.',
    #         "Made an example graph composed of a household layout. If there were any" + \
    #             " nodes/edges that were already present from a previous `/server quick` call," + \
    #             " they've been overwritten.",
    #         'Your other data is untouched.')

    #     await ctx.respond(embed = embed)
    #     return

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

        guildData = oop.GuildData(ctx.guild_id)

        async def refreshEmbed():

            if view.people():
                playerMentions = [person.mention for person in view.people()]
                description = f'Add {await oop.Format.words(playerMentions)} to '
            else:
                description = 'Add who as a new player to '

            if view.nodes():
                nodeName = view.nodes()[0]
                node = guildData.nodes[nodeName]
                description += f"{node.mention}?"
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

            newPlayers = [person for person in view.people() \
                if person.id not in guildData.players]

            if not view.nodes():
                await fn.noNodes(interaction, singular = True)
                return

            if not view.people():
                await fn.noPeople(interaction)
                return
                
            nodeName = view.nodes()[0]   
            
            maker = oop.ChannelMaker(interaction.guild, 'players')
            await maker.initialize()
            for person in newPlayers:

                newChannel = await maker.newChannel(person.name, person)
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
                await newChannel.send(embed = embed)

                playerData = oop.Player(person.id, ctx.guild_id)
                playerData.channelID = newChannel.id
                playerData.location = nodeName
                await playerData.save()
                guildData.players.add(person.id)

            #Add the players to the guild nodes as occupants
            playerIDs = [player.id for player in newPlayers]
            node = guildData.nodes[nodeName]
            await node.addOccupants(playerIDs)
            await guildData.save()

            #Inform the node occupants
            playerMentions = await oop.Format.players(playerIDs)
            playersEmbed, _ = await fn.embed(
                'Someone new.',
                f"{playerMentions} is here.",
                'Perhaps you should greet them.')         
            await postToDirects(
                playersEmbed, 
                interaction.guild, 
                node.channelID,
                onlyOccs = True)

            #Inform own node                
            embed, _ = await fn.embed(
                'New player(s).',
                f'Added {playerMentions} to this node to begin their journey.',
                'You can view all players and where they are with /player find.') 
            nodeChannel = get(interaction.guild.text_channels, id = node.channelID)
            await nodeChannel.send(embed = embed)

            await queueRefresh(interaction.guild)

            description = f"Successfully added {playerMentions} to this server," + \
                    f" starting their journey at {node.mention}."

            existingPlayers = len(view.people()) - len(newPlayers)
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

        view = oop.DialogueView(ctx.guild, refreshEmbed) 
        await view.addPeople()
        await view.addNodes(guildData.nodes.keys(), manyNodes = False)
        await view.addSubmit(submitPlayers)
        await view.addCancel()
        embed = await refreshEmbed()
        await ctx.respond(embed = embed, view = view)
        return
    
    @player.command(
        name = 'delete',
        description = 'Remove a player from the game (but not the server).')
    async def delete( 
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        async def refreshEmbed():

            if view.players():
                playerMentions = await oop.Format.players(view.players())
                description = f'Remove {playerMentions} from the game?'
            else:
                description = "For all the players you list, this command will:" + \
                "\n• Delete their player channel.\n• Remove them as occupants in" + \
                " the location they're in.\n• Remove their ability to play, returning" + \
                " them to the state they were in before they were added as a player." + \
                "\n\nIt will not:\n• Kick or ban them from the server.\n• Delete their" + \
                " messages.\n• Keep them from using the bot in other servers."

            embed, _ = await fn.embed(
                'Delete player(s)?',
                description,
                "This won't remove them from the server.")
            return embed

        async def deletePlayers(interaction: discord.Interaction):

            await interaction.response.defer()

            deletingIDs = set(int(ID) for ID in view.players() if ID in guildData.players)

            if not deletingIDs:
                await fn.noPeople(interaction)
                return
                
            leavingNodes = {}
            for ID in deletingIDs:
                
                playerData = oop.Player(ID, ctx.guild_id)
                         
                occupiedNode = guildData.nodes[playerData.location]
                
                await occupiedNode.removeOccupants({ID})
                
                playerMention = f'<@{ID}>'
                playerEmbed, _ = await fn.embed(
                    'Where did they go?',
                    f"You look around, but {playerMention} seems to have vanished into thin air.",
                    "You get the impression you won't be seeing them again.")         
                await postToDirects(
                    playerEmbed, 
                    interaction.guild, 
                    occupiedNode.channelID,
                    onlyOccs = True)
   
                leavingNodes.setdefault(occupiedNode.channelID, [])
                leavingNodes[occupiedNode.channelID].append(ID)

                playerChannel = get(interaction.guild.text_channels, id = playerData.channelID)
                if playerChannel:
                    await playerChannel.delete()

                #Delete their data
                await playerData.delete()
                
                #Remove them from server player list
                guildData.players.discard(ID)
            
            await guildData.save()

            for channelID, playerIDs in leavingNodes.items():
                deletedMentions = await oop.Format.players(playerIDs)
                embed, _ = await fn.embed(
                    'Fewer players.',
                    f'Removed {deletedMentions} from the game (and this node).',
                    'You can view all remaining players with /player find.') 
                nodeChannel = get(interaction.guild.text_channels, id = channelID)
                await nodeChannel.send(embed = embed)

            await queueRefresh(interaction.guild)

            deletingMentions = await oop.Format.players(deletingIDs)
            description = f"Successfully removed {deletingMentions} from the game."

            embed, _ = await fn.embed(
                'Delete player results.',
                description,
                'Hasta la vista.')
            try:
                await fn.noCopies(
                    (interaction.channel_id in leavingNodes),
                    embed,
                    interaction)
            except:
                pass
            return

        view = oop.DialogueView(ctx.guild, refreshEmbed) 
        await view.addPlayers(guildData.players)
        await view.addEvilConfirm(deletePlayers)
        await view.addCancel()
        embed = await refreshEmbed()
        await ctx.respond(embed = embed, view = view)
        return
    
    # @player.command(
    #     name = 'review',
    #     description = 'Change some player-specific data.')
    # async def review(
    #     self,
    #     ctx: discord.ApplicationContext):

    #     await ctx.defer(ephemeral = True)

    #     guildData, members = db.mag(ctx.guild_id)

    #     if not members:
    #         embed, _ = await fn.embed(
    #         'But nobody came.',
    #         'There are no players, so nobody to locate.',
    #         'The title of this embed is a reference, by the way.')
    #         await ctx.respond(embed = embed)
    #         return

    #     if player:
    #         if player in members:
    #             playerIDs = [player.id]
    #         else:
    #             embed, _ = await embed(
    #                 f'{player.mention}?',
    #                 "But they aren't a player.",
    #                 'So how can they be located?')
    #             await ctx.edit(
    #                 embed = embed,
    #                 view = None)
    #             return
    #     else:
    #         playerIDs = members
                
    #     description = ''

    #     occupiedNodes = await fn.getOccupants(guildData['nodes'])
    #     for nodeName, occupantIDs in occupiedNodes.items():
    #         occupantMentions = [f'<@{occupantID}>' for occupantID in occupantIDs if occupantID in playerIDs]
    #         if occupantMentions:
    #             description += f"\n• <#{guildData['nodes'][nodeName]['channelID']}>: {await fn.listWords(occupantMentions)}"
                
    #     if not description:
    #         description = "• No players found. That's a big problem. Run `/server fix`."

    #     embed, _ = await fn.embed(
    #         'Find results',
    #         description,
    #         'Looked high and low.')
    #     await ctx.respond(embed = embed)
    #     return
    
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

        guildData = oop.GuildData(ctx.guild_id)

        if not guildData.players:
            embed, _ = await fn.embed(
            'But nobody came.',
            'There are no players, so nobody to locate.',
            'Feel free to keep looking though.')
            await ctx.respond(embed = embed)
            return

        if player:
            if player.id in guildData.players:
                playerIDs = [player.id]
            else:
                embed, _ = await embed(
                    f'{player.mention}?',
                    "But they aren't a player.",
                    'So how could they be located?')
                await ctx.edit(
                    embed = embed,
                    view = None)
                return
        else:
            playerIDs = guildData.players
                
        description = ''

        for node in guildData.nodes.values():

            occupantMentions = [f'<@{ID}>' for ID in node.occupants if ID in playerIDs]
            if occupantMentions:
                description += f"\n• {node.mention}: {await oop.Format.words(occupantMentions)}."
                
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

        guildData = oop.GuildData(ctx.guild_id)

        async def refreshEmbed():

            if view.players():
                playerMentions = await oop.Format.players(view.players())
                description = f'Teleport {playerMentions} to '
            else:
                description = 'Teleport who to '

            if view.nodes():
                nodeName = view.nodes()[0]
                node = guildData.nodes[nodeName]
                description += f"{node.mention}?"
            else:
                description += 'which node?'

            embed, _ = await fn.embed(
                'Teleport player(s)?',
                description,
                "Just tell me where to put who.")
            return embed

        async def teleportPlayers(interaction: discord.Interaction):

            await fn.waitForRefresh(interaction)

            if not view.nodes():
                await fn.noNodes(interaction, True)
                return
            
            if not view.players():
                await fn.noPeople(interaction)
                return
                
            nodeName = view.nodes()[0]
            node = guildData.nodes[nodeName]

            description = ''
            teleportingMentions = await oop.Format.players(view.players())
            description += f"• Teleported {teleportingMentions} to {node.mention}."

            exitingNodes = {}
            for ID in view.players():
                ID = int(ID)
                playerData = oop.Player(ID, ctx.guild_id)

                oldNode = guildData.nodes[playerData.location]
                await oldNode.removeOccupants({ID})

                exitingNodes.setdefault(oldNode.channelID, [])
                exitingNodes[oldNode.channelID].append(ID)

                playerData.location = nodeName
                playerData.eavesdropping = None
                await playerData.save()

            #Add players to new location
            await node.addOccupants({int(ID) for ID in view.players()})
            await guildData.save()

            await queueRefresh(interaction.guild)

            for channelID, exitingPlayerIDs in exitingNodes.items():

                #Inform old location occupants
                playerMentions = await oop.Format.players(exitingPlayerIDs)
                playersEmbed, _ = await fn.embed(
                    'Gone in a flash.',
                    f"{playerMentions} disappeared somewhere.",
                    "But where?")         
                await postToDirects(
                    playersEmbed, 
                    interaction.guild, 
                    channelID, 
                    onlyOccs = True)

                #Inform old node                
                embed, _ = await fn.embed(
                    'Teleported player(s).',
                    f"Teleported {playerMentions} to {node.mention}.",
                    'You can view all players and where they are with /player find.') 
                nodeChannel = get(interaction.guild.text_channels, id = channelID)
                await nodeChannel.send(embed = embed)
        
            #Inform new location occupants
            playersEmbed, _ = await fn.embed(
                'Woah.',
                f"{teleportingMentions} appeared in **#{nodeName}**.",
                "Must have been relocated by someone else.")         
            await postToDirects(
                playersEmbed, 
                interaction.guild, 
                node.channelID,
                onlyOccs = True)

            #Inform new node                
            embed, _ = await fn.embed(
                'Teleported player(s).',
                f"{playerMentions} got teleported here.",
                'You can view all players and where they are with /player find.') 
            nodeChannel = get(interaction.guild.text_channels, id = node.channelID)
            await nodeChannel.send(embed = embed)

            embed, _ = await fn.embed(
                'Teleport results.',
                description,
                'Woosh.')
            await fn.noCopies(
                (interaction.channel_id in exitingNodes or interaction.channel_id == node.channelID), 
                embed, 
                interaction)
            return

        view = oop.DialogueView(ctx.guild, refreshEmbed)
        await view.addPlayers(guildData.players)
        await view.addNodes(guildData.nodes.keys(), manyNodes = False)
        await view.addSubmit(teleportPlayers)
        await view.addCancel()
        embed = await refreshEmbed()
        await ctx.respond(embed = embed, view = view)
        return

class freeCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot
        self.updateChannels.start()

    def cog_unload(self):
        self.updateChannels.cancel()

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
                guildData = oop.GuildData(interaction.guild_id)
                player = oop.Player(interaction.user.id, ctx.guild_id)
                if player.location:
                    tutorialData['Player Channels'] += f" You're a" + \
                        " player in this server, so you'll use" + \
                        f" <#{player.channelID}>."
                    tutorialData['Locations'] += f" Right now, you're" + \
                        f" in **#{player.location}**."
                
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

        view = oop.DialogueView()
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
        await view.addCancel()
        await ctx.respond(embed = embed, view = view)
        return

    # @commands.slash_command(
    #     name = 'say',
    #     description = 'Here.')
    # async def say(
    #     self,
    #     ctx: discord.ApplicationContext):

    #     embed = discord.Embed(
    #         title = 'Version 1.1: The Tough Stuff Update',
    #         description = "This bot just got a lot harder to break. P.S. -" + \
    #             " Minecraft names their updates. That's fun, so I'll do it too.",
    #         color = discord.Color.from_rgb(67, 8, 69))

    #     embed.set_footer(text = 'I also spent two weeks rewriting the code' + \
    #         ' to be within an OOP framework. That took like 80% of the ' + \
    #         ' work and it barely makes a footnote because nobody knows what ' + \
    #         ' the hell an OOP is.')

    #     embed.add_field(
    #         name = 'New Features',
    #         value = "1. Renaming a channel..." + \
    #                 "\n - Is perfectly safe on player channels." + \
    #                 "\n - On node channels, renames the node." + \
    #                 "\n - ...unless that name's taken. Then it's name-2." + \
    #             "\n2. Deleting a channel..." + \
    #                 "\n - On player channels, deletes the player." + \
    #                 "\n - On node channels, deletes the node." + \
    #                 "\n - ...Unless it's occupied, then it'll remake it and scold you." + \
    #             "\n3. Messing with webhooks for node or player, same deal. :)",
    #         inline = False)      

    #     embed.add_field(
    #         name = 'Fixes',
    #         value = "1. Overhearing a node that gets deleted no longer" +\
    #                     " *permanently breaks your ability to overhear.*" + \
    #                 "\n2. Maps generated for `/server view`, `/map`, etc. now" + \
    #                     " won't have the node labels overlap with the edge arrows." + \
    #                 "\n3. The bot has a profile picture in *all* of its messages." + \
    #                 "\n4. Deleting multiple players who were in the same location" + \
    #                     " doesn't spam you anymore." + \
    #                 "\n5. TONS of formatting and typo corrections." + \
    #                 "\n6. Increased reliablity, scalability, and readability. The" + \
    #                     " code runs smoother, can be upgraded easier, and looks " + \
    #                     " better to the guy making it.",
    #         inline = False)        
            

    #     # embed, file = await fn.embed(
    #     #     'A locked computer.',
    #     #     "You used your *extension cord*. The **computer** " + \
    #     #         "is locked by a password.",
    #     #     "Just as an example.",
    #     #     ('assets/mockup.png', 'full'))

    #     # view = discord.ui.View()
    #     # button = discord.ui.Button(
    #     #     label = 'Input password',
    #     #     style = discord.ButtonStyle.secondary)
    #     # view.add_item(button)        
    #     # button = discord.ui.Button(
    #     #     label = 'Reclaim "Extension Cord"',
    #     #     style = discord.ButtonStyle.secondary)
    #     # view.add_item(button)
    #     # button = discord.ui.Button(
    #     #     label = 'Walk away',
    #     #     style = discord.ButtonStyle.secondary)
    #     # view.add_item(button)

    #     await ctx.respond(embed = embed)
    #     return

    @tasks.loop(seconds = 5.0)
    async def updateChannels(self):

        for guild in list(needingUpdate):

            guildData = oop.GuildData(guild.id)
            guildListeners = {}
            guildIndirects = {}

            cachedChannelReferences = {}
            cachedPlayerData = {}
            playerCacheHits = 0
            channelCacheHits = 0

            async def addListener(speaker: int, listener: discord.TextChannel, eavesdropping: bool = False):
                guildListeners.setdefault(speaker, [])
                guildListeners[speaker].append((listener, eavesdropping))
                return
            
            async def addIndirect(speaker: int, speakerLocation: str, listener: discord.TextChannel):
                guildIndirects.setdefault(speaker, [])
                guildIndirects[speaker].append((speakerLocation, listener))
                return

            async def channelLoad(channelID: int):

                channel = cachedChannelReferences.get(channelID, None)
                if not channel:
                    channel = get(guild.text_channels, id = channelID)
                    cachedChannelReferences[channelID] = channel
                else:
                    nonlocal channelCacheHits
                    channelCacheHits += 1                

                return channel

            async def playerLoad(playerID: int):

                player = cachedPlayerData.get(playerID, None)
                if not player:
                    player = oop.Player(playerID, guild.id)
                    cachedPlayerData[playerID] = player
                else:
                    nonlocal playerCacheHits
                    playerCacheHits += 1

                return player
            
            for ID in guildData.players:

                player = await playerLoad(ID)
                directListeners.pop(player.channelID, None)
                indirectListeners.pop(player.channelID, None)

            for name, node in guildData.nodes.items(): #For every node in the graph

                #Get node channel
                channel = await channelLoad(node.channelID)

                for ID in node.occupants: #For each occupant...

                    player = await playerLoad(ID)
                    await addListener(player.channelID, channel) #Node listens to player

                    playerChannel = await channelLoad(player.channelID)
                    await addListener(node.channelID, playerChannel) #Player listens to node

                    for occupant in node.occupants: #For every occupant...

                        if occupant != ID: #That isn't yourself...
                            occPlayer = await playerLoad(occupant)
                            await addListener(occPlayer.channelID, playerChannel) #Add them as a listener to you.

                    for neighborName in node.neighbors.keys():

                        neighborNode = guildData.nodes[neighborName]

                        for neighborOccupant in neighborNode.occupants: #For every person in the neighbor node...

                            neighOccPlayer = await playerLoad(neighborOccupant)
                            neighOccChannel = await channelLoad(neighOccPlayer.channelID)

                            if neighOccPlayer.eavesdropping == name: #If they're eavesdropping on us...
                                await addListener(player.channelID, neighOccChannel, True)
                                await addListener(node.channelID, neighOccChannel, True)
                            else: #Otherwise...
                                await addIndirect(player.channelID, player.location, neighOccChannel)

            directListeners.update(guildListeners)
            indirectListeners.update(guildIndirects)

            needingUpdate.remove(guild)
            updatedGuilds.add(guild.id)

        if brokenWebhooks:

            print(f'Fixing webhooks for {len(brokenWebhooks)} channels.')
            
            with open('assets/avatar.png', 'rb') as file:
                avatar = file.read()

            embed, _ = await fn.embed(
                'Hey. Stop that.',
                "Don't mess with the webhooks on here.",
                "They're mine, got it?")
                
            for channel in brokenWebhooks:

                webhooks = await channel.webhooks()
                if len(webhooks) != 1:
                    pass
                else:
                    firstHook = webhooks[0]
                    if firstHook.user == self.prox.user:
                        brokenWebhooks.discard(channel)
                        return

                for hook in webhooks:
                    await hook.delete()

                await channel.create_webhook(name = 'Proximity', avatar = avatar)
                await channel.send(embed = embed)
                brokenWebhooks.discard(channel)
                return
    
        #import json
        #printableListeners = {speakerID : [channel.name for channel, _ in listeners] 
        #    for speakerID, listeners in directListeners.items()}
        #print(f"Direct listeners: {json.dumps(printableListeners, indent = 4)}")

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

        guildData = oop.GuildData(ctx.guild_id)

        if ctx.author.id not in guildData.players:
            await fn.notPlayer(ctx)
            return

        player = oop.Player(ctx.author.id, ctx.guild_id)
        node = guildData.nodes[player.location]

        description = ''

        node.occupants.discard(ctx.author.id)
        if node.occupants:
            otherMentions = await oop.Format.players(node.occupants)
            description += f"There's {otherMentions} with you inside **#{player.location}**."
        else:
            description += f"You're by yourself inside **#{player.location}**. "

        ancestors = [name for name, edge in node.neighbors.items() if edge.directionality == 0]
        mutuals = [name for name, edge in node.neighbors.items() if edge.directionality == 1]
        successors = [name for name, edge in node.neighbors.items() if edge.directionality == 2]

        if ancestors:
            if len(ancestors) > 1:
                boldedNodes = await fn.boldNodes(ancestors)
                description += f" There are one-way routes from (<-) {boldedNodes}. "
            else:
                description += f" There's a one-way route from (<-) **#{ancestors[0]}**. "

        if mutuals:
            if len(mutuals) > 1:
                boldedNodes = await fn.boldNodes(mutuals)
                description += f" There's ways to {boldedNodes} from here. "
            else:
                description += f" There's a way to get to **#{mutuals[0]}** from here. "

        if successors:
            if len(successors) > 1:
                boldedNodes = await fn.boldNodes(successors)
                description += f" There are one-way routes to (->) {boldedNodes}. "
            else:
                description += f" There's a one-way route to (->) **#{successors[0]}**. "
      
        if not (ancestors or mutuals or successors):
            description += "There's no way in or out of here. Oh dear."

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

        guildData = oop.GuildData(ctx.guild_id)

        if ctx.author.id not in guildData.players:
            await fn.notPlayer(ctx)
            return
        
        player = oop.Player(ctx.author.id, ctx.guild_id)
        node = guildData.nodes[player.location]
        if player.eavesdropping:
            eavesNode = guildData.nodes.get(player.eavesdropping, None)
            if not eavesNode:
                player.eavesdropping = None
                await player.save()
        
        if player.eavesdropping: 
            
            if eavesNode.occupants:
                occupantMentions = await oop.Format.players(eavesNode.occupants)
                description = f"You're eavesdropping on {occupantMentions} in **#{player.eavesdropping}**."
            else:
                description = f"You're eavesdropping on **#{player.eavesdropping}**, but you think nobody is there."

            async def stopEavesdropping(interaction: discord.Interaction):

                await fn.waitForRefresh(interaction)

                embed, _ = await fn.embed(
                    'Saw that.',
                    f"You notice {ctx.author.mention} play it off like they" + \
                        f" weren't just listening in on **#{player.eavesdropping}**.",
                    'Do with that what you will.')
                await postToDirects(
                    embed, 
                    interaction.guild, 
                    node.channelID, 
                    player.channelID,
                    onlyOccs = True)
                
                player.eavesdropping = None
                await player.save()

                await queueRefresh(interaction.guild)

                await interaction.delete_original_response()
                embed, _ = await fn.embed(
                    'All done.',
                    "You're minding your own business, for now.",
                    'You can always choose to eavesdrop again later.')
                playerChannel = get(interaction.guild.text_channels, id = player.channelID)
                await playerChannel.send(embed = embed)
                return

            view = oop.DialogueView()
            await view.addEvilConfirm(callback = stopEavesdropping)
            await view.addCancel()
            embed, _ = await fn.embed(
                'Nosy.',
                description,
                'Would you like to stop eavesdropping?')
            await ctx.respond(embed = embed, view = view)
            return

        if node.neighbors:
            neighborNodes = await guildData.filterNodes(node.neighbors.keys())

            if any(node.occupants for node in neighborNodes.values()):

                occupiedNeighbors = {name : node for name, node in neighborNodes.items() \
                    if node.occupants}
                unoccupiedNeighbors = {name for name in neighborNodes.keys() if name not \
                    in occupiedNeighbors}

                description = 'Listening closely, you think that you can hear '
                fullList = []
                for neighborName, neighborNode in occupiedNeighbors.items():
                    occupantMentions = await oop.Format.players(neighborNode.occupants)
                    fullList.append(f'{occupantMentions} in **#{neighborName}**')
                description += f'{await oop.Format.words(fullList)}. '
                if unoccupiedNeighbors:
                    boldedUnoccupied = await oop.Format.bold(unoccupiedNeighbors)
                    description += f"You can also listen in on {boldedUnoccupied}, but it sounds like nobody is in there."
            else:
                boldedNeighbors = await oop.Format.bold(node.neighbors.keys())
                description = f"You're able to listen in on {boldedNeighbors} from here," + \
                    " but you don't hear anyone over there. "
        else:
            description = "If there was someplace nearby, you could listen in on it, but" + \
                " there's not. Wait, does that mean you're stuck here?"

        async def refreshEmbed():

            nonlocal description

            if view.nodes():
                selectedNode = view.nodes()[0]
                description = f'Eavesdrop on **#{selectedNode}**?'
            else:
                pass

            embed, _ = await fn.embed(
                'Eavesdrop?',
                description,
                'You can listen in on any place near you.')

            return embed

        async def submitEavesdrop(interaction: discord.Interaction):

            await fn.waitForRefresh(interaction)

            if not view.nodes():
                embed, _ = await fn.embed(
                    'Eavesdrop where?',
                    'You have to tell me where you would like to eavesdrop.',
                    'Try calling /eavesdrop again.')
                await interaction.followup.edit_message(
                    message_id = interaction.message.id,
                    embed = embed,
                    view = None)
                return
                
            player.eavesdropping = view.nodes()[0]
            await player.save()

            await queueRefresh(interaction.guild)

            embed, _ = await fn.embed(
                'Sneaky.',
                f"You notice {ctx.author.mention} start to listen in on **#{player.eavesdropping}**.",
                'Do with that what you will.')
            await postToDirects(
                embed, 
                interaction.guild, 
                node.channelID, 
                player.channelID,
                onlyOccs = True)

            await interaction.delete_original_response()
            embed, _ = await fn.embed(
                'Listening close...',
                f"Let's hear what's going on over there in **#{player.eavesdropping}**, shall we?",
                "Be mindful that people can see that you're doing this.")
            playerChannel = get(interaction.guild.text_channels, id = player.channelID)
            await playerChannel.send(embed = embed)
            return

        view = oop.DialogueView(refresh = refreshEmbed)
        await view.addUserNodes(node.neighbors.keys())
        if node.neighbors:
            await view.addSubmit(submitEavesdrop)
            await view.addCancel()
            embed = await refreshEmbed()
            await ctx.respond(embed = embed, view = view)
        else:
            embed = await refreshEmbed()
            await ctx.respond(embed = embed)
        return

    @commands.slash_command(
        name = 'map',
        description = 'See where you can go.',
        guild_only = True)
    async def map(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        if ctx.author.id not in guildData.players:
            await fn.notPlayer(ctx)
            return
        
        player = oop.Player(ctx.author.id, ctx.guild_id)
        playerRoleIDs = [role.id for role in ctx.author.roles]

        graph = await guildData.filterMap(
            playerRoleIDs,
            ctx.author.id, 
            player.location)
        map = await guildData.toMap(graph)

        embed, file = await fn.embed(
            'Map',
            f"Here are all the places you can reach from **#{player.location}**." + \
                " You can travel along the arrows that point to where you want to go. ",
            "Use /move to go there.",
            (map, 'full'))
        
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
            autocomplete = oop.Auto.map,
            required = False)):

        await ctx.defer(ephemeral = True)

        guildData = oop.GuildData(ctx.guild_id)

        if ctx.author.id not in guildData.players:
            await fn.notPlayer(ctx)
            return

        player = oop.Player(ctx.author.id, ctx.guild_id)

        playerRoleIDs = [role.id for role in ctx.author.roles]
        map = await guildData.filterMap(
            playerRoleIDs,
            ctx.author.id,
            player.location)
        
        description = f"Move from **#{player.location}**"

        destinationName = node if node and node != player.location else None

        async def refreshEmbed():

            fullDescription = description

            nonlocal destinationName

            if view.nodes():
                destinationName = view.nodes()[0]
            
            if destinationName:
                fullDescription += f' to **#{destinationName}**?'
            else:
                fullDescription += f'? Where would you like to go?'

            embed, _ = await fn.embed(
                'Move?',
                fullDescription,
                "Bear in mind that others will notice.")
            return embed

        async def submitDestination(interaction: discord.Interaction):

            await fn.waitForRefresh(interaction)

            path = nx.shortest_path(map,
                source = player.location,
                target = destinationName)

            pathAdjs = await guildData.neighbors(set(path), exclusive = True)
            nonPathAdjNodes = await guildData.filterNodes(pathAdjs)
            nearbyOccs = await guildData.getUnifiedOccupants(nonPathAdjNodes.values())

            for occID in nearbyOccs:
                eavesPlayer = oop.Player(occID, ctx.guild_id)
                if eavesPlayer.location in path:
                    continue
                if eavesPlayer.eavesdropping in path:
                    whichPart = path.index(eavesPlayer.eavesdropping)
                    eavesChannel = get(interaction.guild.text_channels, id = eavesPlayer.channelID)

                    match whichPart:

                        case 0:
                            embed, _ = await fn.embed(
                                'Someone got moving.',
                                f"You can hear someone in **#{path[whichPart]}** start" + \
                                    f" to go towards **#{path[whichPart + 1]}**.",
                                'Who could it be?')
                            await eavesChannel.send(embed = embed)

                        case halfway if whichPart < len(path):
                            embed, _ = await fn.embed(
                                'Someone passed through.',
                                f"You can hear someone go through **#{path[whichPart]}**,\
                                from **#{path[whichPart - 1]}** to **#{path[whichPart + 1]}**.",
                                'On the move.')
                            await eavesChannel.send(embed = embed)

                        case ending if whichPart == len(path) - 1:
                            embed, _ = await fn.embed(
                                'Someone stopped by.',
                                f"You can hear someone come from **#{path[whichPart - 1]}**" +
                                    f" and stop at **#{path[whichPart + 1]}**.",
                                'Wonder why they chose here.')
                            await eavesChannel.send(embed = embed)

            #Inform origin occupants
            embed, _ = await fn.embed(
                'Departing.',
                f"You notice {ctx.author.mention} leave, heading towards **#{path[1]}**.",
                'Maybe you can follow them?')
            await postToDirects(
                embed, 
                interaction.guild, 
                guildData.nodes[path[0]].channelID, 
                player.channelID,
                onlyOccs = True)

            nodeChannel = get(
                interaction.guild.text_channels,
                id = guildData.nodes[path[0]].channelID)
            embed, _ = await fn.embed(
                'Departing.',
                f"{interaction.user.mention} left here to go to **#{path[-1]}**.",
                f"They went from {' -> '.join(path)}.")
            await nodeChannel.send(embed = embed)

            #Inform destination occupants
            embed, _ = await fn.embed(
                'Arrived.',
                f"You notice {ctx.author.mention} arrive from the direction of **#{path[-2]}**.",
                'Say hello.')
            await postToDirects(embed, 
                interaction.guild, 
                guildData.nodes[path[-1]].channelID,
                player.channelID,
                onlyOccs = True)

            nodeChannel = get(
                interaction.guild.text_channels,
                id = guildData.nodes[path[-1]].channelID)
            embed, _ = await fn.embed(
                'Arriving.',
                f"{interaction.user.mention} arrived here from **#{path[0]}**.",
                f"They went from {' -> '.join(path)}.")
            await nodeChannel.send(embed = embed)

            #Inform intermediary nodes + their occupants
            for index, midwayName in enumerate(path[1:-1]): 
                embed, _ = await fn.embed(
                    'Passing through.',
                    f"You notice {interaction.user.mention} come in" + \
                        f" from the direction of **#{path[index]}**" + \
                        f" before continuing on their way towards **#{path[index + 2]}**.",
                    'Like two ships in the night.')
                await postToDirects(embed, 
                    interaction.guild, 
                    guildData.nodes[midwayName].channelID,
                    onlyOccs = True)

                nodeChannel = get(
                    interaction.guild.text_channels,
                    id = guildData.nodes[midwayName].channelID)
                embed, _ = await fn.embed(
                    'Transit.',
                    f"{interaction.user.mention} passed through here when traveling from" + \
                        f" **#{path[0]}>** to **#{path[-1]}**.",
                    f"They went from {' -> '.join(path)}.")
                await nodeChannel.send(embed = embed)

            pathNodes = await guildData.filterNodes(path)
            await pathNodes[path[0]].removeOccupants({player.id})

            #Calculate who they saw on the way
            fullMessage = []
            for name, node in pathNodes.items():

                if node.occupants:
                    occupantsMention = await oop.Format.players(node.occupants)
                    fullMessage.append(f'{occupantsMention} in **#{name}**')

            #Inform player of who they saw and what path they took
            if fullMessage:
                description = f"Along the way, you saw (and were seen" + \
                    f"by) {await fn.listWords(fullMessage)}."
            else:
                description = "You didn't see anyone along the way."

            #Change occupants
            await pathNodes[path[-1]].addOccupants({player.id})
            await guildData.save()

            #Update location and eavesdropping
            player.location = path[-1]
            player.eavesdropping = None
            await player.save()

            await queueRefresh(interaction.guild)

            #Tell player
            embed, _ = await fn.embed(
                'Movement',
                description,
                f"The path you traveled was {' -> '.join(path)}.")
            playerChannel = get(interaction.guild.text_channels, id = player.channelID)
            await playerChannel.send(embed = embed)
            await interaction.followup.delete_message(message_id = interaction.message.id)
            return

        view = oop.DialogueView(refresh = refreshEmbed)
        if not destinationName:
            await view.addUserNodes(
                [node for node in map.nodes if node != player.location])
        await view.addSubmit(submitDestination)
        await view.addCancel()
        embed = await refreshEmbed()        
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

        for guild in self.prox.guilds:
            needingUpdate.add(guild)
            print(f'Added {guild.name} to the queue of servers needing updated listeners.')

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

