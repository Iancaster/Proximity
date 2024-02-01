

#Import-ant Libraries
from discord import Guild, PermissionOverwrite, Interaction, \
	ComponentType, InputTextStyle, ButtonStyle, TextChannel, \
	ChannelType, CategoryChannel, ApplicationContext, MISSING
from discord.errors import NotFound
from discord.utils import get, get_or_fetch
from discord.ui import View, Select, Button, Modal, InputText

from libraries.universal import mbd, send_message
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

async def test_func(id: int):

	di = str(id)
	di = int(id)
	return di

async def tester_func(ctx):
	di = str(ctx.author.id)
	di = int(di)
	return di

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

	async def add_occupants(self, arriving: dict):
		self.occupants |= arriving
		return

	async def remove_occupants(self, departing: dict):
		self.occupants -= departing
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

# Character
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

# Data
@s(auto_attribs = True)
class GuildData:
	guild_ID: int
	load_places: bool = ib(default = False)
	load_characters: bool = ib(default = False)
	load_roles: bool = ib(default = False)
	load_settings: bool = ib(default = False)

	def __attrs_post_init__(self):

		def return_dictionary(cursor, data):
			fields = [column[0] for column in cursor.description]
			return {column : data for column, data in zip(fields, data)}

		guild_con = connect(join(getcwd(), 'data', 'guild.db'))
		guild_con.row_factory = return_dictionary
		cursor = guild_con.cursor()

		cursor.execute("SELECT * FROM guilds WHERE guild_ID = ? LIMIT 1", (self.guild_ID,))
		GD = cursor.fetchone()
		guild_con.close()

		self.places = dict()
		self.characters = dict()
		self.roles = set()

		self.view_distance = 99
		self.map_override = None
		self.visibility = 'private'
		self.peephole = True
		self.eavesdropping_allowed = True

		self.first_boot = not GD

		if self.first_boot:
			return

		if self.load_places:

			decoded_places = b64decode(GD['places'])
			places_dict = loads(decoded_places)

			for name, place_data in places_dict.items():
				self.places[name] = Location(
					channel_ID = place_data['channel_ID'],
					occupants = place_data.get('occupants', set()),
					allowed_roles = place_data.get('allowed_roles', set()),
					allowed_characters = place_data.get('allowed_characters', set()),
					neighbors = place_data.get('neighbors', dict()))

		if self.load_characters:
			decoded_chars = b64decode(GD['characters'])
			self.characters = loads(decoded_chars)

		if self.load_roles:
			self.roles = {int(role_ID) for role_ID in GD['roles'].split()}

		if self.load_settings:
			decoded_settings = b64decode(GD['settings'])
			settings_dict = loads(decoded_settings)

			self.view_distance = settings_dict.get('view_distance', 99)
			self.map_override = settings_dict.get('map_override', None)
			self.visibility = settings_dict.get('visibility', 'private')
			self.eavesdropping_allowed = settings_dict.get('eavesdropping', True)
			self.peephole = settings_dict.get('peephole', True)

		return

	# Places
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
		places = places or self.places
		return {occ_ID for place in places for occ_ID in place.occupants}

	async def _gate_guard(self, comp: Component, char_ID: int, role_IDs: iter):

		if not comp.allowed_characters and not comp.allowed_roles:
			return True

		elif char_ID in comp.allowed_characters:
			return True

		return bool(comp.allowed_roles.intersection(role_IDs))

	async def accessible_locations(self, role_IDs: iter, char_ID: int, origin: str):

		accessible = set()
		seen_places = set()

		async def identify_accessible_neighbors(place_name: str):

			seen_places.add(place_name)
			place = self.places[place_name]

			if not await self._gate_guard(place, char_ID, role_IDs):
				return False

			for neighbor_name, path in place.neighbors.items():

				if neighbor_name in seen_places:
					continue

				if path.directionality < 1:
					continue

				if await self._gate_guard(path, char_ID, role_IDs):
					await identify_accessible_neighbors(neighbor_name)

			accessible.add(place_name)
			return True

		if not await identify_accessible_neighbors(origin):
			accessible.add(origin)

		return accessible

	async def accessible_map(self, role_IDs: iter, char_ID: int, origin: str):

		graph = DiGraph()
		seen_places = set()

		async def identify_accessible_neighbors(place_name: str):

			seen_places.add(place_name)
			place = self.places[place_name]

			if not await self._gate_guard(place, char_ID, role_IDs):
				return False

			graph.add_node(place_name)

			for neighbor_name, path in place.neighbors.items():

				if neighbor_name in seen_places:
					continue

				if path.directionality < 1:
					continue

				if await self._gate_guard(path, char_ID, role_IDs):

					if not await identify_accessible_neighbors(neighbor_name):
						continue

					graph.add_edge(place_name, neighbor_name)

					if path.directionality == 1:
						graph.add_edge(neighbor_name, place_name)

			return True

		if not await identify_accessible_neighbors(origin):
			graph.add_node(origin)

		return graph

	# Paths
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

	# Characters
	async def validate_membership(self, char_ID: int, ctx: ApplicationContext = None):

		if char_ID in self.characters:
			return True

		elif ctx:
			embed, _ = await mbd(
				'Hold on.',
				'This is a command for characters. If you have access' \
					' to any Character Channels, call the command' \
					' in there instead.',
				'Otherwise, ask a Host to make a /new character for you.')
			await send_message(ctx.respond, embed)

		return False

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

	async def evict_character(self, char_data: Character):

		occupied_place = self.places[char_data.location]
		await occupied_place.remove_occupants({char_data.channel_ID})
		char_data.location = None
		char_data.eavesdropping = None
		return

	async def insert_character(self, char_data: Character, new_place_name: str):

		char_data.location = new_place_name
		new_place = self.places[new_place_name]
		await new_place.add_occupants({char_data.channel_ID})
		return


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

