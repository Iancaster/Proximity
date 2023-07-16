import discord.ui
from discord.utils import get

import functions as fn
import databaseFunctions as db

import attr, base64, pickle, sqlite3
import networkx as nx

@attr.s(auto_attribs = True)
class ChannelMaker:
    guild: discord.Guild
    categoryName: str

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

@attr.s(auto_attribs = True)
class Component:
    allowedRoles: list[int] = attr.Factory(list)
    allowedPeople: list[int] = attr.Factory(list)

    async def addRole(self, roleID: int):
        self.allowedRoles.append(role_id)
        return

    async def removeRole(self, roleID: int):
        if roleID in self.allowedRoles:
            self.allowedRoles.remove(roleID)
        return

    async def addPerson(self, personID: int):
        self.allowedPeople.append(personID)
        return

    async def removePerson(self, personID: int):
        if personID in self.allowedPeople:
            self.allowedPeople.remove(personID)
        return

    async def clearWhitelist(self):
        self.allowedRoles = []
        self.allowedPeople = []
        return

    async def __dict__(self):
        returnDict = {}
        
        if self.allowedRoles:
            returnDict['allowedRoles'] = self.allowedRoles

        if self.allowedPeople:
            returnDict['allowedPeople'] = self.allowedPeople

        return returnDict

@attr.s(auto_attribs = True)
class Edge(Component):
    directionality: int = attr.ib(default = 1)
    # directionality > 0 means it's going TO the destination
    # directionality < 2 means it's coming FROM the target

    async def __dict__(self):
        returnDict = await super().__dict__()
        returndict['directionality'] = self.directionality
        return returnDict

@attr.s(auto_attribs = True)
class Node(Component):
    channelID: int = attr.ib(default = 0)
    occupants: list[int] = attr.ib(default = [])
    neighbors: dict = attr.ib(default = {})

    def __attrs_pre_init__(self):
        super().__init__()
        return    
    
    def __attrs_post_init__(self):
        self.mention = f'<#{self.channelID}>'
        return

    async def addOccupants(self, occupantIDs: list[int]):
        self.occupants.extend(occupantIDs)
        return

    async def __str__(self):
        return f'Node, channel ...{channelID[12:]}'

    async def __dict__(self):
        returnDict = await super().__dict__()
        returnDict['channelID'] = self.channelID
        returnDict['occupants'] = self.occupants
        return returnDict

