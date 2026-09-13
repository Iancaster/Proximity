"""Where most core functionality resides."""

from discord import (ApplicationContext, Interaction,
    TextChannel, CategoryChannel, Guild,
    Bot, Webhook, PermissionOverwrite,
    HTTPException, NotFound, Embed, Permissions)
from discord.abc import GuildChannel
from discord.utils import get_or_fetch, find
from libraries.user_interface import safe_send, safe_del_channels
from data.database_handler import CommitResult, UNSET, _Unset
from data.database_entries import (
    roleplay_repo, location_repo, character_repo, route_repo,
    RoleplayData, LocationData, CharacterData, RouteData)
from libraries.logger import get_logger, Lumberjack
from libraries.user_interface import reference_validator, get_channel, get_bot
from math import radians, cos, sin

from libraries.embed_templates import ErrorEmbeds


from networkx import DiGraph, ego_graph, draw_networkx_nodes, \
	draw_networkx_edges, shell_layout, draw_networkx_labels
from math import sqrt
from matplotlib.pyplot import margins, gcf, tight_layout, axis, close, figure
from matplotlib.patches import ArrowStyle
from collections.abc import Callable
from io import BytesIO

from datetime import datetime as dt

async def in_text_channel(ctx: ApplicationContext) -> bool:

    if not isinstance(ctx.channel, TextChannel):
        embed = ErrorEmbeds.non_text_channel()
        await ctx.respond(embed = embed, ephemeral = True)
        return False
    
    return True

async def in_prox_rp(ctx: ApplicationContext) -> bool:

    if await roleplay_repo.exists(ctx.guild_id) != CommitResult.SUCCESS:
        embed = ErrorEmbeds.non_prox_rp()
        await ctx.respond(embed = embed, ephemeral = True)
        return False

    return True

async def is_administrator(ctx: ApplicationContext) -> bool: # Revisit this once the bot is done.

    return True
    
    if not ctx.channel.permissions_for(ctx.author).administrator:
        await ctx.respond("To prevent abuse, only server administrators may use this command.", ephemeral = True)
        return False

    return True

async def in_location(ctx: ApplicationContext) -> bool:

    if await location_repo.exists(ctx.channel_id) != CommitResult.SUCCESS:
        embed = ErrorEmbeds.non_location()
        await ctx.respond(embed = embed, ephemeral = True)
        return False
    
    return True

