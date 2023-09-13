

#Import-ant Libraries
from discord import Bot, ApplicationContext
from discord.ext import commands
from libraries.classes import Player, GuildData, Format
from libraries.universal import embed


class guildCommands(commands.Cog):

    def __init__(self, bot: Bot):
        self.prox = bot

    @commands.slash_command(
        name = 'look',
        description = 'Look around your location.',
        guild_only = True)
    async def look(
        self,
        ctx: ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData = GuildData(ctx.guild_id)

        if ctx.author.id not in guildData.players:
            await fn.notPlayer(ctx)
            return

        player = Player(ctx.author.id, ctx.guild_id)
        node = guildData.nodes[player.location]

        description = ''

        node.occupants.discard(ctx.author.id)
        if node.occupants:
            others = await Format.characters(node.occupants, ctx.guild_id)
            description += f"There's {others} with you inside **#{player.location}**."
        else:
            description += f"You're by yourself inside **#{player.location}**. "

        ancestors = [name for name, edge in node.neighbors.items() if edge.directionality == 0]
        mutuals = [name for name, edge in node.neighbors.items() if edge.directionality == 1]
        successors = [name for name, edge in node.neighbors.items() if edge.directionality == 2]

        if ancestors:
            if len(ancestors) > 1:
                boldedNodes = await fn.boldNodes(ancestors)
                description += f" There are one-way routes from (<-) {boldedNodes}. "
            else:
                description += f" There's a one-way route from (<-) **#{ancestors[0]}**. "

        if mutuals:
            if len(mutuals) > 1:
                boldedNodes = await fn.boldNodes(mutuals)
                description += f" There's ways to {boldedNodes} from here. "
            else:
                description += f" There's a way to get to **#{mutuals[0]}** from here. "

        if successors:
            if len(successors) > 1:
                boldedNodes = await fn.boldNodes(successors)
                description += f" There are one-way routes to (->) {boldedNodes}. "
            else:
                description += f" There's a one-way route to (->) **#{successors[0]}**. "

        if not (ancestors or mutuals or successors):
            description += " There's no way in or out of here. Oh dear."

        embed, _ = await embed(
            'Looking around...',
            description,
            'You can /eavesdrop on a nearby location.')
        await ctx.respond(embed = embed)
        return

    @commands.slash_command(
        name = 'eavesdrop',
        description = 'Listen in on a nearby location.',
        guild_only = True)
    async def eavesdrop(
        self,
        ctx: ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData = GuildData(ctx.guild_id)

        if ctx.author.id not in guildData.players:
            await fn.notPlayer(ctx)
            return

        player = Player(ctx.author.id, ctx.guild_id)
        node = guildData.nodes[player.location]
        if player.eavesdropping:
            eavesNode = guildData.nodes.get(player.eavesdropping, None)
            if not eavesNode:
                player.eavesdropping = None
                await player.save()

        if player.eavesdropping:

            if eavesNode.occupants:
                occupantMentions = await Format.characters(eavesNode.occupants, ctx.guild_id)
                description = f"You're eavesdropping on {occupantMentions} in **#{player.eavesdropping}**."
            else:
                description = f"You're eavesdropping on **#{player.eavesdropping}**, but you think nobody is there."

            async def stopEavesdropping(interaction: discord.Interaction):

                await fn.waitForRefresh(interaction)

                embed, _ = await embed(
                    'Saw that.',
                    f"You notice {ctx.author.mention} play it off like they" + \
                        f" weren't just listening in on **#{player.eavesdropping}**.",
                    'Do with that what you will.')
                await postToDirects(
                    embed,
                    interaction.guild,
                    node.channelID,
                    player.channelID,
                    onlyOccs = True)

                player.eavesdropping = None
                await player.save()

                await queueRefresh(interaction.guild)

                await interaction.delete_original_response()
                embed, _ = await embed(
                    'All done.',
                    "You're minding your own business, for now.",
                    'You can always choose to eavesdrop again later.')
                playerChannel = get(interaction.guild.text_channels, id = player.channelID)
                await playerChannel.send(embed = embed)
                return

            view = DialogueView()
            await view.addEvilConfirm(callback = stopEavesdropping)
            await view.addCancel()
            embed, _ = await embed(
                'Nosy.',
                description,
                'Would you like to stop eavesdropping?')
            await ctx.respond(embed = embed, view = view)
            return

        if node.neighbors:
            neighborNodes = await guildData.filterNodes(node.neighbors.keys())

            if any(node.occupants for node in neighborNodes.values()):

                occupiedNeighbors = {name : node for name, node in neighborNodes.items() \
                    if node.occupants}
                unoccupiedNeighbors = {name for name in neighborNodes.keys() if name not \
                    in occupiedNeighbors}

                description = 'Listening closely, you think that you can hear '
                fullList = []
                for neighborName, neighborNode in occupiedNeighbors.items():
                    occupantMentions = await Format.characters(neighborNode.occupants, ctx.guild_id)
                    fullList.append(f'{occupantMentions} in **#{neighborName}**')
                description += f'{await Format.words(fullList)}. '
                if unoccupiedNeighbors:
                    boldedUnoccupied = await Format.bold(unoccupiedNeighbors)
                    description += f"You can also listen in on {boldedUnoccupied}, but it sounds like nobody is in there."
            else:
                boldedNeighbors = await Format.bold(node.neighbors.keys())
                description = f"You're able to listen in on {boldedNeighbors} from here," + \
                    " but you don't hear anyone over there. "
        else:
            description = "If there was someplace nearby, you could listen in on it, but" + \
                " there's not. Wait, does that mean you're stuck here?"

        async def refreshEmbed():

            nonlocal description

            if view.nodes():
                selectedNode = view.nodes()[0]
                description = f'Eavesdrop on **#{selectedNode}**?'
            else:
                pass

            embed, _ = await embed(
                'Eavesdrop?',
                description,
                'You can listen in on any place near you.')

            return embed

        async def submitEavesdrop(interaction: discord.Interaction):

            await fn.waitForRefresh(interaction)

            if not view.nodes():
                embed, _ = await embed(
                    'Eavesdrop where?',
                    'You have to tell me where you would like to eavesdrop.',
                    'Try calling /eavesdrop again.')
                await interaction.followup.edit_message(
                    message_id = interaction.message.id,
                    embed = embed,
                    view = None)
                return

            player.eavesdropping = view.nodes()[0]
            await player.save()

            await queueRefresh(interaction.guild)

            embed, _ = await embed(
                'Sneaky.',
                f"You notice {ctx.author.mention} start to listen in on **#{player.eavesdropping}**.",
                'Do with that what you will.')
            await postToDirects(
                embed,
                interaction.guild,
                node.channelID,
                player.channelID,
                onlyOccs = True)

            await interaction.delete_original_response()
            embed, _ = await embed(
                'Listening close...',
                f"Let's hear what's going on over there in **#{player.eavesdropping}**, shall we?",
                "Be mindful that people can see that you're doing this.")
            playerChannel = get(interaction.guild.text_channels, id = player.channelID)
            await playerChannel.send(embed = embed)
            return

        view = DialogueView(refresh = refreshEmbed)
        await view.addUserNodes(node.neighbors.keys())
        if node.neighbors:
            await view.addSubmit(submitEavesdrop)
            await view.addCancel()
            embed = await refreshEmbed()
            await ctx.respond(embed = embed, view = view)
        else:
            embed = await refreshEmbed()
            await ctx.respond(embed = embed)
        return

    @commands.slash_command(
        name = 'map',
        description = 'See where you can go.',
        guild_only = True)
    async def map(
        self,
        ctx: ApplicationContext):

        await ctx.defer(ephemeral = True)

        guildData = GuildData(ctx.guild_id)

        if ctx.author.id not in guildData.players:
            await fn.notPlayer(ctx)
            return

        player = Player(ctx.author.id, ctx.guild_id)
        playerRoleIDs = [role.id for role in ctx.author.roles]

        graph = await guildData.filterMap(
            playerRoleIDs,
            ctx.author.id,
            player.location)
        map = await guildData.toMap(graph)

        embed, file = await embed(
            'Map',
            f"Here are all the places you can reach from **#{player.location}**." + \
                " You can travel along the arrows that point to where you want to go. ",
            "Use /move to go there.",
            (map, 'full'))

        await ctx.respond(embed = embed, file = file)
        return

    @commands.slash_command(
        name = 'move',
        description = 'Go someplace new.',
        guild_only = True)
    async def move(
        self,
        ctx: ApplicationContext,
        node: discord.Option(
            str,
            description = "Name where you would like to go?",
            autocomplete = Auto.map,
            required = False)):

        await ctx.defer(ephemeral = True)

        guildData = GuildData(ctx.guild_id)

        if ctx.author.id not in guildData.players:
            await fn.notPlayer(ctx)
            return

        player = Player(ctx.author.id, ctx.guild_id)

        playerRoleIDs = [role.id for role in ctx.author.roles]
        map = await guildData.filterMap(
            playerRoleIDs,
            ctx.author.id,
            player.location)

        description = f"Move from **#{player.location}**"

        destinationName = node if node and node != player.location else None

        async def refreshEmbed():

            fullDescription = description

            nonlocal destinationName

            if view.nodes():
                destinationName = view.nodes()[0]

            if destinationName:
                fullDescription += f' to **#{destinationName}**?'
            else:
                fullDescription += '? Where would you like to go?'

            embed, _ = await embed(
                'Move?',
                fullDescription,
                "Bear in mind that others will notice.")
            return embed

        async def submitDestination(interaction: discord.Interaction):

            await fn.waitForRefresh(interaction)

            path = nx.shortest_path(map,
                source = player.location,
                target = destinationName)

            pathAdjs = await guildData.neighbors(set(path), exclusive = True)
            nonPathAdjNodes = await guildData.filterNodes(pathAdjs)
            nearbyOccs = await guildData.getUnifiedOccupants(nonPathAdjNodes.values())

            for occID in nearbyOccs:
                eavesPlayer = Player(occID, ctx.guild_id)
                if eavesPlayer.location in path:
                    continue
                if eavesPlayer.eavesdropping in path:
                    whichPart = path.index(eavesPlayer.eavesdropping)
                    eavesChannel = get(interaction.guild.text_channels, id = eavesPlayer.channelID)

                    match whichPart:

                        case 0:
                            embed, _ = await embed(
                                'Someone got moving.',
                                f"You can hear someone in **#{path[whichPart]}** start" + \
                                    f" to go towards **#{path[whichPart + 1]}**.",
                                'Who could it be?')
                            await eavesChannel.send(embed = embed)

                        case _ if whichPart < len(path):
                            embed, _ = await embed(
                                'Someone passed through.',
                                f"You can hear someone go through **#{path[whichPart]}**,\
                                from **#{path[whichPart - 1]}** to **#{path[whichPart + 1]}**.",
                                'On the move.')
                            await eavesChannel.send(embed = embed)

                        case _ if whichPart == len(path) - 1:
                            embed, _ = await embed(
                                'Someone stopped by.',
                                f"You can hear someone come from **#{path[whichPart - 1]}**" +
                                    f" and stop at **#{path[whichPart + 1]}**.",
                                'Wonder why they chose here.')
                            await eavesChannel.send(embed = embed)

            #Inform origin occupants
            authorName = await Format.characters(list(ctx.author.id), interaction.guild.id)
            embed, _ = await embed(
                'Departing.',
                f"You notice {authorName} leave, heading towards **#{path[1]}**.",
                'Maybe you can follow them?')
            await postToDirects(
                embed,
                interaction.guild,
                guildData.nodes[path[0]].channelID,
                player.channelID,
                onlyOccs = True)

            nodeChannel = get(
                interaction.guild.text_channels,
                id = guildData.nodes[path[0]].channelID)
            embed, _ = await embed(
                'Departing.',
                f"{interaction.user.mention} left here to go to **#{path[-1]}**.",
                f"They went from {' -> '.join(path)}.")
            await nodeChannel.send(embed = embed)

            #Inform destination occupants
            embed, _ = await embed(
                'Arrived.',
                f"You notice {authorName} arrive from the direction of **#{path[-2]}**.",
                'Say hello.')
            await postToDirects(embed,
                interaction.guild,
                guildData.nodes[path[-1]].channelID,
                player.channelID,
                onlyOccs = True)

            nodeChannel = get(
                interaction.guild.text_channels,
                id = guildData.nodes[path[-1]].channelID)
            embed, _ = await embed(
                'Arriving.',
                f"{authorName} arrived here from **#{path[0]}**.",
                f"They went from {' -> '.join(path)}.")
            await nodeChannel.send(embed = embed)

            #Inform intermediary nodes + their occupants
            for index, midwayName in enumerate(path[1:-1]):
                embed, _ = await embed(
                    'Passing through.',
                    f"You notice {authorName} come in" + \
                        f" from the direction of **#{path[index]}**" + \
                        f" before continuing on their way towards **#{path[index + 2]}**.",
                    'Like two ships in the night.')
                await postToDirects(embed,
                    interaction.guild,
                    guildData.nodes[midwayName].channelID,
                    onlyOccs = True)

                nodeChannel = get(
                    interaction.guild.text_channels,
                    id = guildData.nodes[midwayName].channelID)
                embed, _ = await embed(
                    'Transit.',
                    f"{interaction.user.mention} passed through here when traveling from" + \
                        f" **#{path[0]}>** to **#{path[-1]}**.",
                    f"They went from {' -> '.join(path)}.")
                await nodeChannel.send(embed = embed)

            pathNodes = await guildData.filterNodes(path)
            await pathNodes[path[0]].removeOccupants({player.id})

            #Calculate who they saw on the way
            fullMessage = []
            for name, node in pathNodes.items():

                if node.occupants:
                    occupantsMention = await Format.characters(node.occupants, interaction.guild.id)
                    fullMessage.append(f'{occupantsMention} in **#{name}**')

            #Inform player of who they saw and what path they took
            if fullMessage:
                description = 'Along the way, you saw (and were seen' + \
                    f" by) {await Format.words(fullMessage)}."
            else:
                description = "You didn't see anyone along the way."

            #Change occupants
            await pathNodes[path[-1]].addOccupants({player.id})
            await guildData.save()

            #Update location and eavesdropping
            player.location = path[-1]
            player.eavesdropping = None
            await player.save()

            await queueRefresh(interaction.guild)

            #Tell player
            embed, _ = await embed(
                'Movement',
                description,
                f"The path you traveled was {' -> '.join(path)}.")
            playerChannel = get(interaction.guild.text_channels, id = player.channelID)
            await playerChannel.send(embed = embed)
            await interaction.followup.delete_message(message_id = interaction.message.id)
            return

        view = DialogueView(refresh = refreshEmbed)
        if not destinationName:
            await view.addUserNodes(
                [node for node in map.nodes if node != player.location])
        await view.addSubmit(submitDestination)
        await view.addCancel()
        embed = await refreshEmbed()
        await ctx.respond(embed = embed, view = view)
        return


def setup(prox):

    prox.add_cog(guildCommands(prox), override = True)