@attr.s(auto_attribs = True)
class GuildData:
    guildID: int
    maker: ChannelMaker = attr.ib(default = None)
    nodes: dict = attr.Factory(dict)
    players: list[int] = attr.Factory(list)

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

            for nodeName, nodeData in nodesDict.items():
                self.nodes[nodeName] = Node(
                        channelID = nodeData['channelID'],
                        occupants = nodeData['occupants'],
                        allowedRoles = nodeData.get('allowedRoles', None),
                        allowedPeople = nodeData.get('allowedPeople', None))

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
        allowedRoles: list[int] = [], 
        allowedPeople: list[int] = []):

        if name in self.nodes:
            print('Node already existing, no overwrting!')
            return

        self.nodes[name] = Node(
            channelID = channelID,
            allowedPeople = allowedPeople, 
            allowedRoles = allowedRoles)

        return

    async def deleteNode(self, name: str):
        self.nodes.pop(name, None)
        return

    async def filter(self, nodeNames: list[str]):
        return {name : self.nodes[name] for name in nodeNames}

    async def mentionNodes(self, nodeNames: list[str]):
        return await fn.listWords([self.nodes[name].mention for name in nodeNames])

    async def getUnifiedOccupants(self, nodeNames: list[str]):

        nodes = await filter(nodeNames)
        occupants = []
        (occupants.extend[node.occupants] for node in nodeValues)
        return occupants


    #Edges
    async def setEdge(
        self, 
        origin: str, 
        destination: str, 
        edge: Edge,
        overwrite: bool = False):

        if overwrite:
            if destination in self.nodes[origin].neighbors or \
                origin in self.nodes[destination].neighbors:
                priorEdge = True
            else:
                priorEdge = False

        else:
            if destination in self.nodes[origin].neighbors or \
                origin in self.nodes[destination].neighbors:
                return True

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

    #Players
    async def newPlayer(self, playerID: int, location: str):

        if location in self.nodes:
            self.nodes[location].addOccupants([playerID])
        else:
            print(f'Attempted to add player no nonexistent node named {location}.')
            return

        self.members.append(playerID)
        return

    #Guild Data
    async def toGraph(self):
        graph = nx.DiGraph()

        madeEdges = set()
        for name, node in self.nodes.items():
            graph.add_node(
                name,
                channelID = node.channelID)
            
            allowedRoles = node.allowedRoles
            allowedPeople = node.allowedPeople
            occupants = node.occupants

            for destination, edge in node.edges:

                if destination in madeEdges:
                    continue

                if edge.directionality < 0:
                    graph.add_edge(name, destination)
                    graph[name][destination]['allowedRoles'] = edge.allowedRoles
                    graph[name][destination]['allowedPeople'] = edge.allowedPeople
                
                if edge.directionality > 2:
                    graph.add_edge(destination, name)
                    graph[destionation][name]['allowedRoles'] = edge.allowedRoles
                    graph[destination][time]['allowedPeople'] = edge.allowedPeople

            madeEdges.add(name)

        return graph

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
        self.nodes = {}

        guildCon = sqlite3.connect('guildDB.db')
        cursor = guildCon.cursor()

        for node in self.nodes:
            cursor.execute(f"""DELETE FROM messages WHERE
                            locationChannelID = ?""", (node.channelID,))

        
            
        cursor.execute(f"""DELETE FROM guilds WHERE guildID = {self.guildID}""")
        guildCon.commit()

        print(f'Guild removed, ID: {self.guildID}.')
        return

@attr.s(auto_attribs = True)
class DialogueView(discord.ui.View):
    guild: discord.Guild = attr.ib(default = None)
    refresh: callable = attr.ib(default = None)

    def __attrs_pre_init__(self):
        super().__init__()

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
        return [role.id for role in self.roleSelect.values]

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

    async def addPlayers(self, playerIDs: list[int], onlyOne: bool = False, callback: callable = None):

        playerSelect = discord.ui.Select(
            placeholder = 'Which players?',
            min_values = 0,
            max_values = 1)

        addedMembers = 0
        for playerID in playerIDs:
            member = get(self.guild.members, id = playerID)
            playerSelect.add_option(
                label = member.display_name,
                value = str(playerID))
            addedMembers += 1

        if addedMembers == 0: 
            playerSelect.placeholder = 'No players to select.'
            playerSelect.add_option(label = 'No players!')
            playerSelect.disabled = True
        elif onlyOne:
            pass
        else:
            playerSelect.max_values = addedMembers

        playerSelect.callback = callback if callback else self._callRefresh

        self.add_item(playerSelect)
        self.playerSelect = playerSelect
        return 

    def players(self):
        return [int(playerID) for playerID in self.playerSelect.values]

    async def addNodes(self, nodeNames: list[str], callback: callable = None, manyNodes: bool = True):

        if not nodeNames:
            nodeSelect = discord.ui.Select(
                placeholder = 'No nodes to select.',
                disabled = True)
            nodeSelect.add_option(
                label = 'Nothing to choose.')
            self.add_item(nodeSelect)
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

        for node in nodeNames:
            nodeSelect.add_option(
                label = node)

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
        if not self.nameSelect.value:
            return ''
        else:
            sanitized = ''.join(character.lower() for character in \
                                self.nameSelect.value if (character.isalnum() or character.isspace() or character == '-'))
            spaceless = '-'.join(sanitized.split())

            return spaceless[:19]

        
    #Buttons
    async def addClear(self, callback: callable):

        clear = discord.ui.Button(
            label = 'Clear Whitelist',
            style = discord.ButtonStyle.secondary)
        clear.callback = callback
        self.add_item(clear)
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


