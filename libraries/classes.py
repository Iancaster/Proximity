

#Import-ant Libraries
from discord import Guild, PermissionOverwrite, Interaction, \
	ComponentType, InputTextStyle, ButtonStyle, TextChannel, \
	ChannelType, CategoryChannel
from discord.errors import NotFound
from discord.utils import get, get_or_fetch
from discord.ui import View, Select, Button, Modal, InputText

from libraries.universal import mbd
from libraries.formatting import format_whitelist
from data.listeners import direct_listeners, indirect_listeners, \
	remove_speaker

#Data Libraries
from attr import s, ib, Factory
from sqlite3 import connect
from base64 import b64encode, b64decode
from pickle import loads, dumps
from io import BytesIO
from os import getcwd
from os.path import join

#Math Libraries
from networkx import DiGraph, ego_graph, draw_networkx_nodes, \
	draw_networkx_edges, shell_layout, draw_networkx_labels
from math import sqrt
from matplotlib.pyplot import margins, gcf, tight_layout, axis, close
from matplotlib.patches import ArrowStyle

#Graph
@s(auto_attribs = True)
class Component:
	allowed_roles: set = Factory(set)
	allowed_characters: set = Factory(set)

	async def set_roles(self, role_IDs: set):
		self.allowed_roles = role_IDs
		return

	async def set_characters(self, characters_IDs: set):
		self.allowed_characters = characters_IDs
		return

	async def clear_whitelist(self):
		self.allowed_roles = set()
		self.allowed_characters = set()
		return

	async def __dict__(self):
		return_dict = {}

		if self.allowed_roles:
			return_dict['allowed_roles'] = self.allowed_roles

		if self.allowed_characters:
			return_dict['allowed_characters'] = self.allowed_characters

		return return_dict

@s(auto_attribs = True)
class Path(Component):
	"""
	For the sake of anyone reading this, a directionality > 0
	means it's going TO the destination, while directionality < 2
	means it's coming FROM the target. < /  -  / >
	"""

	directionality: int = ib(default = 1)

	async def __dict__(self):
		return_dict = await super().__dict__()
		return_dict['directionality'] = self.directionality
		return return_dict

@s(auto_attribs = True)
class Location(Component):
	channel_ID: int = ib(default = 0)
	occupants: dict = Factory(dict)
	neighbors: dict = Factory(dict)

	def __attrs_post_init__(self):

		if not self.neighbors:
			return

		self.neighbors = {name : Path(
			directionality = data['directionality'],
			allowed_roles = data.get('allowed_roles', set()),
			allowed_characters = data.get('allowed_characters', set()))
				for name, data in self.neighbors.items()}

		return

	async def add_occupants(self, occupants: dict):
		return self.occupants.update(occupants)

	async def remove_occupants(self, occupants: dict):
		self.occupants = {occ_ID : occ_name for occ_ID, occ_name in self.occupants.items() if occ_ID not in occupants}
		return

	async def __dict__(self):
		return_dict = await super().__dict__()
		return_dict['channel_ID'] = self.channel_ID

		if self.occupants:
			return_dict['occupants'] = self.occupants

		if self.neighbors:
			neighbors_dict = {}
			for neighbor, path in self.neighbors.items():
				neighbors_dict[neighbor] = await path.__dict__()

			return_dict['neighbors'] = neighbors_dict

		return return_dict


