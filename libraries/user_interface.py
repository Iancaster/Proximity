"""Used for sending through Discord."""

from aiohttp import ClientSession, ClientTimeout
from typing import Callable, Any
from io import BytesIO
from enum import IntEnum
from pathlib import Path
from abc import ABC, abstractmethod

from discord import ComponentType, Interaction, ChannelType, MISSING, \
    HTTPException, TextChannel, Bot, SelectOption
from discord.ui import View, Select, Button as ButtonInput, Modal, InputText
from discord.abc import GuildChannel
from discord import File, Embed, ButtonStyle, InputTextStyle
from discord.utils import get_or_fetch

from config.cfg_parser import cfg
from libraries.logger import get_logger
from data.database_handler import _Unset, CommitResult

#"Constants"
NO_AVATAR_PFP = str(cfg("images", "no_pfp"))
LOGO = str(cfg("images", "logo"))
BAD_LINK = str(cfg("images", "bad_link"))
ASSETS_DIR = Path().cwd() / "assets"
VALID_IMAGE_TYPES = [
    "image/png", 
    "image/jpeg", 
    "image/jpg", 
    "image/webp", 
    "text/plain"] # I can't explain it but this image of Billy Bob proves the case
 # https://upload.wikimedia.org/wikipedia/commons/0/00/Billy_Bob_Thornton_2017_%28cropped%29.jpg

logger = get_logger("UI")

proximity: Bot | None = None

def set_bot(bot: Bot) -> None:
    global proximity
    proximity = bot
    return

def get_bot() -> Bot:
    global proximity
    assert proximity is not None, "Bot has not been initialized yet."
    return proximity

async def get_channel(channel_id: int | None | _Unset) -> GuildChannel | None:

    if channel_id is None:
        return None

    elif isinstance(channel_id, _Unset):
        return None

    return await get_or_fetch(get_bot(), "channel", channel_id, default = None)

class ImageSource(IntEnum):
    ASSET = 0
    URL = 1
    BYTES = 2

def ellipticize(string: str, max_length: int) -> str:
    
    if string == "":
        return "..."

    if len(string) <= max_length:
        return string

    else:
        return string[:max_length - 3] + "..."

def text_embed(
    title: str = "No Title", 
    description: str = "No description.", 
    footer: str = "No footer.",
    ) -> Embed:

    embed = Embed(
        title = ellipticize(title, max_length = 256),
        description = ellipticize(description, max_length = 4096),
        color = 670869)
    embed.set_footer(text = footer)

    return embed

async def _validate_url(url: str | None) -> bool:

    if url is None:
        return False
    
    # forgive me
    try:
        async with ClientSession() as session:
            async with session.head(url, timeout = ClientTimeout(5)) as response:
                content_type = response.headers.get("content-type") 
                return content_type in VALID_IMAGE_TYPES
            
    except Exception:
        return False

async def image_embed(
    title: str = "No Title", 
    description: str = "No description.", 
    footer: str = "No footer.",
    thumbnail: bool = True,
    source: ImageSource = ImageSource.ASSET,
    asset_str: str | None = "avatar.png",
    asset_bytes: BytesIO | None = None,
    ) -> tuple[Embed, File | None]:

    embed = text_embed(title, description, footer)
    file = None

    if source == ImageSource.ASSET and asset_str == "":
        return embed, file

    place_image = embed.set_thumbnail if thumbnail else embed.set_image

    if source == ImageSource.URL:

        if asset_str in [LOGO, BAD_LINK, NO_AVATAR_PFP, "", None]:
            asset_str = ""
        elif not await _validate_url(asset_str):
            asset_str = NO_AVATAR_PFP

        if asset_str:
            file = None
            place_image(url = asset_str)

    elif source == ImageSource.BYTES:

        if asset_bytes is None:
            raise ValueError("Forgot to pass in a byte image.")
        
        file = File(asset_bytes, filename = "image.png")
        place_image(url = "attachment://image.png")  # pyright: ignore[reportCallIssue]
        
    else:

        asset_path = ASSETS_DIR / (asset_str if asset_str is not None else "")

        if not asset_path.exists():
            asset_str = "bad_link.png"
        else:
            asset_str = str(asset_path)

        file = File(asset_str, filename = "image.png")
        place_image(url = "attachment://image.png")  # pyright: ignore[reportCallIssue]

    return embed, file

