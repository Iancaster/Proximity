
#Import-ant Libraries
from discord import Embed, MISSING, File
from requests import head

#Dialogues
async def mbd(
    title: str = 'No Title',
    description: str = 'No description.',
    footer: str = 'No footer.',
    imageDetails = None):

    embed = Embed(
        title = title,
        description = description,
        color = 670869)
    embed.set_footer(text = footer)

    match imageDetails:
        
        case None:
            file = MISSING

        case _ if imageDetails[0] == None:
            file = MISSING

        case _ if imageDetails[1] == 'thumb':

            file = File('/./assets/badLink.png', filename = 'image.png')
            embed.set_thumbnail(url = 'attachment://image.png')

            try:
                response = head(imageDetails[0])
                if response.headers["content-type"] in {"image/png", "image/jpeg", "image/jpg"}:
                    embed.set_thumbnail(url = imageDetails[0])
                    file = MISSING
                else:
                    pass
            except:
                pass
        
        case _ if imageDetails[1] == 'full':
            file = File(imageDetails[0], filename = 'image.png')
            embed.set_image(url = 'attachment://image.png')
            
        case _:
            print('Unrecognized image viewing mode in dialogue!')
            file = MISSING

    return embed, file
#
# async def nullResponse(interaction: discord.Interaction):
#
#     await interaction.response.edit_message()
#     return #get fucked lmao
#
# async def addArrows(leftCallback: callable = None, rightCallback: callable = None):
#
#     view = discord.ui.View()
#
#     if leftCallback:
#         left = discord.ui.Button(
#             label = '<',
#             style = discord.ButtonStyle.secondary)
#         left.callback = leftCallback
#         view.add_item(left)
#
#     else:
#         left = discord.ui.Button(
#             label = '-',
#             style = discord.ButtonStyle.secondary,
#             disabled = True)
#         view.add_item(left)
#
#     if rightCallback:
#         right = discord.ui.Button(
#             label = '>',
#             style = discord.ButtonStyle.secondary)
#         right.callback = rightCallback
#         view.add_item(right)
#
#     else:
#         right = discord.ui.Button(
#             label = 'Done',
#             style = discord.ButtonStyle.secondary,
#             disabled = True)
#         view.add_item(right)
#
#     return view
#
# #Formatting
# async def whitelistsSimilar(components: list):
#
#     firstRoles = components[0].get('allowedRoles', [])
#     firstPeople = components[0].get('allowedPeople', [])
#     for component in components:
#
#         if firstRoles != component.get('allowedRoles', []) or firstPeople != component.get('allowedPeople', []):
#             return False
#
#     return True
#
# async def formatEdges(nodes: dict, ancestors: list, neighbors: list, successors: list):
#
#     description = ''
#     for ancestor in ancestors:
#         description += f"\n<- <#{nodes[ancestor]['channelID']}>"
#     for neighbor in neighbors:
#         description += f"\n<-> <#{nodes[neighbor]['channelID']}>"
#     for successor in successors:
#         description += f"\n-> <#{nodes[successor]['channelID']}>"
#
#     return description
#
# #Edges
# async def getConnections(graph: nx.Graph, nodes: list, split: bool = False):
#
#     successors = set()
#     ancestors = set()
#
#     for node in nodes:
#         successors = successors.union(graph.successors(node))
#         ancestors = ancestors.union(graph.predecessors(node))
#
#     if split:
#         mutuals = ancestors.intersection(successors)
#         ancestors -= mutuals
#         successors -= mutuals
#         return list(ancestors), list(mutuals), list(successors)
#
#     else:
#         neighbors = ancestors.union(successors)
#         return list(neighbors)
#
# #Guild
# async def identifyNodeChannel(
#     nodesNames: dict,
#     originChannelName: str = '',
#     namedChannelName: str = ''):
#
#     if not nodesNames:
#
#         embedData, _ = await embed(
#             'Easy, bronco.',
#             "You've got no nodes to work with.",
#             'Make some first with /node new.')
#
#         return embedData
#
#     elif namedChannelName:
#
#         if namedChannelName in nodesNames:
#             return namedChannelName
#
#         else:
#
#             embedData, _ = await embed(
#                 'What?',
#                 f"**#{namedChannelName}** isn't a node channel. Did you select the wrong one?",
#                 'Try calling the command again.')
#
#             return embedData
#
#     if originChannelName in nodesNames:
#         return originChannelName
#
#     else:
#         return None
#
# async def waitForRefresh(interaction: discord.Interaction):
#
#     embedData, _ = await embed(
#         'Moving...',
#         'Getting into position.',
#         'This will only be a moment.')
#     await interaction.response.edit_message(
#         embed = embedData,
#         view = None)
#     return
#
# async def loading(interaction: discord.Interaction):
#
#     embedData, _ = await embed(
#         'Loading...',
#         'Recalculating listeners.',
#         'Usually takes less than five seconds.')
#     await interaction.response.edit_message(
#         embed = embedData,
#         view = None,
#         attachments = [])
#     return
#
# #Checks
# async def nodeExists(node, interaction: discord.Interaction):
#     embedData, _ = await embed(
#         'Already exists.',
#         f"There's already a {node.mention}. Rename it with `/node review` or use a new name for this one.",
#         'Try calling the command again.')
#     await interaction.followup.edit_message(message_id = interaction.message.id, embed = embedData, view = None)
#     return
#
# async def noNodes(interaction: discord.Interaction, singular: bool = False):
#     if singular:
#         embedData, _ = await embed(
#             'No nodes!',
#             "Please select a valid node first.",
#             'Try calling the command again.')
#     else:
#         embedData, _ = await embed(
#             'No nodes!',
#             "You've got to select some.",
#             'Try calling the command again.')
#     await interaction.followup.edit_message(
#         message_id = interaction.message.id,
#         embed = embedData,
#         view = None,
#         attachments = [])
#     return
#
# async def noEdges(interaction: discord.Interaction):
#     embedData, _ = await embed(
#         'No edges!',
#         "You've got to select at least one.",
#         'Try calling the command again.')
#     await interaction.followup.edit_message(
#         message_id = interaction.message.id,
#         embed = embedData,
#         view = None,
#         attachments = [])
#     return
#
# async def noPeople(interaction: discord.Interaction):
#
#     embedData, _ = await embed(
#         'Who?',
#         "You didn't select any valid people.",
#         'You can call the command again and specify someone new.')
#     await interaction.followup.edit_message(
#         message_id = interaction.message.id,
#         embed = embedData,
#         view = None)
#     return
#
# async def noChanges(interaction: discord.Interaction):
#
#     embedData, _ = await embed(
#         'Success?',
#         "You didn't make any changes.",
#         "Unsure what the point of that was.")
#     await interaction.followup.edit_message(
#         message_id = interaction.message.id,
#         embed = embedData,
#         view = None,
#         attachments = [])
#     return
#
# async def hasWhitelist(components):
#
#     for component in components:
#         if component.get('allowedRoles', False) or component.get('allowedPeople', False):
#             return True
#
#     return False
#
# async def notPlayer(ctx: discord.ApplicationContext, members: list):
#
#     embedData, _ = await embed(
#         'Easy there.',
#         "You're not a player in this server, so you're not able to do this.",
#         'You can ask the server owner to make you a player?')
#     await ctx.respond(embed = embedData)
#     return
#
# async def noCopies(test, embed: Embed, interaction: discord.Interaction):
#
#     if test:
#         await interaction.delete_original_response()
#
#     else:
#         await interaction.followup.edit_message(
#             message_id = interaction.message.id,
#             embed = embed,
#             view = None)
#
#     return
#
#
