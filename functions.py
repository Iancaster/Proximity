import discord
import databaseFunctions as db
import networkx as nx
from io import BytesIO
import matplotlib.pyplot as plt
from discord.utils import get_or_fetch, get
import oopFunctions as oop

#Dialogues
async def embed(
    title: str = 'No Title',
    description: str = 'No description.',
    footer: str = 'No footer.',
    imageDetails = None):

    embed = discord.Embed(
        title = title,
        description = description,
        color = discord.Color.from_rgb(67, 8, 69))

    embed.set_footer(text = footer)

    match imageDetails:
        
        case None:
            file = discord.MISSING

        case thumb if imageDetails[1] == 'thumb':
            file = discord.File(imageDetails[0], filename='image.png')
            embed.set_thumbnail(url='attachment://image.png')
        
        case full if imageDetails[1] == 'full':
            file = discord.File(imageDetails[0], filename='image.png')
            embed.set_image(url='attachment://image.png')
            
        case _:
            print(f"Unrecognized image viewing mode in dialogue!")
            file = discord.MISSING

    return embed, file

async def nullResponse(interaction: discord.Interaction):

    await interaction.response.edit_message()
    return #get fucked lmao

async def addEdges(
        ancestors: list, 
        neighbors: list, 
        successors: list, 
        view: discord.ui.View, 
        delete: bool = True,
        callback: callable = None):

    action = 'delete' if delete else 'review whitelists'

    edgeSelect = discord.ui.Select(
        placeholder = f'Which edges to {action}?',
        min_values = 0,
        max_values = len(ancestors + neighbors + successors))
    edgeSelect.callback = callback

    for ancestor in ancestors:
        edgeSelect.add_option(label = f'<- {ancestor}',
                                value = ancestor)

    for neighbor in neighbors:
        edgeSelect.add_option(label = f'<-> {neighbor}',
                                value = neighbor)
    
    for successor in successors:
        edgeSelect.add_option(label = f'-> {successor}',
                                value = successor)

    view.add_item(edgeSelect)

    return view, edgeSelect

async def addUserNodes(view: discord.ui.View, nodes: list, callback: callable = None, refresh: callable = None):

    if not nodes:
        nodeSelect = discord.ui.Select(
            placeholder = 'No places you can access.',
            disabled = True)
        nodeSelect.add_option(
            label = 'Nothing to choose.')
        view.add_item(nodeSelect)
        return view, nodeSelect

    nodeSelect = discord.ui.Select(placeholder = 'Which place?')
    if callback:
        nodeSelect.callback = callback
    else:
        async def nodesChosen(interaction: discord.Interaction):
            embed = await refresh()
            await interaction.response.edit_message(embed = embed)
            return
        nodeSelect.callback = nodesChosen


    for node in nodes:
        nodeSelect.add_option(
            label = node)
    
    view.add_item(nodeSelect)
    return view, nodeSelect

async def addArrows(leftCallback: callable = None, rightCallback: callable = None):

    view = discord.ui.View()

    if leftCallback:
        left = discord.ui.Button(
            label = '<',
            style = discord.ButtonStyle.secondary)
        left.callback = leftCallback
        view.add_item(left)
    
    else:
        left = discord.ui.Button(
            label = '-',
            style = discord.ButtonStyle.secondary,
            disabled = True)
        view.add_item(left)
        
    if rightCallback:
        right = discord.ui.Button(
            label = '>',
            style = discord.ButtonStyle.secondary)
        right.callback = rightCallback
        view.add_item(right)

    else:
        right = discord.ui.Button(
            label = 'Done',
            style = discord.ButtonStyle.secondary)
        right.callback = closeDialogue
        view.add_item(right)

    return view

#Formatting
async def whitelistsSimilar(components: list):

    firstRoles = components[0].get('allowedRoles', [])
    firstPeople = components[0].get('allowedPeople', [])
    for component in components:

        if firstRoles != component.get('allowedRoles', []) or firstPeople != component.get('allowedPeople', []):
            return False

    return True

async def formatEdges(nodes: dict, ancestors: list, neighbors: list, successors: list):

    description = ''
    for ancestor in ancestors:
        description += f"\n<- <#{nodes[ancestor]['channelID']}>"
    for neighbor in neighbors:
        description += f"\n<-> <#{nodes[neighbor]['channelID']}>"        
    for successor in successors:
        description += f"\n-> <#{nodes[successor]['channelID']}>"

    return description
    
#Edges
async def colorEdges(graph: nx.Graph, originName: str, coloredNeighbors: list, color: str):

    edgeColors = []
    for origin, destination in graph.edges:
        if origin in coloredNeighbors and destination == originName:
            edgeColors.append(color)
        elif origin == originName and destination in coloredNeighbors:
            edgeColors.append(color)
        else:
            edgeColors.append('black')

    return edgeColors
    
async def getConnections(graph: nx.Graph, nodes: list, split: bool = False):
    
    successors = set()
    ancestors = set()

    for node in nodes:
        successors = successors.union(graph.successors(node))
        ancestors = ancestors.union(graph.predecessors(node))

    if split:
        mutuals = ancestors.intersection(successors)
        ancestors -= mutuals
        successors -= mutuals
        return list(ancestors), list(mutuals), list(successors)
    
    else: 
        neighbors = ancestors.union(successors)
        return list(neighbors)

