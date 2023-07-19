import discord.ui
from discord.utils import get

import functions as fn
import databaseFunctions as db

import attr, base64, pickle, sqlite3, math
import networkx as nx
import matplotlib.pyplot as plt
from io import BytesIO

@attr.s
class Format:
    
    @classmethod
    async def words(cls, words: iter):
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

    @classmethod
    async def roles(cls, roleIDs: iter):
        return await cls.words([f'<@&{roleID}>' for roleID in roleIDs])

    @classmethod
    async def players(cls, playerIDs: iter):
        return await cls.words([f'<@{playerID}>' for playerID in playerIDs])
    
    @classmethod
    async def whitelist(cls, allowedRoles: iter = set(), allowedPlayers: iter = set()):

        if not allowedRoles or allowedPlayers:
            return 'Everyone will be allowed to travel to/through this place.'

        roleMentions = await cls.roles(allowedRoles)
        playerMentions = await cls.players(allowedPlayers)

        if allowedRoles and not allowedPlayers:
            return f'Only people with these roles are allowed through this place: ({roleMentions}).'

        elif allowedPlayers and not allowedRoles:
            return f'Only these people are allowed through this place: ({playerMentions}).'

        rolesDescription = f'any of these roles: ({roleMentions})' if allowedRoles else 'any role'

        playerDescription = f'any of these people: ({playerMentions})' if allowedPlayers else 'everyone else'

        return f'People with {rolesDescription} will be allowed to come here as well as {playerDescription}.'

    @classmethod
    def discordify(cls, text: str):

        if not text:
            return ''
        
        sanitized = ''.join(character.lower() for character in \
                            text if (character.isalnum() or character.isspace() or character == '-'))
        spaceless = '-'.join(sanitized.split())

        return spaceless[:19]

    @classmethod
    async def bold(cls, nodeNames: iter):
        return await cls.words([f"**#{name}**" for name in nodeNames]) 

    @classmethod
    async def nodes(cls, nodes: iter):
        return await cls.words([node.mention for node in nodes])

@attr.s(auto_attribs = True)
class Player:
    id: int = attr.ib(default = 0)
    guildID: int = attr.ib(default = 0)
    
    def __attrs_post_init__(self):

        def returnDictionary(cursor, players):
            fields = [column[0] for column in cursor.description]
            return {fieldName: data for fieldName, data in zip(fields, players)}

        playerCon = sqlite3.connect('playerDB.db')
        playerCon.row_factory = returnDictionary
        cursor = playerCon.cursor()
        cursor.execute(f"""SELECT * FROM players WHERE playerID = {self.id}""")
        playerData = cursor.fetchone()

        if playerData:
            decodedPlayer = base64.b64decode(playerData)
            self.playerDict = pickle.loads(decodedPlayer)
            serverData = self.playerDict.get(self.guildID, {})
        else:
            self.playerDict = {}
            serverData = {}
        
        self.channelID = serverData.get('channelID', None)
        self.location = serverData.get('location', None)
        self.eavesdropping = serverData.get('eavesdropping', None)
        return

    async def save(self):

        playerCon = sqlite3.connect('playerDB.db')
        cursor = playerCon.cursor()

        self.playerDict[self.guildID] = {
            'channelID' : self.channelID,
            'location' : self.location,
            'eavesdropping' : self.eavesdropping}
        
        return await self._commit(playerCon, cursor)

    async def delete(self):

        self.playerDict.pop(self.guildID)

        playerCon = sqlite3.connect('playerDB.db')
        cursor = playerCon.cursor()
        
        if self.playerDict:
            return await self._commit(playerCon, cursor)

        cursor.execute(f"DELETE FROM players WHERE playerID = ?", (self.id,))
        playerCon.commit()
        print(f'Player deleted, ID: {self.id}.')
        return

    async def _commit(self, playerCon, cursor):

        serializedData = pickle.dumps(self.playerDict)
        encodedData = base64.b64encode(serializedData)
        cursor.execute("INSERT or REPLACE INTO players(playerID, serverData) VALUES(?, ?)", 
            (self.id, encodedData))

        playerCon.commit()
        playerCon.close()
        return

