import os
import sqlite3
from sqlite3 import Error
import json
import base64
import pickle

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

def connectToPlayer():
    connection = None
    
    try:
        connection = sqlite3.connect('playerDB.db')
        return connection
        
    except Error as problem:
        print(f'Error when connecting to player database: {problem}.')
        return None

def newGuildDB():
    if os.path.isfile('guildDB.db'):
        os.remove('guildDB.db')
    
    connection = sqlite3.connect('guildDB.db')

    tables = ["""CREATE TABLE guilds
                (guildID INTEGER PRIMARY KEY,
                nodes TEXT);""",
                """CREATE TABLE messages
                (locationChannelID INTEGER PRIMARY KEY,
                title TEXT,
                description TEXT,
                footer TEXT);""",
                """CREATE TABLE playerData
                (guildID INTEGER PRIMARY KEY,
                players TEXT);""",]

    if isinstance(connection, sqlite3.Connection):
        print(f'New guild database created, version {sqlite3.version}.')
        print("Adding 'Guilds' table...")
        newTable(connection, tables[0])
        print("Adding 'Messages' table...")
        newTable(connection, tables[1])
        print("Adding 'Players' table...")
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
                serverData TEXT);"""

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

#Members
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