class Relayable:
    """Methods for manipulating channels that relay, like Locations and Character channels."""

    default_avatar_asset: str = "logo.png"        

    @staticmethod
    async def create_category(
        guild_id: int,
        is_location_cat: bool
    ) -> CategoryChannel | CommitResult:

        rp = await Roleplay.load(guild_id)
        if rp is None:
            return CommitResult.NO_UPDATE 
        
        guild = await get_or_fetch(get_bot(), "guild", guild_id, default = None)
        if guild is None:
            return CommitResult.NO_UPDATE

        if is_location_cat:
            category_type = "locations_cat"
            category_name = "locations"
        else:
            category_type = "characters_cat"
            category_name = "characters"

        try: 
            category = await guild.create_category_channel(
                name = category_name,
                position = 999,
                reason = "Requested by user for roleplay purposes.",
                overwrites = {
                    guild.default_role:
                        PermissionOverwrite(read_messages = False),
                    guild.me : PermissionOverwrite(
                        send_messages = True,
                        read_messages = True,
                        manage_channels = True)})

        except HTTPException:
            return CommitResult.NO_UPDATE

        db_result = await rp.update(**{category_type : category.id})

        if db_result != CommitResult.SUCCESS:
            await safe_del_channels([category], "Failed to update RP with new category.")
            return CommitResult.NO_UPDATE
        
        return category
    
    @staticmethod
    async def create_channel(
        channel_name: str, 
        guild_id: int,        
        is_location: bool
    ) -> TextChannel | CommitResult:

        fetch_result = await roleplay_repo.fetch(guild_id)

        if not isinstance(fetch_result, RoleplayData):
            return CommitResult.NO_UPDATE

        category = await get_channel(fetch_result.locations_cat if is_location else fetch_result.characters_cat)
        if category is None:
            category_result = await Relayable.create_category(guild_id, is_location)

            if not isinstance(category_result, CategoryChannel):
                return CommitResult.NO_UPDATE

            category = category_result

        guild = await get_or_fetch(get_bot(), "guild", id = fetch_result.roleplay_id, default = None)
        if guild is None:
            return CommitResult.NO_UPDATE

        try:

            new_channel = await guild.create_text_channel( 
                name = channel_name,
                category = category,
                reason = f"Requested by user for roleplay purposes.")

        except HTTPException:
            new_channel = None

        if new_channel is not None:
            await Relayable.create_webhook(new_channel)

        return new_channel if new_channel is not None else CommitResult.NO_UPDATE

    @staticmethod
    async def ensure_webhook(channel: TextChannel) -> Webhook:

        webhook = await Relayable.find_webhook(channel)
        
        if webhook is None:
            webhook = await Relayable.create_webhook(channel)

        return webhook # pyright: ignore[reportReturnType]

    @staticmethod
    async def find_webhook(channel: TextChannel) -> Webhook | None:

        user = get_bot().user

        if user is None:
            return None
        
        return find(lambda w : w.user.id == user.id if w.user else False, await channel.webhooks()) 
    
    @staticmethod
    async def delete_webhook(channel: TextChannel) -> bool:
        """Deletes this dedicated webhook. Returns whether successfully removed."""

        webhook = await Relayable.find_webhook(channel)

        if webhook is None:
            return True
        
        try:
            await webhook.delete(reason = "No longer needed.")
            return True
        except NotFound:
            return True

        return False

    @classmethod
    async def create_webhook(cls, channel: TextChannel) -> Webhook:

        with open("assets/" + cls.default_avatar_asset, "rb") as file:
            avatar = file.read()
 
        return await channel.create_webhook(
            name = "Proximity",
            avatar = avatar,
            reason = "For use in roleplay.")

class Roleplay:
    """Represents a guild (a.k.a. a server) that hosts a Prox roleplay."""

    _logger: Lumberjack = get_logger("Roleplay", console_level = 0)

    def __init__(self, data: RoleplayData):
        self.data = data
        return

    @classmethod
    async def create(cls, data: RoleplayData) -> Roleplay | CommitResult:

        result = await roleplay_repo.create(data)

        if result != CommitResult.SUCCESS:
            return result

        fetch_result = await roleplay_repo.fetch(data.roleplay_id)

        if not isinstance(fetch_result, RoleplayData):
            return CommitResult.UNKNOWN_ERR
        
        return cls(fetch_result)      

    @classmethod
    async def load(cls, roleplay_id: int) -> Roleplay | None:
        fetch_result = await roleplay_repo.fetch(roleplay_id)
        return cls(fetch_result) if isinstance(fetch_result, RoleplayData) else None

    async def update(self, 
        log_channel_id: int | None | _Unset = UNSET, 
        locations_cat: int | None | _Unset = UNSET,
        characters_cat: int | None | _Unset = UNSET,
        name: str | _Unset = UNSET,
        description: str | None | _Unset = UNSET,
        reference: str | None | _Unset = UNSET,
        character_limit: int | _Unset = UNSET,
        location_limit: int | _Unset = UNSET,
        subscription_end: dt | None | _Unset = UNSET
    ) -> CommitResult:
        """Updates with current values. Set a value to None to null it out."""

        changed_values = {k : v for k, v in locals().items() if v != self}
        changed_values = {k : v for k, v in changed_values.items() if v != getattr(self.data, k) and v is not UNSET}

        for channel_name in ("log_channel_id", "locations_cat", "characters_cat"):

            channel_id = changed_values.get(channel_name, UNSET)

            if isinstance(channel_id, _Unset):
                continue

            channel = await get_channel(int(channel_id))

            if channel is None:
                del changed_values[channel_name]

            guild = await get_or_fetch(get_bot(), "guild", self.data.roleplay_id)
            if not channel.permissions_for(guild.me).send_messages: # pyright: ignore[reportOptionalMemberAccess]
                del changed_values[channel_name]

        if reference is not UNSET:
            url_result = await reference_validator(reference) # pyright: ignore[reportArgumentType]

            if url_result != CommitResult.SUCCESS:
                del changed_values["reference"]

        if not changed_values:
            return CommitResult.NO_UPDATE
            
        result = await roleplay_repo.apply(self.data, **changed_values)
        return result

    async def delete(self) -> CommitResult: 
        
        for loc_data in await self.locations:
            location = Location(loc_data)
            await location.delete()

        for character_data in await self.characters:
            character = Character(character_data)
            await character.delete()

        return await roleplay_repo.delete(self.data.roleplay_id)

    @property
    async def location_count(self) -> int:
        return await location_repo.count("roleplay_id", self.data.roleplay_id)
    
    @property
    async def character_count(self) -> int:
        return await character_repo.count("roleplay_id", self.data.roleplay_id)

    @property
    async def locations(self) -> list[LocationData]:
        return await location_repo.fetch_all("roleplay_id", self.data.roleplay_id)

    @property
    async def characters(self) -> list[CharacterData]:
        return await character_repo.fetch_all("roleplay_id", self.data.roleplay_id)

