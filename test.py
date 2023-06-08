import networkx as nx
import matplotlib.pyplot as plt
import databaseFunctions as db

def makeGraph(guildData: dict):
    graph = nx.DiGraph(id = 0)

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

con = db.connectToGuild()
guildData = db.getGuild(con, 1114005940392439899)
con.close()
graph = makeGraph(guildData)
nx.draw_shell(graph, with_labels=True, font_weight='bold')
plt.show()


#neighbors = graph.neighbors('room')
#nodeInfo = graph.nodes[node]

