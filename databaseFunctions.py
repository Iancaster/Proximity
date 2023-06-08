import os
import sqlite3
from sqlite3 import Error
import json
import base64

#Internal
def newTable(connection, table):

    try:
        cursor = connection.cursor()
        cursor.execute(table)
        print('Table added to database.')
        return True

    except Error as problem:
        print(f'Error when adding table: {problem}.')
        return False

def connectToGuild() -> 'connection':
    connection = None
    
    try:
        connection = sqlite3.connect('guildDB.db')
        return connection
        
    except Error as problem:
        print(f'Error when connecting  to guild database: {problem}.')
        return None

def connectToPlayer() -> 'connection':
    connection = None
    
    try:
        connection = sqlite3.connect('playerDB.db')
        return connection
        
    except Error as problem:
        print(f'Error when connecting  to player database: {problem}.')
        return None

def newGuildDB() -> 'connection':
    if os.path.isfile('guildDB.db'):
        os.remove('guildDB.db')
    
    connection = connectToGuild()

    tables = ["""CREATE TABLE guilds
                (guildID INTEGER PRIMARY KEY,
                nodes TEXT,
                edges TEXT);""",
                """CREATE TABLE messages
                (locationChannelID INTEGER PRIMARY KEY,
                title TEXT,
                description TEXT,
                footer TEXT);"""]

    if isinstance(connection, sqlite3.Connection):
        print(f'New guild database created, version {sqlite3.version}.')
        print("Adding 'Guilds' table...")
        newTable(connection, tables[0])
        print("Adding 'Messages' table...")
        newTable(connection, tables[1])
    
    else:
        print('New guild database failed to create. No tables made.')
    
    return connection

def newPlayerDB() -> 'connection':
    if os.path.isfile('playerDB.db'):
        os.remove('playerDB.db')
    
    connection = connectToPlayer()

    table = """CREATE TABLE players
                (playerID integer PRIMARY KEY,
                channelID integer,
                location text,
                eavesdropping text);"""

    if isinstance(connection, sqlite3.Connection):
        print(f'New players database created, version {sqlite3.version}.')
        print("Adding 'Players' table...")
        newTable(connection, table)
    
    else:
        print('New players database failed to create. No tables made.')
    
    return connection

#Table membership
def newPlayer(con, playerID: int, channelID: int): 
    cursor = con.cursor()
    cursor.execute(f"""INSERT or REPLACE INTO players(playerID, channelID)
              VALUES('{playerID}', '{channelID}')""")
    con.commit()
    print(f'Player registered, ID: {playerID}.')
    return

def deleteGuild(con, guild_id: int):
    cursor = con.cursor()

    guildData = getGuild(con, guild_id)

    for nodeData in guildData['nodes'].values():
        cursor.execute(f"""DELETE FROM messages WHERE
                        locationChannelID = ?""", (nodeData['channelID'],))
        
    cursor.execute(f"""DELETE FROM guilds WHERE guildID = {guild_id}""")
    con.commit()
    print(f'Guild removed, ID: {guild_id}.')
    return

def deleteMessage(con, locationChannelID: int):
    cursor = con.cursor()
    cursor.execute(f"""DELETE FROM messages WHERE locationChannelID = {locationChannelID}""")
        
    con.commit()
    print(f'Location message removed, ID: {locationChannelID}.')
    return

def deletePlayer(con, playerID: int):
    cursor = con.cursor()
    cursor.execute(f"""DELETE FROM players WHERE playerID = {playerID}""")
    con.commit()
    print(f'Player removed, ID: {playerID}.')
    return

def eraseGuildDB(con):
    cursor = con.cursor()
    cursor.execute("""DELETE FROM guilds""")
    cursor.execute("""DELETE FROM messages""")
    con.commit()
    print('All guilds and messages removed.')
    return

def erasePlayerDB(con):
    cursor = con.cursor()
    cursor.execute("""DELETE FROM players""")
    con.commit()
    print('All players removed.')
    return

