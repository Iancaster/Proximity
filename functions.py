import discord
import asyncio
import databaseFunctions as db

#Dialogues
async def embed(
    title: str = 'No Title',
    description: str = 'No description.',
    footer: str = 'No footer.',
    imageDetails = None):

    embed = discord.Embed(
        title = title,
        description = description,
        color = discord.Color.from_rgb(102, 89, 69))

    embed.set_footer(text = footer)

    if imageDetails == None:
        file = None

    else:
        match imageDetails[0]:

            case 'thumb':
                file = discord.File(f'assets/imagery/{imageDetails[1]}', filename='image.png')
                embed.set_thumbnail(url='attachment://image.png')
            
            case 'full':
                file = discord.File(imageDetails[1], filename='image.png')
                embed.set_image(url='attachment://image.png')
                
            case _:
                print(f"Unrecognized file in dialogue headed with: {title}")
                file = None

    return embed, file

async def closeDialogue(interaction: discord.Interaction):

    view = discord.ui.View()
    actionRows = interaction.message.components
    for actionRow in actionRows:

        for component in actionRow.children:

            if isinstance(component, discord.Button):
                button = discord.ui.Button(
                    label = component.label,
                    style = component.style,
                    disabled = True)
                view.add_item(button)
            
            if isinstance(component, discord.ui.Select):
                button = discord.ui.Select(
                    placeholder = 'Disabled',
                    min_values = 0,
                    max_values = 0,
                    disabled = 0)
                view.add_item(button)
  
    await interaction.response.edit_message(view = view)
    return   
 
async def dialogue(
    title: str = 'No Title',
    description: str = 'No description.',
    footer: str = 'No footer.',
    callbacks: list = [],
    includeReject = False,
    imageDetails = None):

    callbacks.extend([closeDialogue, closeDialogue, closeDialogue])

    embedData, file = await embed(
        title,
        description,
        footer,
        imageDetails)

    view = discord.ui.View()
    buttonAccept = discord.ui.Button(
        label = 'Accept',
        style = discord.ButtonStyle.success)
    buttonAccept.callback = callbacks[0]  
    view.add_item(buttonAccept)
    if includeReject:
        buttonReject = discord.ui.Button(
            label = 'Reject',
            style = discord.ButtonStyle.danger)
        buttonReject.callback = callbacks[1]
        view.add_item(buttonReject)
    buttonCancel = discord.ui.Button(
        label = 'Cancel',
        style = discord.ButtonStyle.secondary)
    buttonCancel.callback = callbacks[2]
    view.add_item(buttonCancel)

    return embedData, file, view

async def nullResponse(interaction: discord.Interaction) -> 'nothing_lol':

    await interaction.response.defer()

    return #get fucked lmao

async def initWhitelist(
    maxRoles: int,
    maxPeople: int):

    addRole = discord.ui.Select(
        placeholder = 'Allow only certain roles?',
        select_type = discord.ComponentType.role_select,
        min_values = 0,
        max_values = maxRoles)
    
    addPerson = discord.ui.Select(
        placeholder = 'Allow only certain people?',
        select_type = discord.ComponentType.user_select,
        min_values = 0,
        max_values = maxPeople)
    
    submit = discord.ui.Button(
        label = 'Submit',
        style = discord.ButtonStyle.success)
    
    return addRole, addPerson, submit

async def refineWhitelist(
    addRole,
    addPerson,
    submit,
    callbacks: list = []) -> 'view':

    callbacks.extend([nullResponse, nullResponse, nullResponse])
    view = discord.ui.View()

    addRole.callback = callbacks[0]
    view.add_item(addRole)
    
    addPerson.callback = callbacks[1]
    view.add_item(addPerson)

    submit.callback = callbacks[2]
    view.add_item(submit)

    return view

#Formatting
async def listWords(words: list):

    passage = ''
    wordCount = len(words)

    for index, word in enumerate(words):

        if index < wordCount - 1 and wordCount > 2:
            passage += f'{word}, '
        
        elif index < wordCount - 1 and wordCount <= 2:
            passage += f'{word} '
        elif index == wordCount - 1 and wordCount > 1:
            passage += f'and {word}'
        else:
            passage += word

    return passage

async def formatWhitelist(allowedRoles: list = [], allowedPeople: list = []):

    if allowedRoles and not allowedPeople:
        return f'Only people with these roles are allowed into this node: ({await listWords(allowedRoles)}).'

    elif allowedPeople and not allowedRoles:
        return f'Only these people are allowed into this node: ({await listWords(allowedPeople)}).'

    if allowedRoles:
        rolesDescription = f'any of these roles: ({await listWords(allowedRoles)})'
    else:
        rolesDescription = 'any role'

    if allowedPeople:
        peopleDescription = f'any of these people: ({await listWords(allowedPeople)})'
    else:
        peopleDescription = 'everyone else'

    description = f'People with {rolesDescription} will be allowed to come here,\
        as well as {peopleDescription}.'
    if not allowedPeople:
        description = 'Everyone will be allowed to travel to/through this node.'

    return description

async def formatNodeName(rawName: str):

    sanitizedName = ''
    lowerName = rawName.lower()
    spacelessName = lowerName.replace(' ', '-')

    sanitizedName = ''.join(character for character in spacelessName if character.isalnum())

    return sanitizedName

#Graph
async def newNode(name: str, channelID: int, allowedRoles: list = [], allowedPeople: list = [], occupants: list = []):
    
    node = {name : 
                {'channelID' : channelID,
                'allowedRoles' : allowedRoles,
                'allowedPeople' : allowedPeople,
                'occupants' : occupants}}
    
    return node
