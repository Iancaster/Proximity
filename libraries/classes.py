"""Where most core functionality resides."""

from typing import Iterable, Self

from discord import Client, ApplicationContext, TextChannel, \
    CategoryChannel, Guild, PermissionOverwrite, Forbidden, \
    HTTPException, Webhook, NotFound, Interaction, MISSING
from discord.utils import get_or_fetch, find
from libraries.user_interface import text_embed, image_embed, ImageSource, safe_log, safe_del_channels
from data.database_handler import DatabaseMixin, CommitResult, \
    ServerEntry, LocationEntry, CharacterEntry
from os import environ

SELF_USER_ID: int = int(environ.get("USER_ID", default = 0))

async def in_text_channel(ctx: ApplicationContext) -> bool:

    if not isinstance(ctx.channel, TextChannel):
        embed = text_embed(
            "Where am I?",
            "This command only works in a normal text channel.",
            "Try calling this command again, but from there instead.")
        await ctx.respond(embed = embed, ephemeral = True)
        return False
    
    return True

async def in_prox_rp(ctx: ApplicationContext) -> bool:

    if not await RPServer(ctx.guild_id).exists:

        embed = text_embed(
            "Hold your horses, cowboy.",
            "This command is for Proximity roleplay servers, which this is not."
                " You can make a server into a Prox RP by doing `/new roleplay`"
                " in it, once I'm there too. Assuming you've got the permissions," \
                " of course.",
            "Or just head to your favorite roleplay and ask the staff about it.")
        await ctx.respond(embed = embed, ephemeral = True)
        return False

    return True

async def is_administrator(ctx: ApplicationContext) -> bool:

    return True
    
    if not ctx.channel.permissions_for(ctx.author).administrator:
        await ctx.respond("To prevent abuse, only server administrators may use this command.", ephemeral = True)
        return False

    return True

class RelayableMixin:

    default_avatar_asset: str = "logo.png"

    def __init__(self):
        self.id: int = 0
        return

    @staticmethod
    async def make_channel(
        category_name: str,
        channel_name: str, 
        guild: Guild
    ) -> TextChannel | None:

        server = RPServer(guild.id)
        await server.fetch()

        loc_category = await server.get_category(
            category_name,
            guild = guild,
            category_id = server.locations_cat if \
                category_name == "locations" else server.characters_cat,
            make_if_needed = True)

        try:

            new_rp_channel = await guild.create_text_channel( 
                name = channel_name,
                category = loc_category,
                reason = f"Requested by user for roleplay purposes.")

        except HTTPException, Forbidden:
            new_rp_channel = None

        if new_rp_channel is not None:
            await RelayableMixin.create_webhook(new_rp_channel)

        return new_rp_channel

    async def get_channel(self, guild: Guild | None) -> TextChannel | None:

        return await get_or_fetch(
            guild, 
            "channel", 
            self.id, 
            default = None)

    @staticmethod
    async def ensure_webhook(channel: TextChannel) -> Webhook:

        webhook = RelayableMixin.find_webhook(channel)
        
        if webhook is None:
            webhook = RelayableMixin.create_webhook(channel)

        return webhook # pyright: ignore[reportReturnType]

    @staticmethod
    async def find_webhook(channel: TextChannel) -> Webhook | None:
        return find(lambda w : w.user.id == SELF_USER_ID if w.user else False, await channel.webhooks())
    
    @staticmethod
    async def delete_webhook(channel: TextChannel) -> bool:
        """Deletes this dedicated webhook. Returns whether successfully removed."""

        webhook = await RelayableMixin.find_webhook(channel)

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