#Guild manipulation
def getGuild(con, guild_id: int) -> 'guild_data':

    def returnDictionary(cursor, guild):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, guild)}

    con.row_factory = returnDictionary
    cursor = con.cursor()
    cursor.execute(f"""SELECT * FROM guilds WHERE guildID = {guild_id}""")
    guildData = cursor.fetchone()

    if not guildData:
        cursor.execute(f"""INSERT or REPLACE INTO guilds(guildID, nodes, edges)
                VALUES({guild_id}, zeroblob(50000), zeroblob(50000))""")
        con.commit()
        print(f'Guild registered, ID: {guild_id}.')
        newGuild = {
            'guildID' : guild_id,
            'nodes' : {},
            'edges' : {}}
        return newGuild

    nodesUTF = base64.b64decode(guildData['nodes'])
    nodes = nodesUTF.decode('utf-8')
    if nodes:
        guildData['nodes'] = json.loads(nodes)
    else:
        guildData['nodes'] = dict()

    edgesUTF = base64.b64decode(guildData['edges'])
    edges = edgesUTF.decode('utf-8')
    if edges:
        edgesJSON = json.loads(edges)
        guildData['edges'] = {}
        
        for edgeSTR, edgeData in edgesJSON.items():
            edgeName = tuple(edgeSTR.strip('()').replace("'", '').split(', '))
            guildData['edges'][edgeName] = edgeData
            
    else:
        guildData['edges'] = dict()

    return guildData
  
def updateGuild(con, guildData = dict):

    cursor = con.cursor()
    guildID = guildData['guildID']

    nodes = guildData.get('nodes', {})
    nodesJSON = json.dumps(nodes)
    nodesUTF = nodesJSON.encode('utf-8')
    nodes64 = base64.b64encode(nodesUTF)
    cursor.execute(f"""UPDATE guilds 
                        SET nodes = ? WHERE guildID = {guildID}""", (nodes64,))
    
    edges = guildData.get('edges', {})
    edges = {str(edgeName) : edgeData for edgeName, edgeData in edges.items()}

    edgesJSON = json.dumps(edges)
    edgesUTF = edgesJSON.encode('utf-8')
    edges64 = base64.b64encode(edgesUTF)
    cursor.execute(f"""UPDATE guilds 
                        SET edges = ? WHERE guildID = {guildID}""", (edges64,))

    con.commit()
    return 
  
def newMessage(con, locationChannelID: int, title: str = '', description: str = '', footer: str = ''):
    cursor = con.cursor()
    cursor.execute(f"""INSERT or REPLACE INTO messages(locationChannelID, title, description, footer) 
                   VALUES('{locationChannelID}', '{title}', '{description}', '{footer}')""")
    con.commit()
    print(f'Channel message added, ID: {locationChannelID}.')
    return

def getAllGuilds(con):
    
    def returnDictionary(cursor, guild):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, guild)}

    con.row_factory = returnDictionary
    cursor = con.cursor()
    cursor.execute("SELECT * FROM guilds")
    return cursor.fetchall()

def getAllMessages(con):
    
    def returnDictionary(cursor, guild):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, guild)}

    con.row_factory = returnDictionary
    cursor = con.cursor()
    cursor.execute("SELECT * FROM messages")
    return cursor.fetchall()

#Player manipulation
def getPlayer(con, playerID: int) -> 'player_data':

    def returnDictionary(cursor, guild):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, guild)}

    con.row_factory = returnDictionary
    cursor = con.cursor()
    cursor.execute(f"""SELECT * FROM players WHERE playerID = {playerID}""")
    return cursor.fetchone()
  
def updatePlayer(con,
    playerID: int,
    channelID: int = 0,
    location: str = '',
    eavesdropping: str = ''):

    cursor = con.cursor()
    if channelID:
        cursor.execute(f"""UPDATE players
                    SET channelID = {channelID} WHERE playerID = {playerID}""")

    if location:
        cursor.execute(f"""UPDATE players
                    SET location = {location} WHERE playerID = {playerID}""")
        
    if eavesdropping:
        cursor.execute(f"""UPDATE players
                    SET eavesdropping = {eavesdropping} WHERE playerID = {playerID}""")
        
    con.commit()
    return 

def getAllPlayers(con):
    
    def returnDictionary(cursor, guild):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, guild)}

    con.row_factory = returnDictionary
    cursor = con.cursor()
    cursor.execute("SELECT * FROM players")
    return cursor.fetchall()
