import networkx as nx
import matplotlib.pyplot as plt
import databaseFunctions as db
import io

def makeGraph(guildData: dict):
    graph = nx.DiGraph()

    nodes = guildData.get('nodes', {})
    for nodeName, nodeData in nodes.items():
        graph.add_node(
            nodeName,
            channelID = nodeData['channelID'],
            allowedRoles = nodeData['allowedRoles'],
            allowedPeople = nodeData['allowedPeople'],
            occupants = nodeData['occupants'])
    
    edges = guildData.get('edges', {})
    for edgeName, edgeData in edges.items():

        graph.add_edge(
            edgeName[0],
            edgeName[1],
            allowedRoles = edgeData['allowedRoles'],
            allowedPeople = edgeData['allowedPeople'])
        
    return graph

def showGraph(graph: nx.Graph):
    
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
        edge_color = 'red')
    
    graphImage = plt.gcf()
    plt.show()

    return

#con = db.connectToGuild()
guildData = {'guildID': 1114005940392439899, 'nodes': {'really long name': {'channelID': 1116244275718541314, 'allowedRoles': [], 'allowedPeople': [], 'occupants': []}, 'second': {'channelID': 1116244294597087333, 'allowedRoles': [], 'allowedPeople': [], 'occupants': []}, 'third': {'channelID': 1116251961457647636, 'allowedRoles': [], 'allowedPeople': [], 'occupants': []}, 'fourth': {'channelID': 1116252005804019823, 'allowedRoles': [], 'allowedPeople': [], 'occupants': []}, 'fifth': {'channelID': 1116252036254666812, 'allowedRoles': [], 'allowedPeople': [], 'occupants': 
[]}}, 'edges': {('second', 'third'): {'allowedRoles': [], 'allowedPeople': []}, ('third', 'second'): {'allowedRoles': [], 'allowedPeople': []}, ('second', 'really long name'): {'allowedRoles': [], 'allowedPeople': []}, ('really long name', 'second'): {'allowedRoles': [], 'allowedPeople': []}, ('fourth', 'third'): {'allowedRoles': [], 'allowedPeople': []}, ('third', 'fourth'): {'allowedRoles': [], 'allowedPeople': []}, ('really long name', 'fifth'): {'allowedRoles': [], 'allowedPeople': []}, ('fifth', 'really long name'): {'allowedRoles': [], 'allowedPeople': []}, ('really long name', 'third'): {'allowedRoles': [], 'allowedPeople': []}, ('third', 'really long name'): {'allowedRoles': [], 'allowedPeople': []}, ('fifth', 'fourth'): {'allowedRoles': [], 'allowedPeople': []}, ('fourth', 'fifth'): {'allowedRoles': [], 'allowedPeople': []}}}
#guildData = db.getGuild(con, 1114005940392439899)
#con.close()
graph = makeGraph(guildData)

#bytesIO = showGraph(graph)

from timeit import timeit
print(timeit(lambda: db.gd(1114005940392439899), number = 1))