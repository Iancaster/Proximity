

#Import-ant Libraries
from discord import ApplicationContext, Interaction, Embed, \
    Member, Option, ButtonStyle, RawMemberRemoveEvent, Bot
from discord.ui import Button
from discord.utils import get, get_or_fetch
from discord.ext import commands
from discord.commands import SlashCommandGroup

from libraries.classes import GuildData, DialogueView, ChannelMaker, Player
from libraries.formatting import format_words, format_players
from libraries.universal import mbd, loading, no_nodes_selected, \
    no_redundancies, identify_player_id, no_changes
from data.listeners import to_direct_listeners, queue_refresh

from requests import head

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

    def __init__(self, bot: Bot):
        self.prox = bot
        return

    @player.command(name = 'new', description = 'Add a new player to the server.')
    async def new(self, ctx: ApplicationContext, player: Option(Member, description = 'Who to add?', default = None)):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def create_player(person: Member):

            nonlocal guild_data

            if person.id in guild_data.players:
                embed, _ = await mbd(
                    'Way ahead of you.',
                    f"{person.mention} is already a player.",
                    'You can review them with /player review.')
                await ctx.edit(
                    embed = embed,
                    view = None)
                return

            person = person
            valid_url = False

            async def refresh_embed():

                nonlocal guild_data, person, valid_url

                description = f'• Player: {person.mention}'
                if view.nodes():
                    node_name = view.nodes()[0]
                    node = guild_data.nodes[node_name]
                    description += f"\n• Location: {node.mention}"
                else:
                    description += '\n• Location: Nowhere set yet! Use the' + \
                        ' dropdown menu to choose where this player will start.'

                description += '\n• Character name: '
                description += f'*{await view.name()}*' if await view.name() else 'Not set yet.' + \
                    " You can choose how this player's messages appears to others."

                if view.url():
                    try:
                        response = head(view.url())
                        if response.headers["content-type"] in {"image/png", "image/jpeg", "image/jpg"}:
                            description += '\n\nSetting a new character avatar.'
                            avatar_display = (view.url(), 'thumb')
                            valid_url = True
                        else:
                            description += '\n\n**Error,** Character avatars have to be a still image.'
                            avatar_display = ('bad_link.png', 'thumb')
                            valid_url = False


                    except:
                        description += '\n\n**Error,** The avatar URL you provided is broken.'
                        avatar_display = ('bad_link.png', 'thumb')
                        valid_url = False

                else:
                    try:
                        avatar_display = (person.display_avatar.url, 'thumb')
                    except:
                        avatar_display = None

                    description += "\n\nChoose an avatar for this character's" + \
                        " proxy by uploading a picture URL. It's better for it to be" + \
                        " a permanent one like Imgur, but it can be URL, really."


                embed, file = await mbd(
                    'New player?',
                    description,
                    "You can set their character info now, or do it" + \
                        " later with /player review.",
                    avatar_display)
                return embed, file

            async def refresh_message(interaction: Interaction):
                embed, file = await refresh_embed()
                await interaction.response.edit_message(embed = embed, file = file)
                return

            async def submit_player(interaction: Interaction):

                nonlocal guild_data, person, valid_url

                await loading(interaction)

                if not view.nodes():
                    await no_nodes_selected(interaction, singular = True)
                    return

                node_name = view.nodes()[0]

                #Inform player
                maker = ChannelMaker(interaction.guild, 'players')
                await maker.initialize()
                player_channel = await maker.create_channel(person.name, person)

                embed, _ = await mbd(
                    'Welcome.',
                    f"This is your very own channel, {person.mention}." + \
                    "\n• Speak to others by just talking in this chat. Anyone who can hear you" + \
                        " will see your messages pop up in their own player channel." + \
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

                if await view.name():
                    player_data.name = character_name = await view.name()
                else:
                    character_name = person.display_name

                if view.url() and valid_url:
                    player_data.avatar = character_avatar = view.url()
                else:
                    try:
                        character_avatar = person.display_avatar.url
                    except:
                        character_avatar = None

                await player_data.save()

                webhook = (await player_channel.webhooks())[0]
                character_message = "By the way, this is how your messages " + \
                        " will appear to the other players. You can have" + \
                        " admins change your character's name or profile" + \
                        " picture by asking them to do `/player review`."
                if character_avatar:
                    await webhook.send(
                        character_message,
                        username = character_name,
                        avatar_url = character_avatar)
                    avatar_display = (character_avatar, 'thumb')
                else:
                    await webhook.send(
                        character_message,
                        username = character_name)
                    avatar_display = None


                #Inform the node occupants
                node = guild_data.nodes[node_name]
                person_formatted = await format_players({person.id})
                player_embed, _ = await mbd(
                    'Someone new.',
                    f"{person_formatted} is here.",
                    'Perhaps you should greet them.',
                        avatar_display)
                await to_direct_listeners(
                    player_embed,
                    interaction.guild,
                    node.channel_ID,
                    occupants_only = True)

                #Add the players to the guild nodes as occupants
                await node.add_occupants({person.id})
                guild_data.players.add(person.id)
                await guild_data.save()

                #Inform admins node
                description = f"• Added {person.mention} as a player. " + \
                        f"\n• They're starting at {node.mention}."
                if await view.name() == character_name:
                    description +=  "\n• Messages are being sent under" + \
                        f" the name *{character_name}*."
                if avatar_display:
                    description += "\n• Messages are sent with the avatar" + \
                        " in the top right of this embed."
                embed, _ = await mbd(
                    'Say hello.',
                    description,
                    'You can view all players and where they are with /player find.',
                    avatar_display)
                node_channel = get(interaction.guild.text_channels, id = node.channel_ID)
                await node_channel.send(embed = embed)

                await queue_refresh(interaction.guild)

                return await no_redundancies(
                    (interaction.channel.name == node_name),
                    embed,
                    interaction)

            view = DialogueView(ctx.guild)
            await view.add_nodes(guild_data.nodes.keys(), refresh_message, False)
            await view.add_submit(submit_player)
            await view.add_rename(bypass_formatting = True, callback = refresh_message)
            await view.add_URL(callback = refresh_message)
            await view.add_cancel()
            embed, file = await refresh_embed()
            await ctx.respond(embed = embed, file = file, view = view, ephemeral = True)
            return

        if player:
            await create_player(player)
            return

        embed, _ = await mbd(
            'New player?',
            "You can create a player two ways:" + \
                "\n• Do `/player new @player`." + \
                "\n• Select a player from the list below.",
            "You can set their details and submit on the next step after this.")

        async def submit_person(interaction: Interaction):
            await ctx.delete()
            await create_player(list(view.people())[0])
            return

        view = DialogueView(guild = ctx.guild)
        await view.add_people(1, submit_person)
        await view.add_cancel()
        await ctx.respond(embed = embed, view = view)

        return

    @player.command(name = 'delete', description = 'Remove a player from the game (but not the server).')
    async def delete(self, ctx: ApplicationContext, player: Option(Member, description = 'Who to remove?', default = None)):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def delete_players(deleting_player_IDs: set):

            player_mentions = await format_players(deleting_player_IDs)
            description = f'Remove {player_mentions} from the game?' + \
                "\n\n For deleted players, this command will:" + \
                "\n• Delete their player channel.\n• Remove them as" + \
                " occupants in the location they're in.\n• Remove their" + \
                " ability to play, returning them to the state they were" + \
                " in before they were added as a player." + \
                "\n\nIt will **not**:\n• Kick or ban them from the server." + \
                "\n• Delete their messages.\n• Keep them from using the" + \
                " bot in other servers."

            embed, _ = await mbd(
                f'Delete {len(deleting_player_IDs)} player(s)?',
                description,
                "This is mostly reversible.")

            async def confirm_delete(interaction: Interaction):

                await interaction.response.defer()

                nonlocal deleting_player_IDs

                guild_data.players -= set(deleting_player_IDs)

                await guild_data.save() #to appease the on_channel_delete listener

                vacating_nodes = {}
                for ID in deleting_player_IDs:

                    player_data = Player(ID, ctx.guild_id)
                    occupied_node = guild_data.nodes[player_data.location]

                    await occupied_node.remove_occupants({ID})

                    vacating_nodes.setdefault(occupied_node.channel_ID, [])
                    vacating_nodes[occupied_node.channel_ID].append(ID)

                    player_channel = get(interaction.guild.text_channels, id = player_data.channel_ID)
                    if player_channel:
                        await player_channel.delete()

                    #Delete their data
                    await player_data.delete()

                await guild_data.save()
                await queue_refresh(interaction.guild)

                for channel_ID, deleted_occupants in vacating_nodes.items():

                    deleted_mentions = await format_players(deleted_occupants)

                    player_embed, _ = await mbd(
                        'Where did they go?',
                        f"You look around, but {deleted_mentions} seems" + \
                            " to have vanished into thin air.",
                        "You get the impression you won't be seeing them again.")
                    await to_direct_listeners(
                        player_embed,
                        interaction.guild,
                        occupied_node.channel_ID,
                        occupants_only = True)

                    embed, _ = await mbd(
                        'Fewer players.',
                        f'Removed {deleted_mentions} from the game (and this node).',
                        'You can view all remaining players with /player find.')
                    node_channel = get(interaction.guild.text_channels, id = channel_ID)
                    await node_channel.send(embed = embed)

                deleting_mentions = await format_players(deleting_player_IDs)
                description = f"Successfully removed {deleting_mentions} from the game."

                embed, _ = await mbd(
                    'Delete player results.',
                    description,
                    'Hasta la vista.')
                try:
                    await no_redundancies(
                        (interaction.channel_id in vacating_nodes),
                        embed,
                        interaction)
                except:
                    pass
                return

            view = DialogueView(ctx.guild)
            await view.add_confirm(confirm_delete)
            await view.add_cancel()
            await ctx.respond(embed = embed, view = view)
            return

        result = await identify_player_id(player, guild_data.players, ctx.channel.id, ctx.guild_id)
        match result:
            case _ if isinstance(result, Embed):
                await ctx.respond(embed = result)
            case _ if isinstance(result, int):
                await delete_players([result])
            case None:
                embed, _ = await mbd(
                    'Delete player(s)?',
                    "You can delete a player three ways:" + \
                        "\n• Call this command inside of a player channel." + \
                        "\n• Do `/player delete @player`." + \
                        "\n• Select multiple players with the list below.",
                    "This won't delete them, there's more details and a prompt after this.")

                async def submit_players(interaction: Interaction):
                    await ctx.delete()
                    await delete_players(view.players())
                    return

                view = DialogueView(guild = ctx.guild)
                await view.add_players(guild_data.players, callback = submit_players)
                await view.add_cancel()
                await ctx.respond(embed = embed, view = view)

        return

    @player.command(name = 'review', description = 'Review player data.')
    async def review(self, ctx: ApplicationContext, player: Option(Member, description = 'Who to review?', default = None)):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def review_player(player_ID: int):

            player_data = Player(player_ID, ctx.guild_id)

            intro = f'• Mention: <@{player_ID}>'
            if player_data.name:
                intro += f'\n• Character Name: {player_data.name}'

            location_node = guild_data.nodes[player_data.location]
            description = f'\n• Location: {location_node.mention}'
            description += f'\n• Player Channel: <#{player_data.channel_ID}>'

            valid_url = False

            if player_data.eavesdropping:
                eavesdropping_node = guild_data.nodes[player_data.eavesdropping]
                description += f'\n• Eavesdropping: {eavesdropping_node.mention}'

            async def refresh_embed(interaction: Interaction = None):

                nonlocal valid_url

                full_description = intro
                if await view.name():
                    full_description += f'\n• New Character Name: *{await view.name()}*'
                full_description += description

                if view.url():
                    try:
                        response = head(view.url())
                        if response.headers["content-type"] in {"image/png", "image/jpeg", "image/jpg"}:
                            full_description += '\n\nSetting a new character avatar.'
                            avatar_display = (view.url(), 'thumb')
                            valid_url = True
                        else:
                            full_description += '\n\n**Error,** Character avatars have to be a still image.'
                            avatar_display = ('bad_link.png', 'thumb')
                            valid_url = False

                    except:
                        full_description += '\n\n**Error,** The avatar URL you provided is broken.'
                        avatar_display = ('bad_link.png', 'thumb')
                        valid_url = False

                elif player_data.avatar:
                    avatar_display = (player_data.avatar, 'thumb')

                else:
                    try:
                        member = await get_or_fetch(ctx.guild, 'member', id = player_ID)
                        avatar_display = (member.display_avatar.url, 'thumb')
                    except:
                        avatar_display = None

                    full_description += "\n\nChoose an avatar for this character's" + \
                        " proxy by uploading a picture URL. It's better for it to be" + \
                        " a permanent one like Imgur, but it can be URL, really."

                footnotes = []
                if not player_data.name and not await view.name():
                    footnotes.append('has no character name override')
                if not player_data.eavesdropping:
                    footnotes.append("isn't eavesdropping on anyone")
                if footnotes:
                    footer = f'This user {await format_words(footnotes)}.'
                else:
                    footer = "And that's everything."

                embed, file = await mbd(
                    'Player review',
                    full_description,
                    footer,
                    avatar_display)
                return embed, file

            async def refresh_message(interaction: Interaction):
                embed, file = await refresh_embed()
                await interaction.response.edit_message(embed = embed, file = file)
                return

            async def submit_review(interaction: Interaction):

                nonlocal valid_url

                await loading(interaction)

                if not (await view.name() or view.url()):
                    await no_changes(interaction)
                    return

                description = ''
                if await view.name():
                    player_data.name = await view.name()
                    description += f'• Changed their character name to *{await view.name()}.*'

                if view.url():

                    if valid_url:
                        player_data.avatar = view.url()
                        description += '\n• Changed their character avatar.'
                    else:
                        description += "\n• Couldn't change the avatar, invalid URL."

                await player_data.save()

                player_channel = get(interaction.guild.text_channels, id = player_data.channel_ID)
                webhook = (await player_channel.webhooks())[0]
                if player_data.avatar:
                    player_avatar = player_data.avatar
                else:
                    person = await get_or_fetch(interaction.guild, 'member', player_data.id)
                    player_avatar = person.display_avatar.url
                character_message = "Good news! A host just updated your character," + \
                    " so now you'll appear like this to the other players."

                character_name = await view.name() if await view.name() else \
                    person.display_name
                if player_avatar:
                    await webhook.send(
                        character_message,
                        username = character_name,
                        avatar_url = player_avatar)
                else:
                    await webhook.send(
                        character_message,
                        username = character_name)

                embed, _ = await mbd(
                    'Review results',
                    description,
                    'Much better.')
                await interaction.followup.edit_message(
                    message_id = interaction.message.id,
                    embed = embed,
                    view = None)
                return

            view = DialogueView(ctx.guild)
            await view.add_submit(submit_review)
            existing = player_data.name if player_data.name else ''
            await view.add_rename(existing = existing, bypass_formatting = True, callback = refresh_message)
            await view.add_URL(callback = refresh_message)
            await view.add_cancel()
            embed, file = await refresh_embed()
            await ctx.respond(embed = embed, file = file, view = view, ephemeral = True)
            return

        result = await identify_player_id(player, guild_data.players, ctx.channel.id, ctx.guild_id)
        match result:
            case _ if isinstance(result, Embed):
                await ctx.respond(embed = result)
            case _ if isinstance(result, int):
                await review_player(result)
            case None:
                embed, _ = await mbd(
                    'Review player?',
                    "You can review a player three ways:" + \
                        "\n• Call this command inside of a player channel." + \
                        "\n• Do `/player review @player`." + \
                        "\n• Select a player from the list below.",
                    "This will let you change their character info.")

                async def submit_player(interaction: Interaction):
                    await ctx.delete()
                    await review_player(list(view.players())[0])
                    return

                view = DialogueView(guild = ctx.guild)
                await view.add_players(guild_data.players, True, submit_player)
                await view.add_cancel()
                await ctx.respond(embed = embed, view = view)

        return

    @player.command(name = 'find', description = 'Locate the players.')
    async def find(self, ctx: ApplicationContext, player: Option(Member, description = 'Find anyone in particular?', default = None)):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def find_players(player_IDs: iter):

            description = ''

            if len(player_IDs) == 1:

                player_ID = player_IDs[0]
                player_data = Player(player_ID, ctx.guild_id)
                occupied_node = guild_data.nodes[player_data.location]

                description += f'<@{player_ID}> is currently at ' + \
                    f'<#{occupied_node.channel_ID}>'

                other_occupants = occupied_node.occupants.difference(player_IDs)
                if other_occupants:
                    description += f', alongside {await format_players(other_occupants)}'

                else:
                    description += ' by themself.'

            else:
                for node in guild_data.nodes.values():

                    relevant_players = await format_players({ID for ID in \
                        node.occupants if ID in player_IDs})

                    if not relevant_players:
                        continue

                    description += f"\n• {relevant_players} located in \
                    <#{node.channel_ID}>."

            embed, _ = await mbd(
                'Find results',
                description,
                'Looked high and low.')
            await ctx.respond(embed = embed, ephemeral = True)
            return

        result = await identify_player_id(player, guild_data.players, ctx.channel.id, ctx.guild_id)
        match result:
            case _ if isinstance(result, Embed):
                await ctx.respond(embed = result)
            case _ if isinstance(result, int):
                await find_players([result])
            case None:
                embed, _ = await mbd(
                    'Find player(s)?',
                    "You can find a player four ways:" + \
                        "\n• Call this command inside of a player channel." + \
                        "\n• Do `/player find @player`." + \
                        "\n• Select multiple players with the list below." + \
                        "\n• View all player locations with the button below.",
                    "You'll see where all the people are after this.")

                async def submit_players(interaction: Interaction):
                    await ctx.delete()
                    await find_players(list(view.players()))
                    return

                async def submit_all(interaction: Interaction):
                    await ctx.delete()
                    await find_players(list(guild_data.players))
                    return

                view = DialogueView(guild = ctx.guild)
                await view.add_players(guild_data.players, callback = submit_players)

                view_all_button = Button(
                    label = 'Find All',
                    style = ButtonStyle.success)
                view_all_button.callback = submit_all
                view.add_item(view_all_button)

                await view.add_cancel()
                await ctx.respond(embed = embed, view = view)

        return

    @player.command(name = 'tp', description = 'Teleport people to where you want.')
    async def teleport(self, ctx: ApplicationContext, player: Option(Member, description = 'Move anyone in particular?', default = None)):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        async def teleport_players(teleporting_IDs: iter):

            async def refresh_embed():

                player_mentions = await format_players(teleporting_IDs)
                description = f'Teleport {player_mentions} to '

                if view.nodes():
                    node_name = view.nodes()[0]
                    node = guild_data.nodes[node_name]
                    description += f"{node.mention}?"
                else:
                    description += 'which node?'

                embed, _ = await mbd(
                    'Teleport player(s)?',
                    description,
                    "Just tell me where to put who.")
                return embed

            async def teleport_players(interaction: Interaction):

                await loading(interaction)

                if not view.nodes():
                    await no_nodes_selected(interaction, True)
                    return

                node_name = view.nodes()[0]
                destination_node = guild_data.nodes[node_name]

                description = ''
                teleporting_mentions = await format_players(teleporting_IDs)
                description += f"• Teleported {teleporting_mentions} to {destination_node.mention}."

                vacating_nodes = {}
                redundant_tp_IDs = set()
                for ID in list(teleporting_IDs):

                    player_data = Player(ID, ctx.guild_id)

                    old_node = guild_data.nodes[player_data.location]

                    if player_data.location == node_name:
                        redundant_tp_IDs.add(ID)
                        teleporting_IDs.discard(ID)
                        continue

                    await old_node.remove_occupants({ID})

                    vacating_nodes.setdefault(old_node.channel_ID, [])
                    vacating_nodes[old_node.channel_ID].append(ID)

                    player_data.location = node_name
                    player_data.eavesdropping = None
                    await player_data.save()

                if not teleporting_IDs:

                    embed, _ = await mbd(
                        'Teleport results.',
                        f"{teleporting_mentions}'s already at \
                            <#{destination_node.channel_ID}>.",
                        'Mission accomplished?')

                    await interaction.followup.edit_message(
                        message_id = interaction.message.id,
                        embed = embed,
                        view = None)
                    return

                #Add players to new location
                await destination_node.add_occupants(teleporting_IDs)
                await guild_data.save()

                await queue_refresh(interaction.guild)

                for channel_ID, vacating_players in vacating_nodes.items():

                    #Inform old location occupants
                    player_mentions = await format_players(vacating_players)
                    player_embed, _ = await mbd(
                        'Gone in a flash.',
                        f"{player_mentions} disappeared somewhere.",
                        "But where?")
                    await to_direct_listeners(
                        player_embed,
                        interaction.guild,
                        channel_ID,
                        occupants_only = True)

                    #Inform old node
                    embed, _ = await mbd(
                        'Teleported player(s).',
                        f"Teleported {player_mentions} to {destination_node .mention}.",
                        'You can view all players and where they are with /player find.')
                    node_channel = get(interaction.guild.text_channels, id = channel_ID)
                    await node_channel.send(embed = embed)

                #Inform new location occupants
                player_embed, _ = await mbd(
                    'Woah.',
                    f"{teleporting_mentions} appeared in **#{node_name}**.",
                    "Must have been relocated by someone else.")
                await to_direct_listeners(
                    player_embed,
                    interaction.guild,
                    destination_node.channel_ID,
                    occupants_only = True)

                #Inform new node
                embed, _ = await mbd(
                    'Teleported player(s).',
                    f"{player_mentions} got teleported here.",
                    'You can view all players and where they are with /player find.')
                node_channel = get(interaction.guild.text_channels, id = destination_node.channel_ID)
                await node_channel.send(embed = embed)

                description = f'• {player_mentions} got teleported to <#{destination_node.channel_ID}>.'
                if redundant_tp_IDs:
                    description += f'\n• {await format_players(redundant_tp_IDs)} got skipped because' + \
                        " they're already located at the destination."

                embed, _ = await mbd(
                    'Teleport results.',
                    description,
                    'Woosh.')

                await no_redundancies(
                    (interaction.channel_id in vacating_nodes or interaction.channel_id == destination_node.channel_ID),
                    embed,
                    interaction)
                return

            view = DialogueView(ctx.guild, refresh_embed)
            await view.add_nodes(guild_data.nodes.keys(), select_multiple = False)
            await view.add_submit(teleport_players)
            await view.add_cancel()
            embed = await refresh_embed()
            await ctx.respond(embed = embed, view = view, ephemeral = True)
            return

        result = await identify_player_id(player, guild_data.players, ctx.channel.id, ctx.guild_id)
        match result:
            case _ if isinstance(result, Embed):
                await ctx.respond(embed = result)
            case _ if isinstance(result, int):
                await teleport_players([result])
            case None:
                embed, _ = await mbd(
                    'Teleport player(s)?',
                    "You can teleport a player three ways:" + \
                        "\n• Call this command inside of a player channel." + \
                        "\n• Do `/player tp @player`." + \
                        "\n• Select multiple players with the list below.",
                    "You'll be able to choose the destination after.")

                async def submit_players(interaction: Interaction):
                    await ctx.delete()
                    await teleport_players(view.players())
                    return

                view = DialogueView(guild = ctx.guild)
                await view.add_players(guild_data.players, callback = submit_players)
                await view.add_cancel()
                await ctx.respond(embed = embed, view = view)

        return

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: RawMemberRemoveEvent):

        player_data = Player(payload.user.id, payload.guild_id)

        if not player_data.location:
            return

        guild_data.players.discard(deleting_player_IDs)

        await guild_data.save()

        occupied_node = guild_data.nodes[player_data.location]

        await occupied_node.remove_occupants({player_data.id})

        guild = await get_or_fetch(self.prox, 'guild', payload.guild_id)
        player_channel = await get_or_fetch(guild, 'channel', player_data.channel_ID)
        if player_channel:
            await player_channel.delete()

        #Delete their data
        await player_data.delete()
        await guild_data.save()
        if guild:
            await queue_refresh(guild)

            player_embed, _ = await mbd(
                'Where did they go?',
                f"You look around, but {payload.user.name} seems" + \
                    " to have vanished into thin air.",
                "You get the impression you won't be seeing them again.")
            await to_direct_listeners(
                player_embed,
                guild,
                occupied_node.channel_ID,
                occupants_only = True)

            embed, _ = await mbd(
                'Fewer players.',
                f'{payload.user.name} left the server (and this node).',
                'You can view all remaining players with /player find.')
            node_channel = await get_or_fetch(guild, 'channel', occupied_node.channel_ID)
            await node_channel.send(embed = embed)

        return

def setup(prox):
    prox.add_cog(PlayerCommands(prox), override = True)