# Server
@s(auto_attribs = True)
class DialogueView(View):
	refresh: callable = ib(default = None)
	should_disable_submit: callable = ib(default = lambda: False)

	# Interior
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

	# Selects
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

	# Modals
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

		first_component = next(iter(components), None)

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
class ChannelManager:
	guild: Guild = ib(default = None)
	GD: GuildData = ib(default = None)

	# Getters
	async def _get_objects(self, objects_to_get: set()):

		for needed_object in objects_to_get:

			if not hasattr(self, needed_object):
				await getattr(self, f'_get_{needed_object}')()
				# eval(await f'_get_{needed_object}()')

		return

	async def _get_avatar(self):

		with open(join(getcwd(), 'assets', 'avatar.png'), 'rb') as file:
			self.avatar = file.read()

		return

	async def _get_permissions(self):

		self.permissions = {
			self.guild.default_role:
				PermissionOverwrite(read_messages = False),
			self.guild.me : PermissionOverwrite(
				send_messages = True,
				read_messages = True,
				manage_channels = True)}

		return

	async def _get_category(self, category_name: str):

		existing_category = get(self.guild.categories, name = category_name)
		if existing_category:
			self.category = existing_category
			return

		found_category = next(
			(channel for channel in await self.guild.fetch_channels() if
				channel.name == category_name and isinstance(channel, CategoryChannel)),
				None)
		if found_category:
			self.category = found_category
			return

		self.category = await self.guild.create_category(category_name, overwrites = self.permissions)
		return

	# Making new shit
	async def create_channel(self, category_name: str, channel_name: str, allowed_people: iter = []):

		await self._get_objects({'permissions'})

		if not hasattr(self, 'category') or self.category.name != category_name:
			await self._get_category(category_name)

		for person in allowed_people:
			self.permissions[person] = PermissionOverwrite(
				send_messages = True,
				read_messages = True)

		new_channel = await self.guild.create_text_channel(channel_name, category = self.category, overwrites = self.permissions)

		await self.create_webhook(new_channel)

		return new_channel

	async def create_webhook(self, channel: TextChannel):

		await self._get_objects({'avatar'})

		return await channel.create_webhook(name = 'Proximity', avatar = self.avatar)

	async def send_embed(self, channel: TextChannel, send_method: callable, title: str = 'No Title', description: str = 'No description.', footer: str = 'No footer.', image_details = None):

		embed, file = await mdb(title, description, footer, image_details)
		await send_message(embed, file)

	# Validate Channels
	async def identify_place_channel(self, ctx: ApplicationContext, submission: callable = None,  presented_name: str = ''):

		if not self.GD.places:

			embed, _ = await mbd(
				'Easy, bronco.',
				"You've got no places to work with.",
				'Make some first with /new place.')
			await send_message(ctx.respond, embed)
			return

		elif presented_name:

			if presented_name in self.GD.places:
				return presented_name

			elif enforce_presented:

				embed, _ = await mbd(
					'What?',
					f"**#{presented_name}** isn't a place channel. Did" +
						" you select the wrong one?",
					'Try calling the command again.')
				await send_message(ctx.respond, embed)
				return

		if ctx.channel.name in self.GD.places:
			return ctx.channel.name

		if submission:
			return await submission()

		return ''

	async def identify_character_channel(self, ctx: ApplicationContext, submission: callable = None, presented_name: str = '', presented_id: int = 0):

		if not self.GD.characters:

			embed, _ = await mbd(
				'Easy, bronco.',
				"You've got no characters yet.",
				'Make a /new place so you can add a /new character.')
			await send_message(ctx.respond, embed)
			return

		elif presented_id:  # Character given (channel)

			if presented_id in self.GD.characters:
				return {presented_character_id : self.GD.characters[presented_id]}

			embed, _ = await mbd(
				'What?',
				f"<#{presented_id}> isn't a character channel. Did" + \
					" you select the wrong one?",
				'Try calling the command again.')
			await send_message(ctx.respond, embed)
			return

		elif presented_name:  # Character given (text)

			if found_character := next({ID : name for ID, name in self.GD.characters.items() if \
					name == presented_name}, None):
				return found_character

			embed, _ = await mbd(
				'What?',
				f"*{presented_character_name}* isn't a character. Did" + \
					" you select the wrong one?",
				'Try calling the command again.')
			await send_message(ctx.respond, embed)
			return

		elif ctx.channel.id in self.GD.characters:  # Character channel
			return {ctx.channel.id : self.GD.characters[ctx.channel.id]}

		if submission:
			return await submission()

		return ''

