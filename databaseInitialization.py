

def newTable(connection, table):

    try:
        cursor = connection.cursor()
        cursor.execute(table)
        print('Table added to database.')
        return True

    except Error as problem:
        print(f'Error when adding table: {problem}.')
        return False


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


#Erase actions
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


#Mall Get
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


#Internal
def countRows(con, tableName):

    cursor = con.cursor()
    cursor.execute(f"""SELECT COUNT(*) FROM {tableName}""")
    rowCount = cursor.fetchone()[0]

    return rowCount
