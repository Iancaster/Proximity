

#Import-ant Libraries
from discord import ApplicationContext, Option, Interaction
from discord.ext import commands
from discord.utils import get

from libraries.classes import GuildData, DialogueView, Player
from libraries.universal import mbd, moving, no_membership
from libraries.formatting import format_words, format_characters, embolden

from libraries.autocomplete import complete_map
from data.listeners import to_direct_listeners, queue_refresh

from networkx import shortest_path


#Classes
class UserCommands(commands.Cog):
    """
    Commands meant to be used by the users.
    The players, more accurately, but players.py
    is already taken by commands used for
    managing players, rather than by their
    players themselves, so, users.py.
    """

    @commands.slash_command(name = 'look', description = 'Look around your location.', guild_only = True)
    async def look(self, ctx: ApplicationContext):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        if ctx.author.id not in guild_data.players:
            await no_membership(ctx)
            return

        player = Player(ctx.author.id, ctx.guild_id)
        node = guild_data.nodes[player.location]

        description = ''

        node.occupants.discard(ctx.author.id)
        if node.occupants:
            others = await format_characters(node.occupants, ctx.guild_id)
            description += f"There's {others} with you inside **#{player.location}**."
        else:
            description += f"You're by yourself inside **#{player.location}**. "

        ancestors = [name for name, edge in node.neighbors.items() if edge.directionality == 0]
        mutuals = [name for name, edge in node.neighbors.items() if edge.directionality == 1]
        successors = [name for name, edge in node.neighbors.items() if edge.directionality == 2]

        if ancestors:
            if len(ancestors) > 1:
                bold_nodes = await embolden(ancestors)
                description += f" There are one-way routes from (<-) {bold_nodes}. "
            else:
                description += f" There's a one-way route from (<-) **#{ancestors[0]}**. "

        if mutuals:
            if len(mutuals) > 1:
                bold_nodes = await embolden(mutuals)
                description += f" There's ways to {bold_nodes} from here. "
            else:
                description += f" There's a way to get to **#{mutuals[0]}** from here. "

        if successors:
            if len(successors) > 1:
                bold_nodes = await embolden(successors)
                description += f" There are one-way routes to (->) {bold_nodes}. "
            else:
                description += f" There's a one-way route to (->) **#{successors[0]}**. "

        if not (ancestors or mutuals or successors):
            description += " There's no way in or out of here. Oh dear."

        embed, _ = await mbd(
            'Looking around...',
            description,
            'You can /eavesdrop on a nearby location.')
        await ctx.respond(embed = embed)
        return

    @commands.slash_command(name = 'eavesdrop', description = 'Listen in on a nearby location.', guild_only = True)
    async def eavesdrop(self, ctx: ApplicationContext):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        if ctx.author.id not in guild_data.players:
            await no_membership(ctx)
            return

        player = Player(ctx.author.id, ctx.guild_id)
        node = guild_data.nodes[player.location]
        if player.eavesdropping:
            eavesdropping_node = guild_data.nodes.get(player.eavesdropping, None)
            if not eavesdropping_node:
                player.eavesdropping = None
                await player.save()

        if player.eavesdropping:

            if eavesdropping_node.occupants:
                occupant_mentions = await format_characters(eavesdropping_node.occupants, ctx.guild_id)
                description = f"You're eavesdropping on {occupant_mentions} in **#{player.eavesdropping}**."
            else:
                description = f"You're eavesdropping on **#{player.eavesdropping}**, but you think nobody is there."

            async def finish_eavesdropping(interaction: Interaction):

                await moving(interaction)

                embed, _ = await mbd(
                    'Saw that.',
                    f"You notice {ctx.author.mention} play it off like they" + \
                        f" weren't just listening in on **#{player.eavesdropping}**.",
                    'Do with that what you will.')
                await to_direct_listeners(
                    embed,
                    interaction.guild,
                    node.channel_ID,
                    player.channel_ID,
                    occupants_only = True)

                player.eavesdropping = None
                await player.save()

                await queue_refresh(interaction.guild)

                await interaction.delete_original_response()
                embed, _ = await mbd(
                    'All done.',
                    "You're minding your own business, for now.",
                    'You can always choose to eavesdrop again later.')
                player_channel = get(interaction.guild.text_channels, id = player.channel_ID)
                await player_channel.send(embed = embed)
                return

            view = DialogueView()
            await view.add_confirm(callback = finish_eavesdropping)
            await view.add_cancel()
            embed, _ = await mbd(
                'Nosy.',
                description,
                'Would you like to stop eavesdropping?')
            await ctx.respond(embed = embed, view = view)
            return

        if node.neighbors:
            neighbor_nodes = await guild_data.filter_nodes(node.neighbors.keys())

            if any(node.occupants for node in neighbor_nodes.values()):

                occupied_neighbors = {name : node for name, node in neighbor_nodes.items() \
                    if node.occupants}
                unoccupied_neighbors = {name for name in neighbor_nodes.keys() if name not \
                    in occupied_neighbors}

                description = 'Listening closely, you think that you can hear '
                nearby_people = []
                for neighbor_name, neighbor_node in occupied_neighbors.items():
                    occupant_mentions = await format_characters(neighbor_node.occupants, ctx.guild_id)
                    nearby_people.append(f'{occupant_mentions} in **#{neighbor_name}**')
                description += f'{await format_words(nearby_people)}. '
                if unoccupied_neighbors:
                    boldedUnoccupied = await embolden(unoccupied_neighbors)
                    description += f"You can also listen in on {boldedUnoccupied}, but it sounds like nobody is in there."
            else:
                bolded_neighbors = await embolden(node.neighbors.keys())
                description = f"You're able to listen in on {bolded_neighbors} from here," + \
                    " but you don't hear anyone over there. "
        else:
            description = "If there was someplace nearby, you could listen in on it, but" + \
                " there's not. Wait, does that mean you're stuck here?"

        async def refresh_embed():

            nonlocal description

            if view.nodes():
                selected_node = view.nodes()[0]
                description = f'Eavesdrop on **#{selected_node}**?'
            else:
                pass

            embed, _ = await mbd(
                'Eavesdrop?',
                description,
                'You can listen in on any place near you.')

            return embed

        async def submit_eavesdrop(interaction: Interaction):

            await moving(interaction)

            if not view.nodes():
                embed, _ = await mbd(
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

            await queue_refresh(interaction.guild)

            embed, _ = await mbd(
                'Sneaky.',
                f"You notice {ctx.author.mention} start to listen in on **#{player.eavesdropping}**.",
                'Do with that what you will.')
            await to_direct_listeners(
                embed,
                interaction.guild,
                node.channel_ID,
                player.channel_ID,
                occupants_only = True)

            await interaction.delete_original_response()
            embed, _ = await mbd(
                'Listening close...',
                f"Let's hear what's going on over there in **#{player.eavesdropping}**, shall we?",
                "Be mindful that people can see that you're doing this.")
            player_channel = get(interaction.guild.text_channels, id = player.channel_ID)
            await player_channel.send(embed = embed)
            return

        view = DialogueView(refresh = refresh_embed)
        await view.add_user_nodes(node.neighbors.keys())
        if node.neighbors:
            await view.add_submit(submit_eavesdrop)
            await view.add_cancel()
            embed = await refresh_embed()
            await ctx.respond(embed = embed, view = view)
        else:
            embed = await refresh_embed()
            await ctx.respond(embed = embed)
        return

    @commands.slash_command(name = 'map', description = 'See where you can go.', guild_only = True)
    async def map(self, ctx: ApplicationContext):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        if ctx.author.id not in guild_data.players:
            await no_membership(ctx)
            return

        player = Player(ctx.author.id, ctx.guild_id)
        player_role_IDs = [role.id for role in ctx.author.roles]

        guild_graph = await guild_data.accessible_locations(
            player_role_IDs,
            ctx.author.id,
            player.location)
        guild_map = await guild_data.to_map(guild_graph)

        embed, file = await mbd(
            'Map',
            f"Here are all the places you can reach from **#{player.location}**." + \
                " You can travel along the arrows that point to where you want to go. ",
            "Use /move to go there.",
            (guild_map, 'full'))

        await ctx.respond(embed = embed, file = file)
        return

    @commands.slash_command(name = 'move', description = 'Go someplace new.', guild_only = True)
    async def move(self, ctx: ApplicationContext, destination: Option( str, "Name where you would like to go?", autocomplete = complete_map, required = False)):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        if ctx.author.id not in guild_data.players:
            await no_membership(ctx)
            return

        player_data= Player(ctx.author.id, ctx.guild_id)

        player_role_IDs = [role.id for role in ctx.author.roles]
        player_map = await guild_data.accessible_locations(
            player_role_IDs,
            ctx.author.id,
            player_data.location)

        intro = f"Move from **#{player_data.location}**"

        destination_name = destination if destination and destination != player_data.location else None

        async def refresh_embed():

            full_description = intro

            nonlocal destination_name

            if not destination_name:
                if view.nodes():
                    destination_name = view.nodes()[0]

            if destination_name:
                full_description += f' to **#{destination_name}**?'
            else:
                full_description += '? Where would you like to go?'

            embed, _ = await mbd(
                'Move?',
                full_description,
                "Bear in mind that others will notice.")
            return embed

        async def submit_destination(interaction: Interaction):

            await moving(interaction)

            path = shortest_path(player_map,
                source = player_data.location,
                target = destination_name)

            """
            Rework this. The way it NEEDS to work is that for every location
            in the path, it will query what occupants are adjacent to it,
            and then send them the message depending on what leg of the journey
            its currently in (Start, intermediary, or end). Blegh.
            """

            # nodes_along_path = await guild_data.neighbors(set(path), exclusive = True)
            # nodes_surrounding_path = await guild_data.filter_nodes(nodes_along_path)
            # player_IDs_surrounding_path = \
            #     await guild_data.get_all_occupants(nodes_surrounding_path.values())

            # for occupant_ID in player_IDs_surrounding_path:
            #     nearby_player = Player(occupant_ID, ctx.guild_id)
            #     if nearby_player.location in path:
            #         continue
            #
            #     heard_segment = path.index(nearby_player.eavesdropping)
            #     nearby_player_channel = get(interaction.guild.text_channels, id = nearby_player.channel_ID)
            #
            #     if heard_segment == 0:
            #         embed, _ = await mbd(
            #             'Someone got moving.',
            #             "You can hear someone in" + \
            #                 f" **#{path[heard_segment]}** start" + \
            #                 " to go towards" + \
            #                 f" **#{path[heard_segment + 1]}**.",
            #             'Who could it be?')
            #         await nearby_player_channel.send(embed = embed)
            #
            #     elif heard_segment == len(path) - 1:
            #         embed, _ = await mbd(
            #             'Someone stopped by.',
            #             "You can hear someone come from " + \
            #                 f" **#{path[heard_segment - 1]}**" + \
            #                 f" and stop at **#{path[heard_segment]}**.",
            #             'Wonder why they chose here.')
            #         await nearby_player_channel.send(embed = embed)
            #
            #     else:
            #
            #         embed, _ = await mbd(
            #             'Someone passed through.',
            #             "You can hear someone go through" + \
            #                 f" **#{path[heard_segment]}**," +\
            #                 f" from **#{path[heard_segment - 1]}**" + \
            #                 f" to **#{path[heard_segment]}**.",
            #             'On the move.')
            #         await nearby_player_channel.send(embed = embed)

            #Inform origin occupants
            moving_character = await format_characters([ctx.author.id], interaction.guild.id)
            embed, _ = await mbd(
                'Departing.',
                f"You notice {moving_character} leave, heading towards **#{path[1]}**.",
                'Maybe you can follow them?')
            await to_direct_listeners(
                embed,
                interaction.guild,
                guild_data.nodes[path[0]].channel_ID,
                player_data.channel_ID,
                occupants_only = True)

            node_channel = get(
                interaction.guild.text_channels,
                id = guild_data.nodes[path[0]].channel_ID)
            embed, _ = await mbd(
                'Departing.',
                f"{interaction.user.mention} left here to go to **#{path[-1]}**.",
                f"They went from {' -> '.join(path)}.")
            await node_channel.send(embed = embed)

            #Inform destination occupants
            embed, _ = await mbd(
                'An arrival.',
                f"You notice {moving_character} arrive from the direction of **#{path[-2]}**.",
                'Say hello.')
            await to_direct_listeners(embed,
                interaction.guild,
                guild_data.nodes[path[-1]].channel_ID,
                player_data.channel_ID,
                occupants_only = True)

            node_channel = get(
                interaction.guild.text_channels,
                id = guild_data.nodes[path[-1]].channel_ID)
            embed, _ = await mbd(
                'Arriving.',
                f"{moving_character} arrived here from **#{path[0]}**.",
                f"They went from {' -> '.join(path)}.")
            await node_channel.send(embed = embed)

            #Inform intermediary nodes + their occupants
            for index, intermediary_name in enumerate(path[1:-1]):
                embed, _ = await mbd(
                    'Passing through.',
                    f"You notice {moving_character} come in" + \
                        f" from the direction of **#{path[index]}**" + \
                        f" before continuing on their way towards **#{path[index + 2]}**.",
                    'Like two ships in the night.')
                await to_direct_listeners(embed,
                    interaction.guild,
                    guild_data.nodes[intermediary_name].channel_ID,
                    occupants_only = True)

                node_channel = get(
                    interaction.guild.text_channels,
                    id = guild_data.nodes[intermediary_name].channel_ID)
                embed, _ = await mbd(
                    'Transit.',
                    f"{interaction.user.mention} passed through here when traveling from" + \
                        f" **#{path[0]}>** to **#{path[-1]}**.",
                    f"They went from {' -> '.join(path)}.")
                await node_channel.send(embed = embed)

            path_nodes = await guild_data.filter_nodes(path)
            await path_nodes[path[0]].remove_occupants({player_data.id})

            #Calculate who they saw on the way
            all_sightings = []
            for name, node in path_nodes.items():

                if node.occupants:
                    occupants_mentions = await format_characters(node.occupants, interaction.guild.id)
                    all_sightings.append(f'{occupants_mentions} in **#{name}**')

            #Inform player of who they saw and what path they took
            if all_sightings:
                description = "Along the way, you saw (and were seen" + \
                    f" by) {await format_words(all_sightings)}."
            else:
                description = "You didn't see anyone along the way."

            #Change occupants
            await path_nodes[path[-1]].add_occupants({player_data.id})
            await guild_data.save()

            #Update location and eavesdropping
            player_data.location = path[-1]
            player_data.eavesdropping = None
            await player_data.save()

            await queue_refresh(interaction.guild)

            #Tell player
            embed, _ = await mbd(
                'Arrived.',
                description,
                f"The path you traveled was {' -> '.join(path)}.")
            player_channel = get(interaction.guild.text_channels, id = player_data.channel_ID)
            await player_channel.send(embed = embed)
            await interaction.followup.delete_message(message_id = interaction.message.id)
            return

        view = DialogueView(refresh = refresh_embed)
        if not destination_name:
            destinations = [node for node in player_map.nodes if node != player_data.location]
            await view.add_user_nodes(destinations)
        await view.add_submit(submit_destination)
        await view.add_cancel()
        embed = await refresh_embed()
        await ctx.respond(embed = embed, view = view)
        return

def setup(prox):
    prox.add_cog(UserCommands(prox), override = True)