@s(auto_attribs = True)
class ListenerManager:
	guild: Guild = ib(default = None)
	GD: GuildData = ib(default = None)
	cached_channels: dict = Factory(dict)
	cached_characters: dict = Factory(dict)

	async def load_channels(self):
		self.channels = await self.guild.fetch_channels()
		return

	async def _add_direct(self, speaker: int, listener: TextChannel, eavesdropping: bool):

		direct_listeners.setdefault(speaker, set())
		direct_listeners[speaker].add((listener, eavesdropping))

		return

	async def _add_indirect(self, speaker: int, listener: TextChannel, speaker_location: str):

		indirect_listeners.setdefault(speaker, set())
		indirect_listeners[speaker].add((listener, speaker_location))

		return

	async def _load_channel(self, channel_ID: int):

		channel = self.cached_channels.get(channel_ID, None)
		if channel := get(self.channels, id = channel_ID):
			self.cached_channels[channel_ID] = channel

		return channel

	async def _load_character(self, character_ID: int):

		character = self.cached_characters.get(character_ID, None)
		if not character:
			character = Character(character_ID)
			self.cached_characters[character_ID] = character

		return character

	async def clean_listeners(self):

		for character_ID in self.GD.characters.keys():
			direct_listeners.pop(character_ID, None)
			indirect_listeners.pop(character_ID, None)

		for place in self.GD.places.values():
			direct_listeners.pop(place.channel_ID, None)

		return

	async def remove_channel(self, channel_ID: int = 0, channel: TextChannel = None):

		condemned_channel = channel or await self._load_channel(channel_ID)

		for listener_dict in [direct_listeners, indirect_listeners]:

			own_listeners = listener_dict.pop(condemned_channel.id, set())

			for listener_channel, secondary in own_listeners:

				their_listeners = listener_dict.get(listener_channel.id, dict())

				their_listeners.discard((condemned_channel, secondary))

				if not their_listeners:
					listener_dict.pop(listener_channel.id)

		return

	async def insert_character(self, char_data: Character, skip_eaves: bool = False):

		char_channel = await self._load_channel(char_data.channel_ID)

		place = self.GD.places[char_data.location]
		place_channel = await self._load_channel(place.channel_ID)

		# Listen to place (and vice versa)
		await self._add_direct(char_data.channel_ID, place_channel, eavesdropping = False)
		await self._add_direct(place.channel_ID, char_channel, eavesdropping = False)

		# Listen to other characters nearby
		for occ_ID in place.occupants:

			if occ_ID == char_data.channel_ID:
				continue

			their_channel = await self._load_channel(occ_ID)
			await self._add_direct(occ_ID, char_channel, eavesdropping = False)
			await self._add_direct(char_data.channel_ID, their_channel, eavesdropping = False)

		# Listen to neighbors
		for neighbor_name in place.neighbors.keys():

			neighbor_place = self.GD.places[neighbor_name]

			if skip_eaves:
				await self._add_indirect(neighbor_place.channel_ID, char_channel, neighbor_name)

			else:
				if self.GD.eavesdropping_allowed and neighbor_name == char_data.eavesdropping:
					await self._add_direct(neighbor_occ_ID, char_channel, eavesdropping = True)

				else:
					await self._add_indirect(neighbor_place.channel_ID, char_channel, neighbor_name)

			for neighbor_occ_ID in neighbor_place.occupants:

				if self.GD.eavesdropping_allowed:

					occ_char = Character(neighbor_occ_ID)

					if neighbor_name == occ_char.eavesdropping:
						await self._add_direct(neighbor_occ_ID, char_channel, eavesdropping = True)
						continue

				await self._add_indirect(neighbor_occ_ID, char_channel, neighbor_name)  # Neighbor only hears occ indirectly.

		return

	async def build_listeners(self):

		for place in self.GD.places.values():

			for occ_ID in place.occupants:

				await self.insert_character(Character(occ_ID), place)

		return