@attr.s(auto_attribs = True)
class ChannelMaker:
    guild: discord.Guild
    categoryName: str  = attr.ib(default = '')

    def __attrs_post_init__(self):

        with open('assets/avatar.png', 'rb') as file:
            self.avatar = file.read()

    async def initialize(self):

        foundCategory = discord.utils.get(self.guild.categories, name = self.categoryName)
        if foundCategory:
            self.category = foundCategory
            return

        newCategory = await self.guild.create_category(self.categoryName)
        self.category = newCategory
        return
    
    async def newChannel(self, name: str, allowedPerson: discord.Member = None):
        permissions = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages = False),
            self.guild.me: discord.PermissionOverwrite(send_messages = True, read_messages = True)}

        if allowedPerson:
            permissions.update({
                allowedPerson: discord.PermissionOverwrite(send_messages = True, read_messages = True)})

        newChannel = await self.guild.create_text_channel(
            name,
            category = self.category,
            overwrites = permissions)
        await newChannel.create_webhook(name = 'Proximity', avatar = self.avatar)
        return newChannel

@attr.s(auto_attribs = True) #Fix bug here where attributes are inexplicably linked between classes
class Component:
    allowedRoles: set = attr.Factory(set)
    allowedPlayers: set = attr.Factory(set)

    async def setRoles(self, roleIDs: set):
        self.allowedRoles = roleIDs
        return

    async def setPlayers(self, playerIDs: set):
        self.allowedPlayers = playerIDs
        return

    async def clearWhitelist(self):
        self.allowedRoles = set()
        self.allowedPlayers = set()
        return

    async def __dict__(self):
        returnDict = {}
        
        if self.allowedRoles:
            returnDict['allowedRoles'] = self.allowedRoles

        if self.allowedPlayers:
            returnDict['allowedPlayers'] = self.allowedPlayers

        return returnDict

@attr.s(auto_attribs = True)
class Edge(Component):
    directionality: int = attr.ib(default = 1)
    # directionality > 0 means it's going TO the destination
    # directionality < 2 means it's coming FROM the target

    async def __dict__(self):
        returnDict = await super().__dict__()
        returnDict['directionality'] = self.directionality
        return returnDict

@attr.s(auto_attribs = True)
class Node(Component):
    channelID: int = attr.ib(default = 0)
    occupants: set = attr.Factory(set)
    neighbors: dict = attr.Factory(dict)

    def __attrs_pre_init__(self):
        super().__init__()
        return    
    
    def __attrs_post_init__(self):
        self.mention = f'<#{self.channelID}>'

        if self.neighbors:
            newNeighbors = {}
            for neighbor, edge in self.neighbors.items():
                newNeighbors[neighbor] = Edge(
                    directionality = edge['directionality'],
                    allowedRoles = edge.get('allowedRoles', set()),
                    allowedPlayers = edge.get('allowedPlayers', set()))

            self.neighbors = newNeighbors
        
        return

    async def addOccupants(self, occupantIDs: iter):
        self.occupants |= occupantIDs
        return

    async def removeOccupants(self, occupantIDs: iter):

        if not occupantIDs.issubset(self.occupants):
            raise KeyError("Trying to remove someone from a node who's already absent.")

        self.occupants -= occupantIDs
        return

    async def clearWhitelist(self):
        self.allowedRoles = set()
        self.allowedPlayers = set()

    async def __str__(self):
        return f'Node, channel ...{self.channelID[12:]}'

    async def __dict__(self):
        returnDict = await super().__dict__()
        returnDict['channelID'] = self.channelID

        if self.occupants:
            returnDict['occupants'] = self.occupants

        if self.neighbors:
            neighborDict = {}
            for neighbor, edge in self.neighbors.items():
                neighborDict[neighbor] = await edge.__dict__()
            
            returnDict['neighbors'] = neighborDict
        
        return returnDict

