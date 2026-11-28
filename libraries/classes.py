"""Where most core functionality resides."""

from io import BytesIO
from datetime import datetime as dt
from random import randint
from networkx import DiGraph, ego_graph, draw_networkx_nodes, \
    draw_networkx_edges, shell_layout, draw_networkx_labels, shortest_path
from matplotlib.pyplot import margins, gcf, tight_layout, \
    axis, close, figure

from discord import ApplicationContext, TextChannel, \
    CategoryChannel, Webhook, PermissionOverwrite, File, HTTPException, \
    Embed, AllowedMentions
from discord.utils import get_or_fetch, find

from data.database_handler import CommitResult, UNSET, _Unset
from data.database_entries import (
    roleplay_repo, RoleplayData,
    location_repo, LocationData,
    character_repo, CharacterData,
    route_repo, RouteData)
from libraries.logger import get_logger, Lumberjack
from libraries.user_interface import reference_validator, \
    get_channel, get_bot, safe_del_channels, safe_send, \
    ellipticize, safe_del_channel, ASSETS_DIR
from libraries.embed_templates import ErrorEmbeds


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
    
    if not ctx.channel.permissions_for(ctx.author).administrator:
        embed = ErrorEmbeds.non_admin()
        await ctx.respond(embed = embed, ephemeral = True)
        return False

    return True

async def in_location(ctx: ApplicationContext) -> bool:

    if await location_repo.exists(ctx.channel_id) != CommitResult.SUCCESS:
        embed = ErrorEmbeds.non_location()
        await ctx.respond(embed = embed, ephemeral = True)
        return False
    
    return True