@s(auto_attribs = True)
class Paginator():
	interaction: Interaction = ib(default = None)
	title_prefix: str = ib(default = '')
	all_pages: dict = Factory(dict)
	all_images: dict = Factory(dict)

	def __attrs_post_init__(self):
		self.current_page = 0
		self.total_pages = len(self.all_pages)

	async def _close_dialogue(self, interaction: Interaction):

		embed, _ = await mbd(
			'All done.',
			'Window closed.',
			'Feel free to call the command again.')

		await self.interaction.followup.edit_message(
			message_id = self.interaction.message.id,
			embed = embed,
			file = MISSING,
			view = None)
		return

	async def _determine_arrows(self, page: int):
		return page > 0, page < self.total_pages - 1

	async def _flip_page_right(self, interaction: Interaction):

		await interaction.response.defer()
		self.current_page += 1
		self.interaction = interaction
		await self.refresh_embed()
		return

	async def _flip_page_left(self, interaction: Interaction):

		await interaction.response.defer()
		self.current_page -= 1
		self.interaction = interaction
		await self.refresh_embed()
		return

	async def _construct_buttons(self, left_arrow_enabled: bool, right_arrow_enabled: bool):

		view = DialogueView()

		if left_arrow_enabled:
			label = '<'
			disabled = False
		else:
			label = '-'
			disabled = True

		left = Button(
			label = label,
			style = ButtonStyle.secondary,
			disabled = disabled)
		left.callback = self._flip_page_left
		view.add_item(left)

		if right_arrow_enabled:
			label = '>'
			callback = self._flip_page_right
		else:
			label = 'Done'
			callback = self._close_dialogue

		right = Button(
			label = label,
			style = ButtonStyle.secondary)
		right.callback = callback
		view.add_item(right)

		return view

	async def refresh_embed(self):

		subheader, page_content = list(self.all_pages.items())[self.current_page]

		page_title = f'{self.title_prefix} {self.current_page + 1}: ' + \
			subheader

		picture = self.all_images.get(subheader, None)
		picture_view = (picture, 'full') if picture else None

		embed, file = await mbd(
			page_title,
			page_content,
			'Use the buttons below to flip the page.',
			picture_view)

		left_arrow_enabled, right_arrow_enabled = \
			await self._determine_arrows(self.current_page)

		if self.current_page < 1:
			furthest_left, furthest_right = True, self.total_pages > 1
		elif self.current_page == self.total_pages - 2:
			furthest_left, furthest_right = self.current_page < 1, False
		else:
			furthest_left, furthest_right = await self._determine_arrows(self.current_page - 1)


		if furthest_left != left_arrow_enabled or \
			furthest_right != right_arrow_enabled:

			await self.interaction.followup.edit_message(
				message_id = self.interaction.message.id,
				embed = embed,
				file = file if file else MISSING,
				view = await self._construct_buttons(left_arrow_enabled, right_arrow_enabled))
		else:

			await self.interaction.followup.edit_message(
				message_id = self.interaction.message.id,
				embed = embed,
				file = file if file else MISSING) #Might be attachments = MISSING

		return

