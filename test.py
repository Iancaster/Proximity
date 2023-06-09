import networkx as nx
import matplotlib.pyplot as plt
import databaseFunctions as db
import io

#con = db.connectToGuild()
guildData = {'guildID': 1114005940392439899, 'nodes': {'really long name': {'channelID': 1116244275718541314, 'allowedRoles': [], 'allowedPeople': [], 'occupants': []}, 'second': {'channelID': 1116244294597087333, 'allowedRoles': [], 'allowedPeople': [], 'occupants': []}, 'third': {'channelID': 1116251961457647636, 'allowedRoles': [], 'allowedPeople': [], 'occupants': []}, 'fourth': {'channelID': 1116252005804019823, 'allowedRoles': [], 'allowedPeople': [], 'occupants': []}, 'fifth': {'channelID': 1116252036254666812, 'allowedRoles': [], 'allowedPeople': [], 'occupants': 
[]}}, 'edges': {('second', 'third'): {'allowedRoles': [], 'allowedPeople': []}, ('third', 'second'): {'allowedRoles': [], 'allowedPeople': []}, ('second', 'really long name'): {'allowedRoles': [], 'allowedPeople': []}, ('really long name', 'second'): {'allowedRoles': [], 'allowedPeople': []}, ('fourth', 'third'): {'allowedRoles': [], 'allowedPeople': []}, ('third', 'fourth'): {'allowedRoles': [], 'allowedPeople': []}, ('really long name', 'fifth'): {'allowedRoles': [], 'allowedPeople': []}, ('fifth', 'really long name'): {'allowedRoles': [], 'allowedPeople': []}, ('really long name', 'third'): {'allowedRoles': [], 'allowedPeople': []}, ('third', 'really long name'): {'allowedRoles': [], 'allowedPeople': []}, ('fifth', 'fourth'): {'allowedRoles': [], 'allowedPeople': []}, ('fourth', 'fifth'): {'allowedRoles': [], 'allowedPeople': []}}}
#guildData = db.getGuild(con, 1114005940392439899)
#con.close()
graph = makeGraph(guildData)
plt.show()

bytesIO = showGraph(graph)



#neighbors = graph.neighbors('room')
#nodeInfo = graph.nodes[node]