class RPServer(DatabaseMixin):
    """Represents one server in the roleplay."""

    def __init__(self, id: int, console_level: int | None = None):

        self.log_channel_id: int | None = None
        self.locations_cat: int | None = None
        self.characters_cat: int | None = None
        self.name: str | None = None
        self.description: str | None = None
        self.reference: str | None = None
        self.character_limit: int | None = None
        self.location_limit: int | None = None
        self.subscription_end: int | None = None

        super().__init__(
            entry_class = ServerEntry, 
            id = id, 
            console_level = console_level)

        return
    
    async def create(self, 
        log_channel_id: int, 
        name: str, 
        description: str | None = None,
        reference: str | None = None,
        character_limit: int | None = 10,
        location_limit: int | None = 10,
        subscription_end: int | None = None,
        log_channel: TextChannel | None = None,
        **_
    ) -> CommitResult:
        """Registers this server as an RP one."""

        result = await super().create(
            log_channel_id = log_channel_id,
            name = name,
            description = description,
            reference = reference,
            character_limit = character_limit,
            location_limit = location_limit,
            subscription_end = subscription_end)

        if log_channel is None:
            return result

        embed, file = await image_embed(
            f"Roleplay Created: {self.name}",
            "Hello! I am Proximity, ",
            "Sorry to see you go.",
            thumbnail = True,
            source = ImageSource.URL if self.reference else ImageSource.ASSET,
            asset_str = self.reference or "")
        
        await safe_log(embed, [log_channel], silent = True, file = file)        
        return result

    async def update(self, 
        log_channel_id: int | None = None, 
        locations_cat: int | None = None,
        characters_cat: int | None = None,
        name: str | None = None, 
        description: str | None = None,
        reference: str | None = None,
        character_limit: int | None = None,
        location_limit: int | None = None,
        subscription_end: int | None = None,
        **_
    ) -> CommitResult:
        """Updates with current values. Returns True on success."""

        return await super().update(
            log_channel_id = log_channel_id,
            locations_cat = locations_cat,
            characters_cat = characters_cat,
            name = name,
            description = description,
            reference = reference,
            character_limit = character_limit,
            location_limit = location_limit,
            subscription_end = subscription_end)

    async def get_logging_channel(self, guild: Guild | None) -> TextChannel | None:

        if self.log_channel_id is None:
            return None

        return await get_or_fetch(
            guild, 
            "channel",
            self.log_channel_id,
            default = None)

    async def get_category(self, 
        category_name: str,
        guild: Guild,
        category_id: int | None = None, 
        make_if_needed: bool = True
    ) -> CategoryChannel | None:
        
        if not await self.exists:
            self._logger.warning(f"Could not find {category_name} category; non-Proximity RP server.")
            return None 
        
        if category_id is not None:

            found_category = await get_or_fetch(
                guild, 
                "channel", 
                category_id, 
                default = None)
            
            if found_category is not None:
                return found_category 
            
            if category_name == "locations":
                await self.update(locations_cat = 0)

            elif category_name == "characters":
                await self.update(characters_cat = 0)
                
        if not make_if_needed:
            self._logger.warning(f"Could not locate {category_name} category for {self.name}.")
            return None
        
        try: 
            found_category = await guild.create_category_channel(
                name = category_name,
                position = 999,
                overwrites = {
                    guild.default_role:
                        PermissionOverwrite(read_messages = False),
                    guild.me : PermissionOverwrite(
                        send_messages = True,
                        read_messages = True,
                        manage_channels = True)})

        except Forbidden, HTTPException:
            return None
        
        if category_name == "locations":
            await self.update(locations_cat = found_category.id)

        elif category_name == "characters":
            await self.update(characters_cat = found_category.id)

        else:
            self._logger.info(f"Made a category named {category_name}.")
        
        return found_category

    async def delete(self, # delete character channels here too
        log_channel: TextChannel | None = None, **_
    ) -> CommitResult:

        if log_channel is None:
            return await super().delete()
        
        loc_category = await self.get_category(
            "locations",
            category_id = self.locations_cat,
            guild = log_channel.guild,
            make_if_needed = False)
        await safe_del_channels([loc_category], "Roleplay is being deleted.")

        for location in await self.locations:

            loc_channel = await location.get_channel(log_channel.guild)
            await location.delete(location_channel = loc_channel)

        char_category = await self.get_category(
            "characters",
            category_id = self.characters_cat,
            guild = log_channel.guild,
            make_if_needed = False)
        await safe_del_channels([char_category], "Roleplay is being deleted.")

        for character in await self.characters:

            char_channel = await character.get_channel(log_channel.guild)
            await character.delete(guild = log_channel.guild)

        embed, file = await image_embed(
            f"Roleplay Deleted: {self.name}",
            "The following has been deleted: " 
                "\n - All server data (name, description, reference, etc)."
                "\n - All Locations, their channels, and all Routes between them."
                "\n - All Characters and their location channels.",
            "Sorry to see you go.",
            thumbnail = True,
            source = ImageSource.URL if self.reference else ImageSource.ASSET,
            asset_str = self.reference or "")
        
        await safe_log(embed, [log_channel], silent = True, file = file)        
        return await super().delete()

    @property
    async def location_count(self) -> int:
        return await LocationEntry.count("guild_id", self.id)
    
    @property
    async def character_count(self) -> int:
        return await CharacterEntry.count("guild_id", self.id)

    @property
    async def locations(self) -> list[Location]:
        return await Location.fetch_all("guild_id", self.id) # pyright: ignore[reportReturnType]

    @property
    async def characters(self) -> list[Character]:
        return await Character.fetch_all("guild_id", self.id) # pyright: ignore[reportReturnType]