#Server
@s(auto_attribs = True)
class DialogueView(View):
	refresh: callable = ib(default = None)
	should_disable_submit: callable = ib(default = lambda: False)

	#Interior
	def __attrs_pre_init__(self):
		super().__init__()
		return

	def __attrs_post_init__(self):
		self.timeout = 120

		self.created_components = set()

		self.overwriting = False
		self.clearing = False
		self.directionality = 1
		return

	async def _call_refresh(self, interaction: Interaction):
		embed, file = await self.refresh()
		if 'submit' in self.created_components:
			should_disable = self.should_disable_submit()
			if self.submit.disabled != should_disable:
				self.submit.style = ButtonStyle.success
				self.submit.disabled = should_disable
				await interaction.response.edit_message(embed = embed, file = file, view = self)
				return
		await interaction.response.edit_message(embed = embed, file = file)
		return

	async def on_timeout(self):

		if not self.message:
			raise TimeoutError('View.message returned None and could not time-out properly!')
			return

		embed, _ = await mbd(
			'Timed out.',
			"This window closed since it hasn't been in use." +
				" It'll delete itself in about 15 seconds.",
			'Feel free to call the command again.')

		try:
			await self.message.edit(
				embed = embed,
				attachments = [],
				view = None)
			await self.message.delete(delay = 15)
		except NotFound:
			pass

		return

	async def _close(self, interaction: Interaction):

		embed, _ = await mbd(
			'Closed.',
			"This will now delete itself.",
			'Feel free to call the command again.')

		await interaction.response.edit_message(
			embed = embed,
			attachments = [],
			view = None,
			delete_after = 5)
		return

	#Selects
	async def add_people(self, singular: bool = False, callback: callable = None):

		plurality = 'person' if singular else 'people'

		self.people_select = Select(
			placeholder = f'Which {plurality}?',
			select_type = ComponentType.user_select,
			min_values = 0,
			max_values = 25)

		self.people_select.callback = callback or self._call_refresh

		self.add_item(self.people_select)
		return

	def people(self):
		return self.people_select.values

	async def add_characters(self, characters: dict, singular: bool = False, callback: callable = None):

		self._characters_dict = characters

		if not characters:
			self.character_select_textual = True
			self.character_select = Select(
				placeholder = 'No characters to select.',
				disabled = True)
			self.character_select.add_option(
				label = '_')
			self.add_item(self.character_select)
			return

		if singular:
			plurality = ''
		else:
			plurality = 's'

		if len(characters) < 25:
			self.character_select_textual = True

			self.character_select = Select(
				select_type = ComponentType.string_select,
				placeholder = f'Which character{plurality}?',
				min_values = 0,
				max_values = 1 if singular else len(characters))
			[self.character_select.add_option(label = name, value = str(ID)) for ID, name in characters.items()]

		else:
			self.character_select_textual = False

			self.character_select = Select(
				select_type = ComponentType.channel_select,
				placeholder = f'Which character{plurality}?',
				min_values = 0,
				max_values = 1 if singular else 25,
				channel_types = [ChannelType.text])

		self.character_select.callback = callback or self._call_refresh
		self.add_item(self.character_select)
		self.created_components.add('character_select')
		return

	def characters(self):
		if self.character_select_textual:
			return {int(ID) : self._characters_dict[int(ID)] for index, ID in enumerate(self.character_select.values)}

		return {channel.id : self._characters_dict[channel.id] for channel in self.character_select.values if channel.id in self._characters_dict}

	async def add_roles(self, singular: bool = False, callback: callable = None):

		self.role_select = Select(
			placeholder = f"Which role{'' if singular else 's'}?",
			select_type = ComponentType.role_select,
			min_values = 0,
			max_values = 25)

		self.role_select.callback = callback or self._call_refresh
		self.add_item(self.role_select)
		self.created_components.add('role_select')
		return

	def roles(self):
		return {role.id for role in self.role_select.values}

	async def add_places(self, place_names: iter,  singular: bool = True, callback: callable = None):

		self.place_names = place_names

		if not place_names:
			self.place_select_textual = True
			self.place_select = Select(
				placeholder = 'No places to select.',
				disabled = True)
			self.place_select.add_option(
				label = '_')
			self.add_item(self.place_select)
			return

		if singular:
			plurality = ''
		else:
			plurality = 's'

		if len(place_names) < 25:
			self.place_select_textual = True

			self.place_select = Select(
				select_type = ComponentType.string_select,
				placeholder = f'Which place{plurality}?',
				min_values = 0,
				max_values = 1 if singular else len(place_names))
			[self.place_select.add_option(label = name) for name in place_names]

		else:
			self.place_select_textual = False

			self.place_select = Select(
				select_type = ComponentType.channel_select,
				placeholder = f'Which place{plurality}?',
				min_values = 0,
				max_values = 1 if singular else 25,
				channel_types = [ChannelType.text])

		self.place_select.callback = callback or self._call_refresh
		self.add_item(self.place_select)
		self.created_components.add('place_select')
		return

	def places(self):
		if self.place_select_textual:
			return self.place_select.values

		return {channel.name for channel in self.place_select.values if channel.name in self.place_names}

	async def add_paths(self, neighbors: dict, callback: callable = None):

		self.path_select = Select(
			placeholder = 'Which path(s)?',
			min_values = 0,
			max_values = len(neighbors))
		self.path_select.callback = callback or self._call_refresh

		for neighbor, edge in neighbors.items():

			match edge.directionality:

				case 0:
					self.path_select.add_option(label = f'<- {neighbor}',
						value = neighbor)

				case 1:
					self.path_select.add_option(label = f'<-> {neighbor}',
						value = neighbor)

				case 2:
					self.path_select.add_option(label = f'-> {neighbor}',
						value = neighbor)

		self.add_item(self.path_select)
		self.created_components.add('path_select')
		return

	def paths(self):
		return self.path_select.values

	#Modals
	async def add_rename(self, existing: str = '', callback: callable = None):

		modal = Modal(title = 'Choose a new name?')

		name_select = InputText(
			label = 'name',
			style = InputTextStyle.short,
			min_length = 0,
			max_length = 25,
			placeholder = "What should it be?",
			value = existing)
		modal.add_item(name_select)
		modal.callback = callback or self._call_refresh

		async def send_modal(interaction: Interaction):
			await interaction.response.send_modal(modal = modal)
			return

		modal_button = Button(
			label = 'Change Name',
			style = ButtonStyle.success)

		modal_button.callback = send_modal
		self.add_item(modal_button)
		self.name_select = name_select
		self.existing = existing
		self.created_components.add('namer')
		return

	def name(self):

		if 'namer' not in self.created_components:
			return None

		if self.name_select.value == self.existing:
			return None

		return self.name_select.value

	async def add_URL(self, callback: callable = None):

		modal = Modal(title = 'Choose a new avatar?')

		url_select = InputText(
			label = 'url',
			style = InputTextStyle.short,
			min_length = 1,
			max_length = 200,
			placeholder = "What's the image URL?")
		modal.add_item(url_select)
		modal.callback = callback or self._call_refresh

		async def send_modal(interaction: Interaction):
			await interaction.response.send_modal(modal = modal)
			return

		modal_button = Button(
			label = 'Change Avatar',
			style = ButtonStyle.success)

		modal_button.callback = send_modal
		self.add_item(modal_button)
		self.url_select = url_select
		return

	def url(self):
		return self.url_select.value

	#Buttons
	async def add_submit(self, callback: callable):

		submit = Button(
			label = 'Submit',
			style = ButtonStyle.secondary if self.should_disable_submit() else ButtonStyle.success)
		submit.callback = callback
		submit.disabled = self.should_disable_submit()
		self.add_item(submit)
		self.submit = submit
		self.created_components.add('submit')
		return

	#Buttons
	async def add_confirm(self, callback: callable):
		confirm = Button(
			label = 'Confirm',
			style = ButtonStyle.danger)
		confirm.callback = callback
		self.add_item(confirm)
		self.created_components.add('confirm')
		return

	async def add_clear(self, callback: callable = None):
		clear = Button(
			label = 'Clear Whitelist',
			style = ButtonStyle.secondary)

		async def clearing(interaction: Interaction):
			self.clearing = not self.clearing
			if callback:
				await callback(interaction)
			else:
				await self._call_refresh(interaction)
			return

		clear.callback = clearing
		self.add_item(clear)
		self.created_components.add('clear')
		return

	async def add_overwrite(self):
		overwrite = Button(
			label = 'Toggle Overwrite',
			style = ButtonStyle.secondary)

		async def overwriting(interaction: Interaction):
			self.overwriting = not self.overwriting
			await self._call_refresh(interaction)
			return

		overwrite.callback = overwriting
		self.add_item(overwrite)
		self.created_components.add('overwrite')
		return

	async def add_directionality(self):
		directionality = Button(
			label = 'Toggle Directionality',
			style = ButtonStyle.secondary)

		async def change_directionality(interaction: Interaction):

			if self.directionality == 2:
				self.directionality = 0
			else:
				self.directionality += 1

			await self._call_refresh(interaction)
			return

		directionality.callback = change_directionality
		self.add_item(directionality)
		self.created_components.add('directionality')
		return

	async def add_cancel(self):

		cancel = Button(
			label = 'Cancel',
			style = ButtonStyle.secondary)
		cancel.callback = self._close
		self.add_item(cancel)
		return

	#Methods
	async def format_whitelist(self, components: iter):

		if self.clearing:
			return "\n• Whitelist: Removing all restrictions. Click 'Clear Whitelist' again" + \
				" to use the old whitelist, or if you select any roles or characters below, to use that."

		if self.roles() or self.characters():
			return "\n• New whitelist(s)-- will overwrite the old whitelist:" + \
				f" {await format_whitelist(self.roles(), self.characters())}"

		first_component = next(iter(components))

		if len(components) == 1:
			return "\n• Whitelist:" + \
				f" {await format_whitelist(first_component.allowed_roles, first_component.allowed_characters)}"

		if any(com.allowed_roles != first_component.allowed_roles or
			com.allowed_characters != first_component.allowed_characters for com in components):
			return '\n• Whitelists: Multiple different whitelists.'

		return "\n• Whitelists: Every part has the same whitelist. " + \
			await format_whitelist(first_component.allowed_roles,
				first_component.allowed_characters)

