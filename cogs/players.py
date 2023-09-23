

#Import-ant Libraries
from discord import ApplicationContext, Interaction
from discord.utils import get
from discord.ext import commands
from discord.commands import SlashCommandGroup

from libraries.classes import GuildData, DialogueView, ChannelMaker, Player
from libraries.formatting import format_words, format_players
from libraries.universal import mbd, loading, no_nodes_selected, \
    no_people_selected, prevent_spam
from data.listeners import to_direct_listeners, queue_refresh

#Classes
class PlayerCommands(commands.Cog): #Create a listener to delete players when they leave the server
    """
    Commands for managing players.
    Not to be confused with commands
    used BY players. That's in guild.py.
    """

    player = SlashCommandGroup(
        name = 'player',
        description = "Manage players.",
        guild_only = True)

    @player.command(
        name = 'new',
        description = 'Add a new player to the server.')
    async def new(self, ctx: ApplicationContext):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def refresh_embed():

            if view.people():
                player_mentions = [person.mention for person in view.people()]
                description = f'Add {await format_words(player_mentions)} '
            else:
                description = 'Add who as a new player '

            if view.nodes():
                node_name = view.nodes()[0]
                node = guild_data.nodes[node_name]
                description += f" to {node.mention}?"
            else:
                description += ' to which node?'

            embed, _ = await mbd(
                'New players?',
                description,
                "Just tell me where to put who.")
            return embed

        async def submit_players(interaction: Interaction):

            nonlocal guild_data

            await loading(interaction)

            new_players = [person for person in view.people() \
                if person.id not in guild_data.players]

            if not view.nodes():
                await no_nodes_selected(interaction, singular = True)
                return

            if not view.people():
                await no_people_selected(interaction)
                return

            node_name = view.nodes()[0]

            maker = ChannelMaker(interaction.guild, 'players')
            await maker.initialize()
            for person in new_players:

                player_channel = await maker.create_channel(person.name, person)
                embed, _ = await mbd(
                    'Welcome.',
                    f"This is your very own channel, {person.mention}." + \
                    "\n• Speak to others by just talking in this chat. Anyone who can hear you" + \
                        "will see your messages pop up in their own player channel." + \
                    f"\n• You can `/look` around. You're at **#{node_name}** right now." + \
                    "\n• Do `/map` to see the other places you can go." + \
                    "\n• ...And `/move` to go there." + \
                    "\n• You can`/eavesdrop` on people nearby room." + \
                    "\n• Other people can't ever see your `/commands`.",
                    'You can always type /help to get more help.')
                await player_channel.send(embed = embed)

                player_data = Player(person.id, ctx.guild_id)
                player_data.channel_ID = player_channel.id
                player_data.location = node_name
                await player_data.save()
                guild_data.players.add(person.id)

            #Inform the node occupants
            node = guild_data.nodes[node_name]
            player_IDs = [player.id for player in new_players]
            player_mentions = await format_players(player_IDs)
            player_embed, _ = await mbd(
                'Someone new.',
                f"{player_mentions} is here.",
                'Perhaps you should greet them.')
            await to_direct_listeners(
                player_embed,
                interaction.guild,
                node.channel_ID,
                occupants_only = True)

            #Add the players to the guild nodes as occupants
            await node.add_occupants(player_IDs)
            await guild_data.save()

            #Inform own node
            embed, _ = await mbd(
                'New player(s).',
                f'Added {player_mentions} to this node to begin their journey.',
                'You can view all players and where they are with /player find.')
            node_channel = get(interaction.guild.text_channels, id = node.channel_ID)
            await node_channel.send(embed = embed)

            await queue_refresh(interaction.guild)

            description = f"Successfully added {player_mentions} to this server," + \
                    f" starting their journey at {node.mention}."

            existing_players = len(view.people()) - len(new_players)
            if existing_players:
                description += f"\n\nYou provided {existing_players} person(s) that are already in," + \
                    " so they got skipped. They're all players now, either way."

            embed, _ = await mbd(
                'New player results.',
                description,
                'The more the merrier.')
            if interaction.channel.name == node_name:
                await ctx.delete()
            else:
                await ctx.edit(
                    embed = embed,
                    view = None)
            return

        view = DialogueView(ctx.guild, refresh_embed)
        await view.add_people()
        await view.add_nodes(guild_data.nodes.keys(), select_multiple = False)
        await view.add_submit(submit_players)
        await view.add_cancel()
        embed = await refresh_embed()
        await ctx.respond(embed = embed, view = view)
        return

    @player.command(
        name = 'delete',
        description = 'Remove a player from the game (but not the server).')
    async def delete(
        self,
        ctx: ApplicationContext):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def refresh_embed():

            if view.players():
                player_mentions = await format_players(view.players())
                description = f'Remove {player_mentions} from the game?'
            else:
                description = "For all the players you list, this command will:" + \
                "\n• Delete their player channel.\n• Remove them as occupants in" + \
                " the location they're in.\n• Remove their ability to play, returning" + \
                " them to the state they were in before they were added as a player." + \
                "\n\nIt will not:\n• Kick or ban them from the server.\n• Delete their" + \
                " messages.\n• Keep them from using the bot in other servers."

            embed, _ = await mbd(
                'Delete player(s)?',
                description,
                "This won't remove them from the server.")
            return embed

        async def delete_players(interaction: Interaction):

            await interaction.response.defer()

            deleting_player_IDs = set(int(ID) for ID in view.players() if ID in guild_data.players)

            if not deleting_player_IDs:
                await no_people_selected(interaction)
                return

            vacating_nodes = {}
            for ID in deleting_player_IDs:

                player_data = Player(ID, ctx.guild_id)

                occupied_node = guild_data.nodes[player_data.location]

                await occupied_node.removeOccupants({ID})

                player_embed, _ = await mbd(
                    'Where did they go?',
                    f"You look around, but <@{ID}> seems to have vanished into thin air.",
                    "You get the impression you won't be seeing them again.")
                await to_direct_listeners(
                    player_embed,
                    interaction.guild,
                    occupied_node.channel_ID,
                    occupants_only = True)

                vacating_nodes.setdefault(occupied_node.channel_ID, [])
                vacating_nodes[occupied_node.channel_ID].append(ID)

                player_channel = get(interaction.guild.text_channels, id = player_data.channel_ID)
                if player_channel:
                    await player_channel.delete()

                #Delete their data
                await player_data.delete()

                #Remove them from server player list
                guild_data.players.discard(ID)

            await guild_data.save()

            for channel_ID, player_IDs in vacating_nodes.items():
                deleted_mentions = await format_players(player_IDs)
                embed, _ = await mbd(
                    'Fewer players.',
                    f'Removed {deleted_mentions} from the game (and this node).',
                    'You can view all remaining players with /player find.')
                node_channel = get(interaction.guild.text_channels, id = channel_ID)
                await node_channel.send(embed = embed)

            await queue_refresh(interaction.guild)

            deleting_mentions = await format_players(deleting_player_IDs)
            description = f"Successfully removed {deleting_mentions} from the game."

            embed, _ = await mbd(
                'Delete player results.',
                description,
                'Hasta la vista.')
            try:
                await prevent_spam(
                    (interaction.channel_id in vacating_nodes),
                    embed,
                    interaction)
            except:
                pass
            return

        view = (ctx.guild, refresh_embed)
        await view.add_players(guild_data.players)
        await view.add_confirm(delete_players)
        await view.add_cancel()
        embed = await refresh_embed()
        await ctx.respond(embed = embed, view = view)
        return

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
#         guild_data = GuildData(ctx.guild_id)
#
#         async def reviewPlayer(player_ID: int):
#
#             player_data = Player(player_ID, ctx.guild_id)
#
#             intro = f'• Mention: <@{player_ID}>'
#             if player_data.name:
#                 intro += f'\n• Character Name: {player_data.name}'
#
#             locationNode = guild_data.nodes[player_data.location]
#             description = f'\n• Location: {locationNode.mention}'
#             description += f'\n• Player Channel: <#{player_data.channel_ID}>'
#
#             if player_data.eavesdropping:
#                 eavesNode = guild_data.nodes[player_data.eavesdropping]
#                 description += f'\n• Eavesdropping: {eavesNode.mention}'
#
#             async def refresh_embed(interaction: Interaction = None):
#
#                 full_description = intro
#                 if view.name():
#                     full_description += f'\n• New Character Name: *{view.name()}*'
#                 full_description += description
#
#                 if view.url():
#                     try:
#                         response = requests.head(view.url())
#                         if response.headers["content-type"] in {"image/png", "image/jpeg", "image/jpg"}:
#                             full_description += '\n\nSetting a new character avatar.'
#                             avatarDisplay = (view.url(), 'thumb')
#                         else:
#                             full_description += '\n\nCharacter avatars have to be a still image.'
#                             avatarDisplay = ('assets/badLink.png', 'thumb')
#                     except:
#                         full_description += '\n\nThe avatar URL you provided is broken.'
#                         avatarDisplay = ('assets/badLink.png', 'thumb')
#                 elif player_data.avatar:
#                     avatarDisplay = (player_data.avatar, 'thumb')
#                 else:
#
#                     try:
#                         member = await get_or_fetch(ctx.guild, 'member', id = player_ID)
#                         avatarDisplay = (member.display_avatar.url, 'thumb')
#                     except:
#                         avatarDisplay = None
#
#                     full_description += "\n\nChoose an avatar for this character's" + \
#                         " proxy by uploading a file URL. Do `/player review avatar:(URL)`." + \
#                         " You'll want it to be a permanent URL like Imgur."
#
#                 noData = []
#                 if not player_data.name and not view.name():
#                     noData.append('has no character name override')
#                 if not player_data.eavesdropping:
#                     noData.append("isn't eavesdropping on anyone")
#                 if noData:
#                     footer = f'This user {await format_words(noData)}.'
#                 else:
#                     footer = "And that's everything."
#
#                 embed, file = await mbd(
#                     'Player review',
#                     full_description,
#                     footer,
#                     avatarDisplay)
#                 return embed, file
#
#             async def refresh_message(interaction: Interaction):
#                 embed, file = await refresh_embed()
#                 await interaction.response.edit_message(embed = embed, file = file)
#                 return
#
#             async def submitReview(interaction: Interaction):
#
#                 await loading(interaction)
#
#                 if not (view.name() or view.url()):
#                     await no_changes(interaction)
#                     return
#
#                 description = ''
#                 if view.name():
#                     player_data.name = view.name()
#                     description += f'• Changed their character name to *{view.name()}.*'
#
#                 if view.url():
#                     player_data.avatar = view.url()
#                     description += f'\n• Changed their character avatar.'
#
#                 await player_data.save()
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
#             existing = player_data.name if player_data.name else ''
#             await view.addName(existing = existing, skipCheck = True, callback = refresh_message)
#             await view.addURL(callback = refresh_message)
#             await view.add_cancel()
#             embed, file = await refresh_embed()
#             await ctx.respond(embed = embed, file = file, view = view, ephemeral = True)
#             return
#
#         if player:
#
#             if player.id in guild_data.players:
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
#         await view.add_players(guild_data.players, onlyOne = True, callback = submitPlayer)
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
#         guild_data = GuildData(ctx.guild_id)
#
#         if not guild_data.players:
#             embed, _ = await mbd(
#             'But nobody came.',
#             'There are no players, so nobody to locate.',
#             'Feel free to keep looking though.')
#             await ctx.respond(embed = embed)
#             return
#
#         if player:
#             if player.id in guild_data.players:
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
#             player_IDs = guild_data.players
#
#         description = ''
#
#         for node in guild_data.nodes.values():
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
#         guild_data = GuildData(ctx.guild_id)
#
#         async def refresh_embed():
#
#             if view.players():
#                 player_mentions = await format_players(view.players())
#                 description = f'Teleport {player_mentions} to '
#             else:
#                 description = 'Teleport who to '
#
#             if view.nodes():
#                 node_name = view.nodes()[0]
#                 node = guild_data.nodes[node_name]
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
#                 await no_people_selected(interaction)
#                 return
#
#             node_name = view.nodes()[0]
#             node = guild_data.nodes[node_name]
#
#             description = ''
#             teleportingMentions = await format_players(view.players())
#             description += f"• Teleported {teleportingMentions} to {node.mention}."
#
#             exitingNodes = {}
#             for ID in view.players():
#                 ID = int(ID)
#                 player_data = Player(ID, ctx.guild_id)
#
#                 oldNode = guild_data.nodes[player_data.location]
#                 await oldNode.removeOccupants({ID})
#
#                 exitingNodes.setdefault(oldNode.channel_ID, [])
#                 exitingNodes[oldNode.channel_ID].append(ID)
#
#                 player_data.location = node_name
#                 player_data.eavesdropping = None
#                 await player_data.save()
#
#             #Add players to new location
#             await node.add_occupants({int(ID) for ID in view.players()})
#             await guild_data.save()
#
#             await queue_refresh(interaction.guild)
#
#             for channel_ID, exitingPlayerIDs in exitingNodes.items():
#
#                 #Inform old location occupants
#                 player_mentions = await format_players(exitingPlayerIDs)
#                 player_embed, _ = await mbd(
#                     'Gone in a flash.',
#                     f"{player_mentions} disappeared somewhere.",
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
#                     f"Teleported {player_mentions} to {node.mention}.",
#                     'You can view all players and where they are with /player find.')
#                 node_channel = get(interaction.guild.text_channels, id = channel_ID)
#                 await node_channel.send(embed = embed)
#
#             #Inform new location occupants
#             player_embed, _ = await mbd(
#                 'Woah.',
#                 f"{teleportingMentions} appeared in **#{node_name}**.",
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
#                 f"{player_mentions} got teleported here.",
#                 'You can view all players and where they are with /player find.')
#             node_channel = get(interaction.guild.text_channels, id = node.channel_ID)
#             await node_channel.send(embed = embed)
#
#             embed, _ = await mbd(
#                 'Teleport results.',
#                 description,
#                 'Woosh.')
#             await prevent_spam(
#                 (interaction.channel_id in exitingNodes or interaction.channel_id == node.channel_ID),
#                 embed,
#                 interaction)
#             return
#
#         view = (ctx.guild, refresh_embed)
#         await view.add_players(guild_data.players)
#         await view.add_nodes(guild_data.nodes.keys(), select_multiple = False)
#         await view.add_submit(teleportPlayers)
#         await view.add_cancel()
#         embed = await refresh_embed()
#         await ctx.respond(embed = embed, view = view)
#         return
#
def setup(prox):
    prox.add_cog(PlayerCommands(prox), override = True)