async def reference_validator(proposed_URL: str) -> CommitResult:

    if proposed_URL == "":
        return CommitResult.NO_UPDATE

    if not await _validate_url(proposed_URL):
        return CommitResult.FOREIGN_KEY_FAIL

    return CommitResult.SUCCESS

def oxfordize(words: list, prefix: str = "", suffix: str = "") -> str:

    if not words:
        return "None."

    if len(words) == 1:
        return f"{prefix}{words[0]}{suffix}"

    if len(words) == 2:
        return f"{prefix}{words[0]}{suffix} and {prefix}{words[1]}{suffix}"

    return ", ".join(f"{prefix}{item}{suffix}" for item in words[:-1]) + \
        f", and {prefix}{words[-1]}{suffix}"

class DialogueMixin(ABC):

    def __init__(self, 
        field_name: str = "Not set!", 
        callback_override: Callable | None = None):

        self.field_name: str = field_name
        if callback_override is not None:
            self.callback = callback_override

        return

    @abstractmethod
    def get_value(self) -> Any:
        ...

    def refresh(self) -> None:
        ...
        
    def should_disable(self) -> bool:
        return False

    def is_valid(self) -> bool:
        return True
    
    async def full_refresh(self) -> None:

        self.disabled = self.should_disable()
        self.refresh()

        return

class UserSelect(Select, DialogueMixin):
    
    def __init__(self, *, 
        purpose: str = "", 
        min_values: int = 1, 
        max_values: int = 1, 
        callback: Callable | None = None):
        
        plurality = "a user" if min_values == 1 else f"{max_values} users" 

        Select.__init__(
            self,
            placeholder = f"Select {plurality}{purpose}.",
            select_type = ComponentType.user_select,
            min_values = min_values,
            max_values = max_values)
        DialogueMixin.__init__(self, field_name = purpose, callback_override = callback)
            
        return

    def get_value(self) -> Any:
        return self.values

class Button(ButtonInput, DialogueMixin):

    def __init__(self, *, 
        label: str, 
        preferred_style: ButtonStyle = ButtonStyle.primary, 
        dialogue_callback: Callable):

        ButtonInput.__init__(self, custom_id = label, label = label, style = preferred_style)
        DialogueMixin.__init__(self, field_name = label, callback_override = dialogue_callback)
        self.preferred_style = preferred_style
        return
    
    def refresh(self):
        self.style = ButtonStyle.secondary if self.disabled else self.preferred_style 
        return
    
    def get_value(self) -> Any:
        return None
    
class ChannelSelect(Select, DialogueMixin):

    def __init__(self, *, 
        label: str,
        purpose: str | None = None,
        dialogue_callback: Callable,
        placeholder: str | None = None,
        min_values: int = 0,
        max_values: int = 1):

        Select.__init__(self, 
            custom_id = purpose, 
            select_type = ComponentType.channel_select,
            channel_types = [ChannelType.text],
            placeholder = placeholder,
            min_values = min_values,
            max_values = max_values)
        DialogueMixin.__init__(self, field_name = label, callback_override = dialogue_callback)
        return
    
    def get_value(self) -> Any:
        return self.values[0].id if self.values is not None else None

    def get_channel_ids(self) -> list[int]:
        return [val.id for val in self.values]
    
    def is_valid(self) -> bool:
        selected_count = len(self.values) if self.values is not None else 0
        return self.min_values <= selected_count <= self.max_values

    @property
    def values(self) -> list[GuildChannel]: # pyright: ignore[reportIncompatibleMethodOverride]
        return super().values # pyright: ignore[reportReturnType]

class TextSelect(Select, DialogueMixin):

    def __init__(self, *, 
        label: str,
        purpose: str | None = None,
        dialogue_callback: Callable,
        options: list[SelectOption],
        placeholder: str | None = None,
        min_values: int = 0,
        max_values: int = 1):

        Select.__init__(self, 
            custom_id = purpose, 
            select_type = ComponentType.string_select,
            options = options,
            placeholder = placeholder,
            min_values = min_values,
            max_values = max_values)
        DialogueMixin.__init__(self, field_name = label, callback_override = dialogue_callback)
        return
    
    def get_value(self) -> Any:
        return self.values[0] if self.values is not None else None
    
    def is_valid(self) -> bool:
        selected_count = len(self.values) if self.values is not None else 0
        return self.min_values <= selected_count <= self.max_values

    @property
    def values(self) -> list[SelectOption]: # pyright: ignore[reportIncompatibleMethodOverride]
        return super().values # pyright: ignore[reportReturnType]

