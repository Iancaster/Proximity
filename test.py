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

# nodes = dict()
# nodes.update(fn.newNode('room', 1114006080570273893))
# nodes.update(fn.newNode('nearby', 1114006028518961304))
# nodes.update(fn.newNode('distant', 1114006097670455396))

# edges = list()
# edges.extend([('room', 'nearby'),
#                  ('nearby', 'room'),
#                  ('nearby', 'distant'),
#                  ('distant', 'nearby')])

# graph = makeGraph(nodes, edges)
# nx.draw_shell(graph, with_labels=True, font_weight='bold')
# plt.show()


#neighbors = graph.neighbors('room')
#nodeInfo = graph.nodes[node]

