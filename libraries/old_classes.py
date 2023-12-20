

#Import-ant Libraries
from discord import Guild, Member, PermissionOverwrite, Interaction, \
	ComponentType, InputTextStyle, ButtonStyle, MISSING, TextChannel
from discord.utils import get, get_or_fetch
from discord.ui import View, Select, Button, Modal, InputText
from asyncio import sleep

from libraries.universal import mbd
from libraries.formatting import discordify, format_whitelist
from data.listeners import direct_listeners, indirect_listeners

#Data Libraries
from attr import s, ib, Factory
from sqlite3 import connect
from base64 import b64encode, b64decode
from pickle import loads, dumps
from io import BytesIO
from os import getcwd, path

#Math Libraries
from networkx import DiGraph, ego_graph, draw_networkx_places, \
	draw_networkx_paths, shell_layout, draw_networkx_labels
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

	async def set_players(self, players_IDs: set):
		self.allowed_characters = players_IDs
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
class Edge(Component):
	directionality: int = ib(default = 1)
	# directionality > 0 means it's going TO the destination
	# directionality < 2 means it's coming FROM the target

	async def __dict__(self):
		return_dict = await super().__dict__()
		return_dict['directionality'] = self.directionality
		return return_dict

@s(auto_attribs = True)
class Node(Component):
	channel_ID: int = ib(default = 0)
	occupants: set = Factory(set)
	neighbors: dict = Factory(dict)

	def __attrs_pre_init__(self):
		super().__init__()
		return

	def __attrs_post_init__(self):
		self.mention = f'<#{self.channel_ID}>'

		if self.neighbors:
			neighbors = {}
			for neighbor, path in self.neighbors.items():
				neighbors[neighbor] = Edge(
					directionality = path['directionality'],
					allowed_roles = path.get('allowed_roles', set()),
					allowed_characters = path.get('allowed_characters', set()))

			self.neighbors = neighbors

		return

	async def add_occupants(self, occupant_IDs: iter):

		if not isinstance(occupant_IDs, set):
			occupant_IDs = set(occupant_IDs)

		self.occupants |= occupant_IDs
		return

	async def remove_occupants(self, occupant_IDs: iter):

		if not isinstance(occupant_IDs, set):
			occupant_IDs = set(occupant_IDs)

		if not occupant_IDs.issubset(self.occupants):
			raise KeyError("Trying to remove someone from a place who's already absent.")

		self.occupants -= occupant_IDs
		return

	async def clear_whitelist(self):
		self.allowed_roles = set()
		self.allowed_characters = set()
		return

	async def __str__(self):
		return f'Node, channel ...{self.channel_ID[12:]}'

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

#Player
@s(auto_attribs = True)
class Player:
	id: int = ib(default = 0)
	guild_ID: int = ib(default = 0)

	def __attrs_post_init__(self):

		def return_dict(cursor, players):
			fields = [column[0] for column in cursor.description]
			return {field_name: data for field_name, data in zip(fields, players)}


		player_con = connect(getcwd() + '/data/player.db')
		player_con.row_factory = return_dict
		cursor = player_con.cursor()
		cursor.execute(f"""SELECT * FROM players WHERE player_ID = {self.id}""")
		player_data = cursor.fetchone()

		if player_data:
			serialized_player = b64decode(player_data['relevant_data'])
			self.as_dict = loads(serialized_player)
			relevant_data = self.as_dict.get(self.guild_ID, {})
		else:
			self.as_dict = relevant_data = {}

		self.channel_ID = relevant_data.get('channel_ID', None)
		self.location = relevant_data.get('location', None)
		self.eavesdropping = relevant_data.get('eavesdropping', None)
		self.name = relevant_data.get('name', None)
		self.avatar = relevant_data.get('avatar', None)
		return

	async def save(self):

		player_con = connect(getcwd() + '/data/player.db')
		cursor = player_con.cursor()

		self.as_dict[self.guild_ID] = {
			'channel_ID' : self.channel_ID,
			'location' : self.location,
			'eavesdropping' : self.eavesdropping,
			'name' : self.name,
			'avatar' : self.avatar}

		return await self._commit(player_con, cursor)

	async def delete(self):

		direct_listeners.pop(self.channel_ID, None)
		indirect_listeners.pop(self.channel_ID, None)
		self.as_dict.pop(self.guild_ID, None)

		player_con = connect(getcwd() + '/data/player.db')
		cursor = player_con.cursor()

		if self.as_dict:
			print(f'Player removed from guild, ID: {self.id}.')
			return await self._commit(player_con, cursor)

		cursor.execute("DELETE FROM players WHERE player_ID = ?", (self.id,))
		player_con.commit()
		print(f'Player deleted, ID: {self.id}.')
		return

	async def _commit(self, player_con, cursor):

		player_serialized = dumps(self.as_dict)
		player_encoded = b64encode(player_serialized)
		cursor.execute("INSERT or REPLACE INTO players(player_ID, relevant_data) VALUES(?, ?)",
			(self.id, player_encoded))

		player_con.commit()
		player_con.close()
		return

