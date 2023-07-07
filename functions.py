import discord
import databaseFunctions as db
import networkx as nx
from io import BytesIO
import matplotlib.pyplot as plt
from discord.utils import get_or_fetch, get
from functools import lru_cache


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

async def closeDialogue(interaction: discord.Interaction):

    embedData, _ = await embed(
        'Cancelled.',
        'Window closed.',
        'Feel free to call the command again.')

    await interaction.response.edit_message(embed = embedData, attachments = [], view = None)
    return   
 
async def nullResponse(interaction: discord.Interaction):

    await interaction.response.edit_message()
    return #get fucked lmao

@lru_cache
async def addRoles(view: discord.ui.View, maxRoles: int, callback: callable = None, refresh: callable = None):

    roleSelect = discord.ui.Select(
        placeholder = 'Which roles to add?',
        select_type = discord.ComponentType.role_select,
        min_values = 0,
        max_values = maxRoles)

    if callback:
        roleSelect.callback = callback
    else:
        async def rolesChosen(interaction: discord.Interaction):
            embed = await refresh()
            await interaction.response.edit_message(embed = embed)
            return
        roleSelect.callback = rolesChosen
    
    view.add_item(roleSelect)
    return view, roleSelect

async def addEdges(callback, ancestors: list, neighbors: list, successors: list, view: discord.ui.View, delete: bool = True):

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

@lru_cache
async def addPeople(view: discord.ui.View, maxUsers: int, callback: callable = None, refresh: callable = None):

    memberSelect = discord.ui.Select(
        placeholder = 'Which people?',
        select_type = discord.ComponentType.user_select,
        min_values = 0,
        max_values = maxUsers)

    if callback:
        memberSelect.callback = callback
    else:
        async def peopleChosen(interaction: discord.Interaction):
            embed = await refresh()
            await interaction.response.edit_message(embed = embed)
            return
        memberSelect.callback = peopleChosen

    view.add_item(memberSelect)
    return view, memberSelect

async def addPlayers(view: discord.ui.View, allMembers: list, playerIDs: list, onlyOne: bool = False, callback: callable = None, refresh: callable = None):

    playerSelect = discord.ui.Select(
        placeholder = 'Which players?',
        min_values = 0,
        max_values = 25)

    addedMembers = 0
    for member in allMembers:
        if member.id in playerIDs:
            playerSelect.add_option(
                label = member.display_name,
                value = str(member.id))
            addedMembers += 1

    if addedMembers == 0: 
        playerSelect.placeholder = 'No players to select.'
        playerSelect.add_option(label = 'No players!')
        playerSelect.disabled = True
        playerSelect.max_values = 1
    elif onlyOne:
        playerSelect.max_values = 1
    else:
        playerSelect.max_values = addedMembers

    if callback:
        playerSelect.callback = callback
    else:
        async def peopleChosen(interaction: discord.Interaction):
            embed = await refresh()
            await interaction.response.edit_message(embed = embed)
            return
        playerSelect.callback = peopleChosen

    view.add_item(playerSelect)
    return view, playerSelect

@lru_cache
async def addClear(view: discord.ui.View, callback: callable):

    clear = discord.ui.Button(
        label = 'Clear Whitelist',
        style = discord.ButtonStyle.secondary)
    clear.callback = callback
    view.add_item(clear)

    return view, clear

@lru_cache
async def addSubmit(view: discord.ui.View, callback: callable):

    submit = discord.ui.Button(
        label = 'Submit',
        style = discord.ButtonStyle.success)
    submit.callback = callback
    view.add_item(submit)

    return view, submit

@lru_cache
async def addEvilConfirm(view: discord.ui.View, callback: callable):

    evilConfirm = discord.ui.Button(
        label = 'Confirm',
        style = discord.ButtonStyle.danger)
    evilConfirm.callback = callback
    view.add_item(evilConfirm)

    return view, evilConfirm

@lru_cache
async def addCancel(view: discord.ui.View):

    cancel = discord.ui.Button(
        label = 'Cancel',
        style = discord.ButtonStyle.secondary)
    cancel.callback = closeDialogue
    view.add_item(cancel)

    return view, cancel