class Location:

    _logger: Lumberjack = get_logger("Location", console_level = 0)

    def __init__(self, data: LocationData):
        self.data = data
        return

    async def update(self, 
        name: str | None | _Unset = UNSET, 
        description: str | None | _Unset = UNSET,
        reference: str | None | _Unset = UNSET,
    ) -> CommitResult:
        """Updates with current values. Set a value to None to null it out."""

        changed_values = {k : v for k, v in locals().items() if v != self}
        changed_values = {k : v for k, v in changed_values.items() if v != getattr(self.data, k) and v is not UNSET}

        return await location_repo.apply(self.data, **changed_values)   

    # async def update(self, 
    #     name: str | None = None, 
    #     description: str | None = None,
    #     reference: str | None = None,
    #     interaction: Interaction | None = None,
    #     **_
    # ) -> CommitResult:
    #     """Updates this location within the RP."""

    #     if interaction is None or interaction.guild is None:
    #         return result

    #     updated_channel = await Relayable.get_channel(self, interaction.guild)

    #     if updated_channel is None:
    #         return result
        
        
    #     if not description:
    #         embed_description = ("This location has no description" 
    #             " yet, but you can add one with `/review location`.")
            
    #     else:
    #         embed_description = ("This location has the following" 
    #             " description set, it'll be visible to players"
    #             " when they `/look` around in here: \n\n>>> ") + description
        
    #     embed, file = await image_embed(
    #         f"New Location: {name}",
    #         description = embed_description,
    #         footer = ("You can also set the reference photo that way." if 
    #             reference == "" else "Love what you've done with the place."),
    #         thumbnail = True,
    #         source = ImageSource.URL if reference else ImageSource.ASSET,
    #         asset_str = reference or "")
        
    #     server = RPServer(self.guild_id)
    #     await server.fetch()
    #     logging_channel = await server.get_logging_channel(guild = updated_channel.guild)
    #     await safe_send(embed, [updated_channel, logging_channel], silent = True, file = file)
        
    #     return result

    @classmethod
    async def create(cls, data: LocationData) -> Location | CommitResult:

        rp_data = await roleplay_repo.fetch(data.roleplay_id)
        if not isinstance(rp_data, RoleplayData):
            return CommitResult.UNKNOWN_ERR
        
        result = await location_repo.create(data)
        if result != CommitResult.SUCCESS:
            return result

        fetch_result = await location_repo.fetch(data.location_id)

        if not isinstance(fetch_result, LocationData):
            return fetch_result
        
        return result

    @classmethod
    async def load(cls, location_id: int) -> Location | None:
        fetch_result = await location_repo.fetch(location_id)
        return cls(fetch_result) if isinstance(fetch_result, LocationData) else None

    async def delete(self) -> CommitResult:
        
        result = await location_repo.delete(self.data.location_id)
        loc_channel = await get_channel(self.data.location_id)
        await safe_del_channels([loc_channel], "Location deleted by user.")

        rp = await Roleplay.load(self.data.roleplay_id)
        if rp is None:
            self._logger.warning(f"Could not find roleplay {self.data.roleplay_id}"
                + f" when deleting location {self.data.location_id}.")
            return result
 
        if await rp.location_count == 0:
            loc_category = await get_channel(rp.data.locations_cat)            
            await safe_del_channels([loc_category], "No more locations remain in this RP.")
        
        return result

    # async def new_route(self, 
    #     to_location: Location, 
    #     guild: Guild,
    #     server: RPServer | None = None
    # ) -> bool:
    
    #     if not await to_location.exists:
    #         return False

    #     self_channel = await self.get_channel(guild)
    #     if self_channel is None:
    #         return False
        
    #     log_embed = text_embed(
    #         "New route.",
    #         f"A new route has been created from <#{self.id}> to <#{to_location.id}>.",
    #         "Note that this is one-way. If this is desired, no issue--otherwise, ensure an opposite route exists too.")
        
    #     if server is None:
    #         server = RPServer(guild.id)
    #         await server.fetch()

    #     logging_channel = await server.get_logging_channel(guild = guild)
    #     await safe_send(log_embed, [self_channel, logging_channel], silent = True)

    #     character_embed = text_embed(
    #         "New route.",
    #         f"You notice a way to reach **{to_location.name}** from here-- is that new?",
    #         "Perhaps  it was always there. Perhaps not.")

    #     await self.send_to_inhabitants(guild, character_embed)        
    #     return True
    
    # async def remove_route(self, 
    #     to_location: Location, 
    #     guild: Guild,
    #     server: RPServer | None = None
    # ) -> bool:

    #     self_channel = await self.get_channel(guild)
    #     if self_channel is None:
    #         return False
        
    #     log_embed = text_embed(
    #         "Route removed.",
    #         f"The route from <#{self.id}> to <#{to_location.id}> has been removed.",
    #         f"Note that there may still be a route from **{to_location.name}** to **{self.name}**.")
        
    #     if server is None:
    #         server = RPServer(guild.id)
    #         await server.fetch()

    #     logging_channel = await server.get_logging_channel(guild = guild)
    #     await safe_send(log_embed, [self_channel, logging_channel], silent = True)

    #     character_embed = text_embed(
    #         "Route disappeared.",
    #         f"You can't seem to reach **{to_location.name}** from here-- I thought you used to be able?",
    #         "Perhaps you never could. Perhaps something changed.") 

    #     await self.send_to_inhabitants(guild, character_embed)        
    #     return True
    
    # async def send_to_inhabitants(self, guild: Guild, embed: Embed) -> None:
    #     """Sends a message to all characters in this location."""

    #     for character in await Character.fetch_all("location_id", self.id):
    #         char_channel = await character.get_channel(guild)
    #         await safe_send(embed = embed, channels = [char_channel])

    #     return

    @property
    async def inlet_routes(self) -> list[RouteData]:
        return await route_repo.fetch_all("to_id", self.data.location_id)

    @property
    async def outlet_routes(self) -> list[RouteData]:
        return await route_repo.fetch_all("from_id", self.data.location_id)

    @property
    async def connections(self) -> list[RouteData]:
        return await self.inlet_routes + await self.outlet_routes

    @property
    async def neighbors(self) -> list[LocationData]:

        conns = await self.connections
        neigh_ids = {id for route in conns for id in (route.to_id, route.from_id)}

        if not neigh_ids:
            return []
        
        neigh_ids.remove(self.data.location_id)
        results = [await location_repo.fetch(id) for id in neigh_ids]

        return [res for res in results if isinstance(res, LocationData)]

    @property
    async def occupant_count(self) -> int:
        return await character_repo.count("location_id", self.data.location_id)
    
    @property
    async def occupants(self) -> list[CharacterData]:
        return await character_repo.fetch_all("location_id", self.data.location_id)