@s(auto_attribs = True)
class ChannelMaker:
	guild: Guild
	category_name: str = ib(default = '')

	def __attrs_post_init__(self):

		with open(join(getcwd(), 'assets', 'avatar.png'), 'rb') as file:
			self.avatar = file.read()

	async def initialize(self):

		self_member = await get_or_fetch(self.guild, 'member', 1161017761888219228)

		self.permissions = {
			self.guild.default_role:
				PermissionOverwrite(read_messages = False),
			self_member : PermissionOverwrite(
				send_messages = True,
				read_messages = True,
				manage_channels = True)}

		existing_category = get(self.guild.categories, name = self.category_name)
		if existing_category:
			self.category = existing_category
			return

		found_category = [channel for channel in await self.guild.fetch_channels() if
			channel.name == self.category_name and isinstance(channel, CategoryChannel)]
		if found_category:
			self.category = found_category[0]
			return

		self.category = await self.guild.create_category(self.category_name, overwrites = self.permissions)
		return

	async def create_channel(self, name: str, people: iter = []):

		for person in people:
			self.permissions[person] = PermissionOverwrite(
				send_messages = True,
				read_messages = True)

		new_channel = await self.guild.create_text_channel(name, category = self.category, overwrites = self.permissions)
		await new_channel.create_webhook(name = 'Proximity', avatar = self.avatar)
		return new_channel