@attr.s(auto_attribs = True)
class GuildData:
    guildID: int
    maker: ChannelMaker = attr.ib(default = None)
    nodes: dict = attr.Factory(dict)
    players: set = attr.Factory(set)

    def __attrs_post_init__(self):

        def returnDictionary(cursor, guild):
            fields = [column[0] for column in cursor.description]
            return {columnName: data for columnName, data in zip(fields, guild)}

        guildCon = sqlite3.connect('guildDB.db')
        guildCon.row_factory = returnDictionary
        cursor = guildCon.cursor()
        
        cursor.execute("SELECT * FROM guilds WHERE guildID = ?", (self.guildID,))
        guildData = cursor.fetchone()    

        if guildData:
            decodedNodes = base64.b64decode(guildData['nodes'])
            nodesDict = pickle.loads(decodedNodes)

            for name, data in nodesDict.items():
                self.nodes[name] = Node(
                        channelID = data['channelID'],
                        occupants = data.get('occupants', set()),
                        allowedRoles = data.get('allowedRoles', set()),
                        allowedPlayers = data.get('allowedPlayers', set()),
                        neighbors = data.get('neighbors', dict()))

        cursor.execute(f"""SELECT * FROM playerData WHERE guildID = {self.guildID}""")
        playerData = cursor.fetchone()

        if playerData:
            self.players = [int(player) for player in playerData['players'].split()]

        guildCon.close()
        return

    #Nodes
    async def newNode(
        self, 
        name: str, 
        channelID: int, 
        allowedRoles: iter = set(), 
        allowedPlayers: iter = set()):

        if name in self.nodes:
            raise KeyError('Node already exists, no overwriting!')
            return

        self.nodes[name] = Node(
            channelID = channelID,
            allowedPlayers = allowedPlayers, 
            allowedRoles = allowedRoles)

        return

    async def deleteNode(self, name: str, channels: iter = set()):
        node = self.nodes.pop(name, None)

        if not node:
            raise KeyError('Tried to delete a nonexistent node!')
            return

        channel = get(channels, id = node.channelID)
        if channel:
            await channel.delete()
        return

    async def filterNodes(self, nodeNames: iter):
        return {name : self.nodes[name] for name in nodeNames}

    async def getUnifiedOccupants(self, nodes: iter):
        occupants = set()
        for node in nodes:
            occupants |= node.occupants
        return occupants

    #Edges
    async def setEdge(
        self, 
        origin: str, 
        destination: str, 
        edge: Edge,
        overwrite: bool = False):

        if destination in self.nodes[origin].neighbors or \
            origin in self.nodes[destination].neighbors:

            if overwrite:
                priorEdge = True
            else:
                return True
        else:
            priorEdge = False

        match edge.directionality:

            case 0:
                self.nodes[origin].neighbors[destination] = edge
                edge.directionality = 2
                self.nodes[destination].neighbors[origin] = edge

            case 1:
                self.nodes[origin].neighbors[destination] = edge
                self.nodes[destination].neighbors[origin] = edge

            case 2:
                self.nodes[origin].neighbors[destination] = edge
                edge.directionality = 0
                self.nodes[destination].neighbors[origin] = edge

        return priorEdge

    async def deleteEdge(self, origin: str, destination: str):
        self.nodes[origin].neighbors.pop(destination)
        self.nodes[destination].neighbors.pop(origin)
        return

    async def neighbors(self, nodeNames: iter, exclusive: bool = True):

        neighbors = set()
        for node in (self.nodes[name] for name in nodeNames):
            neighbors |= node.neighbors.keys()

        if exclusive:
            neighbors -= nodeNames
        else:
            neighbors |= nodeNames
        
        return neighbors

    async def edgeCount(self, nodes: dict = {}):
        countingNodes = nodes if nodes else self.nodes
        visitedNodes = set()
        edgeCount = 0
        for name, node in countingNodes.items():
            for neighbor, edge in node.neighbors.items():
                if neighbor in visitedNodes:
                    continue
                edgeCount += 1
            visitedNodes.add(name)
        return edgeCount

    #Players
    async def newPlayer(self, playerID: int, location: str):

        if location in self.nodes:
            self.nodes[location].addOccupants({playerID})
        else:
            raise KeyError(f'Attempted to add player to nonexistent node named {location}.')
            return

        self.members.add(playerID)
        return

    #Guild Data
    async def toGraph(self, nodeDict: dict = {}): 
        graph = nx.DiGraph()

        nodesToGraph = nodeDict if nodeDict else self.nodes

        madeEdges = set()
        for name, node in nodesToGraph.items():
            graph.add_node(
                name,
                channelID = node.channelID)
            
            allowedRoles = node.allowedRoles
            allowedPlayers = node.allowedPlayers
            occupants = node.occupants

            for destination, edge in node.neighbors.items():

                if destination in madeEdges:
                    continue

                if edge.directionality > 0:
                    graph.add_edge(name, destination)
                    graph[name][destination]['allowedRoles'] = edge.allowedRoles
                    graph[name][destination]['allowedPlayers'] = edge.allowedPlayers
                
                if edge.directionality < 2:
                    graph.add_edge(destination, name)
                    graph[destination][name]['allowedRoles'] = edge.allowedRoles
                    graph[destination][name]['allowedPlayers'] = edge.allowedPlayers

            madeEdges.add(name)

        return graph

    async def toMap(self, graph = None, edgeColor: str = 'black'):

        if not graph:
            graph = await self.toGraph()

        # nx.draw_shell(
        #     graph,
        #     with_labels = True,
        #     font_weight = 'bold',
        #     arrows = True,
        #     arrowsize = 20,
        #     width = 2,
        #     arrowstyle = '->',
        #     node_shape = 'o',
        #     node_size = 4000,
        #     node_color = '#ffffff',
        #     margins = (.3, .1),
        #     edge_color = edgeColor)

        positions = nx.shell_layout(graph)

        # Draw the nodes without edges
        nx.draw_networkx_nodes(
            graph,
            pos = positions,
            node_shape = 'o',
            node_size = 4000,
            node_color = '#ffffff')
        nx.draw_networkx_labels(graph, pos = positions, font_weight = 'bold')

        node_size = 100  # Adjust this value based on your node size
        edge_pos = {}
        for edge in graph.edges():
            u, v = edge
            if u in positions and v in positions:
                x1, y1 = positions[u]
                x2, y2 = positions[v]
                d = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                if d < 100:
                    # Adjust edge positions to maintain the minimum distance
                    offset = (100 - d) / d
                    dx = (x2 - x1) * offset
                    dy = (y2 - y1) * offset
                    x1 -= dx
                    y1 -= dy
                    x2 += dx
                    y2 += dy
                edge_pos[edge] = [(x1, y1), (x2, y2)]
                nx.draw_networkx_edges(graph, pos =  edge_pos, edgelist=[edge], edge_color='black', width=2.0)

        #Adjust margins
        plt.margins(x = .1)
        plt.subplots_adjust(
            left = .2, 
            right = .8, 
            bottom = .1, 
            top = .9)
        plt.axis('off')
        
        #Produce image
        graphImage = plt.gcf()
        plt.close()
        bytesIO = BytesIO()
        graphImage.savefig(bytesIO)
        bytesIO.seek(0)

        return bytesIO

    async def save(self):

        guildCon = sqlite3.connect('guildDB.db')
        cursor = guildCon.cursor()

        nodesData = {nodeName : await node.__dict__() for nodeName, node in self.nodes.items()}
        serializedNodes = pickle.dumps(nodesData)
        encodedNodes = base64.b64encode(serializedNodes)
        cursor.execute("INSERT or REPLACE INTO guilds(guildID, nodes) VALUES(?, ?)", 
            (self.guildID, encodedNodes))

        playerData = ' '.join([str(playerID) for playerID in self.players])
        cursor.execute(f"INSERT or REPLACE INTO playerData(guildID, players) VALUES(?, ?)",
            (self.guildID, playerData))

        guildCon.commit()
        guildCon.close()
        return

    async def delete(self):

        guildCon = sqlite3.connect('guildDB.db')
        cursor = guildCon.cursor()

        for node in self.nodes:
            cursor.execute(f"""DELETE FROM messages WHERE
                            locationChannelID = ?""", (node.channelID,))

        cursor.execute(f"DELETE FROM guilds WHERE guildID = ?", (self.guildID,))
        cursor.execute(f"DELETE FROM playerData WHERE guildID = ?", (self.guildID,))
        guildCon.commit()

        print(f'Guild deleted, ID: {self.guildID}.')
        return

    async def clear(
        self,
        guild: discord.Guild, 
        directListeners: dict, 
        indirectListeners: dict):

        for name, node in list(self.nodes.items()):
            directListeners.pop(node.channelID, None)
            await self.deleteNode(name, guild.channels)

        for playerID in self.players:

            player = Player(playerID, self.guildID)

            channel = get(guild.channels, id = player.channelID)
            if channel:
                await channel.delete()
            
            directListeners.pop(player.channelID, None)
            indirectListeners.pop(player.channelID, None)

            await player.delete()

        for categoryName in ['nodes', 'players']:
            nodeCategory = get(guild.categories, name = categoryName)
            await nodeCategory.delete() if nodeCategory else None

        await self.delete()
        return directListeners, indirectListeners

