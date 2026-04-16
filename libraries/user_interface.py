"""Used for sending through Discord."""

from discord import ComponentType, Interaction, ChannelType, MISSING, \
    HTTPException, TextChannel, Forbidden, CategoryChannel
from discord.ui import View, Select, Button as ButtonInput, Modal, InputText
from discord.errors import NotFound
from discord import File, Embed, ButtonStyle, InputTextStyle
from aiohttp import ClientSession, ClientTimeout
from typing import Callable, Any
from io import BytesIO
from enum import IntEnum
from pathlib import Path
from abc import ABC, abstractmethod

#"Constants"
NO_AVATAR_URL = "https://i.imgur.com/A6qTjRc.jpeg"
ASSETS_DIR = Path().cwd() / "assets"
VALID_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"]

class ImageSource(IntEnum):
    ASSET = 0
    URL = 1
    BYTES = 2

def text_embed(
    title: str = "No Title", 
    description: str = "No description.", 
    footer: str = "No footer.",
    ) -> Embed:

    embed = Embed(
        title = title,
        description = description,
        color = 670869)
    embed.set_footer(text = footer)

    return embed

async def validate_url(url: str) -> bool:
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
    asset_str: str = "avatar.png",
    asset_bytes: BytesIO | None = None,
    ) -> tuple[Embed, File | None]:

    embed = text_embed(title, description, footer)
    file = None

    if source == ImageSource.ASSET and asset_str == "":
        return embed, file

    place_image = embed.set_thumbnail if thumbnail else embed.set_image

    if source == ImageSource.URL:

        if not await validate_url(asset_str):
            asset_str = NO_AVATAR_URL

        file = None
        place_image(url = asset_str)                # pyright: ignore[reportCallIssue]

    elif source == ImageSource.BYTES:

        if asset_bytes is None:
            raise ValueError("Forgot to pass in a byte image.")
        
        file = File(asset_bytes, filename = "image.png")
        place_image(url = "attachment://image.png")  # pyright: ignore[reportCallIssue]
        
    else:

        asset_path = ASSETS_DIR / asset_str

        if not asset_path.exists():
            asset_str = "bad_link.png"
        else:
            asset_str = str(asset_path)

        file = File(asset_str, filename = "image.png")
        place_image(url = "attachment://image.png")  # pyright: ignore[reportCallIssue]

    return embed, file

async def reference_validator(description: str, proposed_URL: str) -> tuple[str, str]:

    if proposed_URL == "":
        return description, ""

    description += "\n\nP.S. Took a look at the new reference URL, and it "
    valid_url = await validate_url(proposed_URL)

    if valid_url:
        description += "looks great."

    else:
        description += "doesn't seem to be a valid image. Try again maybe?"
        proposed_URL = ""

    return description, proposed_URL

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
        purpose: str = "",
        dialogue_callback: Callable,
        placeholder: str | None = None,
        min_values: int = 0):

        Select.__init__(self, 
            custom_id = purpose, 
            select_type = ComponentType.channel_select,
            channel_types = [ChannelType.text],
            placeholder = placeholder,
            min_values = min_values)
        DialogueMixin.__init__(self, field_name = label, callback_override = dialogue_callback)
        return
    
    def get_value(self) -> Any:
        return self.values[0].id if self.values is not None else None # pyright: ignore[reportAttributeAccessIssue]
    
    def is_valid(self) -> bool:
        selected_count = len(self.values) if self.values is not None else 0
        return self.min_values <= selected_count <= self.max_values

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
        
        matches = interaction.user.id == self.owner_id

        return matches
    
    async def on_timeout(self):
        
        if self.original_interaction:

            try:
                await self.original_interaction.edit_original_response(
                    content = "This dialogue has timed out. Feel free to call the command again.",
                    embed = None,
                    attachments= [],
                    view = None,
                    delete_after = 5)
            except NotFound, HTTPException:
                pass
        
        return

    async def refresh_children(self):

        for child in self.children:  

            if not isinstance(child, DialogueMixin):
                print(f"Warning: child {child} does not implement DialogueMixin. Skipping refresh.")
                continue

            await child.full_refresh()

        return