async def filterMap(guildData: dict, roleIDs: list, userID: int, origin: str):

    graph = nx.DiGraph()

    acceptedNodes = set()

    for nodeName, nodeData in guildData['nodes'].items():

        if nodeName == origin:
            graph.add_node(nodeName)
            acceptedNodes.add(nodeName)
            continue

        allowedPeople = nodeData.get('allowedPeople', [])
        allowedRoles = nodeData.get('allowedRoles', [])

        if not allowedPeople and not allowedRoles:
            graph.add_node(nodeName)
            acceptedNodes.add(nodeName)
            continue

        if userID in allowedPeople:
            graph.add_node(nodeName)
            acceptedNodes.add(nodeName)
            continue

        for roleID in roleIDs:
            if roleID in allowedRoles:
                graph.add_node(nodeName)
                acceptedNodes.add(nodeName)
                continue

    for edgeName, edgeData in guildData['edges'].items():

        if edgeName[0] in acceptedNodes and edgeName[1] in acceptedNodes:
            pass
        else:
            continue

        allowedPeople = edgeData.get('allowedPeople', [])
        allowedRoles = edgeData.get('allowedRoles')

        if not allowedPeople and not allowedRoles:
            graph.add_edge(edgeName[0], edgeName[1])
            continue

        if userID in allowedPeople:
            graph.add_edge(edgeName[0], edgeName[1])
            continue

        for roleID in roleIDs:
            if roleID in allowedRoles:
                graph.add_edge(edgeName[0], edgeName[1])
                continue
    
    return nx.ego_graph(graph, origin, radius = 99)

#Guild
async def identifyNodeChannel(
    nodesNames: dict,
    originChannelName: str = '',
    namedChannelName: str = ''):

    if not nodesNames: 

        embedData, _ = await embed(
            'Easy, bronco.',
            "You've got no nodes to work with.",
            'Make some first with /node new.')

        return embedData
    
    elif namedChannelName:

        if namedChannelName in nodesNames:
            return namedChannelName
        
        else:

            embedData, _ = await embed(
                'What?',
                f"**#{namedChannelName}** isn't a node channel. Did you select the wrong one?",
                'Try calling the command again.')
            
            return embedData

    if originChannelName in nodesNames:
        return originChannelName
    
    else:
        return None

async def autocompleteNodes(ctx: discord.AutocompleteContext):

    guildData = db.gd(ctx.interaction.guild_id)

    if not guildData['nodes']:
        return ['No nodes!']
    
    return guildData['nodes']

async def autocompleteMap(ctx: discord.AutocompleteContext):

    guildData = db.gd(ctx.interaction.guild_id)
    con = db.connectToPlayer()
    playerData = db.getPlayer(con, ctx.interaction.user.id)
    serverData = playerData.get(str(ctx.interaction.guild_id), None)

    if not serverData:
        return ['For players only!']

    accessibleNodes = await filterMap(guildData,
        [role.id for role in ctx.interaction.user.roles],
        ctx.interaction.user.id,
        serverData['locationName'])

    if not accessibleNodes:
        return ['No where you can go.']
    
    return accessibleNodes.nodes

async def waitForRefresh(interaction: discord.Interaction):

    embedData, _ = await embed(
        'Moving...',
        'Getting into position.',
        'This will only be a moment.')
    await interaction.response.edit_message(
        embed = embedData,
        view = None)
    return

async def loading(interaction: discord.Interaction):

    embedData, _ = await embed(
        'Loading...',
        'Recalculating listeners.',
        'This will take less than five seconds.')
    await interaction.response.edit_message(
        embed = embedData,
        view = None,
        attachments = [])
    return

#Checks
async def nodeExists(node, interaction: discord.Interaction):
    embedData, _ = await embed(
        'Already exists.',
        f"There's already a {node.mention}. Rename it with `/node review` or use a new name for this one.",
        'Try calling the command again.')        
    await interaction.followup.edit_message(message_id = interaction.message.id, embed = embedData, view = None)
    return

async def noNodes(interaction: discord.Interaction, singular: bool = False):
    if singular:
        embedData, _ = await embed(
            'No nodes!',
            "Please select a valid node first.",
            'Try calling the command again.')
    else:
        embedData, _ = await embed(
            'No nodes!',
            "You've got to select some.",
            'Try calling the command again.')        
    await interaction.followup.edit_message(
        message_id = interaction.message.id,
        embed = embedData,
        view = None,
        attachments = [])
    return

async def noEdges(edges, interaction: discord.Interaction):

    if not edges:

        embedData, _ = await embed(
            'No edges!',
            "You've got to select some.",
            'Try calling the command again.')        
        await interaction.followup.edit_message(
            message_id = interaction.message.id, 
            embed = embedData, 
            view = None,
            attachments = [])
        return True
    
    return False

async def noPeople(values, interaction: discord.Interaction):

    if not values:
        embedData, _ = await embed(
            'Who?',
            "You didn't select any valid people.",
            'You can call the command again and specify someone new.')
        await interaction.followup.edit_message(
            message_id = interaction.message.id,
            embed = embedData,
            view = None)
        return True

    return False

async def noChanges(test, interaction: discord.Interaction):

    if not test:
        embedData, _ = await embed(
            'Success?',
            "You didn't make any changes.",
            "Unsure what the point of that was.")
        await interaction.followup.edit_message(
            message_id = interaction.message.id,
            embed = embedData,
            view = None,
            attachments = [])
        return True

    return False

async def hasWhitelist(components):

    for component in components:
        if component.get('allowedRoles', False) or component.get('allowedPeople', False):
            return True
    
    return False

async def notPlayer(ctx: discord.ApplicationContext, members: list):

    if ctx.author.id not in members:
        embedData, _ = await embed(
            'Easy there.',
            "You're not a player in this server, so you're not able to do this.",
            'You can ask the server owner to make you a player?')
        await ctx.respond(embed = embedData)
        return True

    return False

async def noCopies(test, embed: discord.Embed, interaction: discord.Interaction):

    if test:
        await interaction.delete_original_response()

    else:
        await interaction.followup.edit_message(
            message_id = interaction.message.id,
            embed = embed,
            view = None)

    return

    