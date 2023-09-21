#
#
# #Import-ant Libraries
from discord.ext import commands
#
# #Classes
class PlayerCommands(commands.Cog): #Create a listener to delete players when they leave the server
    """
    Commands for managing players.
    Not to be confused with commands
    used BY players. That's in guild.py.
    """
    pass
#
#     def __init__(self, bot: discord.Bot):
#         self.prox = bot
#
#     player = SlashCommandGroup(
#         name = 'player',
#         description = "Manage players.",
#         guild_only = True)
#
#     @player.command(
#         name = 'new',
#         description = 'Add a new player to the server.')
#     async def new(
#         self,
#         ctx: ApplicationContext):
#
#         await ctx.defer(ephemeral = True)
#
#         guildData = GuildData(ctx.guild_id)
#
#         async def refresh_embed():
#
#             if view.people():
#                 playerMentions = [person.mention for person in view.people()]
#                 description = f'Add {await format_words(playerMentions)} to '
#             else:
#                 description = 'Add who as a new player to '
#
#             if view.nodes():
#                 nodeName = view.nodes()[0]
#                 node = guildData.nodes[nodeName]
#                 description += f"{node.mention}?"
#             else:
#                 description += 'which node?'
#
#             embed, _ = await mbd(
#                 'New players?',
#                 description,
#                 "Just tell me where to put who.")
#             return embed
#
#         async def submitPlayers(interaction: Interaction):
#
#             nonlocal guildData
#
#             await loading(interaction)
#
#             newPlayers = [person for person in view.people() \
#                 if person.id not in guildData.players]
#
#             if not view.nodes():
#                 await no_nodes_selected(interaction, singular = True)
#                 return
#
#             if not view.people():
#                 await fn.noPeople(interaction)
#                 return
#
#             nodeName = view.nodes()[0]
#
#             maker = ChannelMaker(interaction.guild, 'players')
#             await maker.initialize()
#             for person in newPlayers:
#
#                 newChannel = await maker.newChannel(person.name, person)
#                 embed, _ = await mbd(
#                     f'Welcome.',
#                     f"This is your very own channel, {person.mention}." + \
#                     "\n• Speak to others by just talking in this chat. Anyone who can hear you" + \
#                         "will see your messages pop up in their own player channel." + \
#                     f"\n• You can `/look` around. You're at **#{nodeName}** right now." + \
#                     "\n• Do `/map` to see the other places you can go." + \
#                     "\n• ...And `/move` to go there." + \
#                     "\n• You can`/eavesdrop` on people nearby room." + \
#                     "\n• Other people can't ever see your `/commands`.",
#                     'You can always type /help to get more help.')
#                 await newChannel.send(embed = embed)
#
#                 playerData = Player(person.id, ctx.guild_id)
#                 playerData.channel_ID = newChannel.id
#                 playerData.location = nodeName
#                 await playerData.save()
#                 guildData.players.add(person.id)
#
#             #Add the players to the guild nodes as occupants
#             player_IDs = [player.id for player in newPlayers]
#             node = guildData.nodes[nodeName]
#             await node.addOccupants(player_IDs)
#             await guildData.save()
#
#             #Inform the node occupants
#             playerMentions = await format_players(player_IDs)
#             player_embed, _ = await mbd(
#                 'Someone new.',
#                 f"{playerMentions} is here.",
#                 'Perhaps you should greet them.')
#             await to_direct_listeners(
#                 player_embed,
#                 interaction.guild,
#                 node.channel_ID,
#                 occupants_only = True)
#
#             #Inform own node
#             embed, _ = await mbd(
#                 'New player(s).',
#                 f'Added {playerMentions} to this node to begin their journey.',
#                 'You can view all players and where they are with /player find.')
#             node_channel = get(interaction.guild.text_channels, id = node.channel_ID)
#             await node_channel.send(embed = embed)
#
#             await queue_refresh(interaction.guild)
#
#             description = f"Successfully added {playerMentions} to this server," + \
#                     f" starting their journey at {node.mention}."
#
#             existingPlayers = len(view.people()) - len(newPlayers)
#             if existingPlayers:
#                 description += f"\n\nYou provided {existingPlayers} person(s) that are already in," + \
#                     " so they got skipped. They're all players now, either way."
#
#             embed, _ = await mbd(
#                 'New player results.',
#                 description,
#                 'The more the merrier.')
#             if interaction.channel.name == nodeName:
#                 await ctx.delete()
#             else:
#                 await ctx.edit(
#                     embed = embed,
#                     view = None)
#             return
#
#         view = (ctx.guild, refresh_embed)
#         await view.addPeople()
#         await view.add_nodes(guildData.nodes.keys(), manyNodes = False)
#         await view.add_submit(submitPlayers)
#         await view.add_cancel()
#         embed = await refresh_embed()
#         await ctx.respond(embed = embed, view = view)
#         return
#
#     @player.command(
#         name = 'delete',
#         description = 'Remove a player from the game (but not the server).')
#     async def delete(
#         self,
#         ctx: ApplicationContext):
#
#         await ctx.defer(ephemeral = True)
#
#         guildData = GuildData(ctx.guild_id)
#
#         async def refresh_embed():
#
#             if view.players():
#                 playerMentions = await format_players(view.players())
#                 description = f'Remove {playerMentions} from the game?'
#             else:
#                 description = "For all the players you list, this command will:" + \
#                 "\n• Delete their player channel.\n• Remove them as occupants in" + \
#                 " the location they're in.\n• Remove their ability to play, returning" + \
#                 " them to the state they were in before they were added as a player." + \
#                 "\n\nIt will not:\n• Kick or ban them from the server.\n• Delete their" + \
#                 " messages.\n• Keep them from using the bot in other servers."
#
#             embed, _ = await mbd(
#                 'Delete player(s)?',
#                 description,
#                 "This won't remove them from the server.")
#             return embed
#
#         async def deletePlayers(interaction: Interaction):
#
#             await interaction.response.defer()
#
#             deletingIDs = set(int(ID) for ID in view.players() if ID in guildData.players)
#
#             if not deletingIDs:
#                 await fn.noPeople(interaction)
#                 return
#
#             leavingNodes = {}
#             for ID in deletingIDs:
#
#                 playerData = Player(ID, ctx.guild_id)
#
#                 occupiedNode = guildData.nodes[playerData.location]
#
#                 await occupiedNode.removeOccupants({ID})
#
#                 playerMention = f'<@{ID}>'
#                 playerEmbed, _ = await mbd(
#                     'Where did they go?',
#                     f"You look around, but {playerMention} seems to have vanished into thin air.",
#                     "You get the impression you won't be seeing them again.")
#                 await to_direct_listeners(
#                     playerEmbed,
#                     interaction.guild,
#                     occupiedNode.channel_ID,
#                     occupants_only = True)
#
#                 leavingNodes.setdefault(occupiedNode.channel_ID, [])
#                 leavingNodes[occupiedNode.channel_ID].append(ID)
#
#                 playerChannel = get(interaction.guild.text_channels, id = playerData.channel_ID)
#                 if playerChannel:
#                     await playerChannel.delete()
#
#                 #Delete their data
#                 await playerData.delete()
#
#                 #Remove them from server player list
#                 guildData.players.discard(ID)
#
#             await guildData.save()
#
#             for channel_ID, player_IDs in leavingNodes.items():
#                 deletedMentions = await format_players(player_IDs)
#                 embed, _ = await mbd(
#                     'Fewer players.',
#                     f'Removed {deletedMentions} from the game (and this node).',
#                     'You can view all remaining players with /player find.')
#                 node_channel = get(interaction.guild.text_channels, id = channel_ID)
#                 await node_channel.send(embed = embed)
#
#             await queue_refresh(interaction.guild)
#
#             deletingMentions = await format_players(deletingIDs)
#             description = f"Successfully removed {deletingMentions} from the game."
#
#             embed, _ = await mbd(
#                 'Delete player results.',
#                 description,
#                 'Hasta la vista.')
#             try:
#                 await fn.noCopies(
#                     (interaction.channel_id in leavingNodes),
#                     embed,
#                     interaction)
#             except:
#                 pass
#             return
#
#         view = (ctx.guild, refresh_embed)
#         await view.add_players(guildData.players)
#         await view.addEvilConfirm(deletePlayers)
#         await view.add_cancel()
#         embed = await refresh_embed()
#         await ctx.respond(embed = embed, view = view)
#         return
#
#     @player.command(
#         name = 'review',
#         description = 'Review player data.')
#     async def review(
#         self,
#         ctx: ApplicationContext,
#         player: Option(
#             discord.Member,
#             'Who to review?',
#             default = None)):
#
#         await ctx.defer(ephemeral = True)
#
#         guildData = GuildData(ctx.guild_id)
#
#         async def reviewPlayer(player_ID: int):
#
#             playerData = Player(player_ID, ctx.guild_id)
#
#             intro = f'• Mention: <@{player_ID}>'
#             if playerData.name:
#                 intro += f'\n• Character Name: {playerData.name}'
#
#             locationNode = guildData.nodes[playerData.location]
#             description = f'\n• Location: {locationNode.mention}'
#             description += f'\n• Player Channel: <#{playerData.channel_ID}>'
#
#             if playerData.eavesdropping:
#                 eavesNode = guildData.nodes[playerData.eavesdropping]
#                 description += f'\n• Eavesdropping: {eavesNode.mention}'
#
#             async def refresh_embed(interaction: Interaction = None):
#
#                 fullDescription = intro
#                 if view.name():
#                     fullDescription += f'\n• New Character Name: *{view.name()}*'
#                 fullDescription += description
#
#                 if view.url():
#                     try:
#                         response = requests.head(view.url())
#                         if response.headers["content-type"] in {"image/png", "image/jpeg", "image/jpg"}:
#                             fullDescription += '\n\nSetting a new character avatar.'
#                             avatarDisplay = (view.url(), 'thumb')
#                         else:
#                             fullDescription += '\n\nCharacter avatars have to be a still image.'
#                             avatarDisplay = ('assets/badLink.png', 'thumb')
#                     except:
#                         fullDescription += '\n\nThe avatar URL you provided is broken.'
#                         avatarDisplay = ('assets/badLink.png', 'thumb')
#                 elif playerData.avatar:
#                     avatarDisplay = (playerData.avatar, 'thumb')
#                 else:
#
#                     try:
#                         member = await get_or_fetch(ctx.guild, 'member', id = player_ID)
#                         avatarDisplay = (member.display_avatar.url, 'thumb')
#                     except:
#                         avatarDisplay = None
#
#                     fullDescription += "\n\nChoose an avatar for this character's" + \
#                         " proxy by uploading a file URL. Do `/player review avatar:(URL)`." + \
#                         " You'll want it to be a permanent URL like Imgur."
#
#                 noData = []
#                 if not playerData.name and not view.name():
#                     noData.append('has no character name override')
#                 if not playerData.eavesdropping:
#                     noData.append("isn't eavesdropping on anyone")
#                 if noData:
#                     footer = f'This user {await format_words(noData)}.'
#                 else:
#                     footer = "And that's everything."
#
#                 embed, file = await mbd(
#                     'Player review',
#                     fullDescription,
#                     footer,
#                     avatarDisplay)
#                 return embed, file
#
#             async def refreshMessage(interaction: Interaction):
#                 embed, file = await refresh_embed()
#                 await interaction.response.edit_message(embed = embed, file = file)
#                 return
#
#             async def submitReview(interaction: Interaction):
#
#                 await loading(interaction)
#
#                 if not (view.name() or view.url()):
#                     await fn.no_changes(interaction)
#                     return
#
#                 description = ''
#                 if view.name():
#                     playerData.name = view.name()
#                     description += f'• Changed their character name to *{view.name()}.*'
#
#                 if view.url():
#                     playerData.avatar = view.url()
#                     description += f'\n• Changed their character avatar.'
#
#                 await playerData.save()
#
#                 embed, _ = await mbd(
#                     'Review results',
#                     description,
#                     'Much better.')
#                 await interaction.followup.edit_message(
#                     message_id = interaction.message.id,
#                     embed = embed,
#                     view = None)
#                 return
#
#             view = (ctx.guild)
#             await view.add_submit(submitReview)
#             existing = playerData.name if playerData.name else ''
#             await view.addName(existing = existing, skipCheck = True, callback = refreshMessage)
#             await view.addURL(callback = refreshMessage)
#             await view.add_cancel()
#             embed, file = await refresh_embed()
#             await ctx.respond(embed = embed, file = file, view = view, ephemeral = True)
#             return
#
#         if player:
#
#             if player.id in guildData.players:
#                 await reviewPlayer(player.id)
#                 return
#
#             embed, _ = await mbd(
#                 'Them?',
#                 f"But {player.mention} isn't a player in this server.",
#                 "Try someone else.")
#             await ctx.respond(embed = embed)
#             return
#
#         async def submitPlayer(interaction: Interaction):
#             await ctx.delete()
#             await reviewPlayer(list(view.players())[0])
#             return
#
#         embed, _ = await mbd(
#             'Who to review?',
#             f"Select who you'd like to review. You can also do" + \
#                 " `/player review @player-name`.",
#             "Or just choose someone below.")
#         view = (guild = ctx.guild)
#         await view.add_players(guildData.players, onlyOne = True, callback = submitPlayer)
#         await view.add_cancel()
#         await ctx.respond(embed = embed, view = view)
#         return
#
#     @player.command(
#         name = 'find',
#         description = 'Locate the players.')
#     async def find(
#         self,
#         ctx: ApplicationContext,
#         player: Option(
#             discord.Member,
#             description = 'Find anyone in particular?',
#             default = None)):
#
#         await ctx.defer(ephemeral = True)
#
#         guildData = GuildData(ctx.guild_id)
#
#         if not guildData.players:
#             embed, _ = await mbd(
#             'But nobody came.',
#             'There are no players, so nobody to locate.',
#             'Feel free to keep looking though.')
#             await ctx.respond(embed = embed)
#             return
#
#         if player:
#             if player.id in guildData.players:
#                 player_IDs = [player.id]
#             else:
#                 embed, _ = await embed(
#                     f'{player.mention}?',
#                     "But they aren't a player.",
#                     'So how could they be located?')
#                 await ctx.edit(
#                     embed = embed,
#                     view = None)
#                 return
#         else:
#             player_IDs = guildData.players
#
#         description = ''
#
#         for node in guildData.nodes.values():
#
#             occupantMentions = [f'<@{ID}>' for ID in node.occupants if ID in player_IDs]
#             if occupantMentions:
#                 description += f"\n• {node.mention}: {await format_words(occupantMentions)}."
#
#         embed, _ = await mbd(
#             'Find results',
#             description,
#             'Looked high and low.')
#         await ctx.respond(embed = embed)
#         return
#
#     @player.command(
#         name = 'tp',
#         description = 'Teleport the players.')
#     async def teleport(
#         self,
#         ctx: ApplicationContext):
#
#         await ctx.defer(ephemeral = True)
#
#         guildData = GuildData(ctx.guild_id)
#
#         async def refresh_embed():
#
#             if view.players():
#                 playerMentions = await format_players(view.players())
#                 description = f'Teleport {playerMentions} to '
#             else:
#                 description = 'Teleport who to '
#
#             if view.nodes():
#                 nodeName = view.nodes()[0]
#                 node = guildData.nodes[nodeName]
#                 description += f"{node.mention}?"
#             else:
#                 description += 'which node?'
#
#             embed, _ = await mbd(
#                 'Teleport player(s)?',
#                 description,
#                 "Just tell me where to put who.")
#             return embed
#
#         async def teleportPlayers(interaction: Interaction):
#
#             await fn.waitForRefresh(interaction)
#
#             if not view.nodes():
#                 await no_nodes_selected(interaction, True)
#                 return
#
#             if not view.players():
#                 await fn.noPeople(interaction)
#                 return
#
#             nodeName = view.nodes()[0]
#             node = guildData.nodes[nodeName]
#
#             description = ''
#             teleportingMentions = await format_players(view.players())
#             description += f"• Teleported {teleportingMentions} to {node.mention}."
#
#             exitingNodes = {}
#             for ID in view.players():
#                 ID = int(ID)
#                 playerData = Player(ID, ctx.guild_id)
#
#                 oldNode = guildData.nodes[playerData.location]
#                 await oldNode.removeOccupants({ID})
#
#                 exitingNodes.setdefault(oldNode.channel_ID, [])
#                 exitingNodes[oldNode.channel_ID].append(ID)
#
#                 playerData.location = nodeName
#                 playerData.eavesdropping = None
#                 await playerData.save()
#
#             #Add players to new location
#             await node.addOccupants({int(ID) for ID in view.players()})
#             await guildData.save()
#
#             await queue_refresh(interaction.guild)
#
#             for channel_ID, exitingPlayerIDs in exitingNodes.items():
#
#                 #Inform old location occupants
#                 playerMentions = await format_players(exitingPlayerIDs)
#                 player_embed, _ = await mbd(
#                     'Gone in a flash.',
#                     f"{playerMentions} disappeared somewhere.",
#                     "But where?")
#                 await to_direct_listeners(
#                     player_embed,
#                     interaction.guild,
#                     channel_ID,
#                     occupants_only = True)
#
#                 #Inform old node
#                 embed, _ = await mbd(
#                     'Teleported player(s).',
#                     f"Teleported {playerMentions} to {node.mention}.",
#                     'You can view all players and where they are with /player find.')
#                 node_channel = get(interaction.guild.text_channels, id = channel_ID)
#                 await node_channel.send(embed = embed)
#
#             #Inform new location occupants
#             player_embed, _ = await mbd(
#                 'Woah.',
#                 f"{teleportingMentions} appeared in **#{nodeName}**.",
#                 "Must have been relocated by someone else.")
#             await to_direct_listeners(
#                 player_embed,
#                 interaction.guild,
#                 node.channel_ID,
#                 occupants_only = True)
#
#             #Inform new node
#             embed, _ = await mbd(
#                 'Teleported player(s).',
#                 f"{playerMentions} got teleported here.",
#                 'You can view all players and where they are with /player find.')
#             node_channel = get(interaction.guild.text_channels, id = node.channel_ID)
#             await node_channel.send(embed = embed)
#
#             embed, _ = await mbd(
#                 'Teleport results.',
#                 description,
#                 'Woosh.')
#             await fn.noCopies(
#                 (interaction.channel_id in exitingNodes or interaction.channel_id == node.channel_ID),
#                 embed,
#                 interaction)
#             return
#
#         view = (ctx.guild, refresh_embed)
#         await view.add_players(guildData.players)
#         await view.add_nodes(guildData.nodes.keys(), manyNodes = False)
#         await view.add_submit(teleportPlayers)
#         await view.add_cancel()
#         embed = await refresh_embed()
#         await ctx.respond(embed = embed, view = view)
#         return
#
def setup(prox):
    prox.add_cog(PlayerCommands(prox), override = True)
