import discord
import databaseFunctions as db
import networkx as nx
from io import BytesIO
import matplotlib.pyplot as plt


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
            file = discord.File(f'assets/imagery/{imageDetails[0]}', filename='image.png')
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

    await interaction.response.defer()
    return #get fucked lmao

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

    action = 'delete' if delete else 'change whitelists'

    edgeSelect = discord.ui.Select(
        placeholder = f'Which edges to {action}?',
        min_values = 0,
        max_values = len(ancestors + neighbors + successors))
    edgeSelect.callback = callback

    for ancestor in ancestors:
        edgeSelect.add_option(label = f'<- {ancestor}')

    for neighbor in neighbors:
        edgeSelect.add_option(label = f'<-> {neighbor}')
    
    for successor in successors:
        edgeSelect.add_option(label = f'-> {successor}')

    view.add_item(edgeSelect)

    return view, edgeSelect

async def addPeople(view: discord.ui.View, maxUsers: int, callback: callable = None, refresh: callable = None):

    memberSelect = discord.ui.Select(
        placeholder = 'Which people to add?',
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

async def addClear(view: discord.ui.View, callback: callable):

    clear = discord.ui.Button(
        label = 'Clear Whitelist',
        style = discord.ButtonStyle.secondary)
    clear.callback = callback
    view.add_item(clear)

    return view, clear

async def addSubmit(view: discord.ui.View, callback: callable):

    submit = discord.ui.Button(
        label = 'Submit',
        style = discord.ButtonStyle.success)
    submit.callback = callback
    view.add_item(submit)

    return view, submit

async def addEvilConfirm(view: discord.ui.View, callback: callable):

    evilConfirm = discord.ui.Button(
        label = 'Confirm',
        style = discord.ButtonStyle.danger)
    evilConfirm.callback = callback
    view.add_item(evilConfirm)

    return view, evilConfirm

async def addCancel(view: discord.ui.View):

    cancel = discord.ui.Button(
        label = 'Cancel',
        style = discord.ButtonStyle.secondary)
    cancel.callback = closeDialogue
    view.add_item(cancel)

    return view, cancel

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
        return f'Only people with these roles are allowed into this node: ({await listWords(roleMentions)}).'

    elif allowedPeople and not allowedRoles:
        return f'Only these people are allowed into this node: ({await listWords(peopleMentions)}).'

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

#Nodes
async def newNode(channelID: int, allowedRoles: list = [], allowedPeople: list = []):
    
    node = {'channelID' : channelID}

    if allowedRoles:
        node['allowedRoles'] = allowedRoles
    
    if allowedPeople:
        node['allowedPeople'] = allowedPeople
    
    return node

async def nodesFromNames(nodeNames: list, guildNodes: dict):

    return {node : guildNodes[node] for node in nodeNames if node in guildNodes}

#Edges
async def newEdge(origin: str, destination: str, allowedRoles: list = [], allowedPeople: list = []):
    
    edge = {(origin, destination) : {}}

    if allowedRoles:
        edge['allowedRoles'] = allowedRoles

    if allowedPeople:
        edge['allowedPeople'] = allowedPeople
    
    return edge

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

async def showGraph(graph: nx.Graph, edgeColor: list = None):
    
    if not edgeColor:
        edgeColor = ['black'] * len(graph.edges)

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

#Guild
async def assertPlayerCategory(guild: discord.Guild):

    playerCategory = discord.utils.get(guild.categories, name = 'players')
    
    if playerCategory:
        return playerCategory
    
    return guild.create_category('players')

async def identifyNodeChannel(
    guildData: dict,
    originChannelName: str = '',
    namedChannelName: str = ''):

    nodes = guildData['nodes']

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

    con = db.connectToGuild()
    guildData = db.getGuild(con, ctx.interaction.guild_id)
    con.close()

    if not guildData['nodes']:
        return ['No nodes!']
    
    return guildData['nodes']

async def newChannel(guild: discord.guild, name: str, category: str):

    neededCategory = discord.utils.get(guild.categories, name = category)
    
    if not neededCategory:
        neededCategory = await guild.create_category(category)

    permissions = {guild.default_role : discord.PermissionOverwrite(read_messages = False),
    guild.me : discord.PermissionOverwrite(send_messages = True, read_messages =True)}
    channel = await guild.create_text_channel(
        name,
        category = neededCategory,
        overwrites = permissions)
    
    return channel