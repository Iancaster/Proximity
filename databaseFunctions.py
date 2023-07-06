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

def connectToGuild():
    connection = None
    
    try:
        connection = sqlite3.connect('guildDB.db')
        return connection
        
    except Error as problem:
        print(f'Error when connecting  to guild database: {problem}.')
        return None

def connectToPlayer():
    connection = None
    
    try:
        connection = sqlite3.connect('playerDB.db')
        return connection
        
    except Error as problem:
        print(f'Error when connecting  to player database: {problem}.')
        return None

def newGuildDB():
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
                footer TEXT);""",
                """CREATE TABLE members
                (guildID INTEGER PRIMARY KEY,
                members TEXT);""",]

    if isinstance(connection, sqlite3.Connection):
        print(f'New guild database created, version {sqlite3.version}.')
        print("Adding 'Guilds' table...")
        newTable(connection, tables[0])
        print("Adding 'Messages' table...")
        newTable(connection, tables[1])
        print("Adding 'Members' table...")
        newTable(connection, tables[2])
    
    else:
        print('New guild database failed to create. No tables made.')
    
    return connection

def newPlayerDB():
    if os.path.isfile('playerDB.db'):
        os.remove('playerDB.db')
    
    connection = connectToPlayer()

    table = """CREATE TABLE players
                (playerID integer PRIMARY KEY,
                places TEXT);"""

    if isinstance(connection, sqlite3.Connection):
        print(f'New players database created, version {sqlite3.version}.')
        print("Adding 'Players' table...")
        newTable(connection, table)
    
    else:
        print('New players database failed to create. No tables made.')
    
    return connection

def countRows(con, tableName):

    cursor = con.cursor()
    cursor.execute(f"""SELECT COUNT(*) FROM {tableName}""")
    rowCount = cursor.fetchone()[0]

    return rowCount

#Guilds
def getGuild(con, guild_id: int):

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
            'nodes' : {},
            'edges' : {}}
        return newGuild

    nodesUTF = base64.b64decode(guildData['nodes'])
    nodesJSON = nodesUTF.decode('utf-8')
    if nodesJSON:
        guildData['nodes'] = json.loads(nodesJSON)
    else:
        guildData['nodes'] = dict()

    edgesUTF = base64.b64decode(guildData['edges'])
    edgesJSON = edgesUTF.decode('utf-8')
    if edgesJSON:
        edgesJSON = json.loads(edgesJSON)
        guildData['edges'] = {}
        
        for edgeSTR, edgeData in edgesJSON.items():
            edgeName = tuple(edgeSTR.strip('()').replace("'", '').split(', '))
            guildData['edges'][edgeName] = edgeData
            
    else:
        guildData['edges'] = dict()

    return guildData
  
def updateGuild(con, guildData: dict, guild_id: int):

    cursor = con.cursor()

    nodes = guildData.get('nodes', {})
    nodesJSON = json.dumps(nodes)

    nodesUTF = nodesJSON.encode('utf-8')
    nodes64 = base64.b64encode(nodesUTF)
    cursor.execute(f"""UPDATE guilds 
                        SET nodes = ? WHERE guildID = {guild_id}""", (nodes64,))
    
    edges = guildData.get('edges', {})
    edges = {str(edgeName) : edgeData for edgeName, edgeData in edges.items()}

    edgesJSON = json.dumps(edges)
    edgesUTF = edgesJSON.encode('utf-8')
    edges64 = base64.b64encode(edgesUTF)
    cursor.execute(f"""UPDATE guilds 
                        SET edges = ? WHERE guildID = {guild_id}""", (edges64,))

    con.commit()
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

#Members
def getMembers(con, guild_id: int):

    def returnDictionary(cursor, guild):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, guild)}

    con.row_factory = returnDictionary

    cursor = con.cursor()
    cursor.execute(f"""SELECT * FROM members WHERE guildID = {guild_id}""")
    memberData = cursor.fetchone()

    if not memberData:
        cursor.execute(f"""INSERT or REPLACE INTO members(guildID, members)
                VALUES({guild_id}, '')""")
        con.commit()
        print(f'Members registered, guild ID: {guild_id}.')
        return []

    members = [int(member) for member in memberData['members'].split()]
    return members
  
def updateMembers(con, members: list, guild_id: int):

    cursor = con.cursor()

    memberData = ' '.join([str(id) for id in members])
    cursor.execute(f"""UPDATE members 
                        SET members = ? WHERE guildID = {guild_id}""", (memberData,))
            
    con.commit()
    return 
  
def deleteMembers(con, guild_id: int):
    cursor = con.cursor()

    members = getMembers(con, guild_id)        
    cursor.execute(f"""DELETE FROM members WHERE guildID = {guild_id}""")
    con.commit()
    print(f'Members removed, guild ID: {guild_id}.')
    return

#Messages
def newMessage(con, locationChannelID: int, title: str = '', description: str = '', footer: str = ''):
    cursor = con.cursor()
    cursor.execute(f"""INSERT or REPLACE INTO messages(locationChannelID, title, description, footer) 
                   VALUES('{locationChannelID}', '{title}', '{description}', '{footer}')""")
    con.commit()
    print(f'Channel message added, ID: {locationChannelID}.')
    return

def deleteMessage(con, locationChannelID: int):
    cursor = con.cursor()
    cursor.execute(f"""DELETE FROM messages WHERE locationChannelID = {locationChannelID}""")
        
    con.commit()
    print(f'Location message removed, ID: {locationChannelID}.')
    return


#Players
def getPlayer(con, playerID: int):
    
    def returnDictionary(cursor, players):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, players)}

    con.row_factory = returnDictionary
    cursor = con.cursor()
    cursor.execute(f"""SELECT * FROM players WHERE playerID = {playerID}""")
    playerData = cursor.fetchone()

    if not playerData:
        cursor.execute(f"""INSERT or REPLACE INTO players(playerID, places)
                VALUES({playerID}, zeroblob(10000))""")
        con.commit()
        print(f'Player registered, ID: {playerID}.')
        return {}

    playerUTF = base64.b64decode(playerData['places'])
    playerJSON = playerUTF.decode('utf-8')
    if playerJSON:
        playerData = json.loads(playerJSON)
    else:
        playerData = {}  
    return playerData
  
def updatePlayer(con, playerData: dict, playerID: int):

    if not playerData:
        deletePlayer(con, playerID)
        return

    cursor = con.cursor()

    dataJSON = json.dumps(playerData)
    dataUTF = dataJSON.encode('utf-8')
    data64 = base64.b64encode(dataUTF)
    cursor.execute(f"""UPDATE players 
                        SET places = ? WHERE playerID = {playerID}""", (data64,))
    con.commit()
    return

def deletePlayer(con, playerID: int):
    cursor = con.cursor()
    cursor.execute(f"""DELETE FROM players WHERE playerID = {playerID}""")
    con.commit()
    print(f'Player removed, ID: {playerID}.')
    return


#Mass actions
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

def getAllPlayers(con):
    
    def returnDictionary(cursor, guild):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, guild)}

    con.row_factory = returnDictionary
    cursor = con.cursor()
    cursor.execute("SELECT * FROM players")
    return cursor.fetchall()

#Shorthand
def gd(guild_id):

    con = connectToGuild()
    guildData = getGuild(con, guild_id)
    con.close()
    return guildData

def ml(guild_id):

    con = connectToGuild()
    memberList = getMembers(con, guild_id)
    con.close()
    return memberList

def mag(guild_id):

    con = connectToGuild()
    guildData = getGuild(con, guild_id)
    memberList = getMembers(con, guild_id)
    con.close()
    return guildData, memberList