#Data
@s(auto_attribs = True)
class GuildData:
	guild_ID: int
	load_places: bool = ib(default = False)
	load_characters: bool = ib(default = False)
	load_roles: bool = ib(default = False)
	load_settings: bool = ib(default = False)
	direct_listeners: dict = ib(direct_listeners)
	indirect_listeners: dict = ib(indirect_listeners)

	def __attrs_post_init__(self):

		def return_dictionary(cursor, data):
			fields = [column[0] for column in cursor.description]
			return {column : data for column, data in zip(fields, data)}

		guild_con = connect(join(getcwd(), 'data', 'guild.db'))
		guild_con.row_factory = return_dictionary
		cursor = guild_con.cursor()

		cursor.execute("SELECT * FROM guilds WHERE guild_ID = ? LIMIT 1", (self.guild_ID,))
		guild_data = cursor.fetchone()
		guild_con.close()

		self.places = dict()
		self.characters = dict()
		self.roles = set()

		self.view_distance = 99
		self.map_override = None
		self.visibility = 'private'
		self.peephole = True
		self.eavesdropping_allowed = True

		self.first_boot = not guild_data

		if self.first_boot:
			return

		if self.load_places:

			decoded_places = b64decode(guild_data['places'])
			places_dict = loads(decoded_places)

			for name, place_data in places_dict.items():
				self.places[name] = Location(
					channel_ID = place_data['channel_ID'],
					occupants = place_data.get('occupants', set()),
					allowed_roles = place_data.get('allowed_roles', set()),
					allowed_characters = place_data.get('allowed_characters', set()),
					neighbors = place_data.get('neighbors', dict()))

		if self.load_characters:
			decoded_chars = b64decode(guild_data['characters'])
			self.characters = loads(decoded_chars)

		if self.load_roles:
			self.roles = {int(role_ID) for role_ID in guild_data['roles'].split()}

		if self.load_settings:
			decoded_settings = b64decode(guild_data['settings'])
			settings_dict = loads(decoded_settings)

			self.view_distance = settings_dict.get('view_distance', 99)
			self.map_override = settings_dict.get('map_override', None)
			self.visibility = settings_dict.get('visibility', 'private')
			self.eavesdropping_allowed = settings_dict.get('eavesdropping', True)
			self.peephole = settings_dict.get('peephole', True)

		return

	#Places
	async def create_place(self, name: str, channel_ID: int, role_IDs: iter = set(), char_IDs: iter = set()):

		if name in self.places:
			raise KeyError('Place already exists, no overwriting!')
			return

		self.places[name] = Location(
			channel_ID = channel_ID,
			allowed_characters = char_IDs,
			allowed_roles = role_IDs)

		return

	async def delete_place(self, name: str):

		if name not in self.places:
			raise KeyError('Tried to delete a nonexistent place!')
			return

		condemned_place = self.places.pop(name)

		for role in condemned_place.allowed_roles:

			if not any(role in place.allowed_roles for place in self.places.values()):
				self.roles.discard(role)

		for neighbor_place_name in condemned_place.neighbors.keys():
			await self.delete_path(name, neighbor_place_name)

		return

	async def filter_places(self, place_names: iter):
		return {name : self.places[name] for name in place_names}

	async def get_occupants(self, places: dict = None):
		places = places if places else self.places
		return {occ_ID for place in places for occ_ID in place.occupants}

	async def accessible_locations(self, role_IDs: iter, char_ID: int, origin: str):

		graph = DiGraph()

		accessible_places = set()
		inaccessible_places = set()

		for name, place in self.places.items():

			if name == origin:
				graph.add_place(name)
				accessible_places.add(name)

			elif ((not place.allowed_characters) or (char_ID in place.allowed_characters)) \
				and ((not place.allowed_roles) or any(ID in place.allowed_roles for ID in role_IDs)):
				graph.add_place(name)
				accessible_places.add(name)

			else:
				inaccessible_places.add(name)

		completed_paths = set()

		for name in accessible_places:

			for neighbor, path in self.places[name].neighbors.items():

				if (neighbor not in accessible_places
					or neighbor in completed_paths):
					continue

				if ((not path.allowed_characters and not path.allowed_roles)
					or char_ID in path.allowed_characters
					or any(ID in path.allowed_roles for ID in role_IDs)):
					pass
				else:
					continue

				if path.directionality > 0:
					graph.add_path(name, neighbor)

				if path.directionality < 2:
					graph.add_path(neighbor, name)

			completed_paths.add(name)

		return ego_graph(graph, origin, radius = 99)

	#Paths
	async def set_path(self, origin: str, destination: str, path: Path, overwrite: bool = False):

		prior_path = destination in self.places[origin].neighbors

		if prior_path and not overwrite:
			return True

		self.places[origin].neighbors[destination] = path
		new_path = Path(
			allowed_roles = path.allowed_roles,
			allowed_characters = path.allowed_characters,
			directionality = 2 - path.directionality)
		self.places[destination].neighbors[origin] = new_path

		return prior_path

	async def delete_path(self, origin_name: str, destination: str):
		origin = self.places.get(origin_name, None)
		if origin:
			origin.neighbors.pop(destination, None)

		destination = self.places.get(destination, None)
		if destination:
			destination.neighbors.pop(origin_name, None)

		return

	async def neighbors(self, place_names: iter, exclusive: bool = True):

		neighbors = set()
		for place in (self.places[name] for name in place_names):
			neighbors |= place.neighbors.keys()

		if exclusive:
			neighbors -= place_names
		else:
			neighbors |= place_names

		return neighbors

	async def count_paths(self, places: dict = {}):

		included_places = places if places else self.places
		total = 0
		visited_places = set()

		for name, place in included_places.items():
			total += sum(1 for neighbor, path in place.neighbors.items()
				if neighbor not in visited_places)
			visited_places.add(name)

		return total

	async def format_paths(self, neighbors: dict):

		description = ''
		for neighbor_name, path in neighbors.items():

			match path.directionality:

				case 0:
					description += '\n<-'

				case 1:
					description += '\n<->'

				case 2:
					description += '\n->'

			description += f' <#{self.places[neighbor_name].channel_ID}>'

		return description

	#Characters
	async def delete_character(self, char_ID: int):

		if char_ID not in self.characters:
			raise KeyError('Tried to delete a nonexistent character!')
			return

		self.characters.pop(char_ID)
		condemned_char = Character(char_ID)
		await condemned_char.delete()

		last_seen_place = self.places.get(condemned_char.location, None)
		last_seen_place.occupants.discard(char_ID)

		return condemned_char, last_seen_place

	async def _evict_character(self):

		await remove_speaker()
		# Remove listeners
		# Remove from location (both Place as well as Character data)
		# Do NOT save, will immediately be followed up with placing them

		# Inform Place that they left?
		# Inform nearby people?
		# Inform character?

	#Server Data
	async def to_graph(self, places: dict = None):

		graph = DiGraph()

		if not places:
			places = self.places

		completed_paths = set()

		for name, place in places.items():
			graph.add_node(
				name,
				channel_ID = place.channel_ID)

			for destination, path in place.neighbors.items():

				if destination in completed_paths:
					continue

				if path.directionality > 0:
					graph.add_edge(name, destination)
					graph[name][destination]['allowed_roles'] = path.allowed_roles
					graph[name][destination]['allowed_characters'] = path.allowed_characters

				if path.directionality < 2:
					graph.add_edge(destination, name)
					graph[destination][name]['allowed_roles'] = path.allowed_roles
					graph[destination][name]['allowed_characters'] = path.allowed_characters

			completed_paths.add(name)

		return graph

	async def to_map(self, graph: DiGraph = None, path_color: str = []):

		graph = graph or await self.to_graph()

		if not path_color:
			path_color = ['black'] * len(graph.edges)

		positions = shell_layout(graph)

		# Draw the places without paths
		draw_networkx_nodes(
			graph,
			pos = positions,
			node_shape = 'o',
			node_size = 1,
			node_color = '#ffffff')
		draw_networkx_labels(graph, pos = positions, font_weight = 'bold')

		index = 0
		letter_spacing = 0.03
		for origin, destination in graph.edges:

			ox, oy = positions[origin]
			dx, dy = positions[destination]
			distance = sqrt((dx - ox) ** 2 + (dy - oy) ** 2)

			if distance > letter_spacing * 2:

				if dx - ox != 0:
					slope = abs((dy - oy) / (dx - ox))
					angle_spacing = 1 - abs((1 - slope) / (1 + slope)) * 0.15

					label_factor = 1 / (abs(slope) + 1)

					origin_spacing = 0.1 * (1 - angle_spacing) + len(origin) * \
						letter_spacing * angle_spacing * label_factor
					destination_spacing = 0.1 * (1 - angle_spacing) + len(destination) * \
						letter_spacing * angle_spacing * label_factor

					ox += (dx - ox) * origin_spacing / distance
					oy += (dy - oy) * origin_spacing / distance

					dx += (ox - dx) * destination_spacing / distance
					dy += (oy - dy) * destination_spacing / distance

			else:
				ox = dx = (dx + ox) / 2
				oy = dy = (dy + oy) / 2

			draw_networkx_edges(
				graph,
				pos = {origin : (ox, oy),
					destination: (dx, dy)},
				edgelist = [(origin, destination)],
				edge_color = path_color[index],
				width = 3.0,
				arrowstyle =
					ArrowStyle('-|>'),
				arrowsize = 15)
			index += 1

		#Adjust the rest
		margins(x = 0.3, y = 0.1)
		tight_layout(pad = 0.8)
		axis('on')

		#Produce image
		map_image = gcf()
		close()
		bytesIO = BytesIO()
		map_image.savefig(bytesIO)
		bytesIO.seek(0)

		return bytesIO

	async def save(self):

		guild_con = connect(join(getcwd(), 'data', 'guild.db'))
		cursor = guild_con.cursor()

		if self.first_boot:
			serialized_null = dumps(dict())
			encoded_null = b64encode(serialized_null)

			cursor.execute("INSERT or REPLACE INTO guilds" +
				"(guild_ID, places, characters, roles, settings) VALUES(?, ?, ?, ?, ?)",
				(self.guild_ID, encoded_null, encoded_null, '', encoded_null))

		if self.load_places:
			all_places = {place_name : await place.__dict__() for place_name, place in self.places.items()}
			serialized_places = dumps(all_places)
			encoded_places = b64encode(serialized_places)

			cursor.execute("UPDATE guilds SET places = ? WHERE guild_id = ?;",
				(encoded_places, self.guild_ID))

		if self.load_characters:
			serialized_chars = dumps(self.characters)
			encoded_chars = b64encode(serialized_chars)

			cursor.execute("UPDATE guilds SET characters = ? WHERE guild_id = ?;",
				(encoded_chars, self.guild_ID))

		if self.load_roles:
			role_data = ' '.join([str(role_ID) for role_ID in self.roles])

			cursor.execute("UPDATE guilds SET roles = ? WHERE guild_id = ?;",
				(role_data, self.guild_ID))

		if self.load_settings:
			server_settings = dict()
			if self.view_distance != 99:
				server_settings['view_distance'] = self.view_distance

			if self.map_override:
				server_settings['map_override'] = self.map_override

			if self.visibility != 'private':
				server_settings['visibility'] = self.visibility

			if not self.eavesdropping_allowed:
				server_settings['eavesdropping_allowed'] = False

			if self.peephole:
				server_settings['peephole'] = True

			serialized_settings = dumps(server_settings)
			encoded_settings = b64encode(serialized_settings)

			cursor.execute("UPDATE guilds SET settings = ? WHERE guild_id = ?;",
				(encoded_settings, self.guild_ID))

		guild_con.commit()
		guild_con.close()
		return

	async def delete(self, guild: Guild):

		guild_con = connect(join(getcwd(), 'data', 'guild.db'))
		cursor = guild_con.cursor()

		cursor.execute("DELETE FROM guilds WHERE guild_ID = ?", (self.guild_ID,))
		guild_con.commit()

		for char_ID in self.characters.keys():

			direct_listeners.pop(char_ID, None)
			indirect_listeners.pop(char_ID, None)

			channel = await get_or_fetch(guild, 'channel', char_ID, default = None)
			if channel:
				await channel.delete()
				# await sleep(0.5)

		for name, place in list(self.places.items()):

			direct_listeners.pop(place.channel_ID, None)

			place_channel = await get_or_fetch(guild, 'channel', place.channel_ID, default = None)
			if place_channel:
				await self.delete_place(name)
				await place_channel.delete()

			else:
				print(f'Failed to locate place to delete, named \
					{name} with channel ID {place.channel_ID}.')

		for category_name in ['places', 'characters']:
			category = get(guild.categories, name = category_name)
			if category:
				await category.delete()

		print(f'Guild deleted, ID: {self.guild_ID}.')
		return

