"""Where most core functionality resides."""

from dataclasses import dataclass
from data.database_handler import ServerEntry, CommitResult

class RPServer:
    """Represents one server in the roleplay."""

    def __init__(self, id: int):

        self.id: int = id
        self.logging_channel_id: int | None = None
        self.name: str | None = None
        self.description: str | None = None
        self.reference: str | None = None

        return
    
    async def fetch(self) -> CommitResult:
        
        results = await ServerEntry.fetch(self.id)

        if results is None:
            return CommitResult.ROW_MISSING
        
        self.logging_channel_id, self.name, self.description, self.reference = results[1: ]
        return CommitResult.SUCCESS
    
    async def create(self, 
        logging_channel_id: int, 
        name: str, 
        description: str | None = None,
        reference: str | None = None
    ) -> CommitResult:
        """Registers this server as an RP one."""

        self.logging_channel_id = logging_channel_id
        self.name = name
        self.description = description
        self.reference = reference

        return await ServerEntry.create(
            self.id, 
            logging_channel_id, 
            name, 
            description, 
            reference)

    async def update(self,
        logging_channel_id: int | None = None, 
        name: str | None = None, 
        description: str | None = None,
        reference: str | None = None
    ) -> CommitResult:
        """Updates with current values. Returns True on success."""

        if logging_channel_id is not None:
            self.logging_channel_id = logging_channel_id

        if name is not None:
            self.name = name
        
        if description is not None:
            self.description = description if description else None

        if reference is not None:
            self.reference = reference if reference else None
        
        return await ServerEntry.update(
            self.id, 
            self.logging_channel_id, 
            self.name, 
            self.description, 
            self.reference)

    async def delete(self) -> CommitResult:
        return await ServerEntry.delete(self.id)

    @property
    async def exists(self) -> bool:
        """True if the server is in the database."""
        return await ServerEntry.exists(self.id)



# @dataclass(slots = True)
# class Character:
#     name: str
#     avatar: str
#     location_id: str
#     eavesdropping: bool

    