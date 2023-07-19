import networkx as nx
import matplotlib.pyplot as plt
import databaseFunctions as db
import io
import oopFunctions as oop

async def main():
    print('Attempting to run?')
    guildData = oop.GuildData(0)
    guildData.newNode(
        name = 'origin', 
        channelID = 5)
    guildData.newNode(
        name = 'destination', 
        channelID = 6)

    edge = oop.Edge(directionality = 1)

    guildData.setEdge('origin', 'destination', edge)

    print(guildData.edgeCount())