async def in_char_channel(ctx: ApplicationContext) -> bool:

    if await character_repo.exists(ctx.channel_id) != CommitResult.SUCCESS:
        embed = ErrorEmbeds.non_character()
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
            await safe_del_channels([category], \
                reason = "Failed to update RP with new category.")
            return CommitResult.NO_UPDATE
        
        return category
    
    @staticmethod
    async def create_channel(
        channel_name: str, 
        guild_id: int,        
        is_location: bool
    ) -> TextChannel | CommitResult:

        rp_data = await roleplay_repo.fetch(guild_id)

        if not isinstance(rp_data, RoleplayData):
            return CommitResult.NO_UPDATE

        category = await get_channel(rp_data.locations_cat if \
            is_location else rp_data.characters_cat)
        
        if category is None:
            category_result = await Relayable.create_category(
                guild_id = guild_id, 
                is_location_cat = is_location)

            if not isinstance(category_result, CategoryChannel):
                return CommitResult.NO_UPDATE

            category = category_result

        guild = await get_or_fetch(
            obj = get_bot(), 
            attr = "guild", 
            id = rp_data.roleplay_id, 
            default = None)
        
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

        try:
            webhooks = await channel.webhooks()

        except HTTPException:
            return None
        
        return find(lambda w : w.user.id == user.id if w.user else False, webhooks) 
    
    @staticmethod
    async def delete_webhook(channel: TextChannel) -> bool:
        """Deletes this dedicated webhook. Returns whether successfully removed."""

        webhook = await Relayable.find_webhook(channel)

        if webhook is None:
            return True
        
        try:
            await webhook.delete(reason = "No longer needed.")
            return True
        except HTTPException:
            return False

    @classmethod
    async def create_webhook(cls, channel: TextChannel) -> Webhook:

        with open(ASSETS_DIR / cls.default_avatar_asset, "rb") as file:
            avatar = file.read()
 
        return await channel.create_webhook(
            name = "Proximity",
            avatar = avatar,
            reason = "For use in roleplay.")

    @staticmethod
    def _copy_file(file: File) -> File:
        position = file.fp.tell()
        file.fp.seek(0)
        try:
            contents = file.fp.read()
        finally:
            file.fp.seek(position)

        return File(
            BytesIO(contents),
            filename = file.filename or "attachment",
            description = file.description,
            spoiler = file.spoiler)

    @classmethod
    async def send_through_hook(cls, 
        channel: TextChannel, 
        avatar_url: str | None = None,
        content: str | None = None,
        username: str | None = None,
        embed: Embed | None = None,
        files: list[File] | None = None,
        file: File | None = None
    ) -> bool:

        message_details = {k : v for k, v in locals().items() if v not in (None, cls)} 
        message_details.pop("channel", None)
        message_details.pop("file", None)
        message_details.pop("files", None)

        if username:
            message_details["username"] = ellipticize(
                string = message_details["username"], 
                max_length = 80)

        webhook = await Relayable.ensure_webhook(channel)
        upload_files: list[File] = []
        
        try:
            for source_file in ([file] if file is not None else []) + (files or []):
                upload_files.append(cls._copy_file(source_file))

            if upload_files:
                message_details["files"] = upload_files

            await webhook.send(
                **message_details, 
                allowed_mentions = AllowedMentions.none())
        
        except HTTPException:
            return False
        
        finally:
            for upload_file in upload_files:
                upload_file.close()

        return True

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

    @classmethod
    async def ensure_load(cls, roleplay_id: int) -> Roleplay:
        fetch_result = await cls.load(roleplay_id)
        assert fetch_result is not None
        return fetch_result

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

        changed_values = {k : v for k, v in locals().items() if k != "self"}
        changed_values = {k : v for k, v in changed_values.items() if v != getattr(self.data, k) and v is not UNSET}

        for channel_name in ("log_channel_id", "locations_cat", "characters_cat"):

            channel_id = changed_values.get(channel_name, UNSET)

            if not isinstance(channel_id, int):
                continue

            channel = await get_channel(int(channel_id))

            if channel is None:
                del changed_values[channel_name]
                continue

            guild = await get_or_fetch(
                obj = get_bot(), 
                attr = "guild", 
                id = self.data.roleplay_id, 
                default = None)
            
            if guild is None or not channel.permissions_for(guild.me).send_messages: 
                del changed_values[channel_name]

        if "reference" in changed_values and reference is not None:
            url_result = await reference_validator(reference) # pyright: ignore[reportArgumentType]

            if url_result != CommitResult.SUCCESS:
                changed_values.pop("reference", None)

        if not changed_values:
            return CommitResult.NO_UPDATE
            
        result = await roleplay_repo.apply(self.data, **changed_values)
        return result

    async def delete(self) -> CommitResult: 
        
        for character_data in await self.characters:
            character = Character(character_data)
            await character.delete()

        for loc_data in await self.locations:
            location = Location(loc_data)
            await location.delete()

        return await roleplay_repo.delete(self.data.roleplay_id)

    async def notify_log(self, 
        embed: Embed, 
        file: File | None = None
    ) -> None:
        return await safe_send(embed, [self.data.log_channel_id], silent = True, file = file)

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
        self._channel: TextChannel | None = None
        return 

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
        
        return cls(fetch_result)

    @classmethod
    async def load(cls, location_id: int) -> Location | None:
        fetch_result = await location_repo.fetch(location_id)
        return cls(fetch_result) if isinstance(fetch_result, LocationData) else None

    async def update(self, 
        name: str | None | _Unset = UNSET, 
        description: str | None | _Unset = UNSET,
        reference: str | None | _Unset = UNSET,
    ) -> CommitResult:
        """Updates with current values. Set a value to None to null it out."""

        changed_values = {k : v for k, v in locals().items() if  k != "self"}
        changed_values = {k : v for k, v in changed_values.items() if \
            v != getattr(self.data, k) and v is not UNSET}

        return await location_repo.apply(self.data, **changed_values)  
    
    async def delete(self) -> CommitResult:
        
        loc_channel = await get_channel(self.data.location_id)
        del_result = await safe_del_channel(loc_channel, "Location deleted by user.")

        if del_result == CommitResult.UNKNOWN_ERR:
            return CommitResult.UNKNOWN_ERR

        db_result = await location_repo.delete(self.data.location_id)

        rp = await Roleplay.load(self.data.roleplay_id)

        if rp is None:
            
            self._logger.warning(f"Could not find roleplay {self.data.roleplay_id}" + \
                f" when deleting location {self.data.location_id}.")
            
            return db_result
 
        if await rp.location_count == 0:

            loc_category = await get_channel(rp.data.locations_cat)            
            await safe_del_channel(loc_category, "No more locations remain in this RP.")

            await rp.update(locations_cat = None)
        
        return db_result

    async def notify_log(self, 
        embed: Embed, 
        file: File | None = None
    ) -> None:
        return await safe_send(embed, [self.data.location_id], silent = True, file = file)

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
    

    async def speak(self,
        content: str | None = None,
        embed: Embed | None = None,
        file: File | None = None,
        files: list[File] | None = None,
    ) -> None:

        loc_channel = await get_channel(self.data.location_id)

        if isinstance(loc_channel, TextChannel):

            await Relayable.send_through_hook(
                channel = loc_channel,
                avatar_url = self.data.reference,
                content = content,
                username = self.data.name,
                embed = embed,
                file = file,
                files = files)

        for character in await self.occupants:

            char_channel = await get_channel(character.character_id)

            if not isinstance(char_channel, TextChannel):
                continue
            
            await Relayable.send_through_hook(
                channel = char_channel,
                avatar_url = self.data.reference,
                content = content,
                username = self.data.name,
                embed = embed,
                file = file,
                files = files)

        return

    async def send_to_occupants(self, 
        avatar_url: str | None = None,
        content: str | None = None,
        username: str | None = None,
        embed: Embed | None = None,
        file: File | None = None,
        files: list[File] | None = None,
        exclude: list[int] | None = None
    ) -> None:

        if exclude is None:
            exclude = []

        for character in await self.occupants:

            if character.character_id in exclude:
                continue

            char_channel = await get_channel(character.character_id)
            
            if not isinstance(char_channel, TextChannel):
                continue
        
            await Relayable.send_through_hook(
                channel = char_channel, # pyright: ignore[reportArgumentType]
                avatar_url = avatar_url,
                content = content,
                username = username,
                embed = embed,
                file = file,
                files = files)

        return

    async def send_to_neighbors(self,
        avatar_url: str | None = None,
        content: str | None = None,
        mumble: bool = True,
        username: str | None = None,
        embed: Embed | None = None,
        files: list[File] | None = None,
        file: File | None = None,
    ) -> None:

        for neighbor_data in await self.neighbors:

            neighbor = Location(neighbor_data)

            for occ in await neighbor.occupants:

                char_channel = await get_channel(occ.character_id)

                if not isinstance(char_channel, TextChannel):
                    continue

                await Relayable.send_through_hook(
                    channel = char_channel, # pyright: ignore[reportArgumentType]
                    avatar_url = avatar_url,
                    content = Character.mumble(content or "") if mumble else content,
                    username = username,
                    embed = embed,
                    files = files,
                    file = file)

        return

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
        
        neigh_ids.discard(self.data.location_id)
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
        
        return cls(fetch_result)

    @classmethod
    async def load(cls, from_id: int, to_id: int) -> Route | None:
        fetch_result = await route_repo.fetch(from_id, to_id)
        return cls(fetch_result) if isinstance(fetch_result, RouteData) else None

    async def delete(self) -> CommitResult:
        return await route_repo.delete(self.data.from_id, self.data.to_id)

    @property
    def ends(self) -> tuple[int, int]:
        return (self.data.from_id, self.data.to_id)

    def __str__(self) -> str:
        return f"{self.data.from_id} -> {self.data.to_id}"