class TextField(InputText, DialogueMixin):

    def __init__(self, *, 
        label: str, 
        placeholder: str | None = None, 
        min_length: int | None = None, 
        max_length: int | None = None, 
        required: bool | None = True, 
        value: str | None = None,
        style: InputTextStyle = InputTextStyle.short):

        InputText.__init__(
            self,
            label = label,
            placeholder = placeholder,
            min_length = min_length,
            max_length = max_length,
            required = required,
            value = value,
            style = style)
        DialogueMixin.__init__(self, field_name = label)

        return
    
    def get_value(self) -> Any:
        return self.value
    
    def is_valid(self) -> bool:

        if not self.required:
            return True
        
        return bool(self.value)
    
class Popup(Modal):

    def add_text(self, 
        label: str, 
        placeholder: str | None = None, 
        min_length: int | None = None, 
        max_length: int | None = None, 
        required: bool = True, 
        value: str | None = None,
        style: InputTextStyle = InputTextStyle.short
        ) -> TextField:

        text_field = TextField(
            label = label,
            placeholder = placeholder,
            min_length = min_length,
            max_length = max_length,
            required = required,
            value = value,
            style = style)
        
        self.add_item(text_field)

        return text_field
    
class DialogueView(View):

    logger = get_logger("Dialogue View")

    timeout_embed = text_embed(
        "Timed out.",
        "Interactions generally time out after thirty seconds of inactivity. Feel free to call the command again!",
        "This message will self-destruct in five seconds. Five...four...")

    def __init__(self, *, timeout: float = 30):
    
        super().__init__(timeout = timeout)
        self.owner_id: int | None = None
        self.original_interaction: Interaction | None = None
        self.fields: list[DialogueMixin] = []
        
        return
    
    def set_interaction(self, interaction: Interaction):
        
        self.original_interaction = interaction
        if interaction.user:
            self.owner_id = interaction.user.id
        
        return

    async def interaction_check(self, interaction: Interaction) -> bool:
        
        if not interaction.user:
            return False
        
        return interaction.user.id == self.owner_id
    
    async def on_timeout(self):
        
        if self.original_interaction:

            try:
                await self.original_interaction.edit_original_response(
                    content = "This dialogue has timed out. Feel free to call the command again.",
                    attachments = [],
                    view = None,
                    suppress = True,
                    delete_after = 5)
                
            except HTTPException:
                pass
        
        return

    async def refresh_children(self):

        for child in self.children:  

            if not isinstance(child, DialogueMixin):
                
                self.logger.warning(f"Warning: child {child} does not implement" + 
                    f" DialogueMixin in {self.original_interaction.guild_id}." +  # pyright: ignore[reportOptionalMemberAccess]
                    f" for message {self.original_interaction.message.id}." +  # pyright: ignore[reportOptionalMemberAccess]
                    " Skipping refresh.")
                
                continue

            await child.full_refresh()

        return

    @property
    def has_changed(self) -> bool:
        return any(field.get_value() for field in self.fields)
 