@s(auto_attribs = True)
class ListenerManager:
	guild: Guild = ib(default = None)
	direct_listeners: dict = ib(direct_listeners)
	indirect_listeners: dict = ib(indirect_listeners)
	guild_directs: dict = Factory(dict)
	guild_indirects: dict = Factory(dict)
	cached_channels: dict = Factory(dict)
	cached_characters: dict = Factory(dict)

	def __attrs_post_init__(self):
		self.guild_data = GuildData(
			self.guild.id,
			load_places = True,
			load_characters = True,
			load_settings = True)

		return

	async def _add_direct(self, speaker: int, listener: TextChannel, eavesdropping: bool):

		self.guild_directs.setdefault(speaker, set())
		self.guild_directs[speaker].add((listener, eavesdropping))

		return

	async def _add_indirect(self, speaker: int, listener: TextChannel, speaker_location: str):

		self.guild_indirects.setdefault(speaker, set())
		self.guild_indirects[speaker].add((listener, speaker_location))

		return

	async def _load_channel(self, channel_ID: int):

		channel = self.cached_channels.get(channel_ID, None)
		if not channel:
			channel = get(self.channels, id = channel_ID)
			self.cached_channels[channel_ID] = channel

		return channel

	async def _load_character(self, character_ID: int):

		character = self.cached_characters.get(character_ID, None)

		if not character:
			character = Character(character_ID)
			self.cached_characters[character_ID] = character

		return character

	async def clean_listeners(self):

		for character_ID in self.guild_data.characters.keys():
			self.direct_listeners.pop(character_ID, None)
			self.indirect_listeners.pop(character_ID, None)

		self.direct_listeners = {channel_ID : eavesdropping for
			channel_ID, eavesdropping in self.direct_listeners.items()
			if channel_ID not in self.guild_data.places}

		return

	async def build_listeners(self):

		self.channels = await self.guild.fetch_channels()

		for place_name, place in self.guild_data.places.items():  # For every place in the graph

			place_channel = await self._load_channel(place.channel_ID)

			for occ_ID in place.occupants:  # For each occupant...

				occ_channel = await self._load_channel(occ_ID)
				occ_player = await self._load_character(occ_ID)

				await self._add_direct(occ_ID, place_channel, eavesdropping = False)  # Location listens to player
				await self._add_direct(place.channel_ID, occ_channel, eavesdropping = False)  # Player listens to location

				for other_occ_ID in place.occupants:  # Add all other occupants as listeners...

					if other_occ_ID == occ_ID:  # Skip yourself.
						continue

					await self._add_direct(other_occ_ID, occ_channel, eavesdropping = False)  # Add them as a listener to you.

				for neighbor_place_name in place.neighbors.keys():

					neighbor_place = self.guild_data.places[neighbor_place_name]

					if self.guild_data.eavesdropping_allowed and neighbor_place_name == occ_player.eavesdropping:
						await self._add_direct(neighbor_place.channel_ID, occ_channel, eavesdropping = True)
					else:
						await self._add_indirect(neighbor_place.channel_ID, occ_channel, neighbor_place_name)

					for neighbor_occ_ID in neighbor_place.occupants:  # For every person in the neighbor place...

						if self.guild_data.eavesdropping_allowed and neighbor_place_name == occ_player.eavesdropping:
							await self._add_direct(neighbor_occ_ID, occ_channel, eavesdropping = True)
						else:
							await self._add_indirect(neighbor_occ_ID, occ_channel, neighbor_place_name)  # Neighbor only hears occ indirectly.

		return self.guild_directs, self.guild_indirects

