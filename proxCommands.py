import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
from discord.utils import get_or_fetch, get

import functions as fn
import databaseFunctions as db

import asyncio
import time
import networkx as nx

global updatedGuilds, needingUpdate, directListeners, indirectListeners, proximity
proximity = None
updatedGuilds = set()
needingUpdate = set()
directListeners = {}
indirectListeners = {}

async def queueRefresh(guild: discord.Guild):
    updatedGuilds.discard(guild.id)
    needingUpdate.add(guild)
    return

async def relay(msg: discord.Message):

    if msg.author.id == 1114004384926421126:
        return

    if msg.guild.id not in updatedGuilds:
        
        needingUpdate.add(msg.guild)
        
        while msg.guild.id not in updatedGuilds:
            print(f'Waiting for updated listeners in server: {msg.guild.name}.')
            await asyncio.sleep(2)

    directs = directListeners.get(msg.channel.id, [])
    for channel, eavesdropping in directs:

        if eavesdropping:
            embed, _ = await fn.embed(
                msg.author.name,
                msg.content,
                'You hear every word that they say.')
            await channel.send(embed = embed)

        else:
            webhook = (await channel.webhooks())[0]
            await webhook.send(msg.content, username = msg.author.display_name, avatar_url = msg.author.avatar.url)

    indirects = indirectListeners.get(msg.channel.id, [])
    for speakerLocation, channel in indirects:
        embed, _ = await fn.embed(
            f'Hm?',
            f"You think you hear {msg.author.mention} in #{speakerLocation}.",
            'This is a placeholder feature. The real version will speak the messages as a proxy.')
        await channel.send(embed = embed)

    if directs or indirects:
        await msg.add_reaction('✔️')   
        
    return

async def postToDirects(embed: discord.Embed, guild: discord.Interaction, channelID: int, exclude: int = 0):

    if guild.id not in updatedGuilds:
    
        needingUpdate.add(guild)
        
        while guild.id not in updatedGuilds:
            print(f'Waiting for updated listeners in server: {guild.name}.')
            await asyncio.sleep(2)
    
    directs = directListeners.get(channelID, [])
    for channel, eavesdropping in directs:

        if channel.id == exclude:
            continue

        try:
            webhook = (await channel.webhooks())[0]
            await webhook.send(embed = embed)
        except:
            print(f"Tried to send a message to a channel that doesn't exist anymore, {channel.id}. It's probably fine.")

    return

class nodeCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    node = SlashCommandGroup(
        name = 'node',
        description = 'Manage the nodes of your graph.',
        guild_only = True,
        guild_ids = [1114005940392439899])

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

        guildData, members = db.mag(ctx.guild_id)

        name = await fn.discordify(name)
        allowedRoles = []

        async def refreshEmbed():

            nonlocal name, allowedRoles
            
            if nameSelect.value:
                name = await fn.discordify(nameSelect.value)

            allowedRoles = [role.id for role in addRoles.values]
            
            description = f'Whitelist: {await fn.formatWhitelist(allowedRoles, addPlayers.values)}'

            #Formatting results
            embed, _ = await fn.embed(
                f'New node: {name}',
                description,
                'You can also create a whitelist to limit who can visit this node.')
            
            return embed

        async def submitNode(interaction: discord.Interaction):
            
            await interaction.response.defer()

            nonlocal allowedRoles

            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)

            if await fn.nodeExists(guildData['nodes'], name, interaction):
                return
    
            nodeCategory = await fn.assertCategory(interaction.guild, 'nodes') 
            newChannel = await fn.newChannel(interaction.guild, name, nodeCategory)
            guildData['nodes'][name] = await fn.newNode(
                newChannel, 
                allowedRoles, 
                [int(ID) for ID in addPlayers.values])

            db.updateGuild(con, guildData, interaction.guild_id)
            con.close()

            embed, _ = await fn.embed(
                'Node created!',
                f"You can find it at {newChannel.mention}.\
                The permissions you requested are set-- just not in the channel's Discord\
                settings. No worries, it's all being kept track of by me.",
                'I hope you like it.')        
            await interaction.followup.edit_message(
                message_id = interaction.message.id,
                embed = embed,
                view = None)

            whitelist = await fn.formatWhitelist(allowedRoles, addPlayers.values)
            embed, _ = await fn.embed(
            'Cool, new node.',
            f"**Important!** Don't mess with the settings for this channel! \
            That means no editing the permissions, the name, or deleting it. Use \
            `/node review`, or your network will be broken! If you do, run `/server fix`.\
            \n\nAnyways, here's who is allowed:\n{whitelist}\n\n Of course, this can change \
            with `/node review`, which lets you view/change the whitelist, among other things.",
            "You can also set the location message for this node by doing /node message while you're here.")         
            await newChannel.send(embed = embed)
            return

        view = discord.ui.View()
        view, addRoles = await fn.addRoles(view, len(ctx.guild.roles), refresh = refreshEmbed)
        view, addPlayers = await fn.addPlayers(view, ctx.guild.members, members, refresh = refreshEmbed)
        view, submit = await fn.addSubmit(view, submitNode)
        view, nameSelect = await fn.addNameModal(view, refresh = refreshEmbed)
        view, cancel = await fn.addCancel(view)
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

        guildData = db.gd(ctx.guild_id)

        async def deleteNodes(deletingNodeNames: list):

            deletingNodeNames = deletingNodeNames
            deletingNodes = await fn.filterNodes(guildData['nodes'], deletingNodeNames)
            deletingMentions = await fn.mentionNodes(deletingNodes)
            
            async def confirmDelete(interaction: discord.Interaction):

                await interaction.response.defer()

                nonlocal deletingNodeNames, deletingNodes, deletingMentions

                occupantsData = await fn.getOccupants(deletingNodes)
                deletingNodes = {node : data for node, data in deletingNodes.items() if node not in occupantsData}

                #Inform occupants of neighbor nodes that the node is deleted now
                graph = await fn.makeGraph(guildData)
                for neighbor in await fn.getConnections(graph, deletingNodeNames): 
                    embed, _ = await fn.embed(
                        'Misremembered?',
                        f"Could you be imagining {deletingMentions}? Strangely, there's no trace.",
                        "Whatever the case, it's gone now.")
                    await postToDirects(embed, interaction.guild, guildData['nodes'][neighbor]['channelID'])

                #Delete unoccupied nodes and edges
                for nodeName in deletingNodes:

                    await fn.deleteChannel(ctx.guild.text_channels, guildData['nodes'][nodeName]['channelID'])
                    del guildData['nodes'][nodeName]

                    deletingEdges = [key for key in guildData['edges'].keys() if nodeName in key]
                    for key in deletingEdges:
                        del guildData['edges'][key]

                con = db.connectToGuild()               
                db.updateGuild(con, guildData, interaction.guild_id)
                con.close()
                
                if interaction.channel.name not in deletingNodes:
                    description = ''

                    if deletingNodes:
                        description += f'Successfully deleted the following things about {deletingNodeNames}:\
                            \n• The node data in the database.\
                            \n• The node channels.\
                            \n• All edges to and from the node.'

                    if occupantsData:
                        occupiedNodes = await fn.filterNodes(guildData['nodes'], occupantsData.keys())
                        occupiedMentions = await fn.mentionNodes(occupiedNodes)
                        description += f"\n\nCouldn't delete {occupiedMentions}:\
                        I can't delete a node unless it's unoccupied. Use `/player tp` to move them."
                    
                    embed, _ = await fn.embed(
                        'Delete results',
                        description,
                        'Say goodbye.')
                    await interaction.followup.edit_message(message_id = interaction.message.id, embed = embed, view = None)
                return
         
            view = discord.ui.View()
            view, evilConfirm = await fn.addEvilConfirm(view, confirmDelete)
            view, cancel = await fn.addCancel(view)
            embed, _ = await fn.embed(
                'Confirm deletion?',
                f"Delete {deletingMentions}?",
                'This will also delete any edges connected to the node(s).')
            await ctx.respond(embed = embed, view = view, ephemeral = True)
            return

        result = await fn.identifyNodeChannel(guildData['nodes'], ctx.channel.name, node)
        match result:
            case isMessage if isinstance(result, discord.Embed):
                await ctx.respond(embed = result)
            case isChannel if isinstance(result, str):
                await deleteNodes([result])
            case None:
            
                embed, _ = await fn.embed(
                    'Delete Node(s)?',
                    "You can delete a node three ways:\n\
                    • Call this command inside of a node channel.\n\
                    • Do `/node delete #node-channel`.\n\
                    • Select multiple node channels with the list below.",
                    'This will remove the node(s), all its edges, and any corresponding channels.')

                async def submitNodes(interaction: discord.Interaction):
                    await ctx.delete()
                    await deleteNodes(addNodes.values)
                    return

                view = discord.ui.View()
                view, addNodes = await fn.addNodes(view, guildData['nodes'].keys(), submitNodes)
                view, cancel = await fn.addCancel(view)
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

        guildData, members = db.mag(ctx.guild_id)\

        async def reviseNodes(nodeNames: list):

            title = f'Reviewing {len(nodeNames)} node(s).'
            revisingNodes = await fn.filterNodes(guildData['nodes'], nodeNames)
            firstNodeData = list(revisingNodes.values())[0]
            nodeMentions = await fn.mentionNodes(revisingNodes)
            intro = f"• Selected node(s): {nodeMentions}"

            occupantData = await fn.getOccupants(revisingNodes)
            if occupantData:

                occupantMentions = []
                for occupantList in occupantData.values():
                    for occupant in occupantList:
                        occupantMentions.append(f'<@{occupant}>')
                
                description = f'\n• Occupants: {await fn.listWords(occupantMentions)}'
            else:
                description = '\n• Occupants: There are no people here.'

            graph = await fn.makeGraph(guildData)
            neighbors = await fn.getConnections(graph, nodeNames)
            if neighbors:
                subgraph = graph.subgraph(neighbors + nodeNames)
                description += '\n• Edges: See below.'
                graphView = (await fn.showGraph(subgraph), 'full')
            else:
                description += '\n• Edges: There are no nodes connected to the selected node(s).'
                graphView = None

            hasWhitelist = False
            for node in revisingNodes.values():
                if node.get('allowedRoles', False) or node.get('allowedPeople', False):
                    hasWhitelist = True
                    break

            name = ''
            clearing = False

            async def refreshEmbed():

                nonlocal name
                if len(nodeNames) == 1:
                    name = await fn.discordify(addNameModal.value)

                fullDescription = intro
                if name:
                    fullDescription += f', renaming to {name}.'
                fullDescription += description
                
                if clearing:
                    fullDescription += f"\n• Whitelist: Removing all restrictions. Click 'Clear Whitelist' again\
                        to use the pre-existing whitelist (or the whitelist composed of what's below, if any\
                        roles or people are specified)."
                
                else:
                    if addRoles.values or addPlayers.values:
                        allowedRoles = [role.id for role in addRoles.values]
                        fullDescription += f"\n• New whitelist(s)-- will overwrite any previous whitelist: \
                            {await fn.formatWhitelist(allowedRoles, addPlayers.values)}"

                    elif len(nodeNames) == 1:
                        fullDescription += f"\n• Whitelist: \
                            {await fn.formatWhitelist(firstNodeData.get('allowedRoles', []), firstNodeData.get('allowedPeople', []))}"
            
                    else:
                        if await fn.whitelistsSimilar(revisingNodes.values()):
                            fullDescription += f"\n• Whitelists: Every node has the same whitelist-\
                            \"{await fn.formatWhitelist(firstNodedata.get('allowedRoles', []), firstNodedata.get('allowedPeople', []))}"
                        else:
                            fullDescription += f'\n• Whitelists: Multiple different whitelists.'

                embed, _ = await fn.embed(
                    title,
                    fullDescription,
                    'You can rename a node if you have only one selected.',
                    graphView)
                return embed

            async def clearWhitelist(interaction: discord.Interaction):
                nonlocal clearing
                clearing = not clearing
                embed = await refreshEmbed()
                await interaction.response.edit_message(embed = embed)
                return 

            async def submitNode(interaction: discord.Interaction):

                await interaction.response.defer()

                nonlocal name

                con = db.connectToGuild()
                guildData = db.getGuild(con, interaction.guild_id)
                
                if await fn.nodeExists(guildData['nodes'], name, interaction):
                    return

                if await fn.noChanges((name or addRoles.values or addPlayers.values or clearing), interaction):
                    return

                description = ''

                if clearing:
                    description += '\n• Removed the whitelist(s).'
                    for nodeName in nodeNames:
                        guildData['nodes'][nodeName].pop('allowedRoles', None)
                        guildData['nodes'][nodeName].pop('allowedPeople', None)

                        embed, _ = await fn.embed(
                            'Liberating.',
                            "You feel like this place just got more open somehow.",
                            "For better or for worse.")
                        await postToDirects(embed, interaction.guild, revisingNodes[nodeName]['channelID'])

                else:
                    if addRoles.values:
                        description += '\n• Edited the roles whitelist(s).'
                    if addPlayers.values:
                        description += '\n• Edited the people whitelist(s).'
                    
                    allowedRoles = [role.id for role in addRoles.values]

                    embed, _ = await fn.embed(
                        'Strange.',
                        "There's a sense that this place just changed in some way.",
                        "Only time will tell if you'll be able to return here as easily as you came.")

                    for nodeName in nodeNames:
                        await postToDirects(embed, interaction.guild, revisingNodes[nodeName]['channelID'])

                        if allowedRoles:
                            guildData['nodes'][nodeName]['allowedRoles'] = allowedRoles
                        else:
                            guildData['nodes'][nodeName].pop('allowedRoles', None)
                        
                        if addPlayers.values:
                            guildData['nodes'][nodeName]['allowedPeople'] = [int(ID) for ID in addPlayers.values]
                        else:
                            guildData['nodes'][nodeName].pop('allowedPeople', None)
                    
                if name:
                    guildData['nodes'][name] = guildData['nodes'].pop(nodeNames[0])
                    description += f"\n• Renamed {nodeNames[0]} to <#{firstNodeData['channelID']}>."

                    playerCon = db.connectToPlayer()
                    for occupantList in occupantData.values():

                        for occupant in occupantList:

                            playerData = db.getPlayer(con, occupant)
                            playerData[str(interaction.guild_id)]['locationName'] = name
                            db.updatePlayer(con, playerData, occupant)
                    playerCon.close()
                    
                    nodeChannel = get(interaction.guild.text_channels, id = firstNodeData['channelID'])
                    await nodeChannel.edit(name = name)

                db.updateGuild(con, guildData, interaction.guild_id)
                con.close()        

                embed, _ = await fn.embed(
                    'Edited.',
                    description,
                    'Another successful edit.')
                for node in revisingNodes.values():
                    nodeChannel = get(interaction.guild.text_channels, id = node['channelID'])
                    await nodeChannel.send(embed = embed)  

                if interaction.channel.name in revisingNodes or interaction.channel.name == name:
                    await interaction.delete_original_response()
                else:
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        view = None)

                return              
            
            view = discord.ui.View()
            view, addRoles = await fn.addRoles(view, len(ctx.guild.roles), refresh = refreshEmbed)
            view, addPlayers = await fn.addPlayers(view, ctx.guild.members, members, refresh = refreshEmbed)
            view, submit = await fn.addSubmit(view, submitNode)
            if len(nodeNames) == 1:
                view, addNameModal = await fn.addNameModal(view, refreshEmbed)
            if hasWhitelist:
                view, clear = await fn.addClear(view, clearWhitelist)
            view, cancel = await fn.addCancel(view)
            embed = await refreshEmbed()
            _, file = await fn.embed(
                imageDetails = graphView)

            await ctx.respond(embed = embed, view = view, file = file, ephemeral = True)
            return

        result = await fn.identifyNodeChannel(guildData['nodes'], ctx.channel.name, node)
        match result:
            case isMessage if isinstance(result, discord.Embed):
                await ctx.respond(embed = result)
            case isChannel if isinstance(result, str):
                await reviseNodes([result])
            case None:
            
                embed, _ = await fn.embed(
                    'Review node(s)?',
                    "You can revise a node three ways:\n\
                    • Call this command inside of a node channel.\n\
                    • Do `/node review #node-channel`.\n\
                    • Select multiple node channels with the list below.",
                    'This will allow you to view the nodes, their edges, and the whitelists.')

                async def submitNodes(interaction: discord.Interaction):
                    await ctx.delete()
                    await reviseNodes(addNodes.values)
                    return

                view = discord.ui.View()       
                
                nodes = [nodeName for nodeName, nodeData in guildData['nodes'].items() if nodeData['channelID'] != ctx.channel_id]
                view, addNodes = await fn.addNodes(view, nodes, submitNodes)
                view, cancel = await fn.addCancel(view)
                await ctx.respond(embed = embed, view = view)

        return

class edgeCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    edge = SlashCommandGroup(
        name = 'edge',
        description = 'Manage edges between nodes.',
        guild_only = True,
        guild_ids = [1114005940392439899])

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

        guildData, members = db.mag(ctx.guild_id)

        if len(guildData['nodes']) < 2:
            embed, _ = await fn.embed(
                'Hold on.',
                'An edge is a connection between two nodes. As such, it needs two nodes\
                before you can make an edge. You can make some with `/node new`.',
                'Head there first.')
            await ctx.respond(embed = embed)
            return

        async def createEdges(originName: str):

            origin = guildData['nodes'][originName]
            originMention = f"<#{origin['channelID']}>"
            directionality = 1
            overwrites = False
            destinations = []
            
            async def refreshEmbed():

                nonlocal destinations

                description = f'• Origin: {originMention}'

                if addNodes.values:
                    destinations = await fn.filterNodes(guildData['nodes'], addNodes.values)
                    destinationMentions = await fn.mentionNodes(destinations)
                    description += f'\n• Destination(s): {destinationMentions}.'
                else:
                    description += f"\n• Destination(s): None yet! Add some nodes to draw an edge to."

                allowedRoles = [role.id for role in addRoles.values]
                description += f"\n• Whitelist: {await fn.formatWhitelist(allowedRoles, [int(ID) for ID in addPlayers.values])}"

                match directionality:
                    case 0:
                        description += f'\n• Directionality: These connections are **one-way** (<-) from\
                        the destination(s) to {originMention}.'
                    case 1:
                        description += f'\n• Directionality: **Two-way** (<->), people will be able to travel\
                        back and forth between {originMention} and the destination(s).'
                    case 2:
                        description += f'\n• Directionality: These connections are **one-way** (->) from\
                        {originMention} to the destination(s).'

                if overwrites:
                    description += f"\n• **Overwriting** edges. Old edges will be erased where new one are laid."
                else:
                    description += f"\n• Will not overwrite edges. Click below to toggle."

                embed, _ = await fn.embed(
                    f'New edge(s)',
                    description,
                    'Which nodes are we hooking up?')
                return embed
            
            async def toggledDir(interaction: discord.Interaction):
                nonlocal directionality
                if directionality < 2:
                    directionality += 1
                else:
                    directionality = 0

                embed = await refreshEmbed()
                await interaction.response.edit_message(embed = embed)
                return 
            
            async def toggledOW(interaction: discord.Interaction):
                nonlocal overwrites
                overwrites = not overwrites
                embed = await refreshEmbed()
                await interaction.response.edit_message(embed = embed)
                return 

            async def submitEdges(interaction: discord.Interaction):

                await fn.loading(interaction)
                    
                #Screen for no nodes selected
                if await fn.noNodes(addNodes.values, interaction, True):
                    return

                #Prep edges for being written to
                existingEdges = 0
                if overwrites:
                    for destination in destinations.keys():
                        firstEdge = guildData['edges'].pop((originName, destination), None)
                        secondEdge = guildData['edges'].pop((destination, originName), None)
                        if firstEdge or secondEdge:
                            existingEdges += 1
                else:
                    for destination in list(destinations.keys()):
                        firstEdge = guildData['edges'].get((originName, destination), None)
                        secondEdge = guildData['edges'].get((destination, originName), None)
                        if firstEdge != None or secondEdge != None:
                            del destinations[destination]
                            existingEdges += 1
                            continue
                
                #Mention existing nodes impact on the result
                description = ''
                if existingEdges:
                    if overwrites:
                        description += f'\n• Overwrote {existingEdges} edge(s).'
                    else:
                        description += f'\n• Skipped {existingEdges} edge(s) because the nodes were already connected. Enable overwriting to ignore.'
                
                #Screen for no available nodes
                if not destinations:
                    embed, _ = await fn.embed(
                        'Hm.',
                        description,
                        "And that's all that you gave.")
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        view = None)  
                    return

                #Make edges now that destinations are clear for launch
                newEdges = {}
                for destination in destinations.keys():
                    if directionality > 0:
                        newEdges[(originName, destination)] = {}
                
                    if directionality < 2:
                        newEdges[(destination, originName)] = {}

                if addRoles.values:
                    allowedRoles = [role.id for role in addRoles.values]
                    for edgeName in newEdges.keys():
                        newEdges[edgeName]['allowedRoles'] = allowedRoles

                if addPlayers.values:
                    for edgeName in newEdges.keys():
                        newEdges[edgeName]['allowedPeople'] = [int(ID) for ID in addPlayers.values]
                
                con = db.connectToGuild()
                guildData['edges'].update(newEdges)
                db.updateGuild(con, guildData, interaction.guild_id)
                con.close()
                await queueRefresh(interaction.guild)
                    
                #Inform neighbors occupants and neighbor nodes
                destinationMentions = await fn.mentionNodes(destinations)
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"You notice a way to get between this place and {originMention}. Has that always been there?",
                    'And if so, has it always been like that?')
                nodeEmbed, _ = await fn.embed(
                    'Edge created.',
                    f'Created an edge between here and {originMention}.',
                    'You can view its details with /node review.')
                for data in destinations.values():
                    await postToDirects(playersEmbed, interaction.guild, data['channelID'])
                    nodeChannel = get(interaction.guild.text_channels, id = data['channelID'])
                    await nodeChannel.send(embed = nodeEmbed)

                #Inform edited node occupants
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"You notice that this place is connected to {destinationMentions}. Something about that seems new.",
                    "Perhaps you're only imagining it.")         
                await postToDirects(playersEmbed, interaction.guild, guildData['nodes'][originName]['channelID'])

                #Inform own node
                description += f'• Connected {originMention}'
                match directionality:
                    case 0:
                        description += ' <- from '
                    case 1:
                        description += ' <-> back and forth to '
                    case 2:
                        description += ' -> to '
                description += f'{destinationMentions}.'
                
                if addRoles.values:
                    description += '\n• Imposed the role restrictions on the whitelist.'
                    allowedRoles =  [role.id for role in addRoles.values]
                    for edgeName in newEdges.keys():
                        newEdges[edgeName]['allowedRoles'] = allowedRoles

                if addPlayers.values:
                    description += '\n• Imposed the person restrictions on the whitelist.'
                    for edgeName in newEdges.keys():
                        newEdges[edgeName]['allowedPeople'] = [int(ID) for ID in addPlayers.values]

                description += 'You can view the graph with `/server view`, or view\
                the edges of specific nodes with `/node review`.'
                
                embed, file = await fn.embed(
                    'New edge results.',
                    description,
                    'I hope you like it.')        
                nodeChannel = get(interaction.guild.text_channels, id = origin['channelID'])
                await nodeChannel.send(embed = embed)

                if interaction.channel.name in destinations or interaction.channel.name == originName:
                    await interaction.delete_original_response()
                else:
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        view = None)    
                return

            view = discord.ui.View()
            nodes = [nodeName for nodeName in guildData['nodes'].keys() if nodeName != originName]
            view, addNodes = await fn.addNodes(view, nodes, refresh = refreshEmbed)
            view, addRoles = await fn.addRoles(view, len(ctx.guild.roles), refresh = refreshEmbed)
            view, addPlayers = await fn.addPlayers(view, ctx.guild.members, members, refresh = refreshEmbed)
            view, submit = await fn.addSubmit(view, submitEdges)

            toggleDir = discord.ui.Button(
                label = 'Toggle Directionality',
                style = discord.ButtonStyle.secondary)
            toggleDir.callback = toggledDir
            view.add_item(toggleDir)

            toggleOW = discord.ui.Button(
                label = 'Toggle Overwrites',
                style = discord.ButtonStyle.secondary)
            toggleOW.callback = toggledOW
            view.add_item(toggleOW)

            view, cancel = await fn.addCancel(view)
            embed = await refreshEmbed()
                
            await ctx.respond(embed = embed, view = view, ephemeral = True)
            return

        result = await fn.identifyNodeChannel(guildData['nodes'], ctx.channel.name, origin)
        match result:
            case isMessage if isinstance(result, discord.Embed):
                await ctx.respond(embed = result)
            case isChannel if isinstance(result, str):
                await createEdges(result)
            case None:
            
                embed, _ = await fn.embed(
                    'Connect nodes?',
                    "You can create a new edge three ways:\n\
                    • Call this command inside of a node channel.\n\
                    • Do `/edge new #node-channel`.\n\
                    • Select a node channel with the list below.",
                    "This is just to select the origin, you'll select the destinations next.")

                async def submitNodes(interaction: discord.Interaction):
                    await ctx.delete()
                    await createEdges(addNodes.values[0])
                    return

                view = discord.ui.View()          
                view, addNodes = await fn.addNodes(view, guildData['nodes'].keys(), submitNodes, manyNodes = False)
                view, cancel = await fn.addCancel(view)
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
            ancestors, neighbors, successors = await fn.getConnections(graph, [originName], True)
            allNeighbors = ancestors + neighbors + successors
            if not allNeighbors:
                embed, _ = await fn.embed(
                    'No edges.',
                    f'{originMention} has no edges to view.',
                    'So I suppose that answers your inquiry.')
                await ctx.respond(embed = embed, ephemeral = True)
                return

            subgraph = graph.subgraph(allNeighbors + [originName])
            description = f'{originMention} has the following connections:'

            description += await fn.formatEdges(guildData['nodes'], ancestors, neighbors, successors)

            deletedEdges = []
            graphImage = None

            async def refreshEmbed():

                embed, file = await fn.embed(
                    'Delete edge(s)?',
                    description,
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
                await interaction.response.edit_message(file = discord.File(graphImage, filename = 'image.png'))
                return

            async def confirmDelete(interaction: discord.Interaction):

                await fn.loading(interaction)

                #Delete edges
                for neighbor in deletedEdges:

                    guildData['edges'].pop((neighbor, originName), None)
                    guildData['edges'].pop((originName, neighbor), None)

                con = db.connectToGuild()
                db.updateGuild(con, guildData, interaction.guild_id)
                con.close()

                await queueRefresh(interaction.guild)

                deletedNeighbors = await fn.filterNodes(guildData['nodes'], deletedEdges)
                deletedMentions = await fn.mentionNodes(deletedNeighbors)

                #Inform neighbors occupants and neighbor nodes
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"The path between here and {originMention} just closed.",
                    'Just like that...')
                nodeEmbed, _ = await fn.embed(
                    'Edge deleted.',
                    f'Removed an edge between here and {originMention}.',
                    'You can view the remaing edges with /node review.')
                for data in deletedNeighbors.values():
                    await postToDirects(playersEmbed, interaction.guild, data['channelID'])
                    nodeChannel = get(interaction.guild.text_channels, id = data['channelID'])
                    await nodeChannel.send(embed = nodeEmbed)

                #Inform edited node occupants
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"This place just lost access to {deletedMentions}.",
                    "Will that path ever be restored?")         
                await postToDirects(playersEmbed, interaction.guild, guildData['nodes'][originName]['channelID'])

                #Inform own node            
                embed, _ = await fn.embed(
                    'Edges deleted.',
                    f'Removed the edges to {deletedMentions}. Talk about cutting ties.',
                    'You can always make some new ones with /edge new.')   
                nodeChannel = get(interaction.guild.text_channels, name = originName)
                await nodeChannel.send(embed = embed)

                if interaction.channel.name == originName:
                    await ctx.delete()
                else:
                    await ctx.edit(
                        embed = embed,
                        view = None)    
                return

            view = discord.ui.View()
            view, addEdges = await fn.addEdges(refreshFile, ancestors, neighbors, successors, view)
            view, evilConfirm = await fn.addEvilConfirm(view, confirmDelete)
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
            ancestors, neighbors, successors = await fn.getConnections(graph, [originName], True)
            allNeighbors = ancestors + neighbors + successors
            edgeData = [graph.edges[edge] for edge in (graph.in_edges(originName) or graph.out_edges(originName))]
            if not allNeighbors:
                embed, _ = await fn.embed(
                    'No edges.',
                    f'{originMention} has no edges of which to modify the whitelists.',
                    'So I suppose that answers your inquiry.')
                await ctx.respond(embed = embed, ephemeral = True)
                return

            subgraph = graph.subgraph(allNeighbors + [originName])
            description = f'• Selected node: {originMention}\n• Neighbors:'

            description += await fn.formatEdges(guildData['nodes'], ancestors, neighbors, successors)
            hasWhitelist = await fn.hasWhitelist(edgeData)

            clearing = False

            async def refreshEmbed():

                fullDescription = description

                if addEdges.values:
                    selectedAncestors = [ancestor for ancestor in ancestors if ancestor in addEdges.values]
                    selectedNeighbors = [neighbor for neighbor in neighbors if neighbor in addEdges.values]
                    selectedSuccessors = [successor for neighbor in successors if successor in addEdges.values]
                    fullDescription += f"\n• Selected Edges: {await fn.formatEdges(guildData['nodes'], selectedAncestors, selectedNeighbors, selectedSuccessors)}."                      
                else:
                    fullDescription += '\n• Selected Edges: None yet. Use the dropdown below to pick one or more.'
                    
                if clearing:
                    fullDescription += f"\n• Whitelist: Removing all restrictions. Click 'Clear Whitelist' again\
                        to use the pre-existing whitelist (or the whitelist composed of what's below, if any\
                        roles or people are specified)."
                
                else:
                    if addRoles.values or addPlayers.values:
                        allowedRoles = [role.id for role in addRoles.values]
                        fullDescription += f"\n• New whitelist(s)-- will overwrite any previous whitelist: \
                            {await fn.formatWhitelist(allowedRoles, addPlayers.values)}"

                    elif not addEdges.values:
                        fullDescription += f"\n• Whitelist: Selected edges will have their whitelists shown here."

                    elif len(addEdges.values) == 1:
                        fullDescription += f"\n• Whitelist: \
                            {await fn.formatWhitelist(edgeData[0].get('allowedRoles', []), edgeData[0].get('allowedPeople', []))}"
                    
                    else:
                        if await fn.whitelistsSimilar(edgeData):
                            fullDescription += f"\n• Whitelists: Every edge has the same whitelist-\
                            \"{await fn.formatWhitelist(edgeData[0].get('allowedRoles', []), edgeData[0].get('allowedPeople', []))}\""
                        else:
                            fullDescription += f'\n• Whitelists: Multiple different whitelists.'

                edgeColors = await fn.colorEdges(subgraph, originName, addEdges.values, 'blue')
                graphImage = await fn.showGraph(subgraph, edgeColors)
                embed, file = await fn.embed(
                    'Change whitelists?',
                    fullDescription,
                    'This can always be reversed.',
                    (graphImage, 'full'))

                return embed, file

            async def callRefresh(interaction: discord.Interaction):

                await interaction.response.defer()
                embed, file = await refreshEmbed()
                await interaction.followup.edit_message(
                    message_id = interaction.message.id,
                    embed = embed)
                
                return
            
            async def clearWhitelist(interaction: discord.Interaction):
                nonlocal clearing
                clearing = not clearing
                embed, _ = await refreshEmbed()
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
                    if isinstance(toNeighbor, dict):
                        editedEdges[(originName, destination)] = {}
                    if isinstance(fromNeighbor, dict):
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
                neighborMentions = await fn.mentionNodes(neighborNodes)
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"You feel like the way to {originMention} changed somehow.",
                    'Will it be easier to travel through, or harder?')
                nodeEmbed, _ = await fn.embed(
                    f'Edge with {originMention} changed.',
                    description,
                    'You can view its details with /edge allow.')
                for neighbor in neighborNodes.values():
                    await postToDirects(playersEmbed, interaction.guild, neighbor['channelID'])
                    nodeChannel = get(interaction.guild.text_channels, id = neighbor['channelID'])
                    await nodeChannel.send(embed = nodeEmbed)

                #Inform edited node occupants
                playersEmbed, _ = await fn.embed(
                    'Hm?',
                    f"You notice that the're been in change in the way this place is connected to {neighborMentions}.",
                    "Perhaps you're only imagining it.")         
                await postToDirects(playersEmbed, interaction.guild, guildData['nodes'][originName]['channelID'])

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
            view, addEdges = await fn.addEdges(callRefresh, ancestors, neighbors, successors, view, False)
            view, addRoles = await fn.addRoles(view, len(ctx.guild.roles), callback = callRefresh)
            view, addPlayers = await fn.addPlayers(view, ctx.guild.members, members, callback = callRefresh)
            view, submit = await fn.addSubmit(view, confirmEdges)
            if hasWhitelist:
                view, clear = await fn.addClear(view, clearWhitelist)
            view, cancel = await fn.addCancel(view)
            embed, file = await refreshEmbed()

            await ctx.respond(embed = embed,
            file = file,
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
        guild_only = True,
        guild_ids = [1114005940392439899])

    @server.command(
        name = 'clear',
        description = 'Delete all server data.')
    async def clear(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        #con = db.newGuildDB()
        #con = db.newPlayerDB()
        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        members = db.getMembers(con, ctx.guild_id)
        con.close()

        if not guildData['nodes'] and not guildData['edges'] and not members:
            con = db.connectToGuild()
            db.deleteGuild(con, ctx.guild_id)
            db.deleteMembers(con, ctx.guild_id)
            con.close()

            embed, _ = await fn.embed(
            f'No data to delete!',
            'Data is only made when you create a node or an edge.',
            'Wish granted?')

            await ctx.respond(embed = embed)
            return

        edgeCount = 0
        visited = set()
        for origin, destination in guildData['edges'].keys():
            if (destination, origin) in visited:
                continue
            visited.add((origin, destination))
            edgeCount += 1
 
        async def deleteData(interaction: discord.Interaction):
            
            for nodeData in guildData['nodes'].values():
                await fn.deleteChannel(interaction.guild.text_channels, nodeData['channelID'])

            con = db.connectToGuild()
            db.deleteGuild(con, interaction.guild_id)
            db.deleteMembers(con, interaction.guild_id)
            con.close()

            con = db.connectToPlayer()
            for memberID in members:
                playerData = db.getPlayer(con, memberID)

                await fn.deleteChannel(interaction.guild.text_channels, playerData[str(interaction.guild_id)]['channelID'])
            
                del playerData[str(interaction.guild_id)]

                db.updatePlayer(con, playerData, memberID)

            con.close()

            await queueRefresh(interaction.guild)

            for categoryName in ['nodes', 'players']:
                try:
                    nodeCategory = get(interaction.guild.categories, name = categoryName)
                    await nodeCategory.delete()
                except:
                    pass
            
            embed, _ = await fn.embed(
                'See you.',
                'The following has been deleted: \n• All guild data.\n• All nodes and their channels.\
                \n• All location messages.\n• All edges.\n• All player info and their channels.',
                'You can always make them again if you change your mind.')

            await interaction.response.edit_message(embed = embed, view = None)
            return

        view = discord.ui.View()
        view, evilConfirm = await fn.addEvilConfirm(view, deleteData)
        view, cancel = await fn.addCancel(view)
        embed, _ = await fn.embed(
        f'Delete all data?',
        f"You're about to delete {len(guildData['nodes'])} nodes \
            and {edgeCount} edges, alongside player data for {len(members)} people.",
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

        guildData = db.gd(ctx.guild_id)

        async def viewEgo(guildData: dict, centerName: str = None):

            graph = await fn.makeGraph(guildData)

            #Nothing provided
            if not centerName:
                graphView = await fn.showGraph(graph)
                embed, file = await fn.embed(
                    'Complete graph',
                    'Here is a view of every node and edge.',
                    'To view only a single node and its neighbors, use /server view #node.',
                    (graphView, 'full'))

                await ctx.respond(embed = embed, file = file, ephemeral = True)
                return

            #If something provided
            connections = await fn.getConnections(graph, [centerName])
            connections.append(centerName)
            subgraph = graph.subgraph(connections)
            graphView = await fn.showGraph(subgraph)

            nodeMention = f"<#{guildData['nodes'][centerName]['channelID']}>"
            embed, file = await fn.embed(
                f"{nodeMention}'s neighbors",
                "Here is the node, plus any neighbors.",
                'To view every node and edge, call /server view without the #node.',
                (graphView, 'full'))

            await ctx.respond(embed = embed, file = file, ephemeral = True)
            return
              
        result = await fn.identifyNodeChannel(guildData['nodes'], node)
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
                ghostNodeNames.append(nodeName)

                newNodeChannel = await fn.newChannel(ctx.guild, node, nodesCategory)
                ghostNodeMentions.append(newNodeChannel.mention)
                guildData['nodes'][node]['channelID'] = newNodeChannel.id

                whitelist = await fn.formatWhitelist(guildData['nodes'][node].get('allowedRoles', []),
                    guildData['nodes'][node].get('allowedPeople', []))
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
            noAccessMentions = [f"<#{guildData['nodes'][node]['channelID']}>" for node in noAccess]
            description += f'\n• The following nodes have no edges for entry or exit, meaning \
                **players can only come or go through** `/player tp`**:** {await fn.listWords(noAccessMentions)}.'

        if noExits:
            noExitsMentions = [f"<#{guildData['nodes'][node]['channelID']}>" for node in noExits]
            description += f'\n• The following nodes have no edges for exiting, meaning \
                **players can get trapped:** {await fn.listWords(noExitsMentions)}.'

        if noEntrances:
            noEntrancesMentions = [f"<#{guildData['nodes'][node]['channelID']}>" for node in noEntrances]
            description += f'\n• The following nodes have no edges as entrances, meaning \
                **players will never enter:** {await fn.listWords(noEntrancesMentions)}.'

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
                    occupants = guildData['nodes'][lastLocatioPn].get('occupants', None)
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
                db.updatePlayer(con, playerData, playerID)

                locationName = playerData[str(ctx.guild_id)]['locationName']
                
                embed, _ = await fn.embed(
                    f'Welcome.',
                    f"""This is your very own channel, again, {player.mention}.
                    • Speak to others by just talking in this chat. Anyone who can hear you\
                    will see your messages pop up in their own player channel.
                    • You can `/look` around. You're at **{locationName}** right now.
                    • Do `/map` to see the other places you can go.
                    • ...And `/move` to go there. .
                    • You can`/eavesdrop` on people nearby room.
                    • Other people can't see your `/commands`.
                    • Tell the host not to accidentally delete your channel again.""",
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
            description += f'\n• The following players got back their deleted player channels:\
                {await fn.listWords(noChannelMentions)}.'

        if missingPlayers:
            description += f'\n• Deleted data and any remaining player channelsfor {len(missingPlayers)}\
            players who left the server without ever being officially removed as players. My best guess\
            for the name(s) of those who left is {await fn.listWords(missingPlayers)}.'

        if wrongWebhooks:
            description += f'\n• Fixed the webhook(s) for the following player channel(s):\
            {await fn.listWords(wrongWebhooks)}.' 
     
        if not description:
            description += "Congratulations! This server has no detectable issues.\
            \n• All nodes have a channel, weren't renamed improperly, and have their\
            webhooks intact.\n• Every node has at least one way in and out.\n• No\
            players left the server and left behind data or a channel.\n• Every player\
            has a channel of their own, with those webhooks intact too."

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

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        members = db.getMembers(con, ctx.guild_id)
        con.close()

        embed = discord.Embed(
            title = 'Debug details',
            description = '(Mostly) complete look into what the databases hold.',
            color = discord.Color.from_rgb(67, 8, 69))

        embed.set_footer(text = 'Peer behind the veil.')

        guildDescription = ''
        guildDescription += f"\n• Guild ID: {ctx.guild_id}"
        guildDescription += f"\n• Nodes: "
        for index, nodeData in enumerate(guildData['nodes'].values()):
            guildDescription += f"\n{index}. <#{nodeData['channelID']}>: "
            allowedRoles = nodeData.get('allowedRoles', [])
            allowedPeople = nodeData.get('allowedPeople', [])
            guildDescription += f'\n-- Whitelist: {await fn.formatWhitelist(allowedRoles, allowedPeople)}'
            occupants = nodeData.get('occupants', [])
            if occupants:
                occupantMentions = [f'<@{occupant}>' for occupant in occupants]
                guildDescription += f'\n-- Occupants: {await fn.listWords(occupantMentions)}'

        guildDescription += f"\n• Edges: {guildData['edges']}"

        embed.add_field(
            name = 'Server Data: guilds.guilds.db',
            value = guildDescription[:1000],
            inline = False)        
            
        memberMentions = [f'<@{member}>' for member in members]
        memberDescription = f'\n• Players: {await fn.listWords(memberMentions)}'

        embed.add_field(
            name = 'Player List: guilds.members.db',
            value = memberDescription,
            inline = False)
            
        con = db.connectToPlayer()
        playerData = db.getPlayer(con, ctx.author.id)
        con.close()

        playerDescription = f'• Your User ID: {ctx.author.id}'
        for serverID, serverData in playerData.items():
            playerDescription += f"\n• Server {serverID}:"
            playerDescription += f"\n- Channel: {serverData['channelID']}"
            playerDescription += f"\n- Location: {serverData['locationName']}"
            eavesdropping = serverData.get('eavesdropping', None)
            if eavesdropping:
                playerDescription += f"\n- Eavesdropping: {eavesdropping}"

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

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)

        exampleNodes = ['the-kitchen', 'the-living-room', 'the-dining-room', 'the-bedroom']
                
        nodesCategory = await fn.assertCategory(ctx.guild, 'nodes')
        for nodeName in exampleNodes:

            if nodeName in guildData['nodes']:
                guildData['nodes'][nodeName].pop('allowedNames', None)
                guildData['nodes'][nodeName].pop('allowedPeople', None)
                continue

            newChannel = await fn.newChannel(ctx.guild, nodeName, nodesCategory)
            guildData['nodes'][nodeName] = await fn.newNode(newChannel, [], [])        

        for nodeName in exampleNodes:

            for origin, destination in guildData['edges'].items():
                if origin == nodeName or destination ==  nodeName:
                    del guildData['edges'][(origin, destination)] 

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

        embed, _ = await fn.embed(
            'Done.',
            "Made an example graph composed of a household layout. If there were any\
            nodes/edges that were already present from a previous `/server quick` call,\
            they've been overwritten.",
            'Your other data is untouched.')

        await ctx.respond(embed = embed)
        return

class playerCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    player = SlashCommandGroup(
        name = 'player',
        description = "Manage players.",
        guild_only = True,
        guild_ids = [1114005940392439899])

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

            if await fn.noNodes(addNodes.values, interaction):
                return

            if await fn.noPeople(addPeople.values, interaction):
                return
                
            nodeName = addNodes.values[0]    
            con = db.connectToPlayer()

            existingPlayers = 0
            newPlayerIDs = []
            playerCategory = await fn.assertCategory(interaction.guild, 'players')
            for person in addPeople.values:

                if person.id in members:
                    existingPlayers += 1
                    continue

                newPlayerChannel = await fn.newChannel(interaction.guild, person.name, playerCategory, person)
                embed, _ = await fn.embed(
                    f'Welcome.',
                    f"""This is your very own channel, {person.mention}.
                    • Speak to others by just talking in this chat. Anyone who can hear you\
                    will see your messages pop up in their own player channel.
                    • You can `/look` around. You're at <#{guildData['nodes'][nodeName]['channelID']}> right now.
                    • Do `/map` to see the other places you can go.
                    • ...And `/move` to go there. .
                    • You can`/eavesdrop` on people nearby room.
                    • Other people can't see your `/commands`.""",
                    'You can always type /help to get more help.')
                await newPlayerChannel.send(embed = embed)

                playerData = db.getPlayer(con, person.id)
                playerData[str(interaction.guild_id)] = {
                    'channelID' : newPlayerChannel.id,
                    'locationName' : nodeName}
                db.updatePlayer(con, playerData, person.id)
                newPlayerIDs.append(person.id)
                members.append(person.id)

            con.close()

            #Add the players to the guild nodes as occupants
            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)
            priorOccupants = guildData['nodes'][nodeName].get('occupants', [])
            guildData['nodes'][nodeName]['occupants'] = priorOccupants + newPlayerIDs
            db.updateGuild(con, guildData, interaction.guild_id)

            #Inform the node occupants
            playerMentions = await fn.listWords([f'<@{ID}>' for ID in newPlayerIDs])
            playersEmbed, _ = await fn.embed(
                'A fresh face.',
                f"{playerMentions} is here.",
                'Perhaps you should greet them.')         
            await postToDirects(playersEmbed, interaction.guild, guildData['nodes'][nodeName]['channelID'])

            #Inform own node                
            embed, _ = await fn.embed(
                'New player(s).',
                f'Added {playerMentions} to this node to begin their journey.',
                'You can view all players and where they are with /player find.') 
            nodeChannel = get(interaction.guild.text_channels, id = guildData['nodes'][nodeName]['channelID'])
            await nodeChannel.send(embed = embed)

            #Add new players to guild member list
            db.updateMembers(con, members, interaction.guild_id)
            con.close()

            await queueRefresh(interaction.guild)

            description = ''
            if newPlayerIDs:
                description += f"Successfully added {playerMentions} to this server,\
                    starting their journey at <#{guildData['nodes'][nodeName]['channelID']}>."

            if existingPlayers:
                description += f"\n\nYou provided {existingPlayers} person(s) that are already in,\
                    so they got skipped. They're all players now, either way."          

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
                description = "For all the players you list, this command will:\
                \n• Delete their player channel(s).\n• Remove them as occupants in\
                the locations they're in.\n• Remove their ability to play, returning\
                them to the state they were in before they were added as a player.\
                \n\nIt will not:\n• Kick or ban them from the server.\n• Delete their\
                messages."

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
                embedData, _ = await embed(
                    f'{player.mention}?',
                    "But they aren't a player.",
                    'So how can they be located?')
                await interaction.followup.edit_message(
                    message_id = interaction.message.id,
                    embed = embedData,
                    view = None)
                return
        else:
            playerIDs = members
                
        description = ''
        locations = {}

        occupiedNodes = await fn.getOccupants(guildData['nodes'])
        for nodeName, occupantIDs in occupiedNodes.items():
            occupantMentions = [f'<@{occupantID}>' for occupantID in occupantIDs if occupantID in playerIDs]
            if occupantMentions:
                description += f"\n• <#{guildData['nodes'][nodeName]['channelID']}>: {await fn.listWords(occupantMentions)}"
                
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
            description += f"• Teleported {teleportingMentions} to \
                    <#{guildData['nodes'][nodeName]['channelID']}>."

            playerCon = db.connectToPlayer()
            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)

            exitingNodes = {}
            for ID in addPlayers.values:
                ID = int(ID)
                playerData = db.getPlayer(playerCon, ID)

                oldLocation = playerData[str(interaction.guild_id)]['locationName']
                guildData['nodes'][oldLocation]['occupants'].remove(ID)
                alreadyMoving = exitingNodes.get(guildData['nodes'][oldLocation]['channelID'], [])
                alreadyMoving.append(ID)
                exitingNodes[guildData['nodes'][oldLocation]['channelID']] = alreadyMoving
                if not guildData['nodes'][oldLocation]['occupants']:
                    guildData['nodes'][oldLocation].pop('occupants')                

                playerData[str(interaction.guild_id)]['locationName'] = nodeName
                playerData[str(interaction.guild_id)].pop('eavesdropping', None)
                db.updatePlayer(playerCon, playerData, ID)
            playerCon.close()

            #Add players to new location
            priorOccupants = guildData['nodes'][nodeName].get('occupants', [])
            guildData['nodes'][nodeName]['occupants'] = priorOccupants + [int(ID) for ID in addPlayers.values]
            db.updateGuild(con, guildData, interaction.guild_id)
            con.close()

            await queueRefresh(interaction.guild)

            for channelID, exitingPlayerIDs in exitingNodes.items():

                #Inform old location occupants
                playerMentions = await fn.listWords([f'<@{ID}>' for ID in exitingPlayerIDs])
                playersEmbed, _ = await fn.embed(
                    'Gone in a flash.',
                    f"{playerMentions} disappeared somewhere.",
                    "But where?")         
                await postToDirects(playersEmbed, interaction.guild, channelID)

                #Inform old node                
                embed, _ = await fn.embed(
                    'Teleported player(s).',
                    f"Teleported {playerMentions} to <#{guildData['nodes'][nodeName]['channelID']}>.",
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
            tutorialData = {'Intro' : "Welcome, this guide\
            will tell you everything you need to know as\
            a player. Let's begin.",
            'Player Channels' : "Players have their own channel\
            for roleplaying. All speech and movement, etc, is\
            done through there.",
            'Locations' : "Your character exists in some location.\
            You can check where you are with `/look`.",
            'Movement' : "You can `/move` to a new place. Certain\
            places or routes might have limits on who's allowed\
            in.",
            'Visibility' : "You're able to see people in the same\
            location as you, even if they're only passing by.",
            'Sound' : "Normally, you can only hear people in the\
            same location as you, and vice versa.",
            'Eavesdropping' : "If you want, you can `/eavesdrop` on\
            people in a location next to you to hear what's going on.",
            'Fin' : "And that's about it! Enjoy the game."}
            
            guildData = db.gd(interaction.guild_id)
            con = db.connectToPlayer()
            playerData = db.getPlayer(con, interaction.user.id)
            con.close()
            serverData = playerData.get(str(interaction.guild_id), None)
            if serverData:
                tutorialData['Player Channels'] += f" You're a\
                player in this server, so you'll use\
                <#{serverData['channelID']}>."
                tutorialData['Locations'] += f" Right now, you're\
                in #{serverData['locationName']}."
            
            await displayTutorial(interaction = interaction)
            return
        
        async def hostTutorial(interaction: discord.Interaction):
            nonlocal tutorialName, tutorialData, tutorialPictures
            tutorialName = 'Host Tutorial, Page'
            tutorialData = {'Intro' : "Buckle up, this guide is\
                a little longer than the Player one. I trust\
                you brought snacks. Let's begin.",
                'The Goal' : "I let the players move around\
                between places, so your job is to tell me\
                what the places are and how players can\
                move around between them.",
                'Nodes' : "Locations that the players\
                can go inside are called nodes. Nodes should\
                be about the size of a room. Use `/node new`\
                to make them.",
                'Edges' : "Edges are the connections between nodes.\
                An edge just means that there is a direct path\
                between two nodes that you can walk through. Maybe it's\
                a doorway or a bridge. Use `/edge new` to connect nodes.",
                'Graph' : "You can view a map of every node and the\
                edges between them. That's called a 'graph'. Nodes\
                are shown as just their name and the edges are\
                shown as arrows between them. Look at the graph\
                with `/server view`.",
                'Quick Start' : "If you want an example of a graph,\
                you can do `/server quick` to make a little house.\
                You can clear out the graph and the player data with\
                `/server clear`.",
                'Players' : "Once you have somewhere to put the players,\
                use `/player new` to add them to the game. You can also\
                move them with `/player tp` or find them with `/player find`.",
                'Fixing' : "If you mess with the channels, or if players leave,\
                if might break the bot causing certain features not to work. Use\
                `/server fix` to automatically fix common issues.",
                'Fin' : "That's about all--you can figure the rest out. If you\
                have any issues or improvements to suggest, just let **davidlancaster**\
                know. Enjoy! :)"}
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
            f"This command will help you learn what the bot does and how it\
        can be used. Additionally, if you want to learn more about any\
        __underlined__ words I use, just say `/help (underlined word)`. :)",
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

    @tasks.loop(seconds=5.0)
    async def updateListeners(self):

        con = None
        if needingUpdate:
            con = db.connectToGuild()

        for guild in list(needingUpdate):

            guildStartTime = time.time()
            
            guildData = db.getGuild(con, guild.id)
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
            for nodeName, nodeData in guildData['nodes'].items():

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

            # shortListeners = {key : [channel.name for channel in value] for key, value in directListeners.items()}
            # print(f'Finished directs are {shortListeners}.')
            # shortIndirects = {key : [both[1].name for both in value] for key, value in indirectListeners.items()}
            # print(f'Finished indirects are {shortIndirects}.')
            needingUpdate.remove(guild)
            updatedGuilds.add(guild.id)
            print(f"Updated {guild.name}'s listeners in {time.time() - guildStartTime} seconds.")

        if con:
            con.close()

        return

class guildCommands(commands.Cog): 

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    @commands.slash_command(
        name = 'look',
        description = 'Look around your location.',
        guild_only = True,
        guild_ids = [1114005940392439899])
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
            description += f"There's {await fn.listWords(occupantMentions)} with you inside <#{nodeData['channelID']}>. "
        else:
            description += f"You're by yourself inside <#{nodeData['channelID']}>. "

        graph = await fn.makeGraph(guildData)
        ancestors, mutuals, successors = await fn.getConnections(graph, [nodeName], True)

        if ancestors:
            ancestorMentions = [f"<#{guildData['nodes'][ancestor]['channelID']}>" for ancestor in ancestors]
            if len(ancestors) > 1:
                description += f"There are one-way routes from (<-) {await fn.listWords(ancestorMentions)}. "
            else:
                description += f"There's a one-way route from (<-) {ancestorMentions[0]}. "

        if successors:
            successorMentions = [f"<#{guildData['nodes'][successor]['channelID']}>" for successor in successors]
            if len(successors) > 1:
                description += f"There are one-way routes to (->) {await fn.listWords(successorMentions)}. "
            else:
                description += f"There's a one-way route to (->) {successorMentions[0]}. "

        if mutuals:
            mutualMentions = [f"<#{guildData['nodes'][mutual]['channelID']}>" for mutual in mutuals]
            if len(mutuals) > 1:
                description += f"There's ways to {await fn.listWords(mutualMentions)} from here. "
            else:
                description += f"There's a way to get to {mutualMentions[0]} from here. "
        
        if not (ancestors or mutuals or successors):
            description += "There's no way in or out of here."

        embed, _ = await fn.embed(
            'Looking around...',
            description,
            'You can eavesdrop on a nearby location.')
        await ctx.respond(embed = embed)
        return

    @commands.slash_command(
        name = 'eavesdrop',
        description = 'Listen in on a nearby location.',
        guild_only = True,
        guild_ids = [1114005940392439899])
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
        if eavesdroppingNode:
            occupants = guildData['nodes'][eavesdroppingNode].get('occupants', False)
            if occupants:
                occupantMentions = await fn.listWords([f'<@{ID}>' for ID in occupants])
                description = f"You're eavesdropping on {occupantMentions} in #{eavesdroppingNode}."
            else:
                description = f"You're eavesdropping on #{eavesdroppingNode}, but you think nobody is there."

            async def stopEavesdropping(interaction: discord.Interaction):

                await fn.waitForRefresh(interaction)
                
                con = db.connectToPlayer()
                del playerData[str(ctx.guild_id)]['eavesdropping']
                db.updatePlayer(con, playerData, ctx.author.id)
                con.close()

                await queueRefresh(interaction.guild)

                embed, _ = await fn.embed(
                    'Saw that.',
                    f"You notice {ctx.author.mention} play it off like they weren't just listening in on #{eavesdroppingNode}.",
                    'Do with that what you will.')
                await postToDirects(
                    embed, 
                    interaction.guild, 
                    guildData['nodes'][serverData['locationName']]['channelID'], 
                    serverData['channelID'])

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
                    fullList.append(f'{occupantMentions} in #{neighborNodeName}')
                description += f'{await fn.listWords(fullList)}. '
                unoccupiedNeighbors = [neighbor for neighbor in neighbors if neighbor not in occupiedNeighbors]
                if unoccupiedNeighbors:
                    hashedUnoccupied =  await fn.listWords([f'#{neighbor}' for neighbor in unoccupiedNeighbors]) 
                    description += f"You can also listen in on {hashedUnoccupied}, but it sounds like nobody is in there."
            else:
                hashedNeighbors = [f'#{neighbor}' for neighbor in neighbors]
                description = f"You're able to listen in on {await fn.listWords(hashedNeighbors)} from here,\
                    but you don't hear anyone over there. "
        else:
            description = "If there was someplace nearby, you could listen in on it, but \
            there's nowhere nearby here. Wait, does that mean you're stuck here?"

        async def refreshEmbed():

            nonlocal selectedNode, description

            if userNodes.values:
                selectedNode = userNodes.values[0]
            else:
                selectedNode = None

            fullDescription = description
            if selectedNode:
                fullDescription = f'Eavesdrop on #{selectedNode}?'

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
                f"You notice {ctx.author.mention} start to listen in on #{userNodes.values[0]}.",
                'Do with that what you will.')
            await postToDirects(embed, interaction.guild, guildData['nodes'][nodeName]['channelID'], serverData['channelID'])

            embed, _ = await fn.embed(
                'Listening close...',
                f"Let's hear what's going on over there in #{userNodes.values[0]}, shall we?",
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
        guild_only = True,
        guild_ids = [1114005940392439899])
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

        playerGraph = await fn.filterMap(guildData, ctx.author.roles, ctx.author.id, serverData['locationName'])
        playerMap = await fn.showGraph(playerGraph)

        embed, file = await fn.embed(
            'Map',
            f"Here are all the places you can reach from **{serverData['locationName']}**.\
            You can travel along the arrows that point to where you want to go. ",
            "Use /move to go there.",
            (playerMap, 'full'))
        
        await ctx.respond(embed = embed, file = file)
        return

    @commands.slash_command(
        name = 'move',
        description = 'Go someplace new.',
        guild_only = True,
        guild_ids = [1114005940392439899])
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

        description = f"Move from #{serverData['locationName']}"
        userNodes = None
        selectedNode = node if node else None

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

            path = nx.shortest_path(playerGraph, source = serverData['locationName'], target = selectedNode)

            #Inform origin occupants
            embed, _ = await fn.embed(
                'Departing.',
                f"You notice {ctx.author.mention} leave, heading towards #{path[1]}.",
                'Maybe you can follow them?')
            await postToDirects(
                embed, 
                interaction.guild, 
                guildData['nodes'][path[0]]['channelID'], 
                serverData['channelID'])

            #Inform destination occupants
            embed, _ = await fn.embed(
                'Arrived.',
                f"You notice {ctx.author.mention} arrive from the direction of #{path[-2]}.",
                'Say hello.')
            await postToDirects(embed, 
            interaction.guild, 
            guildData['nodes'][path[-1]]['channelID'])

            #Inform intemediary nodes + their occupants
            for index, midwayName in enumerate(path[1:-1]): 
                embed, _ = await fn.embed(
                    'Passing through.',
                    f"You notice {ctx.author.mention} come in from the direction of #{path[index]}\
                    before continuing on their way towards #{path[index+2]}.",
                    'Like two ships in the night.')
                await postToDirects(embed, 
                interaction.guild, 
                guildData['nodes'][midwayName]['channelID'])

                nodeChannel = get(interaction.guild.text_channels, name = midwayName)
                embed, _ = await fn.embed(
                    'Transit.',
                    f"{ctx.author.mention} passed through here when travelling from\
                        <#{guildData['nodes'][path[0]]['channelID']}> to\
                        <#{guildData['nodes'][path[-1]]['channelID']}>.",
                    'Just visiting.')
                await nodeChannel.send(embed = embed)

            visitedNodes = await fn.filterNodes(guildData['nodes'], path)
            occupantsData = await fn.getOccupants(visitedNodes)

            #Calculate who they saw on the way
            fullMessage = []
            for nodeName, occupantsList in occupantsData.items():

                if interaction.user.id in occupantsList:
                    occupantsList.remove(interaction.user.id)
                if occupantsList:
                    occupantsMention = await fn.listWords([f"<@{ID}>" for ID in occupantsList])
                    fullMessage.append(f'{occupantsMention} in #{nodeName}')

            #Inform player of who they saw and what path they took
            if fullMessage:
                description = f'Along the way, you saw (and were seen by) {await fn.listWords(fullMessage)}.'
            else:
                description = "You didn't see anyone along the way."

            #Change occupants
            con = db.connectToGuild()
            originOccupants = guildData['nodes'][path[0]]['occupants']
            if not originOccupants:
                del guildData['nodes'][path[0]]['occupants']

            priorOccupants = guildData['nodes'][path[-1]].get('occupants', [])
            priorOccupants.append(ctx.author.id)
            guildData['nodes'][path[-1]]['occupants'] = priorOccupants 

            db.updateGuild(con, guildData, interaction.guild_id)
            con.close()

            #Update location and eavesdropping
            playerCon = db.connectToPlayer()
            playerData[str(ctx.guild_id)]['locationName'] = path[-1]
            playerData[str(ctx.guild_id)].pop('eavesdropping', None)
            db.updatePlayer(playerCon, playerData, ctx.author.id)
            playerCon.close()        

            await queueRefresh(interaction.guild)

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

        con = db.connectToGuild()
        members = db.getMembers(con, guild.id)

        playerCon = db.connectToPlayer()
        for memberID in members:
            playerData = db.getPlayer(con, memberID)

            await fn.deleteChannel(guild.text_channels, playerData[str(guild_id)]['channelID'])
        
            del playerData[str(guild.id)]
            db.updatePlayer(con, playerData, memberID)
        playerCon.close()

        db.deleteGuild(con, guild.id)
        db.deleteMembers(con, guild.id)
        con.close()

        if needingUpdate:
            needingUpdate.discard(guild)
        if updatedGuilds:
            updatedGuilds.discard(guild.id)
        
        return
    #Do something to purge direct and indirect listeners of this guilds channels
    
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
