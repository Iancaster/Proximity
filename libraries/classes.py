"""Where most core functionality resides."""

from discord import ApplicationContext, TextChannel
from data.database_handler import DatabaseMixin, ServerEntry, CommitResult

async def in_text_channel(ctx: ApplicationContext) -> bool:

    if not isinstance(ctx.channel, TextChannel):
        await ctx.respond("Please call this command only from a standard text channel.", ephemeral = True)
        return False
    
    return True

async def is_administrator(ctx: ApplicationContext) -> bool:
    
    if not ctx.channel.permissions_for(ctx.author).administrator:
        await ctx.respond("To prevent abuse, only server administrators may use this command.", ephemeral = True)
        return False

    return True

class RPServer(DatabaseMixin):
    """Represents one server in the roleplay."""

    def __init__(self, id: int, console_level: int | None = None):

        self.log_channel_id: int | None = None
        self.name: str | None = None
        self.description: str | None = None
        self.reference: str | None = None

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
        **_
    ) -> CommitResult:
        """Registers this server as an RP one."""

        return await super().create(
            log_channel_id = log_channel_id,
            name = name,
            description = description,
            reference = reference)

    async def update(self,
        log_channel_id: int | None = None, 
        name: str | None = None, 
        description: str | None = None,
        reference: str | None = None,
        **_
    ) -> CommitResult:
        """Updates with current values. Returns True on success."""

        return await super().update(
            logging_channel_id = log_channel_id,
            name = name,
            description = description,
            reference = reference)

class Location:

    def __init__(self, id: int):

        self.id: int = id
        self.guild_id: int | None = None
        self.name: str | None = None
        self.description: str | None = None
        self.reference: str | None = None

        return
    



# @dataclass(slots = True)
# class Character:
#     name: str
#     avatar: str
#     location_id: str
#     eavesdropping: bool

    