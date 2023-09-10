
#Messages
def updateMessage(con, locationChannelID: int, title: str = '', description: str = '', footer: str = ''):
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



