

#Import-ant Libraries
from discord import Guild
from discord.utils import get

#Data Libraries
from attr import s, ib, Factory
from sqlite3 import connect
from base64 import b64encode, b64decode
from pickle import loads, dumps
from io import BytesIO

#Math Libraries
from nx import DiGraph, ego_graph, draw_networkx_nodes, \
    draw_networkx_edges, shell_layout, draw_networkx_labels
from math import sqrt
from matplotlib.patches import ArrowStyle
from matplotlib import margins, tight_layout, axis, gcf, close


#Classes
@s(auto_attribs = True)
class Component:
    allowed_roles: set = Factory(set)
    allowed_players: set = Factory(set)

    async def set_roles(self, role_IDs: set):
        self.allowed_roles = role_IDs
        return

    async def set_players(self, players_IDs: set):
        self.allowed_players = players_IDs
        return

    async def clear_whitelist(self):
        self.allowed_roles = set()
        self.allowed_players = set()
        return

    async def __dict__(self):
        return_dict = {}

        if self.allowed_roles:
            return_dict['allowed_roles'] = self.allowed_roles

        if self.allowed_players:
            return_dict['allowed_players'] = self.allowed_players

        return return_dict


@s(auto_attribs = True)
class Node(Component):
    channel_ID: int = attr.ib(default = 0)
    occupants: set = attr.Factory(set)
    neighbors: dict = attr.Factory(dict)

    def __attrs_pre_init__(self):
        super().__init__()
        return

    def __attrs_post_init__(self):
        self.mention = f'<#{self.channel_ID}>'

        if self.neighbors:
            neighbors = {}
            for neighbor, edge in self.neighbors.items():
                neighbors[neighbor] = Edge(
                    directionality = edge['directionality'],
                    allowed_roles = edge.get('allowed_roles', set()),
                    allowed_players = edge.get('allowed_players', set()))

            self.neighbors = neighbors

        return

    async def add_occupants(self, occupant_IDs: iter):

        if not isinstance(occupant_IDs, set):
            occupant_IDs = set(occupant_IDs)

        self.occupants |= occupant_IDs
        return

    async def removeOccupants(self, occupant_IDs: iter):

        if not isinstance(occupant_IDs, set):
            occupant_IDs = set(occupant_IDs)

        if not occupant_IDs.issubset(self.occupants):
            raise KeyError("Trying to remove someone from a node who's already absent.")

        self.occupants -= occupant_IDs
        return

    async def clear_whitelist(self):
        self.allowed_roles = set()
        self.allowed_players = set()
        return

    async def __str__(self):
        return f'Node, channel ...{self.channel_ID[12:]}'

    async def __dict__(self):
        return_dict = await super().__dict__()
        return_dict['channel_ID'] = self.channel_ID

        if self.occupants:
            return_dict['occupants'] = self.occupants

        if self.neighbors:
            neighbors_dict = {}
            for neighbor, edge in self.neighbors.items():
                neighbors_dict[neighbor] = await edge.__dict__()

            return_dict['neighbors'] = neighbors_dict

        return return_dict