# class Path:

#     _logger = get_logger("Path Logger")

#     def __init__(self, 
#         route_to: Route | None, 
#         route_from: Route | None):

#         self.route_to = route_to
#         self.route_from = route_from

#         return

#     @classmethod
#     async def create(cls, 
#         route_to: Route | None,
#         route_from: Route | None = None,
#         load_reverse_route: bool = True
#     ) -> Path:

#         if route_to is None and route_from is None:
#             return cls(None, None)

#         if route_to is not None \
#             and route_from is not None \
#             and (route_to.data.to_id != route_from.data.from_id \
#             or route_to.data.from_id != route_from.data.to_id):

#             cls._logger.error("Provided route_to and route_from are mismatched!" + \
#                 f" Received {route_to} and {route_from}.")

#             return cls(route_to, route_from)

#         if route_to is None and load_reverse_route:
            
#             route_to = await Route.load(
#                 route_from.data.to_id, # pyright: ignore[reportOptionalMemberAccess]
#                 route_from.data.from_id) # pyright: ignore[reportOptionalMemberAccess]

#         if route_from is None and load_reverse_route:
            
#             route_from = await Route.load(
#                 route_to.data.to_id, # pyright: ignore[reportOptionalMemberAccess]
#                 route_to.data.from_id) # pyright: ignore[reportOptionalMemberAccess]