class Location(DatabaseMixin, RelayableMixin):

    def __init__(self, id: int, console_level: int | None = None):

        self.id: int = id
        self.guild_id: int | None = None
        self.name: str | None = None
        self.description: str | None = None
        self.reference: str | None = None

        super().__init__(
            entry_class = LocationEntry, 
            id = id, 
            console_level = console_level)

        return
    
    @staticmethod
    async def fetch_all(col_name: str, value: int | str, *_, **__) -> Iterable[Location]:

        return await DatabaseMixin.fetch_all(
            col_name = col_name, 
            value = value,
            entry_class = LocationEntry,
            final_class = Location)

    async def create(self, 
        guild_id: int,
        name: str, 
        description: str | None = None,
        reference: str | None = None,
        interaction: Interaction | None = None,
        **_
    ) -> CommitResult:
        """Registers this location within the RP."""

        async def finalize() -> CommitResult:

            return await DatabaseMixin.create(
                self,
                guild_id = guild_id,
                name = name,
                description = description,
                reference = reference)

        if interaction is None or interaction.guild is None:
            return await finalize()

        new_loc_channel = await RelayableMixin.make_channel(
            category_name = "locations",
            channel_name = name,
            guild = interaction.guild)
        
        if new_loc_channel is None:
            return await finalize()
        
        self.id = new_loc_channel.id
        result = await finalize()
        
        if not description:
            embed_description = ("This location has no description" 
                " yet, but you can add one with `/review location`.")
            
        else:
            embed_description = ("This location has the following" 
                " description set, it'll be visible to players"
                " when they `/look` around in here: \n\n") + description
        
        embed, file = await image_embed(
            f"New Location: {name}",
            description = embed_description,
            footer = ("You can also set the reference photo that way." if 
                reference == "" else "Love what you've done with the place."),
            thumbnail = True,
            source = ImageSource.URL if reference else ImageSource.ASSET,
            asset_str = reference or "")
        
        server = RPServer(guild_id)
        await server.fetch()
        logging_channel = await server.get_logging_channel(guild = new_loc_channel.guild)
        await safe_log(embed, [new_loc_channel, logging_channel], silent = True, file = file)
        
        return result

    async def delete(self, 
        log_channel: TextChannel | None = None, 
        guild: Guild | None = None, **_
    ) -> CommitResult:
        
        result = await super().delete()

        await safe_del_channels([await self.get_channel(guild)], "Location deleted by user.")

        if guild is not None:

            server = RPServer(guild.id)
            await server.fetch()
            if await server.location_count == 0:

                loc_category = await server.get_category(
                    "locations",
                    guild = guild,
                    category_id = server.locations_cat,
                    make_if_needed = False)
                
                await safe_del_channels([loc_category], "No more locations remain in this RP.")
        
        if log_channel is None:
            return result
        
        embed, file = await image_embed(
            f"Location Deleted: {self.name}",
            ("Location removed by user. It no longer exists."
                "\n - If done through slash"
                " commands: please verify that the channel was"
                " deleted properly. Sometimes it can fail due to"
                " external factors or lack of permissions."
                "\n - If triggered by you deleting the location"
                " channel yourself: nothing more needs to be done."),
            "Feel free to make other locations in its stead!",
            thumbnail = True,
            source = ImageSource.URL if self.reference else ImageSource.ASSET,
            asset_str = self.reference or "")
        
        await safe_log(embed, [log_channel], silent = True, file = file)
        return result

    @property
    async def character_count(self) -> int:
        return await CharacterEntry.count("location_id", self.id)

class Character(DatabaseMixin, RelayableMixin):
    
    def __init__(self, id: int, console_level: int | None = None):

        self.id: int = id
        self.location_id: int | None = None
        self.guild_id: int | None = None
        self.eaves_target: int | None = None
        self.name: str | None = None
        self.description: str | None = None
        self.reference: str | None = None

        DatabaseMixin.__init__(
            self,
            entry_class = CharacterEntry, 
            id = id, 
            console_level = console_level)

        return
    
    @staticmethod
    async def fetch_all(col_name: str, value: int | str, *_, **__) -> Iterable[Character]:
        
        return await DatabaseMixin.fetch_all(
            col_name = col_name, 
            value = value,
            entry_class = CharacterEntry,
            final_class = Character)
    
# @dataclass(slots = True)
# class Character:
#     name: str
#     avatar: str
#     location_id: str
#     eavesdropping: bool

    