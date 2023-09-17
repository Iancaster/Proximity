

#Import-ant Libraries
from networkx import DiGraph
from re import search, sub


#Functions
async def format_words(words: iter):

    if not words:
        return ''

    word_list = list(words)

    if len(words) == 1:
        return word_list[0]

    elif len(words) == 2:
        return f'{word_list[0]} and {word_list[1]}'

    formatted_words = ', '.join(word_list[:-1])
    formatted_words += f', and {word_list[-1]}'

    return formatted_words

async def format_roles(role_IDs: iter):
    return await format_words([f'<@&{ID}>' for ID in role_IDs])

async def format_players(player_IDs: iter):
    return await format_words([f'<@{ID}>' for ID in player_IDs])

# async def format_characters(player_IDs: iter, guild_ID: int):
#
#     characters = []
#     for ID in player_IDs:
#         player = Player(ID, guild_ID)
#         name = f'**{player.name}**' if player.name else f'<@{ID}>'
#         characters.append(name)
#
#     return await format_words(characters)

async def format_whitelist(allowed_roles: iter = set(), allowed_players: iter = set()):

    if not allowed_roles and not allowed_players:
        return 'Everyone will be allowed to travel to/through this place.'

    role_mentions = await format_roles(allowed_roles)
    player_mentions = await format_players(allowed_players)

    if allowed_roles and not allowed_players:
        return f'Only people with these roles are allowed through this place: ({role_mentions}).'

    elif allowed_players and not allowed_roles:
        return f'Only these people are allowed through this place: ({player_mentions}).'

    roles_description = f'any of these roles: ({role_mentions})' if allowed_roles else 'any role'

    player_description = f'any of these people: ({player_mentions})' if allowed_players else 'everyone else'

    return f'People with {roles_description} will be allowed to come here as well as {player_description}.'

async def discordify(text: str):

    sanitized = ''.join(character.lower() for character in \
                        text if (character.isalnum() or character.isspace() or character == '-'))
    spaceless = '-'.join(sanitized.split())

    return spaceless[:19]

async def embolden(node_names: iter):
    return await format_words([f"**#{name}**" for name in node_names])

async def format_nodes(nodes: iter):
    return await format_words([node.mention for node in nodes])

async def format_colors(graph: DiGraph, origin_name: str, colored_neighbors: list, color: str):

    edge_colors = []
    for origin, destination in graph.edges:
        if origin in colored_neighbors and destination == origin_name:
            edge_colors.append(color)
        elif origin == origin_name and destination in colored_neighbors:
            edge_colors.append(color)
        else:
            edge_colors.append('black')

    return edge_colors

async def unique_name(candidate_name: str, nodes: iter):

    async def get_index(name):
        match = search(r'\d+$', name)
        if match:
            return int(match.group())
        return 0

    while candidate_name in nodes:
        suffix = await get_index(candidate_name)
        if suffix > 0:
            candidate_name = sub(r'\d+$', str(suffix + 1), candidate_name)
        else:
            candidate_name = f"{candidate_name}-2"

    return candidate_name