#         return cls(route_to, route_from)      

#     @classmethod
#     async def load(cls, 
#         from_id: int, 
#         to_id: int
#     ) -> Path | None:

#         route_to = await Route.load(from_id, to_id)        
#         route_from = await Route.load(to_id, from_id)

#         if route_to is None and route_from is None:
#             return None

#         return cls(route_to, route_from)

#     async def delete(self) -> CommitResult:

#         result_to = await self.route_to.delete() if self.route_to is not None else CommitResult.NO_UPDATE        
#         result_from = await self.route_from.delete() if self.route_from is not None else CommitResult.NO_UPDATE

#         return next((r for r in [result_to, result_from] if r not in (CommitResult.SUCCESS, CommitResult.NO_UPDATE)), CommitResult.SUCCESS)

    # @property
    # def ends(self) -> tuple[int, int]:
    #     return self.route_to.ends 

class Character:

    _logger: Lumberjack = get_logger("Character", console_level = 0)
    
    def __init__(self, data: CharacterData):
        self.data = data
        return

    @classmethod
    async def create(cls, data: CharacterData) -> Character | CommitResult:
        
        result = await character_repo.create(data)
        if result != CommitResult.SUCCESS:
            return result

        fetch_result = await character_repo.fetch(data.character_id)

        if not isinstance(fetch_result, CharacterData):
            return fetch_result
        
        return cls(fetch_result)

    @classmethod
    async def load(cls, character_id: int) -> Character | None:
        fetch_result = await character_repo.fetch(character_id)
        return cls(fetch_result) if isinstance(fetch_result, CharacterData) else None

    async def update(self, 
        name: str | None | _Unset = UNSET, 
        description: str | None | _Unset = UNSET,
        location_id: int | None | _Unset = UNSET,
        eaves_target: int | None | _Unset = UNSET,
        reference: str | None | _Unset = UNSET,
    ) -> CommitResult:
        """Updates with current values. Set a value to None to null it out."""

        changed_values = {k : v for k, v in locals().items() if  k != "self"}
        changed_values = {k : v for k, v in changed_values.items() if 
            v != getattr(self.data, k) and v is not UNSET}

        return await character_repo.apply(self.data, **changed_values)  
    
    async def delete(self) -> CommitResult:
            
        char_channel = await get_channel(self.data.character_id)
        del_result = await safe_del_channel(char_channel, "Character deleted by user.")

        if del_result == CommitResult.UNKNOWN_ERR:
            return CommitResult.UNKNOWN_ERR

        db_result = await character_repo.delete(self.data.character_id)

        rp = await Roleplay.load(self.data.roleplay_id)

        if rp is None:
            
            self._logger.warning(f"Could not find roleplay {self.data.roleplay_id}" + \
                f" when deleting character {self.data.character_id}.")
            
            return db_result

        if await rp.character_count == 0:
            
            char_category = await get_channel(rp.data.characters_cat)            
            await safe_del_channel(char_category, "No more characters remain in this RP.")

            await rp.update(characters_cat = None)
        
        return db_result

    async def speak(self, 
        content: str | None = None,
        file: File | None = None,
        files: list[File] | None = None,
    ) -> CommitResult:

        location = await Location.load(self.data.location_id)

        if location is None:
            return CommitResult.ROW_MISSING

        loc_channel = await get_channel(location.data.location_id)

        if not isinstance(loc_channel, TextChannel):
            return CommitResult.ROW_MISSING

        char_channel = await get_channel(self.data.character_id)
        
        if not isinstance(char_channel, TextChannel):
            return CommitResult.ROW_MISSING
        
        await Relayable.send_through_hook(
            channel = char_channel,
            avatar_url = self.data.reference,
            content = content,
            username = self.data.name,
            embed = None,
            files = files,
            file = file)
        
        await Relayable.send_through_hook(
            channel = loc_channel, 
            avatar_url = self.data.reference,
            content = content,
            username = self.data.name,
            embed = None,
            files = files,
            file = file)
        
        await location.send_to_occupants(
            avatar_url = self.data.reference,
            content = content,
            username = self.data.name,
            embed = None,
            file = file,
            files = files,
            exclude = [self.data.character_id])

        await location.send_to_neighbors(
            avatar_url = self.data.reference,
            content = content,
            username = f"{self.data.name}, from the direction of {location.data.name}...",
            embed = None,
            files = files,
            file = file)

        return CommitResult.SUCCESS

    @staticmethod
    def mumble(content: str) -> str:

        heard_window = 8
        lead = randint(0, 6)
        heard_fraction = 0.3
        period = round(heard_window / heard_fraction)

        result: list[str] = []

        for index, char in enumerate(content):

            if index < lead:
                result.append(".")

            elif not char.isalnum():
                result.append(char)

            elif index % period < heard_window:
                result.append(char)

            else:
                result.append(".")

        return "".join(result)