class Route:

    def __init__(self, data: RouteData):
        self.data = data
        return

    @classmethod
    async def create(cls, data: RouteData) -> Route | CommitResult:
        
        result = await route_repo.create(data)
        if result != CommitResult.SUCCESS:
            return result

        fetch_result = await route_repo.fetch(data.from_id, data.to_id)

        if not isinstance(fetch_result, RouteData):
            return fetch_result
        
        return result

    async def delete(self) -> CommitResult:
        return await route_repo.delete(self.data.from_id, self.data.to_id)

    @property
    async def ends(self) -> tuple[int, int]:
        return (self.data.to_id, self.data.from_id)

class Character:

    _logger: Lumberjack = get_logger("Character", console_level = 0)
    
    def __init__(self, data: CharacterData):
        self.data = data
        return

    @classmethod
    async def load(cls, character_id: int) -> Character | None:
        fetch_result = await character_repo.fetch(character_id)
        return cls(fetch_result) if isinstance(fetch_result, CharacterData) else None


    async def delete(self, silent: bool = False) -> CommitResult:
            
        result = await character_repo.delete(self.data.character_id)
        char_channel = await get_channel(self.data.character_id)
        await safe_del_channels([char_channel], "Character deleted by user.")

        rp = await Roleplay.load(self.data.roleplay_id)
        if rp is None:
            self._logger.warning(f"Could not find roleplay {self.data.roleplay_id}"
                + f" when deleting character {self.data.character_id}.")
            return result

        if await rp.character_count == 0:
            char_category = await get_channel(rp.data.characters_cat)            
            await safe_del_channels([char_category], "No more characters remain in this RP.")
        
        return result