@lru_cache
async def addNameModal(view: discord.ui.View, refresh: callable):

    modal = discord.ui.Modal(title = 'Choose a new name?')

    nameSelect = discord.ui.InputText(
        label = 'name',
        style = discord.InputTextStyle.short,
        min_length = 1,
        max_length = 15,
        placeholder = "What should it be?")
    modal.add_item(nameSelect)
    
    async def nameChosen(interaction: discord.Interaction):
        embed = await refresh()
        await interaction.response.edit_message(embed = embed)
        return
    modal.callback = nameChosen

    async def sendModal(interaction: discord.Interaction):
        await interaction.response.send_modal(modal = modal)
        return

    modalButton = discord.ui.Button(
        label = 'Change Name',
        style = discord.ButtonStyle.success)
    modalButton.callback = sendModal
    view.add_item(modalButton)

    return view, nameSelect

async def addNodes(view: discord.ui.View, nodes: list, callback: callable = None, refresh: callable = None, manyNodes: bool = True):

    if not nodes:
        nodeSelect = discord.ui.Select(
            placeholder = 'No nodes to select.',
            disabled = True)
        nodeSelect.add_option(
            label = 'Nothing to choose.')
        view.add_item(nodeSelect)
        return view, nodeSelect

    if manyNodes:
        maxValues = len(nodes)
    else:
        maxValues = 1
    
    nodeSelect = discord.ui.Select(
        placeholder = 'Which node(s) to select?',
        min_values = 1,
        max_values = maxValues)
    
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

@lru_cache
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
async def listWords(words: list):

    match len(words):

        case 0:
            return ''
        
        case 1:
            return words[0]

        case 2:
            return f'{words[0]} and {words[1]}'

        case _:

            passage = ''

            for index, word in enumerate(words):

                if index < len(words) - 1:
                    passage += f'{word}, '
                    continue
                
                passage += f'and {word}'

            return passage

async def formatWhitelist(allowedRoles: list = [], allowedPeople: list = []):

    roleMentions = [f'<@&{roleID}>' for roleID in allowedRoles]
    peopleMentions = [f'<@{personID}>' for personID in allowedPeople]

    if allowedRoles and not allowedPeople:
        return f'Only people with these roles are allowed through this place: ({await listWords(roleMentions)}).'

    elif allowedPeople and not allowedRoles:
        return f'Only these people are allowed through this place: ({await listWords(peopleMentions)}).'

    if allowedRoles:
        rolesDescription = f'any of these roles: ({await listWords(roleMentions)})'
    else:
        rolesDescription = 'any role'

    if allowedPeople:
        peopleDescription = f'any of these people: ({await listWords(peopleMentions)})'
    else:
        peopleDescription = 'everyone else'

    description = f'People with {rolesDescription} will be allowed to come here,\
        as well as {peopleDescription}.'
    if not allowedPeople:
        description = 'Everyone will be allowed to travel to/through this place.'

    return description

async def discordify(text: str):

    if not text:
        return ''
    spacelessText = '-'.join(text.split())
    discordified = ''.join(character.lower() for character in spacelessText if character.isalnum() or character == '-')

    return discordified[:15]

async def whitelistsSimilar(components: list):

    firstRoles = components[0].get('allowedRoles', [])
    firstPeople = components[0].get('allowedPeople', [])
    for component in components:

        if firstRoles != component.get('allowedRoles', []) or firstPeople != component.get('allowedPeople', []):
            return False

    return True

async def mentionNodes(nodes: dict):

    mentionsList =  [f"<#{node['channelID']}>" for node in nodes.values()]
    
    return await listWords(mentionsList)
    
async def formatEdges(nodes: dict, ancestors: list, neighbors: list, successors: list):

    description = ''
    for ancestor in ancestors:
        description += f"\n<- <#{nodes[ancestor]['channelID']}>"
    for neighbor in neighbors:
        description += f"\n<-> <#{nodes[neighbor]['channelID']}>"        
    for successor in successors:
        description += f"\n-> <#{nodes[successor]['channelID']}>"

    return description

#Nodes
async def newNode(channel: discord.TextChannel, allowedRoles: list = [], allowedPeople: list = []):
    
    node = {'channelID' : channel.id}

    if allowedRoles:
        node['allowedRoles'] = allowedRoles
    
    if allowedPeople:
        node['allowedPeople'] = allowedPeople
    
    return node

async def getOccupants(nodes: dict):

    return {name : data['occupants'] for name, data in nodes.items() if data.get('occupants', False)}

async def filterNodes(nodes: dict, nodeNames: list):

    return {name : nodes[name] for name in nodeNames if name in nodes}
    
#Edges
async def newEdge(origin: str, destination: str, allowedRoles: list = [], allowedPeople: list = []):
    
    edge = {(origin, destination) : {}}

    if allowedRoles:
        edge['allowedRoles'] = allowedRoles

    if allowedPeople:
        edge['allowedPeople'] = allowedPeople
    
    return edge
    
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
    
