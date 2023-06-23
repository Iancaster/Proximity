import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands
from discord.utils import get_or_fetch
import functions as fn
import databaseFunctions as db

class nodeCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    node = SlashCommandGroup(
        name = 'node',
        description = 'Add, review, and delete nodes.',
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
            required = False,
            default = 'new-node')):

        await ctx.defer(ephemeral = True)
        guildData = db.gd(ctx.guild_id)

        nodeName = await fn.discordify(name)
        allowedRoles = []
        allowedPeople = []

        async def refreshEmbed():

            nonlocal nodeName, allowedRoles, allowedPeople
            nodeName = await fn.discordify(nameSelect.value) if nameSelect.value else name
            allowedRoles = [role.id for role in addRoles.values]
            allowedPeople = [person.id for person in addPeople.values]
            
            description = f'Whitelist: {await fn.formatWhitelist(allowedRoles, allowedPeople)}'

            #Formatting results
            embed, _ = await fn.embed(
                f'New node: {nodeName}',
                description,
                'You can also create a whitelist to limit who can visit this node.')
            
            return embed

        async def submitNode(interaction: discord.Interaction):
            
            await interaction.response.defer()

            nonlocal nodeName, allowedRoles, allowedPeople

            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)

            if nodeName in guildData['nodes']:
                embed, _ = await fn.embed(
                    'Hold up.',
                    f"You already have a node named <#{guildData['nodes'][nodeName]['channelID']}>. Either\
                    use `/node edit` to rename that node, or pick a new name for this one instead.",
                    "Sorry that I can't handle dupes like that.")
                await interaction.followup.edit_message(message_id = interaction.message.id, embed = embed, view = None)
                return
 
            newChannel = await fn.newChannel(interaction.guild, nodeName, 'nodes')
            guildData['nodes'][name] = await fn.newNode(newChannel.id, allowedRoles, allowedPeople)

            db.updateGuild(con, guildData, interaction.guild_id)
            con.close()

            embed, _ = await fn.embed(
                'Node created!',
                f"You can find it at {newChannel.mention}.\
                The permissions you requested are set-- just not in the channel's Discord\
                settings. No worries, it's all being kept track of by me.",
                'I hope you like it.')        
            await interaction.followup.edit_message(message_id = interaction.message.id, embed = embed, view = None)

            whitelist = await fn.formatWhitelist(allowedRoles, allowedPeople)
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
        view, addPeople = await fn.addPeople(view, ctx.guild.member_count, refresh = refreshEmbed)
        view, submit = await fn.addSubmit(view, submitNode)
        view, nameSelect = await fn.addNameModal(view, refresh = refreshEmbed)
        view, cancel = await fn.addCancel(view)
        embed = await refreshEmbed()
        await ctx.respond(embed = embed, view = view)
        return

    @node.command(
        name = 'delete',
        description = 'Delete a node.')
    async def delete( #Add a check/warning/contingency if players are located in a node getting deleted
        self,
        ctx: discord.ApplicationContext,
        node: discord.Option(
            str,
            'Call this command in a node (or name it) to narrow it down.',
            autocomplete = fn.autocompleteNodes,
            required = False)):
        
        await ctx.defer(ephemeral = True)

        guildData = db.gd(ctx.guild_id)

        async def deleteNodes(deletingNodes: list):
            
            async def confirmDelete(interaction: discord.Interaction):

                await interaction.response.defer()

                con = db.connectToGuild()
                guildData = db.getGuild(con, ctx.guild_id)

                deletedEdges = []

                for origin, destination in guildData['edges'].keys():

                    if origin in deletingNodes or destination in deletingNodes:
                        deletedEdges.append((origin, destination))

                for edge in deletedEdges:
                    guildData['edges'].pop(edge, None)
                    
                for node in deletingNodes:
                    nodeChannel = await get_or_fetch(ctx.guild, 'channel', guildData['nodes'][node]['channelID'])

                    try:
                        await nodeChannel.delete()
                    except:
                        pass

                    guildData['nodes'].pop(node, None)
                
                db.updateGuild(con, guildData, interaction.guild_id)
                con.close()
                
                if interaction.channel.name not in deletingNodes:
                    embed, _ = await fn.embed(
                        'Deleted.',
                        f'Successfully deleted the following things about {await fn.listWords(deletingNodes)}:\
                        \n• The node data in the database.\
                        \n• The node channels.\
                        \n• All edges to and from the node.',
                        'All gone.')
                    await interaction.followup.edit_message(message_id = interaction.message.id, embed = embed, view = None)
                return

            nodeMentions = [f"<#{guildData['nodes'][node]['channelID']}>" for node in deletingNodes]
         
            view = discord.ui.View()
            view, evilConfirm = await fn.addEvilConfirm(view, confirmDelete)
            view, cancel = await fn.addCancel(view)
            embed, _ = await fn.embed(
                'Confirm deletion?',
                f'Delete {await fn.listWords(nodeMentions)}?',
                'This will also delete any edges connected to the node(s).')
            await ctx.respond(embed = embed, view = view, ephemeral = True)
            return

        result = await fn.identifyNodeChannel(guildData, ctx.channel.name, node)
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
                    await fn.closeDialogue(interaction)
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

        guildData = db.gd(ctx.guild_id)

        async def reviseNodes(nodeNames: list):

            title = f'Reviewing {len(nodeNames)} nodes.'
            nodes = [guildData['nodes'][nodeName] for nodeName in nodeNames]
            nodeMentions = [f"<#{node['channelID']}>" for node in nodes]

            intro = f"• Selected node(s): {await fn.listWords(nodeMentions)}"

            occupants = []
            for node in nodes:
                occupants += node.get('occupants', [])
            occupantMentions = [f'<@{occupant}>' for occupant in occupants]
            description = f'\n• Occupants: {await fn.listWords(occupantMentions)}' if occupantMentions else '\
                \n• Occupants: There are no people in the given node(s).'

            graph = await fn.makeGraph(guildData)
            connections = await fn.getConnections(graph, nodeNames)
            if connections:
                subgraph = graph.subgraph(connections + nodeNames)
                description += '\n• Edges: See below.'
                graphView = (await fn.showGraph(subgraph), 'full')
            else:
                description += '\n• Edges: There are no nodes connected to the selected node(s).'
                graphView = None

            hasWhitelist = False
            for node in nodes:
                if node.get('allowedRoles', None) or node.get('allowedPeople', None):
                    hasWhitelist = True
                    break

            name = None
            clearing = False

            async def refreshEmbed():

                fullDescription = intro
                if name:
                    fullDescription += f', renaming to {name}.'
                fullDescription += description
                
                if clearing:
                    fullDescription += f"\n• Whitelist: Removing all restrictions. Click 'Clear Whitelist' again\
                        to use the pre-existing whitelist (or the whitelist composed of what's below, if any\
                        roles or people are specified)."
                
                if (addRoles.values or addPeople.values) and not clearing:
                    allowedRoles = [role.id for role in addRoles.values]
                    allowedPeople = [person.id for person in addPeople.values]
                    fullDescription += f"\n• New whitelist(s)-- will overwrite any previous whitelist: \
                        {await fn.formatWhitelist(allowedRoles, allowedPeople)}"

                elif len(nodes) == 1 and not clearing:
                    fullDescription += f"\n• Whitelist: \
                        {await fn.formatWhitelist(nodes[0].get('allowedRoles', []), nodes[0].get('allowedPeople', []))}"
        
                elif not clearing:
                    if await fn.whitelistsSimilar(nodes):
                        fullDescription += f"\n• Whitelists: Every node has the same whitelist-\
                        \"{await fn.formatWhitelist(nodes[0].get('allowedRoles', []), nodes[0].get('allowedPeople', []))}"
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

                con = db.connectToGuild()
                guildData = db.getGuild(con, interaction.guild_id)
                
                if name in guildData['nodes']: 
                    embed, _ = await fn.embed(
                        'Hold up.',
                        f"You already have a node named <#{guildData['nodes'][name]['channelID']}>. Either\
                        rename that node first (to free up the name for <#{guildData['nodes'][nodeNames[0]]['channelID']}>),\
                        or pick a different name for this one instead. Or both.",
                        "Sorry that I can't handle dupes like that.")
                    await interaction.followup.edit_message(message_id = interaction.message.id, embed = embed, view = None)
                    return

                if not (name or addRoles.values or addPeople.values or clearing):
                    embed, _ = await fn.embed(
                        'Hold up.',
                        "• You didn't change any names or whitelists.",
                        "Unsure what the point of that was.")
                    await interaction.followup.edit_message(message_id = interaction.message.id, embed = embed, view = None)
                    return

                description = ''

                if clearing:
                    description += '\n• Removed the whitelist(s).'
                    for nodeName in nodeNames:
                        guildData['nodes'][nodeName].pop('allowedRoles', None)
                        guildData['nodes'][nodeName].pop('allowedPeople', None)

                else:
                    if addRoles.values:
                        description += '\n• Edited the roles whitelist(s).'
                    if addPeople.values:
                        description += '\n• Edited the people whitelist(s).'
                    
                    allowedRoles = [role.id for role in addRoles.values]
                    allowedPeople = [person.id for person in addPeople.values]

                    for nodeName in nodeNames:
                        if allowedRoles:
                            guildData['nodes'][nodeName]['allowedRoles'] = allowedRoles
                        else:
                            guildData['nodes'][nodeName].pop('allowedRoles', [])
                        
                        if allowedPeople:
                            guildData['nodes'][nodeName]['allowedPeople'] = allowedPeople
                        else:
                            guildData['nodes'][nodeName].pop('allowedPeople', [])
                    
                if name:
                    guildData['nodes'][name] = guildData['nodes'].pop(nodeNames[0])
                    description += f'\n• Renamed {nodeNames[0]} to {name}, '

                    try:
                        nodeChannel = await get_or_fetch(interaction.guild, 'channel', nodes[0]['channelID'])
                        await nodeChannel.edit(name = name)
                        description += f'and renamed the node channel successfully to {nodeMentions[0]}.'
                    except:
                        description += f"but couldn't rename the node channel! Please run `/server fix` after this."

                db.updateGuild(con, guildData, interaction.guild_id)
                con.close()                    

                embed, _ = await fn.embed(
                    'Review results.',
                    description,
                    'Another successful edit.')
            
                await interaction.followup.edit_message(
                    message_id = interaction.message.id,
                    embed = embed,
                    view = None,
                    attachments = [])
                return              
            
            view = discord.ui.View()
            view, addRoles = await fn.addRoles(view, len(ctx.guild.roles), refresh = refreshEmbed)
            view, addPeople = await fn.addPeople(view, ctx.guild.member_count, refresh = refreshEmbed)
            view, submit = await fn.addSubmit(view, submitNode)
            if len(nodes) == 1:
                view, addNameModal = await fn.addNameModal(view, refreshEmbed)
            if hasWhitelist:
                view, clear = await fn.addClear(view, clearWhitelist)
            view, cancel = await fn.addCancel(view)
            embed = await refreshEmbed()
            _, file = await fn.embed(
                imageDetails = graphView)

            await ctx.respond(embed = embed, view = view, file = file, ephemeral = True)
            return

        result = await fn.identifyNodeChannel(guildData, ctx.channel.name, node)
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
                    • Do `/node revise #node-channel`.\n\
                    • Select multiple node channels with the list below.",
                    'This will allow you to view the nodes, their edges, and the whitelists.')

                async def submitNodes(interaction: discord.Interaction):
                    await fn.closeDialogue(interaction)
                    await reviseNodes(addNodes.values)
                    return

                view = discord.ui.View()                
                view, addNodes = await fn.addNodes(view, guildData['nodes'], submitNodes)
                view, cancel = await fn.addCancel(view)
                await ctx.respond(embed = embed, view = view)

        return

class edgeCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    edge = SlashCommandGroup(
        name = 'edge',
        description = 'Add and review edges.',
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

        guildData = db.gd(ctx.guild_id)

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
            twoWay = True
            
            async def refreshEmbed():

                description = f'• Origin: {originMention}'

                if addNodes.values:
                    destinationMentions = [f"<#{guildData['nodes'][destination]['channelID']}>" for destination in addNodes.values]
                    description += f'\n• Destination(s): {await fn.listWords(destinationMentions)}.'
                else:
                    description += f"\n• Destination(s): None yet! Add some nodes to draw an edge to."

                
                allowedRoles = [role.id for role in addRoles.values]
                allowedPeople = [person.id for person in addPeople.values]
                description += f"\n• Whitelist: {await fn.formatWhitelist(allowedRoles, allowedPeople)}"

                if twoWay:
                    description += f'\n• Directionality: **Two-way,** people will be able to travel\
                    back and forth between {originMention} and the destination(s).'
                else:
                    description += f'\n• Directionality: These connections are **one-way,** from\
                    {originMention} to the destination(s).'

                embed, _ = await fn.embed(
                    f'New edge(s)',
                    description,
                    'This command overwrites old edges.')
                return embed
            
            async def toggled(interaction: discord.Interaction):
                nonlocal twoWay
                twoWay = not twoWay
                embed = await refreshEmbed()
                await interaction.response.edit_message(embed = embed)
                return 

            async def submitEdges(interaction: discord.Interaction):

                await interaction.response.defer()

                con = db.connectToGuild()
                guildData = db.getGuild(con, interaction.guild_id)
                description = ''

                destinations = addNodes.values

                if originName in destinations:
                    destinations.remove(originName)
                    description += f'Hold on, did you just try to add a connection from {originMention}\
                    to itself, {originMention}? How would that even work? Anyways, putting that aside:\n\n'
                
                if not destinations:
                    description += "You didn't select any nodes to draw a connection to."
                    embed, _ = await fn.embed(
                        'No destinations!',
                        description,
                        'You can call the command again and add some.')
                    await interaction.followup.edit_message(message_id = interaction.message.id, embed = embed, view = None)
                    return
                
                newEdges = {}
                for destination in addNodes.values:

                    newEdges[(originName, destination)] = {}
                
                    if twoWay:
                        newEdges[(destination, originName)] = {}

                description += f'• Connected {originMention}'
                description += ' <-> to ' if twoWay else ' -> to '
                destinationMentions = [f"<#{guildData['nodes'][destination]['channelID']}>" for destination in addNodes.values]
                description += f'{await fn.listWords(destinationMentions)}.'
                
                if addRoles.values:

                    description += '\n• Imposed the role restrictions on the whitelist.'
                    allowedRoles =  [role.id for role in addRoles.values]
                    for edgeName in newEdges.keys():
                        newEdges[edgeName]['allowedRoles'] = allowedRoles

                if addPeople.values:

                    description += '\n• Imposed the person restrictions on the whitelist.'
                    allowedPeople = [person.id for person in addPeople.values]
                    for edgeName in newEdges.keys():
                        newEdges[edgeName]['allowedPeople'] = allowedPeople

                for edgeName, edgeData in newEdges.items():
                    guildData['edges'][edgeName] = edgeData
            
                db.updateGuild(con, guildData, interaction.guild_id)
                con.close()
                
                description += 'You can view the graph with `/server view`, or view\
                the edges of specific nodes with `/edge review`.'

                embed, file = await fn.embed(
                    'New edge results.',
                    description,
                    'I hope you like it.')        
                await interaction.followup.edit_message(message_id = interaction.message.id, embed = embed, view = None)       
                return

            view = discord.ui.View()
            view, addNodes = await fn.addNodes(view, guildData['nodes'].keys(), refresh = refreshEmbed)
            view, addRoles = await fn.addRoles(view, len(ctx.guild.roles), refresh = refreshEmbed)
            view, addPeople = await fn.addPeople(view, ctx.guild.member_count, refresh = refreshEmbed)
            view, submit = await fn.addSubmit(view, submitEdges)

            toggleTwoWay = discord.ui.Button(
                label = 'Toggle Directionality',
                style = discord.ButtonStyle.secondary)
            toggleTwoWay.callback = toggled
            view.add_item(toggleTwoWay)

            view, cancel = await fn.addCancel(view)
            embed = await refreshEmbed()
                
            await ctx.respond(embed = embed, view = view, ephemeral = True)
            return

        result = await fn.identifyNodeChannel(guildData, ctx.channel.name, origin)
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
                    await fn.closeDialogue(interaction)
                    await createEdges(addNodes.values[0])
                    return

                view = discord.ui.View()                
                view, addNodes = await fn.addNodes(view, guildData['nodes'], submitNodes, manyNodes = False)
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

            for ancestor in ancestors:
                description += f"\n<- <#{guildData['nodes'][ancestor]['channelID']}>"
            for neighbor in neighbors:
                description += f"\n<-> <#{guildData['nodes'][neighbor]['channelID']}>"        
            for successor in successors:
                description += f"\n-> <#{guildData['nodes'][successor]['channelID']}>"

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

                if len(allNeighbors) > 1:
                    deletedEdges = [selected.split()[1] for selected in addEdges.values]
                else:
                    deletedEdges = [allNeighbors[0]]

                edgeColors = []
                for origin, destination in subgraph.edges:
                    if origin in deletedEdges and destination == originName:
                        edgeColors.append('red')
                    elif destination in deletedEdges and origin == originName:
                        edgeColors.append('red')
                    else:
                        edgeColors.append('black')

                graphImage = await fn.showGraph(subgraph, edgeColors)
                return

            async def refreshFile(interaction: discord.Interaction):   
                await updateFile()
                await interaction.response.edit_message(file = discord.File(graphImage, filename='image.png'))
                return

            async def confirmDelete(interaction: discord.Interaction):

                for origin, destination in subgraph.edges:

                    if origin in deletedEdges and destination == originName:
                        del guildData['edges'][(origin, destination)]
                    elif destination in deletedEdges and origin == originName:
                        del guildData['edges'][(origin, destination)]

                con = db.connectToGuild()
                db.updateGuild(con, guildData, interaction.guild_id)
                con.close()

                embed, _ = await fn.embed(
                    'Edges deleted.',
                    f'Removed {len(deletedEdges)} edge(s). Talk about cutting ties.',
                    'You can always make some new ones with /edge new.')                

                await interaction.response.edit_message(embed = embed, view = None, attachments = [])
                return

            view = discord.ui.View()
            if len(allNeighbors) > 1:
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

        result = await fn.identifyNodeChannel(guildData, ctx.channel.name, origin)
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
                    await fn.closeDialogue(interaction)
                    await deleteEdges(addNodes.values[0])
                    return

                view = discord.ui.View()                
                view, addNodes = await fn.addNodes(view, guildData['nodes'], submitNodes, manyNodes = False)
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

        guildData = db.gd(ctx.guild_id)

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

            for ancestor in ancestors:
                description += f"\n<- <#{guildData['nodes'][ancestor]['channelID']}>"
            for neighbor in neighbors:
                description += f"\n<-> <#{guildData['nodes'][neighbor]['channelID']}>"        
            for successor in successors:
                description += f"\n-> <#{guildData['nodes'][successor]['channelID']}>"

            hasWhitelist = False
            for edge in edgeData:
                if edge.get('allowedRoles', []) or edge.get('allowedPeople', []):
                    hasWhitelist = True
                    break

            affectedNeighbors = []
            clearing = False
            graphImage = None

            async def refreshEmbed():

                fullDescription = description

                if clearing:
                    fullDescription += f"\n• Whitelist: Removing all restrictions. Click 'Clear Whitelist' again\
                        to use the pre-existing whitelist (or the whitelist composed of what's below, if any\
                        roles or people are specified)."
                
                if (addRoles.values or addPeople.values) and not clearing:
                    allowedRoles = [role.id for role in addRoles.values]
                    allowedPeople = [person.id for person in addPeople.values]
                    fullDescription += f"\n• New whitelist(s)-- will overwrite any previous whitelist: \
                        {await fn.formatWhitelist(allowedRoles, allowedPeople)}"

                elif len(allNeighbors) == 1 and not clearing:
                    fullDescription += f"\n• Whitelist: \
                        {await fn.formatWhitelist(edgeData[0].get('allowedRoles', []), edgeData[0].get('allowedPeople', []))}"
                
                elif not clearing:
                    if await fn.whitelistsSimilar(edgeData):
                        fullDescription += f"\n• Whitelists: Every edge has the same whitelist-\
                        \"{await fn.formatWhitelist(edgeData[0].get('allowedRoles', []), edgeData[0].get('allowedPeople', []))}\""
                    else:
                        fullDescription += f'\n• Whitelists: Multiple different whitelists.'

                embed, _ = await fn.embed(
                    'Change whitelists?',
                    fullDescription,
                    'This can always be reversed.',
                    (graphImage, 'full'))

                return embed

            async def updateFile():

                nonlocal graphImage

                if len(allNeighbors) > 1:
                    affectedNeighbors = [selected.split()[1] for selected in addEdges.values]
                else:
                    affectedNeighbors = [allNeighbors[0]]

                edgeColors = []
                for origin, destination in subgraph.edges:
                    if origin in affectedNeighbors and destination == originName:
                        edgeColors.append('blue')
                    elif destination in affectedNeighbors and origin == originName:
                        edgeColors.append('blue')
                    else:
                        edgeColors.append('black')

                graphImage = await fn.showGraph(subgraph, edgeColors)
                return

            async def refreshFile(interaction: discord.Interaction):
                await updateFile()
                await interaction.response.edit_message(file = discord.File(graphImage, filename='image.png'))
                return

            async def clearWhitelist(interaction: discord.Interaction):
                nonlocal clearing
                clearing = not clearing
                embed = await refreshEmbed()
                await interaction.response.edit_message(embed = embed)
                return 

            async def confirmEdges(interaction: discord.Interaction):

                await interaction.response.defer()

                if not affectedNeighbors:
                    embed, _ = await fn.embed(
                        'No edges!',
                        "You didn't select any edges of which to change the permissions.",
                        'You can call the command again and add some.')
                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        view = None,
                        attachments = [])
                    return

                editedEdges = {}
                for origin, destination in subgraph.edges:

                    if origin in affectedNeighbors and destination == originName:
                        editedEdges[(origin, destination)]  = {}
                    elif destination in affectedNeighbors and origin == originName:
                        editedEdges[(destination, origin)] = {}
                    
                con = db.connectToGuild()
                db.updateGuild(con, guildData, interaction.guild_id)
                
                if clearing:
                    description = '\n• Removed the whitelist(s).'
                    for edge in editedEdges:
                        guildData['edges'][edge].pop('allowedPeople', [])
                        guildData['edges'][edge].pop('allowedRoles', [])
                    
                else:
                    
                    description = ''

                    if addRoles.values:
                        description += '\n• Edited the roles whitelist(s).'
                    if addPeople.values:
                        description += '\n• Edited the people whitelist(s).'

                    allowedRoles = [role.id for role in addRoles.values]
                    allowedPeople = [person.id for person in addPeople.values]

                    for edge in editedEdges:
                        if allowedRoles:
                            guildData['edges'][edge]['allowedRoles'] = allowedRoles
                        else:
                            guildData['edges'][edge].pop('allowedRoles', [])
                            
                        if allowedPeople:
                            guildData['edges'][edge]['allowedPeople'] = allowedPeople
                        else:
                            guildData['edges'][edge].pop('allowedPeople', [])

                db.updateGuild(con, guildData, interaction.guild_id)
                con.close()
                
                if not clearing and not allowedRoles and not allowedPeople:
                    description = "• You successfully edited the edges(s) to have the\
                    exact same whitelist as before."

                embed, _ = await fn.embed(
                    'Allow results.',
                    description,
                    'You can always undo these changes.') 
                 
                await interaction.followup.edit_message(
                    message_id = interaction.message.id,
                    embed = embed,
                    view = None,
                    attachments = [])              
                return

            view = discord.ui.View()
            if len(allNeighbors) > 1:
                view, addEdges = await fn.addEdges(refreshFile, ancestors, neighbors, successors, view, False)
            view, addRoles = await fn.addRoles(view, len(ctx.guild.roles), refresh = refreshEmbed)
            view, addPeople = await fn.addPeople(view, ctx.guild.member_count, refresh = refreshEmbed)
            view, submit = await fn.addSubmit(view, confirmEdges)
            if hasWhitelist:
                view, clear = await fn.addClear(view, clearWhitelist)
            view, cancel = await fn.addCancel(view)

            await updateFile()
            embed = await refreshEmbed()

            await ctx.respond(embed = embed,
            file = discord.File(graphImage, filename='image.png'), 
            view = view,
            ephemeral = True)
            return

        result = await fn.identifyNodeChannel(guildData, ctx.channel.name, origin)
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
                    await fn.closeDialogue(interaction)
                    await revisePermissions(addNodes.values[0])
                    return

                view = discord.ui.View()                
                view, addNodes = await fn.addNodes(view, guildData['nodes'], submitNodes, manyNodes = False)
                view, cancel = await fn.addCancel(view)
                await ctx.respond(embed = embed, view = view)

        return

class serverCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    server = SlashCommandGroup(
        name = 'server',
        description = 'View or fix the graph or delete all data.',
        guild_only = True,
        guild_ids = [1114005940392439899])

    @server.command(
        name = 'clear',
        description = 'Delete all server data.')
    async def clear( ##Come back here and include a purge for player channels + db
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        #con = db.connectToGuild()
        guildData = db.gd(ctx.guild_id)
        members = db.ml(ctx.guild_id)
        print(f'Guild data: {guildData}')
        print(f'Members list: {members}')

        if not guildData and not members:
            con = db.connectToGuild()
            db.deleteGuild(con, ctx.guild_id)
            con.close()

            con = db.connectToPlayer()
            db.deleteMembers()
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
            
            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)

            for nodeName, nodeData in guildData['nodes'].items():

                try:
                    nodeChannel = await discord.utils.get_or_fetch(interaction.guild, 'channel', nodeData['channelID'])
                    await nodeChannel.delete()
                except:
                    pass

            members = db.getMembers(con, interaction.guild_id)
            db.deleteGuild(con, interaction.guild_id)
            con.close()

            con = db.connectToPlayer()
            for memberID in members:
                playerData = db.getPlayer(con, memberID)

                try:
                    playerChannel = await discord.utils.get_or_fetch(interaction.guild,
                    'channel',
                    playerData['places'][str(interaction.guild_id)]['channelID'])
                    await playerChannel.delete()
                except:
                    pass
            
                del playerData['places'][str(interaction.guild_id)]
                db.updatePlayer(con, playerData, memberID)

            con.close()
            
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
            and {edgeCount} edges, alongside all player data.",
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
              
        result = await fn.identifyNodeChannel(guildData, node)
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

        guildData = db.gd(ctx.guild_id)

        graph = await fn.makeGraph(guildData)
        description = ''

        channelIDs = [channel.id for channel in ctx.guild.text_channels]
        brokenNodeNames = [node for node in guildData['nodes'] if guildData['nodes'][node]['channelID'] not in channelIDs]
        if brokenNodeNames:
            description += f'\n• The following nodes have no channels, meaning \
                they are **broken:** {await fn.listWords(brokenNodeNames)}.'
        else:
            description += f'\n• Every node has a valid channel.'

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

        if not noAccess and not noExits and not noEntrances:
            description += f'\n• Every node has at least one entrance and at least one exit.'

        async def regenChannels(interaction: discord.Interaction):

            await interaction.response.defer()

            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)

            fixedChannelMentions = []
            for node in brokenNodeNames:
                newNodeChannel = await fn.newChannel(interaction.guild, node, 'nodes')
                fixedChannelMentions.append(newNodeChannel.mention)
                guildData['nodes'][node]['channelID'] = newNodeChannel.id

                whitelist = await fn.formatWhitelist(guildData['nodes'][node].get('allowedRoles', []),
                    guildData['nodes'][node].get('allowedPeople', []))
                embed, _ = await fn.embed(
                'Cool, new node...again.',
                f"**Important!** Don't mess with the settings for this channel! \
                That means no editing the permissions, the name, and **no deleting** it. Use \
                `/node review`, or your network will (once more) be broken! \
                \n\nAnyways, here's who is allowed:\n{whitelist}\n\n Of course, this can change \
                with `/node review`, which lets you view/change the whitelist, among other things.",
                "You can also set the location message for this node by doing /node message while you're here.")         
                await newNodeChannel.send(embed = embed)

            db.updateGuild(con, guildData, interaction.guild_id)
            con.close()            

            embed, _ = await fn.embed(
                'All better.',
                f'\n• Successfully regenerated missing channel(s) for {await fn.listWords(fixedChannelMentions)}.',
                "It'll work again now.")
            
            await interaction.followup.edit_message(message_id = interaction.message.id, embed = embed, view = None)
            return

        view = discord.ui.View()
        if brokenNodeNames:
            regenerate = discord.ui.Button(
                label = 'Regenerate Channels',
                style = discord.ButtonStyle.success)
            regenerate.callback = regenChannels
            view.add_item(regenerate)

        embed, _ = await fn.embed(
        f'Server fix',
        description,
        'Be sure to check this whenever you have issues.')

        await ctx.respond(embed = embed, view = view)
        return

class helpCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    help = SlashCommandGroup(
        name = 'help',
        description = "Understand what's going on.",
        guild_only = True,
        guild_ids = [1114005940392439899])

    @help.command(
        name = 'me',
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
            embed, file = await fn.embed(
            f'Help for "{word}"',
            allHelp[word],
            "Clear things up, I hope?")

            await ctx.respond(embed = embed)
            return

        embed, _ = await fn.embed(
        'Hello!',
        f"This command will help you understand any __underlined__ words\
        in `/help player`, or if you're a server owner, `/help admin`.\
        When you find an underlined word you want to know more about,\
        just do `/help me <word>`. :)",
        "I'll be here if/when you need me.")

        await ctx.respond(embed = embed)
        return

class playerCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    player = SlashCommandGroup(
        name = 'player',
        description = "Add, remove, and manage players.",
        guild_only = True,
        guild_ids = [1114005940392439899])

    @player.command(
        name = 'new',
        description = 'Add a new player to the server.')
    async def new(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData = db.gd(ctx.guild_id)

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

            await interaction.response.defer()

            if not addPeople.values:
                embed, _ = await fn.embed(
                    'Who?',
                    "You didn't select anyone to add.",
                    'You can call the command again specify someone.')
                await interaction.followup.edit_message(
                    message_id = interaction.message.id,
                    embed = embed,
                    view = None)
                return

            if not addNodes.values:
                embed, _ = await fn.embed(
                    'Where?',
                    "You didn't select anywhere to put the new player(s).",
                    'You can call the command again specify a node.')
                await interaction.followup.edit_message(
                    message_id = interaction.message.id,
                    embed = embed,
                    view = None)
                return
                
            nodeName = addNodes.values[0]    
            con = db.connectToPlayer()

            existingPlayers = 0
            newPlayerIDs = []
            for person in addPeople.values:
                playerData = db.getPlayer(con, person.id)

                if playerData['places'].get(str(interaction.guild_id), None):
                    existingPlayers += 1
                    continue

                newPlayerChannel = await fn.newChannel(interaction.guild, person.name, 'players')
                playerData['places'][interaction.guild_id] = {
                    'channelID' : newPlayerChannel.id,
                    'locationName' : nodeName}
                db.updatePlayer(con, playerData, person.id)
                newPlayerIDs.append(person.id)
            con.close()

            #Add the players to the guild nodes as occupants
            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)
            priorOccupants = guildData['nodes'][nodeName].get('occupants', [])
            guildData['nodes'][nodeName]['occupants'] = priorOccupants + newPlayerIDs
            db.updateGuild(con, guildData, interaction.guild_id)

            #Add new players to guild member list
            members = db.getMembers(con, interaction.guild_id)
            members += newPlayerIDs
            db.updateMembers(con, members, interaction.guild_id)
            con.close()
            print(members)

            description = ''
            if newPlayerIDs:
                newPlayerMentions = [f'<@{playerID}>' for playerID in newPlayerIDs]
                description += f"Successfully added {await fn.listWords(newPlayerMentions)} as players to this server,\
                    starting their journey at <#{guildData['nodes'][nodeName]['channelID']}>."

            if existingPlayers:
                description += f"\n\nYou provided {existingPlayers} person(s) that are already in,\
                    so they got skipped. They're all players now, either way."          

            embed, _ = await fn.embed(
                'New player results.',
                description,
                'The more the merrier.')
            await interaction.followup.edit_message(
                message_id = interaction.message.id,
                embed = embed,
                view = None)
            return

        view = discord.ui.View() 
        view, addPeople = await fn.addPeople(view, ctx.guild.member_count, refresh = refreshEmbed)
        view, addNodes = await fn.addNodes(view, guildData['nodes'], refresh = refreshEmbed, manyNodes = False)
        view, submit = await fn.addSubmit(view, submitPlayers)
        view, cancel = await fn.addCancel(view)
        embed = await refreshEmbed()

        await ctx.respond(embed = embed, view = view)
        return
  
def setup(prox):

    prox.add_cog(nodeCommands(prox), override = True)
    prox.add_cog(edgeCommands(prox), override = True)
    prox.add_cog(serverCommands(prox), override = True)
    prox.add_cog(helpCommands(prox), override = True)
    prox.add_cog(playerCommands(prox), override = True)