#Guild
@s(auto_attribs = True)
class ChannelMaker:
	guild: Guild
	category_name: str  = ib(default = '')

	def __attrs_post_init__(self):

		with open('assets/avatar.png', 'rb') as file:
			self.avatar = file.read()

	async def initialize(self):

		existing_category = get(self.guild.categories, name = self.category_name)
		if existing_category:
			self.category = existing_category
			return

		self.category = await self.guild.create_category(self.category_name)
		return

	async def create_channel(self, name: str, allowed_person: Member = None):
		permissions = {
			self.guild.default_role: PermissionOverwrite(read_messages = False),
			self.guild.me: PermissionOverwrite(send_messages = True, read_messages = True)}

		if allowed_person:
			permissions.update({
				allowed_person: PermissionOverwrite(send_messages = True, read_messages = True)})

		create_channel = await self.guild.create_text_channel(
			name,
			category = self.category,
			overwrites = permissions)
		await create_channel.create_webhook(name = 'Proximity', avatar = self.avatar)
		return create_channel

@s(auto_attribs = True)
class GuildData:
	guild_ID: int
	maker: ChannelMaker = ib(default = None)
	places: dict = Factory(dict)
	players: set = Factory(set)

	def __attrs_post_init__(self):

		def return_dictionary(cursor, guild):
			fields = [column[0] for column in cursor.description]
			return {column_name: data for column_name, data in zip(fields, guild)}

		guild_con = connect(path.join(getcwd(),'data','guild.db'))
		guild_con.row_factory = return_dictionary
		cursor = guild_con.cursor()

		cursor.execute("SELECT * FROM guilds WHERE guild_ID = ?", (self.guild_ID,))
		guild_data = cursor.fetchone()
		settings_dict = dict()

		if guild_data:
			decoded_places = b64decode(guild_data['places'])
			places_dict = loads(decoded_places)

			for name, data in places_dict.items():
				self.places[name] = Node(
						channel_ID = data['channel_ID'],
						occupants = data.get('occupants', set()),
						allowed_roles = data.get('allowed_roles', set()),
						allowed_characters = data.get('allowed_characters', set()),
						neighbors = data.get('neighbors', dict()))

			self.players = set(int(player) for player in guild_data['player_list'].split())


			decoded_settings = b64decode(guild_data['settings'])
			settings_dict = loads(decoded_settings)


		self.view_distance = settings_dict.get('view_distance', 99)
		self.map_override = settings_dict.get('map_override', None)
		self.visibility = settings_dict.get('visibility', 'private')
		self.peephole = settings_dict.get('peephole', True)
		self.eavesdropping_allowed = settings_dict.get('eavesdropping', True)

		guild_con.close()
		return

	#Nodes
	async def create_place(self, name: str, channel_ID: int, allowed_roles: iter = set(), allowed_characters: iter = set()):

		if name in self.places:
			raise KeyError('Node already exists, no overwriting!')
			return

		self.places[name] = Node(
			channel_ID = channel_ID,
			allowed_characters = allowed_characters,
			allowed_roles = allowed_roles)

		return

	async def delete_place(self, name: str, channel = None):

		place = self.places.pop(name, None)

		if not place:
			raise KeyError('Tried to delete a nonexistent place!')
			return

		if channel:
			await channel.delete()

		return

	async def filter_places(self, place_names: iter):
		"""iter(place_names) -> {place_name : place_data}"""
		return {name : self.places[name] for name in place_names}

	async def get_all_occupants(self, places: iter = places):
		occupants = set()
		for place in places:
			occupants |= place.occupants
		return occupants

	async def accessible_locations(self, role_IDs: iter, player_ID: int, origin: str):

		graph = DiGraph()

		accessible_places = set()
		inaccessible_places = set()

		for name, place in self.places.items():

			if name == origin:
				graph.add_place(name)
				accessible_places.add(name)

			elif ((not place.allowed_characters) or (player_ID in place.allowed_characters)) \
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
					or player_ID in path.allowed_characters
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

	#Edges
	async def set_path(self, origin: str, destination: str, path: Edge, overwrite: bool = False):

		if destination in self.places[origin].neighbors or \
			origin in self.places[destination].neighbors:

			if overwrite:
				prior_path = True
			else:
				return True
		else:
			prior_path = False

		match path.directionality:

			case 0:
				self.places[origin].neighbors[destination] = path
				new_path = Edge(
					allowed_roles = path.allowed_roles,
					allowed_characters = path.allowed_characters,
					directionality = 2)
				self.places[destination].neighbors[origin] = new_path

			case 1:
				self.places[origin].neighbors[destination] = path
				new_path = Edge(
					allowed_roles = path.allowed_roles,
					allowed_characters = path.allowed_characters,
					directionality = 1)
				self.places[destination].neighbors[origin] = new_path

			case 2:
				self.places[origin].neighbors[destination] = path
				new_path = Edge(
					allowed_roles = path.allowed_roles,
					allowed_characters = path.allowed_characters,
					directionality = 0)
				self.places[destination].neighbors[origin] = new_path

		return prior_path

	async def delete_path(self, origin: str, destination: str):
		self.places[origin].neighbors.pop(destination, None)
		self.places[destination].neighbors.pop(origin, None)
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
		visited_places = set()

		for name, place in included_places.items():
			count_paths = sum(1 for neighbor, path in place.neighbors.items() \
				if neighbor not in visited_places)
			visited_places.add(name)

		return count_paths

	async def format_paths(self, neighbors: dict):

		description = ''
		for neighbor_name, path in neighbors.items():

			match path.directionality:

				case 0:
					description += f'\n<- <#{self.places[neighbor_name].channel_ID}>'

				case 1:
					description += f'\n<-> <#{self.places[neighbor_name].channel_ID}>'

				case 2:
					description += f'\n-> <#{self.places[neighbor_name].channel_ID}>'

		return description

	#Players
	async def create_player(self, player_ID: int, location: str):

		if location in self.places:
			self.places[location].add_occupants({player_ID})
		else:
			raise KeyError(f'Attempted to add player to nonexistent place named {location}.')
			return

		self.members.add(player_ID)
		return

	#Guild Data
	async def to_graph(self, places: dict = None):

		graph = DiGraph()

		places = self.places if not places else places

		completed_paths = set()
		for name, place in places.items():
			graph.add_place(
				name,
				channel_ID = place.channel_ID)

			for destination, path in place.neighbors.items():

				if destination in completed_paths:
					continue

				if path.directionality > 0:
					graph.add_path(name, destination)
					graph[name][destination]['allowed_roles'] = path.allowed_roles
					graph[name][destination]['allowed_characters'] = path.allowed_characters

				if path.directionality < 2:
					graph.add_path(destination, name)
					graph[destination][name]['allowed_roles'] = path.allowed_roles
					graph[destination][name]['allowed_characters'] = path.allowed_characters

			completed_paths.add(name)

		return graph

	async def to_map(self, graph: DiGraph = None, path_color: str = []):

		if not graph:
			graph = await self.to_graph()
		if not path_color:
			path_color = ['black'] * len(graph.paths)

		positions = shell_layout(graph)

		# Draw the places without paths
		draw_networkx_places(
			graph,
			pos = positions,
			place_shape = 'o',
			place_size = 1,
			place_color = '#ffffff')
		draw_networkx_labels(graph, pos = positions, font_weight = 'bold')

		index = 0
		letter_spacing = 0.03
		for origin, destination in graph.paths:

			ox, oy = positions[origin]
			dx, dy = positions[destination]
			distance = sqrt((dx - ox) ** 2 + (dy - oy) ** 2)

			if distance > letter_spacing * 2: #Move the paths away from the labels

				if dx - ox != 0:
					slope = abs((dy - oy) / (dx - ox))
					angle_spacing = 1 - abs((1 - slope) / (1 + slope)) * 0.15

					labelFactor = 1 / (abs(slope) + 1)

					origin_spacing = 0.1 * (1 - angle_spacing) + len(origin) * \
						letter_spacing * angle_spacing * labelFactor
					destination_spacing = 0.1 * (1 - angle_spacing) + len(destination) * \
						letter_spacing * angle_spacing * labelFactor

					ox += (dx - ox) * origin_spacing / distance
					oy += (dy - oy) * origin_spacing / distance

					dx += (ox - dx) * destination_spacing / distance
					dy += (oy - dy) * destination_spacing / distance

			else:
				ox = dx = (dx + ox) / 2
				oy = dy = (dy + oy) / 2

			draw_networkx_paths(
				graph,
				pos = {origin : (ox, oy),
					destination: (dx, dy)},
				pathlist = [(origin, destination)],
				path_color = path_color[index],
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
		#plt.show() #Uncomment this and comment everything below for bugtesting
		map_image = gcf()
		close()
		bytesIO = BytesIO()
		map_image.savefig(bytesIO)
		bytesIO.seek(0)

		return bytesIO

	async def save(self):

		guild_con = connect(path.join(getcwd(),'data','guild.db'))
		cursor = guild_con.cursor()

		all_places = {place_name : await place.__dict__() for place_name, place in self.places.items()}
		serialized_places = dumps(all_places)
		encoded_places = b64encode(serialized_places)

		player_data = ' '.join([str(player_ID) for player_ID in self.players])

		server_settings = dict()

		if self.view_distance != 99:
			server_settings['view_distance'] = self.view_distance

		if self.map_override:
			server_settings['map_override'] = self.map_override

		if self.visibility != 'private':
			server_settings['visibility'] = self.visibility

		if self.peephole:
			server_settings['peephole'] = True

		if not self.eavesdropping_allowed:
			server_settings['eavesdropping_allowed'] = False

		serialized_settings = dumps(server_settings)
		encoded_settings = b64encode(serialized_settings)

		cursor.execute("INSERT or REPLACE INTO guilds" + \
			"(guild_ID, places, player_list, settings) VALUES(?, ?, ?, ?)",
			(self.guild_ID, encoded_places, player_data, encoded_settings))


		guild_con.commit()
		guild_con.close()
		return

	async def delete(self):

		guild_con = connect(getcwd() + '/data/guild.db')
		cursor = guild_con.cursor()

		cursor.execute("DELETE FROM guilds WHERE guild_ID = ?", (self.guild_ID,))
		guild_con.commit()

		print(f'Guild deleted, ID: {self.guild_ID}.')
		return

	async def clear(self, guild: Guild):

		for player_ID in self.players:

			player = Player(player_ID, self.guild_ID)

			channel = await get_or_fetch(guild, 'channel', player.channel_ID)
			if channel:
				await channel.delete()

		for name, place in list(self.places.items()):

			try:
				place_channel = await get_or_fetch(guild, 'channel', place.channel_ID)
				await self.delete_place(name, place_channel)
			except:
				print(f'Could not delete place {name} when clearing data.')
				continue

		for category_name in ['places', 'players']:
			category = get(guild.categories, name = category_name)
			await category.delete() if category else None

		await sleep(3)
		await self.delete()
		return

@s(auto_attribs = True)
class ListenerManager:
	guild: Guild = ib(default = None)
	guild_data: dict = Factory(dict)
	guild_directs: dict = Factory(dict)
	guild_indirects: dict = Factory(dict)
	cached_channels: dict = Factory(dict)
	cached_players: dict = Factory(dict)

	def __attrs_post_init__(self):
		self.guild_data = GuildData(self.guild.id)
		return

	async def _add_direct(self, speaker: int, listener: TextChannel, eavesdropping: bool = False):

		self.guild_directs.setdefault(speaker, [])
		self.guild_directs[speaker].append((listener, eavesdropping))

		return

	async def _add_indirect(self, speaker: int, speaker_location: str, listener: TextChannel):

		self.guild_indirects.setdefault(speaker, [])
		self.guild_indirects[speaker].append((speaker_location, listener))

		return

	async def _load_channel(self, channel_ID: int):

		channel = self.cached_channels.get(channel_ID, None)
		if not channel:
			channel = get(self.channels, id = channel_ID)
			self.cached_channels[channel_ID] = channel

		return channel

	async def _load_player(self, player_ID: int):

		player = self.cached_players.get(player_ID, None)

		if not player:
			player = Player(player_ID, self.guild.id)
			self.cached_players[player_ID] = player

		return player

	async def clean_listeners(self):

		for player_ID in self.guild_data.players:

			player = await self._load_player(player_ID)
			direct_listeners.pop(player.channel_ID, None)
			indirect_listeners.pop(player.channel_ID, None)

		for place in self.guild_data.places.values():

			direct_listeners.pop(place.channel_ID, None)

		return

	async def build_listeners(self):

		self.channels = await self.guild.fetch_channels()

		for name, place in self.guild_data.places.items(): #For every place in the graph

			#Get place channel
			channel = await self._load_channel(place.channel_ID)

			for ID in place.occupants: #For each occupant...

				player = await self._load_player(ID)
				player_channel = await self._load_channel(player.channel_ID)

				await self._add_direct(player.channel_ID, channel) #Node listens to player
				await self._add_direct(place.channel_ID, player_channel) #Player listens to place

				for occupant in place.occupants: #Add all other occupants as listeners...

					if occupant == ID: #Skip yourself.
						continue

					other_occupant = await self._load_player(occupant)
					await self._add_direct(other_occupant.channel_ID, player_channel) #Add them as a listener to you.

				for neighbor_place_name in place.neighbors.keys():

					neighbor_place = self.guild_data.places[neighbor_place_name]

					for neighbor_occ_ID in neighbor_place.occupants: #For every person in the neighbor place...

						neighbor_player = await self._load_player(neighbor_occ_ID)
						neighbor_player_channel = await self._load_channel(neighbor_player.channel_ID)

						if neighbor_player.eavesdropping == name: #If they're eavesdropping on us...
							await self._add_direct(player.channel_ID, neighbor_player_channel, True)
							await self._add_direct(place.channel_ID, neighbor_player_channel, True)
						else: #Otherwise...
							await self._add_indirect(player.channel_ID, player.location, neighbor_player_channel)

		return self.guild_directs, self.guild_indirects

#Dialogues
@s(auto_attribs = True)
class DialogueView(View):
	guild: Guild = ib(default = None)
	refresh: callable = ib(default = None)

	def __attrs_pre_init__(self):
		super().__init__()
		return

	def __attrs_post_init__(self):
		self.clearing = False
		self.overwriting = False
		self.directionality = 1
		return

	async def _close_dialogue(self, interaction: Interaction):

		embed, _ = await mbd(
			'Cancelled.',
			'Window closed.',
			'Feel free to call the command again.')

		await interaction.response.edit_message(
			embed = embed,
			attachments = [],
			view = None)
		return

	async def _call_refresh(self, interaction: Interaction):
		embed = await self.refresh()
		await interaction.response.edit_message(embed = embed)
		return


	#Selects
	async def add_roles(self, max_roles: int = 0, callback: callable = None):

		if not max_roles:
			max_roles = len(self.guild.roles)

		role_select = Select(
			placeholder = 'Which roles to allow?',
			select_type = ComponentType.role_select,
			min_values = 0,
			max_values = max_roles)

		role_select.callback = callback if callback else self._call_refresh

		self.add_item(role_select)
		self.role_select = role_select
		return

	def roles(self):
		return {role.id for role in self.role_select.values}

	async def add_people(self, max_people: int = 0, callback: callable = None):

		if not max_people:
			max_people = 25

		people_select = Select(
			placeholder = 'Which people?',
			select_type = ComponentType.user_select,
			min_values = 0,
			max_values = max_people)

		people_select.callback = callback if callback else self._call_refresh

		self.add_item(people_select)
		self.people_select = people_select
		return

	def people(self):
		return self.people_select.values

	async def add_players(self, player_IDs: iter, only_one: bool = False, callback: callable = None):

		player_select = Select(
			placeholder = 'Which players?',
			min_values = 0,
			max_values = 1)

		player_count = 0
		for player_ID in player_IDs:
			member = get(self.guild.members, id = player_ID)
			player_select.add_option(
				label = member.display_name,
				value = str(player_ID))
			player_count += 1

		if player_count == 0:
			player_select.placeholder = 'No players to select.'
			player_select.add_option(label = 'No players!')
			player_select.disabled = True
			self.player_select = player_select
		elif only_one:
			pass
		else:
			player_select.max_values = player_count

		player_select.callback = callback if callback else self._call_refresh

		self.add_item(player_select)
		self.player_select = player_select
		return

	def players(self):
		return {int(player_ID) for player_ID in self.player_select.values}

	async def add_places(self, place_names: iter, callback: callable = None, select_multiple: bool = True):

		if not place_names:
			place_select = Select(
				placeholder = 'No places to select.',
				disabled = True)
			place_select.add_option(
				label = 'Nothing to choose.')
			self.add_item(place_select)
			self.place_select = place_select
			return

		if select_multiple:
			max_values = len(place_names)
		else:
			max_values = 1

		placeholder = 'Which places to select?' if select_multiple else 'Which place?'

		place_select = Select(
			placeholder = placeholder,
			min_values = 1,
			max_values = max_values)

		place_select.callback = callback if callback else self._call_refresh

		[place_select.add_option(label = place) for place in place_names]

		self.add_item(place_select)
		self.place_select = place_select
		return

	async def add_user_places(self, place_names: iter, callback: callable = None):

		if not place_names:
			place_select = Select(
				placeholder = 'No places you can access.',
				disabled = True)
			place_select.add_option(
				label = 'Nothing to choose.')
			self.add_item(place_select)
			self.place_select = place_select
			return

		place_select = Select(placeholder = 'Which place?')
		place_select.callback = callback if callback else self._call_refresh

		for name in place_names:
			place_select.add_option(
				label = name)

		self.add_item(place_select)
		self.place_select = place_select
		return

	def places(self):
		return self.place_select.values

	async def add_paths(self, neighbors: dict, callback: callable = None):


		path_select = Select(
			placeholder = 'Which paths to review?',
			min_values = 0,
			max_values = len(neighbors))
		path_select.callback = callback if callback else self._call_refresh

		for neighbor, path in neighbors.items():

			match path.directionality:

				case 0:
					path_select.add_option(label = f'<- {neighbor}',
						value = neighbor)

				case 1:
					path_select.add_option(label = f'<-> {neighbor}',
						value = neighbor)

				case 2:
					path_select.add_option(label = f'-> {neighbor}',
						value = neighbor)

		self.add_item(path_select)
		self.path_select = path_select
		return

	def paths(self):
		return self.path_select.values

	#Modals
	async def add_rename(self, existing: str = '', bypass_formatting: bool = False, callback: callable = None):

		modal = Modal(title = 'Choose a new name?')

		name_select = InputText(
			label = 'name',
			style = InputTextStyle.short,
			min_length = 1,
			max_length = 20,
			placeholder = "What should it be?",
			value = existing)
		modal.add_item(name_select)
		modal.callback = callback if callback else self._call_refresh

		async def send_modal(interaction: Interaction):
			await interaction.response.send_modal(modal = modal)
			return

		modal_button = Button(
			label = 'Change Name',
			style = ButtonStyle.success)

		modal_button.callback = send_modal
		self.add_item(modal_button)
		self.name_select = name_select
		self.bypass_formatting = bypass_formatting
		self.existing = existing
		return

	async def name(self):

		if self.name_select.value == self.existing:
			return None

		if self.bypass_formatting:
			return self.name_select.value

		return await discordify(self.name_select.value)

	async def add_URL(self, callback: callable = None):

		modal = Modal(title = 'Choose a new avatar?')

		url_select = InputText(
			label = 'url',
			style = InputTextStyle.short,
			min_length = 1,
			max_length = 200,
			placeholder = "What's the image URL?")
		modal.add_item(url_select)
		modal.callback = callback if callback else self._call_refresh

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
		return

	async def add_directionality(self):
		direct = Button(
			label = 'Toggle Direction',
			style = ButtonStyle.secondary)

		async def change_directionality(interaction: Interaction):
			if self.directionality < 2:
				self.directionality += 1
			else:
				self.directionality = 0
			await self._call_refresh(interaction)
			return

		direct.callback = change_directionality
		self.add_item(direct)
		return

	async def add_submit(self, callback: callable):

		submit = Button(
			label = 'Submit',
			style = ButtonStyle.success)
		submit.callback = callback
		self.add_item(submit)
		return

	async def add_confirm(self, callback: callable):

		evilConfirm = Button(
			label = 'Confirm',
			style = ButtonStyle.danger)
		evilConfirm.callback = callback
		self.add_item(evilConfirm)
		return

	async def add_cancel(self):

		cancel = Button(
			label = 'Cancel',
			style = ButtonStyle.secondary)
		cancel.callback = self._close_dialogue
		self.add_item(cancel)
		return

	#Methods
	async def format_whitelist(self, components: iter): #Revisit this

		if self.clearing:
			return "\n• Whitelist: Removing all restrictions. Click 'Clear Whitelist' again" + \
				" to use the old whitelist, or if you select any roles or players below, to use that."

		if self.roles() or self.players():
			return "\n• New whitelist(s)-- will overwrite the old whitelist:" + \
				f" {await format_whitelist(self.roles(), self.players())}"

		first_component = next(iter(components))

		if len(components) == 1:
			return "\n• Whitelist:" + \
				f" {await format_whitelist(first_component.allowed_roles, first_component.allowed_characters)}"

		if any(com.allowed_roles != first_component.allowed_roles or \
			   com.allowed_characters != first_component.allowed_characters for com in components):
			return '\n• Whitelists: Multiple different whitelists.'

		else:
			return "\n• Whitelists: Every part has the same whitelist. " + \
				await format_whitelist(first_component.allowed_roles, \
					first_component.allowed_characters)

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

		view = View()

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