@attr.s(auto_attribs = True)
class DialogueView(discord.ui.View):
    guild: discord.Guild = attr.ib(default = None)
    refresh: callable = attr.ib(default = None)

    def __attrs_pre_init__(self):
        super().__init__()
        return

    def __attrs_post_init__(self):
        self.clearing = False
        self.overwriting = False
        self.directionality = 1
        return

    async def _closeDialogue(self, interaction: discord.Interaction):

        embed, _ = await fn.embed(
            'Cancelled.',
            'Window closed.',
            'Feel free to call the command again.')

        await interaction.response.edit_message(
            embed = embed, 
            attachments = [], 
            view = None)
        return   
 
    async def _callRefresh(self, interaction: discord.Interaction):
        embed = await self.refresh()
        await interaction.response.edit_message(embed = embed)
        return


    #Selects
    async def addRoles(self, maxRoles: int = 0, callback: callable = None):

        if not maxRoles:
            maxRoles = len(self.guild.roles)

        roleSelect = discord.ui.Select(
            placeholder = 'Which roles to add?',
            select_type = discord.ComponentType.role_select,
            min_values = 0,
            max_values = maxRoles)

        roleSelect.callback = callback if callback else self._callRefresh

        self.add_item(roleSelect)
        self.roleSelect = roleSelect
        return

    def roles(self):
        return {role.id for role in self.roleSelect.values}

    async def addPeople(self, maxUsers: int, callback: callable = None):

        peopleSelect = discord.ui.Select(
            placeholder = 'Which people?',
            select_type = discord.ComponentType.user_select,
            min_values = 0,
            max_values = maxUsers)

        peopleSelect.callback = callback if callback else self._callRefresh

        self.add_item(peopleSelect)
        self.peopleSelect = peopleSelect
        return

    def people(self):
        return self.peopleSelect.values

    async def addPlayers(self, playerIDs: iter, onlyOne: bool = False, callback: callable = None):

        playerSelect = discord.ui.Select(
            placeholder = 'Which players?',
            min_values = 0,
            max_values = 1)

        addedMembers = 0
        for playerID in playerIDs:
            member = get(self.guild.players, id = playerID)
            playerSelect.add_option(
                label = member.display_name,
                value = str(playerID))
            addedMembers += 1

        if addedMembers == 0: 
            playerSelect.placeholder = 'No players to select.'
            playerSelect.add_option(label = 'No players!')
            playerSelect.disabled = True
            self.playerSelect = playerSelect
        elif onlyOne:
            pass
        else:
            playerSelect.max_values = addedMembers

        playerSelect.callback = callback if callback else self._callRefresh

        self.add_item(playerSelect)
        self.playerSelect = playerSelect
        return 

    def players(self):
        return {int(playerID) for playerID in self.playerSelect.values}

    async def addNodes(self, nodeNames: iter, callback: callable = None, manyNodes: bool = True):

        if not nodeNames:
            nodeSelect = discord.ui.Select(
                placeholder = 'No nodes to select.',
                disabled = True)
            nodeSelect.add_option(
                label = 'Nothing to choose.')
            self.add_item(nodeSelect)
            self.nodeSelect = nodeSelect
            return

        if manyNodes:
            maxValues = len(nodeNames)
        else:
            maxValues = 1
        
        nodeSelect = discord.ui.Select(
            placeholder = 'Which node(s) to select?',
            min_values = 1,
            max_values = maxValues)
        
        nodeSelect.callback = callback if callback else self._callRefresh

        [nodeSelect.add_option(label = node) for node in nodeNames]

        self.add_item(nodeSelect)
        self.nodeSelect = nodeSelect
        return

    def nodes(self):
        return self.nodeSelect.values


    #Modal
    async def addName(self):

        modal = discord.ui.Modal(title = 'Choose a new name?')

        nameSelect = discord.ui.InputText(
            label = 'name',
            style = discord.InputTextStyle.short,
            min_length = 1,
            max_length = 20,
            placeholder = "What should it be?")
        modal.add_item(nameSelect)
        modal.callback = self._callRefresh

        async def sendModal(interaction: discord.Interaction):
            await interaction.response.send_modal(modal = modal)
            return

        modalButton = discord.ui.Button(
            label = 'Change Name',
            style = discord.ButtonStyle.success)

        modalButton.callback = sendModal
        self.add_item(modalButton)
        self.nameSelect = nameSelect
        return

    def name(self):
        return Format.discordify(self.nameSelect.value)
        
    #Buttons
    async def addClear(self):
        clear = discord.ui.Button(
            label = 'Clear Whitelist',
            style = discord.ButtonStyle.secondary)

        async def clearing(interaction: discord.Interaction):
            self.clearing = not self.clearing
            await self._callRefresh(interaction)
            return

        clear.callback = clearing
        self.add_item(clear)
        return

    async def addOverwrite(self):
        overwrite = discord.ui.Button(
            label = 'Toggle Overwrite',
            style = discord.ButtonStyle.secondary)

        async def overwriting(interaction: discord.Interaction):
            self.overwriting = not self.overwriting
            await self._callRefresh(interaction)
            return

        overwrite.callback = overwriting
        self.add_item(overwrite)
        return

    async def addDirectionality(self):
        direct = discord.ui.Button(
            label = 'Toggle Direction',
            style = discord.ButtonStyle.secondary)

        async def changeDirectionality(interaction: discord.Interaction):
            if self.directionality < 2:
                self.directionality += 1
            else:
                self.directionality = 0
            await self._callRefresh(interaction)
            return 

        direct.callback = changeDirectionality
        self.add_item(direct)
        return

    async def addSubmit(self, callback: callable):

        submit = discord.ui.Button(
            label = 'Submit',
            style = discord.ButtonStyle.success)
        submit.callback = callback
        self.add_item(submit)
        return

    async def addEvilConfirm(self, callback: callable):

        evilConfirm = discord.ui.Button(
            label = 'Confirm',
            style = discord.ButtonStyle.danger)
        evilConfirm.callback = callback
        self.add_item(evilConfirm)
        return
    
    async def addCancel(self):

        cancel = discord.ui.Button(
            label = 'Cancel',
            style = discord.ButtonStyle.secondary)
        cancel.callback = self._closeDialogue
        self.add_item(cancel)
        return

    #Methods
    async def whitelist(self, components: iter): #Revisit this

        if self.clearing:
            return "\n• Whitelist: Removing all restrictions. Click 'Clear Whitelist' again" + \
                " to use the old whitelist, or if you select any roles or players below, to use that."

        if self.roles() or self.players():
            return "\n• New whitelist(s)-- will overwrite the old whitelist:" + \
                f" {await Format.whitelist(self.roles(), self.players())}"

        firstComponent = list(components)[0]

        if len(components) == 1:
            return "\n• Whitelist:" + \
                f" {await Format.whitelist(firstComponent.allowedRoles, firstComponent.allowedPlayers)}"

        if False: #await self.whitelistsSimilar(components.values()):
            return "\n• Whitelists: Every part has the same whitelist-" + \
                await Format.whitelist(firstComponent.allowedRoles, \
                    firstComponent.allowedPlayers)

        else:
            return '\n• Whitelists: Multiple different whitelists.'

@attr.s(auto_attribs = True)
class Auto:

    @classmethod
    async def nodes(self, ctx: discord.AutocompleteContext):

        guildData = GuildData(ctx.interaction.guild_id)

        if not guildData.nodes:
            return ['No nodes!']
        
        return guildData.nodes
    
    @classmethod
    async def map(self, ctx: discord.AutocompleteContext):

        guildData = GuildData(ctx.interaction.guild_id)
        player = Player(ctx.interaction.user.id, guildData.id)


        return ['Unfinished!']

        if not player.channelID:
            return ['For players only!']

        accessibleNodes = await filterMap(guildData,
            [role.id for role in ctx.interaction.user.roles],
            ctx.interaction.user.id,
            serverData['locationName'])

        if not accessibleNodes:
            return ['No where you can go.']
        
        return accessibleNodes.nodes