@s(auto_attribs = True)
class GuildData:
    guildID: int
    maker: ChannelMaker = ib(default = None)
    nodes: dict = Factory(dict)
    players: set = Factory(set)

    def __attrs_post_init__(self):

        def return_dictionary(cursor, guild):
            fields = [column[0] for column in cursor.description]
            return {column_name: data for column_name, data in zip(fields, guild)}

        guild_con = connect('guildDB.db')
        guild_con.row_factory = return_dictionary
        cursor = guild_con.cursor()

        cursor.execute("SELECT * FROM guilds WHERE guildID = ?", (self.guildID,))
        guild_data = cursor.fetchone()

        if guild_data:
            decoded_nodes = b64decode(guild_data['nodes'])
            nodes_dict = loads(decoded_nodes)

            for name, data in nodes_dict.items():
                self.nodes[name] = Node(
                        channel_ID = data['channel_ID'],
                        occupants = data.get('occupants', set()),
                        allowed_roles = data.get('allowed_roles', set()),
                        allowed_players = data.get('allowed_players', set()),
                        neighbors = data.get('neighbors', dict()))

        cursor.execute(f"""SELECT * FROM player_data WHERE guildID = {self.guildID}""")
        player_data = cursor.fetchone()

        if player_data:
            self.players = set(int(player) for player in player_data['players'].split())

        guild_con.close()
        return

    #Nodes
    async def newNode(
        self,
        name: str,
        channel_ID: int,
        allowed_roles: iter = set(),
        allowed_players: iter = set()):

        if name in self.nodes:
            raise KeyError('Node already exists, no overwriting!')
            return

        self.nodes[name] = Node(
            channel_ID = channel_ID,
            allowed_players = allowed_players,
            allowed_roles = allowed_roles)

        return

    async def delete_node(self, name: str, channels: iter = set()):

        node = self.nodes.pop(name, None)

        if not node:
            raise KeyError('Tried to delete a nonexistent node!')
            return

        channel = get(channels, id = node.channel_ID)
        if channel:
            await channel.delete()

        for other_node in self.nodes.values():
            other_node.neighbors.pop(name, None)

        return

    async def filter_nodes(self, node_names: iter):
        return {name : self.nodes[name] for name in node_names}

    async def get_all_occupants(self, nodes: iter):
        occupants = set()
        for node in nodes:
            occupants |= node.occupants
        return occupants

    async def accessible_locations(self, role_IDs: iter, player_ID: int, origin: str):

        graph = DiGraph()

        accessible_nodes = set()
        inaccessible_nodes = set()

        for name, node in self.nodes.items():

            if (name == origin
                or not node.allowed_players
                or player_ID in node.allowed_players
                or any(ID in node.allowed_roles for ID in role_IDs)):

                graph.add_node(name)
                accessible_nodes.add(name)

            else:
                inaccessible_nodes.add(name)

                completed_edges = set()

        for name in accessible_nodes:

            for neighbor, edge in self.nodes[name].neighbors.items():

                if (neighbor not in accessible_nodes
                    or neighbor in completed_edges):
                    continue

                if ((not edge.allowed_players and not edge.allowed_roles)
                    or player_ID in edge.allowed_players
                    or any(ID in edge.allowed_roles for ID in role_IDs)):
                    pass
                else:
                    continue

                if edge.directionality > 0:
                    graph.add_edge(name, neighbor)

                if edge.directionality < 2:
                    graph.add_edge(neighbor, name)

            completed_edges.add(name)

        return ego_graph(graph, origin, radius = 99)

    #Edges
    async def set_edge(
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
                newEdge = Edge(
                    allowed_roles = edge.allowed_roles,
                    allowed_players = edge.allowed_players,
                    directionality = 2)
                self.nodes[destination].neighbors[origin] = newEdge

            case 1:
                self.nodes[origin].neighbors[destination] = edge
                newEdge = Edge(
                    allowed_roles = edge.allowed_roles,
                    allowed_players = edge.allowed_players,
                    directionality = 1)
                self.nodes[destination].neighbors[origin] = newEdge

            case 2:
                self.nodes[origin].neighbors[destination] = edge
                newEdge = Edge(
                    allowed_roles = edge.allowed_roles,
                    allowed_players = edge.allowed_players,
                    directionality = 0)
                self.nodes[destination].neighbors[origin] = newEdge

        return priorEdge

    async def delete_edge(self, origin: str, destination: str):
        self.nodes[origin].neighbors.pop(destination)
        self.nodes[destination].neighbors.pop(origin)
        return

    async def neighbors(self, node_names: iter, exclusive: bool = True):

        neighbors = set()
        for node in (self.nodes[name] for name in node_names):
            neighbors |= node.neighbors.keys()

        if exclusive:
            neighbors -= node_names
        else:
            neighbors |= node_names

        return neighbors

    async def edge_count(self, nodes: dict = {}):

        included_nodes = nodes if nodes else self.nodes
        visited_nodes = set()

        for name, node in included_nodes.items():
            edge_count = sum(1 for neighbor, edge in node.neighbors.items() \
                if neighbor not in visited_nodes)
            visited_nodes.add(name)

        return edge_count

    async def format_edges(self, neighbors: dict):

        description = ''
        for neighbor_name, edge in neighbors.items():

            match edge.directionality:

                case 0:
                    description += f'\n<- <#{self.nodes[neighbor_name].channel_ID}>'

                case 1:
                    description += f'\n<-> <#{self.nodes[neighbor_name].channel_ID}>'

                case 2:
                    description += f'\n-> <#{self.nodes[neighbor_name].channel_ID}>'

        return description




#Pick up here



    #Players
    async def newPlayer(self, player_ID: int, location: str):

        if location in self.nodes:
            self.nodes[location].add_occupants({player_ID})
        else:
            raise KeyError(f'Attempted to add player to nonexistent node named {location}.')
            return

        self.members.add(player_ID)
        return

    #Guild Data
    async def toGraph(self, nodeDict: dict = {}):
        graph = DiGraph()

        nodesToGraph = nodeDict if nodeDict else self.nodes

        completed_edges = set()
        for name, node in nodesToGraph.items():
            graph.add_node(
                name,
                channel_ID = node.channel_ID)

            for destination, edge in node.neighbors.items():

                if destination in completed_edges:
                    continue

                if edge.directionality > 0:
                    graph.add_edge(name, destination)
                    graph[name][destination]['allowed_roles'] = edge.allowed_roles
                    graph[name][destination]['allowed_players'] = edge.allowed_players

                if edge.directionality < 2:
                    graph.add_edge(destination, name)
                    graph[destination][name]['allowed_roles'] = edge.allowed_roles
                    graph[destination][name]['allowed_players'] = edge.allowed_players

            completed_edges.add(name)

        return graph

    async def toMap(self, graph = None, edgeColor: str = []):

        if not graph:
            graph = await self.toGraph()
        if not edgeColor:
            edgeColor = ['black'] * len(graph.edges)

        positions = shell_layout(graph)

        # Draw the nodes without edges
        draw_networkx_nodes(
            graph,
            pos = positions,
            node_shape = 'o',
            node_size = 1,
            node_color = '#ffffff')
        draw_networkx_labels(graph, pos = positions, font_weight = 'bold')

        currentIndex = 0
        letterSpacing = 0.029
        for origin, destination in graph.edges:

            ox, oy = positions[origin]
            dx, dy = positions[destination]
            distance = sqrt((dx - ox) ** 2 + (dy - oy) ** 2)

            if distance > letterSpacing*2: #Move the edges away from the labels

                if dx - ox != 0:
                    slope = abs((dy - oy) / (dx - ox))
                    angleSpacing = 1 - abs((1 - slope) / (1 + slope)) * 0.15

                    labelFactor = 1 / (abs(slope) + 1)

                    originSpacing = 0.1 * (1 - angleSpacing) + len(origin) * \
                        letterSpacing * angleSpacing * labelFactor
                    destinationSpacing = 0.1 * (1 - angleSpacing) + len(destination) * \
                        letterSpacing * angleSpacing * labelFactor

                    ox += (dx - ox) * originSpacing / distance
                    oy += (dy - oy) * originSpacing / distance

                    dx += (ox - dx) * destinationSpacing / distance
                    dy += (oy - dy) * destinationSpacing / distance

            else:
                ox = dx = (dx + ox) / 2
                oy = dy = (dy + oy) / 2

            draw_networkx_edges(
                graph,
                pos = {origin : (ox, oy),
                    destination: (dx, dy)},
                edgelist = [(origin, destination)],
                edge_color = edgeColor[currentIndex],
                width = 3.0,
                arrowstyle =
                    ArrowStyle('-|>'),
                arrowsize = 15)
            currentIndex += 1

        #Adjust the rest
        margins(x = 0.3, y = 0.1)
        tight_layout(pad = 0.8)
        axis('on')

        #Produce image
        #plt.show() #Uncomment this and comment everything below for bugtesting
        graphImage = gcf()
        close()
        bytesIO = BytesIO()
        graphImage.savefig(bytesIO)
        bytesIO.seek(0)

        return bytesIO

    async def save(self):

        guild_con = connect('guildDB.db')
        cursor = guild_con.cursor()

        nodesData = {nodeName : await node.__dict__() for nodeName, node in self.nodes.items()}
        serializedNodes = dumps(nodesData)
        encodedNodes = b64encode(serializedNodes)
        cursor.execute("INSERT or REPLACE INTO guilds(guildID, nodes) VALUES(?, ?)",
            (self.guildID, encodedNodes))

        player_data = ' '.join([str(player_ID) for player_ID in self.players])
        cursor.execute("INSERT or REPLACE INTO player_data(guildID, players) VALUES(?, ?)",
            (self.guildID, player_data))

        guild_con.commit()
        guild_con.close()
        return

    async def delete(self):

        guild_con = connect('guildDB.db')
        cursor = guild_con.cursor()

        for node in self.nodes:
            cursor.execute("""DELETE FROM messages WHERE
                            locationChannelID = ?""", (node.channel_ID,))

        cursor.execute("DELETE FROM guilds WHERE guildID = ?", (self.guildID,))
        cursor.execute("DELETE FROM player_data WHERE guildID = ?", (self.guildID,))
        guild_con.commit()

        print(f'Guild deleted, ID: {self.guildID}.')
        return

    async def clear(
        self,
        guild: Guild,
        directListeners: dict,
        indirectListeners: dict):

        for player_ID in self.players:

            player = Player(player_ID, self.guildID)

            channel = get(guild.channels, id = player.channel_ID)
            if channel:
                await channel.delete()

            directListeners.pop(player.channel_ID, None)
            indirectListeners.pop(player.channel_ID, None)

            await player.delete()

        for name, node in list(self.nodes.items()):
            directListeners.pop(node.channel_ID, None)
            await self.delete_node(name, guild.channels)

        for categoryName in ['nodes', 'players']:
            nodeCategory = get(guild.categories, name = categoryName)
            await nodeCategory.delete() if nodeCategory else None

        await self.delete()
        return directListeners, indirectListeners
