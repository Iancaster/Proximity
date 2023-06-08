import networkx as nx
import matplotlib.pyplot as plt

import functions as fn
import databaseFunctions as db
import sys

def makeGraph(nodes: dict, edges: list = []) -> 'completed_graph':
    graph = nx.DiGraph(id = 0)

    for nodeName, nodeData in nodes.items():
        graph.add_node(
            nodeName,
            channelID = nodeData['channelID'],
            allowedRoles = nodeData['allowedRoles'],
            allowedPeople = nodeData['allowedPeople'],
            occupants = nodeData['occupants'])
        
    graph.add_edges_from(edges)    
    return graph


guildData = {'guildID': 1114005940392439899, 'nodes': {'first': {'channelID': 1116153314950795304, 'allowedRoles': [], 'allowedPeople': [], 'occupants': []}, 'second': {'channelID': 1116153341672702022, 'allowedRoles': [], 'allowedPeople': [], 'occupants': []}}, 'edges': {('first', 'second'): {'allowedRoles': [], 'allowedPeople': []}}}

# graph = makeGraph(nodes, edges)
# nx.draw_shell(graph, with_labels=True, font_weight='bold')
# plt.show()


#neighbors = graph.neighbors('room')
#nodeInfo = graph.nodes[node]