class Dialogue:

    def __init__(self, 
        starting_embed: Embed, 
        starting_file: File | None = None,
        disable_timeout: bool = False):

        self.view: DialogueView = DialogueView()

        if disable_timeout:
            self.view.timeout = None

        self.fields: dict[str, DialogueMixin] = {}

        self.current_embed = starting_embed
        self.previous_embed: Embed | None = starting_embed

        self.current_file = starting_file
        self.previous_file: File | None = starting_file

        return

    async def refresh(self, interaction: Interaction) -> None:

        kwargs = {}
        kwargs["view"] = self.view

        if self.current_embed != self.previous_embed:
            self.previous_embed = self.current_embed
            kwargs["embed"] = self.current_embed
        
        if self.current_file != self.previous_file:
            self.previous_file = self.current_file
            kwargs["file"] = self.current_file

            if self.current_file is MISSING:
                kwargs["attachments"] = []

        await self.view.refresh_children()
        try:
            await interaction.response.edit_message(**kwargs)
        except NotFound:
            await interaction.respond(
                "The original message has been deleted-- perhaps it timed out?"
                    " Please call the command again.", ephemeral = True)

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
                print(f"Warning: child {child} does not implement DialogueMixin. Skipping insert.")
                continue

            self.fields[child.field_name] = child

        return

    def add_channel_select(self, 
        label: str, 
        purpose: str = "", 
        placeholder: str | None = None,
        min_values: int = 0
    ) -> ChannelSelect:

        channel_select = ChannelSelect(
            label = label,
            purpose = purpose,
            placeholder = placeholder,
            dialogue_callback = self.refresh,
            min_values = min_values)
        
        self.view.add_item(channel_select)
        self.fields[channel_select.field_name] = channel_select

        return channel_select

    def add_close(self) -> Button:

        button = Button(
            label = "Close",
            preferred_style = ButtonStyle.secondary,
            dialogue_callback = self.close)
        self.view.add_item(button)

        return button
    
    async def close(self, interaction: Interaction):

        closed_embed = text_embed(
            title = "Closed.",
            description = "This will now delete itself. Feel free to call the command again.",
            footer = "Or don't, your call.")
        self.view.clear_items()
        
        await interaction.response.edit_message(
            embed = closed_embed, 
            view = self.view, 
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

    await interaction.response.send_message(**options)

    if view is not None:
        view.set_interaction(interaction)

    return

async def safe_log(
    embed: Embed, 
    channels: list[TextChannel | None], 
    silent: bool = True, **kwargs
) -> None:

    for chan in channels:

        if chan is None:
            continue

        try: 
            await chan.send(embed = embed, silent = silent, **kwargs)

        except HTTPException, Forbidden:
            pass

    return

async def safe_del_channels(
    channels: list[TextChannel | CategoryChannel | None],
    reason: str
) -> None:
    
    for chan in channels:

        if chan is None:
            continue
            
        try:
            await chan.delete(reason = reason)
        except Forbidden, HTTPException, NotFound:
            pass
    
    return

# class DialogueView(View):
#     refresh: Callable = ib(default = None)
#     should_disable_submit: Callable = ib(default = lambda: False)

#     # Interior
#     def __attrs_pre_init__(self):
#         super().__init__()
#         return

#     def __attrs_post_init__(self):
#         self.timeout = 120

#         self.created_components = set()

#         self.overwriting = False
#         self.clearing = False
#         self.directionality = 1
#         return

#     async def _call_refresh(self, interaction: Interaction):
#         embed, file = await self.refresh()
#         if 'submit' in self.created_components:
#             should_disable = self.should_disable_submit()
#             if self.submit.disabled != should_disable:
#                 self.submit.style = ButtonStyle.success
#                 self.submit.disabled = should_disable
#                 await interaction.response.edit_message(embed = embed, file = file, view = self)
#                 return
#         await interaction.response.edit_message(embed = embed, file = file)
#         return


#     async def _close(self, interaction: Interaction):

#         embed, _ = await mbd(
#             'Closed.',
#             "This will now delete itself.",
#             'Feel free to call the command again.')

#         await interaction.response.edit_message(
#             embed = embed,
#             attachments = [],
#             view = None,
#             delete_after = 5)
#         return



#     def people(self):
#         return self.people_select.values

#     async def add_characters(self, characters: dict, singular: bool = False, callback: Callable = None):

#         self._characters_dict = characters

#         if not characters:
#             self.character_select_textual = True
#             self.character_select = Select(
#                 placeholder = 'No characters to select.',
#                 disabled = True)
#             self.character_select.add_option(
#                 label = '_')
#             self.add_item(self.character_select)
#             return

#         if singular:
#             plurality = ''
#         else:
#             plurality = 's'

#         if len(characters) < 25:
#             self.character_select_textual = True

#             self.character_select = Select(
#                 select_type = ComponentType.string_select,
#                 placeholder = f'Which character{plurality}?',
#                 min_values = 0,
#                 max_values = 1 if singular else len(characters))
#             [self.character_select.add_option(label = name, value = str(ID)) for ID, name in characters.items()]

#         else:
#             self.character_select_textual = False

#             self.character_select = Select(
#                 select_type = ComponentType.channel_select,
#                 placeholder = f'Which character{plurality}?',
#                 min_values = 0,
#                 max_values = 1 if singular else 25,
#                 channel_types = [ChannelType.text])

#         self.character_select.callback = callback or self._call_refresh
#         self.add_item(self.character_select)
#         self.created_components.add('character_select')
#         return

#     def characters(self):
#         if self.character_select_textual:
#             return {int(ID) : self._characters_dict[int(ID)] for index, ID in enumerate(self.character_select.values)}

#         return {channel.id : self._characters_dict[channel.id] for channel in self.character_select.values if channel.id in self._characters_dict}

#     async def add_roles(self, singular: bool = False, callback: Callable = None):

#         self.role_select = Select(
#             placeholder = f"Which role{'' if singular else 's'}?",
#             select_type = ComponentType.role_select,
#             min_values = 0,
#             max_values = 25)

#         self.role_select.callback = callback or self._call_refresh
#         self.add_item(self.role_select)
#         self.created_components.add('role_select')
#         return

#     def roles(self):
#         return {role.id for role in self.role_select.values}

#     async def add_places(self, place_names: iter,  singular: bool = True, callback: Callable = None):

#         self.place_names = place_names

#         if not place_names:
#             self.place_select_textual = True
#             self.place_select = Select(
#                 placeholder = 'No places to select.',
#                 disabled = True)
#             self.place_select.add_option(
#                 label = '_')
#             self.add_item(self.place_select)
#             return

#         if singular:
#             plurality = ''
#         else:
#             plurality = 's'

#         if len(place_names) < 25:
#             self.place_select_textual = True

#             self.place_select = Select(
#                 select_type = ComponentType.string_select,
#                 placeholder = f'Which place{plurality}?',
#                 min_values = 0,
#                 max_values = 1 if singular else len(place_names))
#             [self.place_select.add_option(label = name) for name in place_names]

#         else:
#             self.place_select_textual = False

#             self.place_select = Select(
#                 select_type = ComponentType.channel_select,
#                 placeholder = f'Which place{plurality}?',
#                 min_values = 0,
#                 max_values = 1 if singular else 25,
#                 channel_types = [ChannelType.text])

#         self.place_select.callback = callback or self._call_refresh
#         self.add_item(self.place_select)
#         self.created_components.add('place_select')
#         return

#     def places(self):
#         if self.place_select_textual:
#             return self.place_select.values

#         return {channel.name for channel in self.place_select.values if channel.name in self.place_names}

#     async def add_paths(self, neighbors: dict, callback: Callable = None):

#         self.path_select = Select(
#             placeholder = 'Which path(s)?',
#             min_values = 0,
#             max_values = len(neighbors))
#         self.path_select.callback = callback or self._call_refresh

#         for neighbor, edge in neighbors.items():

#             match edge.directionality:

#                 case 0:
#                     self.path_select.add_option(label = f'<- {neighbor}',
#                         value = neighbor)

#                 case 1:
#                     self.path_select.add_option(label = f'<-> {neighbor}',
#                         value = neighbor)

#                 case 2:
#                     self.path_select.add_option(label = f'-> {neighbor}',
#                         value = neighbor)

#         self.add_item(self.path_select)
#         self.created_components.add('path_select')
#         return

#     def paths(self):
#         return self.path_select.values

#     # Modals
#     async def add_rename(self, existing: str = '', callback: Callable = None):

#         modal = Modal(title = 'Choose a new name?')

#         name_select = InputText(
#             label = 'name',
#             style = InputTextStyle.short,
#             min_length = 0,
#             max_length = 25,
#             placeholder = "What should it be?",
#             value = existing)
#         modal.add_item(name_select)
#         modal.callback = callback or self._call_refresh

#         async def send_modal(interaction: Interaction):
#             await interaction.response.send_modal(modal = modal)
#             return

#         modal_button = Button(
#             label = 'Change Name',
#             style = ButtonStyle.success)

#         modal_button.callback = send_modal
#         self.add_item(modal_button)
#         self.name_select = name_select
#         self.existing = existing
#         self.created_components.add('namer')
#         return

#     def name(self):

#         if 'namer' not in self.created_components:
#             return None

#         if self.name_select.value == self.existing:
#             return None

#         return self.name_select.value

#     async def add_URL(self, callback: Callable = None):

#         modal = Modal(title = 'Choose a new avatar?')

#         url_select = InputText(
#             label = 'url',
#             style = InputTextStyle.short,
#             min_length = 1,
#             max_length = 200,
#             placeholder = "What's the image URL?")
#         modal.add_item(url_select)
#         modal.callback = callback or self._call_refresh

#         async def send_modal(interaction: Interaction):
#             await interaction.response.send_modal(modal = modal)
#             return

#         modal_button = Button(
#             label = 'Change Avatar',
#             style = ButtonStyle.success)

#         modal_button.callback = send_modal
#         self.add_item(modal_button)
#         self.url_select = url_select
#         return

#     def url(self):
#         return self.url_select.value

#     #Buttons
#     async def add_submit(self, callback: callable):

#         submit = Button(
#             label = 'Submit',
#             style = ButtonStyle.secondary if self.should_disable_submit() else ButtonStyle.success)
#         submit.callback = callback
#         submit.disabled = self.should_disable_submit()
#         self.add_item(submit)
#         self.submit = submit
#         self.created_components.add('submit')
#         return

#     #Buttons
#     async def add_confirm(self, callback: callable):
#         confirm = Button(
#             label = 'Confirm',
#             style = ButtonStyle.danger)
#         confirm.callback = callback
#         self.add_item(confirm)
#         self.created_components.add('confirm')
#         return

#     async def add_clear(self, callback: Callable = None):
#         clear = Button(
#             label = 'Clear Whitelist',
#             style = ButtonStyle.secondary)

#         async def clearing(interaction: Interaction):
#             self.clearing = not self.clearing
#             if callback:
#                 await callback(interaction)
#             else:
#                 await self._call_refresh(interaction)
#             return

#         clear.callback = clearing
#         self.add_item(clear)
#         self.created_components.add('clear')
#         return

#     async def add_overwrite(self):
#         overwrite = Button(
#             label = 'Toggle Overwrite',
#             style = ButtonStyle.secondary)

#         async def overwriting(interaction: Interaction):
#             self.overwriting = not self.overwriting
#             await self._call_refresh(interaction)
#             return

#         overwrite.callback = overwriting
#         self.add_item(overwrite)
#         self.created_components.add('overwrite')
#         return

#     async def add_directionality(self):
#         directionality = Button(
#             label = 'Toggle Directionality',
#             style = ButtonStyle.secondary)

#         async def change_directionality(interaction: Interaction):

#             if self.directionality == 2:
#                 self.directionality = 0
#             else:
#                 self.directionality += 1

#             await self._call_refresh(interaction)
#             return

#         directionality.callback = change_directionality
#         self.add_item(directionality)
#         self.created_components.add('directionality')
#         return

#     async def add_cancel(self):

#         cancel = Button(
#             label = 'Cancel',
#             style = ButtonStyle.secondary)
#         cancel.callback = self._close
#         self.add_item(cancel)
#         return

#     #Methods
#     async def format_whitelist(self, components: iter):

#         if self.clearing:
#             return "\n• Whitelist: Removing all restrictions. Click 'Clear Whitelist' again" + \
#                 " to use the old whitelist, or if you select any roles or characters below, to use that."

#         if self.roles() or self.characters():
#             return "\n• New whitelist(s)-- will overwrite the old whitelist:" + \
#                 f" {await format_whitelist(self.roles(), self.characters())}"

#         first_component = next(iter(components), None)

#         if len(components) == 1:
#             return "\n• Whitelist:" + \
#                 f" {await format_whitelist(first_component.allowed_roles, first_component.allowed_characters)}"

#         if any(com.allowed_roles != first_component.allowed_roles or
#             com.allowed_characters != first_component.allowed_characters for com in components):
#             return '\n• Whitelists: Multiple different whitelists.'

#         return "\n• Whitelists: Every part has the same whitelist. " + \
#             await format_whitelist(first_component.allowed_roles,
#                 first_component.allowed_characters)