class GameWorld:

    def __init__(self, graph: DiGraph):
        self.graph = graph

    @classmethod
    async def _fetch_total(cls, roleplay_id: int) -> DiGraph:

        graph = DiGraph()

        loc_datas = await location_repo.fetch_all("roleplay_id", roleplay_id)
        graph.add_nodes_from((loc.location_id, {"name" : loc.name}) for loc in loc_datas)

        routes = await route_repo.fetch_all("roleplay_id", roleplay_id)
        graph.add_edges_from((r.to_id, r.from_id) for r in routes)

        return graph

    @classmethod
    async def from_roleplay(cls, roleplay_id: int) -> GameWorld:
        return cls(await GameWorld._fetch_total(roleplay_id))

    @classmethod
    async def from_location(cls, 
        location_id: int,
        roleplay_id: int,
        undirected: bool, 
        radius: int,
    ) -> GameWorld:

        return ego_graph(
            await GameWorld._fetch_total(roleplay_id), 
            location_id, 
            radius = radius, 
            undirected = undirected)

    def render(self) -> BytesIO:

        node_count = self.graph.number_of_nodes()
        labels = {node: data["name"] for node, data in graph.nodes(data=True)}

        side = max(6, node_count * 0.9)
        node_size = max(300, 1600 - node_count * 60)
        font_size = max(8, 14 - node_count // 4)

        figure(figsize = (side, side))
        positions = shell_layout(self.graph, rotate = 25)

        draw_networkx_nodes(
            self.graph,
            pos = positions,
            node_shape = "o",
            node_size = node_size,
            node_color = "#ffffff",
            edgecolors = "gray",
            linewidths = 1.5)

        draw_networkx_labels(
            self.graph,
            pos = positions,
            labels = labels,
            font_size = font_size,
            font_weight = "bold")

        draw_networkx_edges(
            self.graph,
            pos = positions,
            node_size = node_size,
            edge_color = "black",
            width = 2.0,
            arrowstyle = ArrowStyle("-|>"), # pyright: ignore[reportArgumentType]
            arrowsize = 25,
            min_source_margin = 30,
            min_target_margin = 30) 

        margins(x = 0.15, y = 0.15)
        tight_layout(pad = 0.8)
        axis("off")

        map_image = gcf()
        close()
        bytesIO = BytesIO()
        map_image.savefig(bytesIO, format = "jpg", dpi = 150)
        bytesIO.seek(0)

        return bytesIO


#         self.eaves_target: int | None = None
#         self.name: str | None = None
#         self.description: str | None = None
#         self.reference: str | None = None

#         DatabaseMixin.__init__(
#             self,
#             entry_class = CharacterEntry, 
#             id = id, 
#             console_level = console_level)

#         return
    
#     @staticmethod
#     async def fetch_all(col_name: str, value: int | str, *_, **__) -> Iterable[Character]:
        
#         return await DatabaseMixin.fetch_all(
#             col_name = col_name, 
#             value = value,
#             entry_class = CharacterEntry,
#             final_class = Character)
    
# @dataclass(slots = True)
# class Character:
#     name: str
#     avatar: str
#     location_id: str
#     eavesdropping: bool

    