class GameWorld:

    def __init__(self, graph: DiGraph | None = None):
        
        self.graph = graph if graph is not None else DiGraph()
        self._loc_lookups: dict[int, LocationData] = dict()
        self._route_lookups: set[tuple[int, int]] = set()

        return 

    def get_path(self, origin: int, destination: int) -> list[LocationData]:

        path = shortest_path(
            self.graph,
            source = origin,
            target = destination)

        return [self._loc_lookups[loc_id] for loc_id in path]

    @staticmethod
    async def _fetch_locs(roleplay_id: int) -> dict[int, LocationData]:
        loc_datas = await location_repo.fetch_all("roleplay_id", roleplay_id)
        return {data.location_id : data for data in loc_datas}

    @staticmethod
    async def _fetch_routes(roleplay_id: int) -> set[tuple[int, int]]:
        routes = await route_repo.fetch_all("roleplay_id", roleplay_id)
        return {(r.from_id, r.to_id) for r in routes}

    @staticmethod
    def compose(
        locations: dict[int, LocationData],
        routes: set[tuple[int, int]]
    ) -> DiGraph:

        graph = DiGraph()

        graph.add_nodes_from((id, {"name" : data.name}) for id, data in locations.items())
        graph.add_edges_from(routes)

        return graph

    @classmethod
    async def from_roleplay(cls, roleplay_id: int) -> GameWorld:

        gw = cls()

        gw._loc_lookups = await gw._fetch_locs(roleplay_id)
        gw._route_lookups = await gw._fetch_routes(roleplay_id)
        gw.graph = gw.compose(gw._loc_lookups, gw._route_lookups)

        return gw

    @classmethod
    async def from_location(cls, 
        location_id: int,
        roleplay_id: int,
        undirected: bool, 
        radius: int,
    ) -> GameWorld:

        gw = cls()

        gw._loc_lookups = await gw._fetch_locs(roleplay_id)
        gw._route_lookups = await gw._fetch_routes(roleplay_id)

        gw.graph = ego_graph(
            gw.compose(gw._loc_lookups, gw._route_lookups), 
            location_id, 
            radius = radius, 
            undirected = undirected)

        gw._loc_lookups = {loc_id : data for loc_id, data in gw._loc_lookups.items() \
            if loc_id in gw.graph}
        gw._route_lookups = {r for r in gw._route_lookups if gw.graph.has_edge(*r)}

        return gw

    def render(self) -> BytesIO:

        node_count = self.graph.number_of_nodes()
        labels = {node : data["name"] for node, data in self.graph.nodes(data = True)}

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
            arrowstyle = "-|>",
            arrowsize = 25,
            min_source_margin = 30,
            min_target_margin = 30) 

        margins(x = 0.15, y = 0.15)
        tight_layout(pad = 0.8)
        axis("off")

        map_image = gcf()
        bytesIO = BytesIO()
        map_image.savefig(bytesIO, format = "png", dpi = 150)
        bytesIO.seek(0)

        close(fig = map_image)

        return bytesIO