#Character
@s(auto_attribs = True)
class Character:
	id: int = ib(default = 0)

	def __attrs_post_init__(self):

		def return_dict(cursor, characters):
			fields = [column[0] for column in cursor.description]
			return {field_name: data for field_name, data in zip(fields, characters)}

		character_con = connect(join(getcwd(), 'data', 'character.db'))
		character_con.row_factory = return_dict
		cursor = character_con.cursor()
		cursor.execute(f"""SELECT * FROM characters WHERE character_ID = {self.id} LIMIT 1""")
		char_data = cursor.fetchone()

		char_data = char_data or dict()

		self.channel_ID = self.id

		self.name = char_data.get('name', None)
		self.avatar = char_data.get('avatar', None)
		self.location = char_data.get('location', None)
		self.eavesdropping = char_data.get('eavesdropping', None)
		self.roles = {int(role_ID) for role_ID in char_data.get('roles', '').split()}

		return

	async def save(self):

		character_con = connect(getcwd() + '/data/character.db')
		cursor = character_con.cursor()

		self.roles = ' '.join([str(role_ID) for role_ID in self.roles])

		print(f'Saved roles as {self.roles}')

		cursor.execute("INSERT or REPLACE INTO characters(character_ID, " +
			"name, avatar, location, eavesdropping, roles) VALUES (?, ?, ?, ?, ?, ?)",
			(self.id, self.name, self.avatar, self.location, self.eavesdropping, self.roles))

		character_con.commit()
		character_con.close()
		return

	async def delete(self):

		character_con = connect(getcwd() + '/data/character.db')
		cursor = character_con.cursor()

		cursor.execute("DELETE FROM characters WHERE character_ID = ?", (self.id,))
		character_con.commit()
		print(f'Character deleted, ID: {self.id}.')
		return