class Dialogue:

    logger = get_logger("Dialogue")

    def __init__(self, 
        starting_embed: Embed, 
        starting_file: File | None = None,
        disable_timeout: bool = False):

        self.view: DialogueView = DialogueView()

        if disable_timeout:
            self.view.timeout = None

        self.fields: dict[str, DialogueMixin] = {}

        self.current_embed = starting_embed
        self._previous_embed: Embed | None = starting_embed

        self.current_file = starting_file
        self._previous_file: File | None = starting_file

        return

    async def refresh(self, interaction: Interaction) -> None:

        options = {}
        options["view"] = self.view

        if self.current_embed != self._previous_embed:
            self._previous_embed = self.current_embed
            options["embed"] = self.current_embed
        
        if self.current_file != self._previous_file:
            self._previous_file = self.current_file

            if self.current_file is not None:
                options["file"] = self.current_file

            if self.current_file in (MISSING, None):
                options["attachments"] = []

        await self.view.refresh_children()

        try:

            if interaction.response.is_done():
                await interaction.edit_original_response(**options)
            else:
                await interaction.response.edit_message(**options)
        
        except HTTPException:

            try:
                await interaction.respond(
                    "The original message has been deleted-- perhaps it timed out?"
                        " Please call the command again.", 
                    ephemeral = True)
                
            except HTTPException:
                pass

        return

    def add_button(self, label: str, style: ButtonStyle = ButtonStyle.primary) -> Button:

        button = Button(
            label = label, 
            preferred_style = style, 
            dialogue_callback = self.refresh)
        
        self.view.add_item(button)
        self.fields[button.field_name] = button

        return button

    def add_modal(self, popup: Modal, button: Button) -> None:

        async def send_modal(interaction: Interaction):
            await self.view.refresh_children()
            await interaction.response.send_modal(modal = popup)
            return

        button.callback = send_modal
        popup.callback = self.refresh 

        for child in popup.children:

            if not isinstance(child, DialogueMixin):
                
                self.logger.warning(f"Warning: child {child} does not" + \
                    " implement DialogueMixin. Skipping insert.")
                
                continue

            self.fields[child.field_name] = child

        return

    def add_channel_select(self, 
        label: str, 
        purpose: str | None = None, 
        placeholder: str | None = None,
        min_values: int = 0,
        max_values: int = 1
    ) -> ChannelSelect:

        channel_select = ChannelSelect(
            label = label,
            purpose = purpose,
            placeholder = placeholder,
            dialogue_callback = self.refresh,
            min_values = min_values,
            max_values = max_values)
        
        self.view.add_item(channel_select)
        channel_select.callback = self.refresh
        self.add_field(channel_select)

        return channel_select

    def add_text_select(self, 
        label: str, 
        text_options: list[SelectOption],
        purpose: str | None = None, 
        placeholder: str | None = None,
        min_values: int = 0,
        max_values: int = 1
    ) -> TextSelect:

        text_select = TextSelect(
            label = label,
            purpose = purpose,
            placeholder = placeholder,
            dialogue_callback = self.refresh,
            options = text_options,
            min_values = min_values,
            max_values = max_values)
        
        self.view.add_item(text_select)
        text_select.callback = self.refresh
        self.add_field(text_select)

        return text_select

    def add_close(self) -> Button:

        button = Button(
            label = "Close",
            preferred_style = ButtonStyle.secondary,
            dialogue_callback = self.close)
        self.view.add_item(button)

        return button
    
    def add_field(self, field) -> None:
        self.fields[field.field_name] = field
        return

    async def close(self, interaction: Interaction):

        closed_embed = text_embed(
            title = "Closed.",
            description = "This will now delete itself. Feel free to call the command again.",
            footer = "Or don't, your call.")
        self.view.clear_items()
        
        await interaction.response.edit_message(
            embed = closed_embed, 
            view = self.view, 
            attachments = [],
            delete_after = 3)
        
        return

    @property
    def is_valid(self) -> bool:
        return all(item.is_valid() for item in self.fields.values())

async def send_message(
    interaction: Interaction, 
    embed: Embed | None = None, 
    view: DialogueView | None = None, 
    file: File | None = None, 
    **options
    ) -> None:
    
    if view is not None:
        options["view"] = view

    if embed is not None:
        options["embed"] = embed

    if file is not None:
        options["file"] = file

    if interaction.response.is_done():
        options.pop("ephemeral", None)
        await interaction.edit_original_response(**options)
    else:
        await interaction.response.send_message(**options)

    if view is not None:
        view.set_interaction(interaction)

    return

async def safe_send(
    embed: Embed, 
    channels: list[GuildChannel | int | None], 
    silent: bool = True, 
    **kwargs
) -> None:

    for chan in channels:

        if isinstance(chan, int):
            chan = await get_or_fetch(get_bot(), "channel", chan, default = None)

        if not isinstance(chan, TextChannel):
            continue

        try: 
            await chan.send(embed = embed, silent = silent, **kwargs)

        except HTTPException:
            logger.warning(f"Failed to send message to channel {chan.id}.")

    return

async def safe_del_channel(
    channel: GuildChannel | int | None,
    reason: str
) -> CommitResult:

    if channel is None:
        return CommitResult.NO_UPDATE

    if isinstance(channel, int):
        channel = await get_channel(channel)

    if channel is None:
        return CommitResult.ROW_MISSING

    try:
        await channel.delete(reason = reason)
        
    except HTTPException:
        logger.warning(f"Failed to delete channel {channel.id}.")
        return CommitResult.UNKNOWN_ERR

    return CommitResult.SUCCESS

async def safe_del_channels(
    channels: list[GuildChannel | int | None],
    reason: str
) -> None:
    
    for chan in channels:
        await safe_del_channel(chan, reason)

    return