#Graph
async def makeGraph(guildData: dict):
    graph = nx.DiGraph()

    nodes = guildData.get('nodes', {})
    for nodeName, nodeData in nodes.items():
        graph.add_node(
            nodeName,
            channelID = nodeData['channelID'])
        
        allowedRoles = nodeData.get('allowedRoles', [])
        if allowedRoles:
            graph.nodes[nodeName]['allowedRoles'] = []

        allowedPeople = nodeData.get('allowedPeople', [])
        if allowedPeople:
            graph.nodes[nodeName]['allowedPeople'] = allowedPeople

        occupants = nodeData.get('occupants', [])
        if occupants:
            graph.nodes[nodeName]['occupants'] = occupants
    
    edges = guildData.get('edges', {})
    for edgeName, edgeData in edges.items():

        graph.add_edge(edgeName[0], edgeName[1])

        allowedRoles = edgeData.get('allowedRoles', [])
        if allowedRoles:
            graph[edgeName[0]][edgeName[1]]['allowedRoles'] = allowedRoles

        allowedPeople = edgeData.get('allowedPeople', [])
        if allowedPeople:
            graph[edgeName[0]][edgeName[1]]['allowedPeople'] = allowedPeople
        
    return graph

@lru_cache
async def showGraph(graph: nx.Graph, edgeColor = 'black'):

    nx.draw_shell(
        graph,
        with_labels = True,
        font_weight = 'bold',
        arrows = True,
        arrowsize = 20,
        width = 2,
        arrowstyle = '->',
        node_shape = 'o',
        node_size = 4000,
        node_color = '#ffffff',
        margins = (.3, .1),
        edge_color = edgeColor)
    
    graphImage = plt.gcf()
    plt.close()
    bytesIO = BytesIO()
    graphImage.savefig(bytesIO)
    bytesIO.seek(0)

    return bytesIO

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
        allowedRoles = nodeData.get('allowedRoles')

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
async def assertCategory(guild: discord.Guild, name: str):

    category = get(guild.categories, name = name)
    
    return category if category else await guild.create_category(name)

async def identifyNodeChannel(
    nodes: dict,
    originChannelName: str = '',
    namedChannelName: str = ''):

    if not nodes: 

        embedData, _ = await embed(
            'Easy, bronco.',
            "You've got no nodes to work with.",
            'Make some first with /node new.')

        return embedData
    
    elif namedChannelName:

        if namedChannelName in nodes:
            return namedChannelName
        
        else:

            embedData, _ = await embed(
            'What?',
            f"{namedChannelName} isn't a node channel. Did you select the wrong one?",
            'Try calling the command again.')
            
            return embedData

    if originChannelName in nodes:
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

async def newChannel(guild: discord.guild, name: str, category: discord.CategoryChannel, allowedPerson: discord.Member = None):
    
    permissions = {guild.default_role : discord.PermissionOverwrite(read_messages = False),
    guild.me : discord.PermissionOverwrite(send_messages = True, read_messages =True)}

    if allowedPerson:
        permissions.update({allowedPerson : discord.PermissionOverwrite(send_messages = True, read_messages = True)})

    channel = await guild.create_text_channel(
        name,
        category = category,
        overwrites = permissions)
    await channel.create_webhook(name = 'Proximity')
    
    return channel

async def deleteChannel(channels: list, channelID: int):

    channel = get(channels, id = channelID)
    if channel:
        await channel.delete()
    return channel

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
async def nodeExists(nodes: dict, name: str, interaction: discord.Interaction):

    if name in nodes:
        embedData, _ = await embed(
            'Already exists.',
            f"There's already a <#{nodes[name]['channelID']}>. Rename it with `/node review` or use a new name for this one.",
            'Try calling the command again.')        
        await interaction.followup.edit_message(message_id = interaction.message.id, embed = embedData, view = None)
        return True
    
    return False

async def noNodes(nodes, interaction: discord.Interaction, singular: bool = False):

    if not nodes:

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
        return True
    
    return False

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
            "You didn't select anyone.",
            'You can call the command again and specify someone.')
        await interaction.followup.edit_message(
            message_id = interaction.message.id,
            embed = embedData,
            view = None)
        return True

    return False

async def noChanges(test, interaction: discord.Interaction):

    if not test:
        embedData, _ = await embed(
            'Sucess?',
            "You didn't make any changes.",
            "Unsure what the point of that was.")
        await interaction.followup.edit_message(
            message_id = interaction.message.id,
            embed = embedData,
            view = None,
            attachments = [])
        return True

    return False

@lru_cache
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