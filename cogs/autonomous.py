

#Import-ant Libraries
from discord import Bot, Message, Guild, Member
from discord.ext import commands, tasks
from discord.utils import get_or_fetch, get

from libraries.new_classes import GuildData, ListenerManager, Character
from libraries.universal import *
from libraries.formatting import *
from data.listeners import *

from itertools import cycle

#Classes
class Autonomous(commands.Cog):
	"""
	This is the cog responsible for automatic
	updates, like events and keeping the listeners
	up to date.
	"""

	def __init__(self, bot: Bot):
		self.prox = bot
		self.loading = cycle(['|', '/', '-', '\\' ])
		self.update.start()
		self.listeners_ready = True
		self.webhooks_ready = True
		return

	def cog_unload(self):
		self.update_listeners.cancel()
		return

	async def _update_listeners(self):

		self.listeners_ready = False

		for guild in list(outdated_guilds):

			GD = GuildData(guild.id, load_places = True, load_characters = True)
			LM = ListenerManager(guild, GD)
			await LM.load_channels()
			await LM.clean_listeners()
			await LM.build_listeners()

			outdated_guilds.remove(guild)
			updated_guild_IDs.add(guild.id)

		self.listeners_ready = True
		return

	async def _update_webhooks(self):

		self.webhooks_ready = False

		for channel in list(broken_webhook_channels):

			valid_webhook_found = False
			for webhook in list(await channel.webhooks()):

				if valid_webhook_found or webhook.user.id != 1114004384926421126:
					await webhook.delete()
					continue

				valid_webhook_found = True

			if valid_webhook_found:
				broken_webhook_channels.discard(channel)


		if not broken_webhook_channels:
			self.webhooks_ready = True
			return

		with open('assets/avatar.png', 'rb') as file:
			avatar = file.read()

		embed, _ = await mbd(
			'Hey. Stop that.',
			"Don't mess with the webhooks on here.",
			"They're mine, got it?")

		for channel in list(broken_webhook_channels):

			await channel.create_webhook(name = 'Proximity', avatar = avatar)
			await channel.send(embed = embed)
			broken_webhook_channels.discard(channel)

		self.webhooks_ready = True

		return

	@tasks.loop(seconds = 6.0)
	async def update(self):

		if self.listeners_ready:
			await self._update_listeners()

		if self.webhooks_ready:
			await self._update_webhooks()

		print(next(self.loading), end = '\r')

		return

	@commands.Cog.listener()
	async def on_ready(self):

		for guild in self.prox.guilds:
			outdated_guilds.add(guild)

		return

	@commands.Cog.listener()
	async def on_message(self, message: Message):

		if message.webhook_id:
			return

		if message.author.id == 1114004384926421126 or message.author.id == 1161017761888219228: #Self.
			return

		if message.content and message.content[0] == '\\':
			return

		await relay(message, Character(message.channel.id))
		return

	@commands.Cog.listener()
	async def on_guild_join(self, guild: Guild):

		embed, _ = await mbd(
			'Nice server.',
			" Use the server link in `/help` to get your bearings.",
			"I look forward to seeing what we can do together.")

		for channel in await guild.fetch_channels():

			try:
				await channel.send(embed = embed)
				break
			except:
				continue

		return

	@commands.Cog.listener()
	async def on_member_join(self, member: Member):

		if member.guild.id != 1114005940392439899:
			return

		if member.bot:
			return

		embed, file = await mbd(
			f'Welcome to the Proximity server, {member.display_name}.',
			"Please make yourself at home. " +
				"\n- Bot information, including the dev log and status, is in the **#information** category." +
				"\n- You can ask question, chat, find support, and make suggestions in the **#discussion** category." +
				"\n- And just ask **David Lancaster** for a tour of the bot's features if you want a test run. ",
			"Just call `/help` if you want to learn more.",
			('avatar.png', 'thumb'))

		await member.send(embed = embed, file = file)
		return

	@commands.Cog.listener()
	async def on_guild_channel_update(self, old_version, new_version):

		if old_version.name == new_version.name:
			return

		GD = GuildData(
			old_version.guild.id,
			load_places = True,
			load_characters = True)

		place_name, place_data = next(((name, place) \
			for name, place in GD.places.items() \
			if place.channel_ID == old_version.id), (None, None))

		if not place_data:
			print(f'Channel updated but it was not a place channel (or was it?)')
			return

		print(f'Found a place named {place_name} with new name of {new_version.name}')

		other_names = GD.places.keys()
		other_names.discard(place_name)
		new_name = await unique_name(new_version.name, other_names)
		if new_name != new_version.name:
			await new_version.edit(name = new_name)
			return
		elif old_version.name == new_name:
			return

		await GD.rename_place(place_name, new_name)
		await GD.save()

		embed, _ = await mbd(
			'Strange.',
			f'This place was once named **#{place_name}**,' +
				f' but you now feel it should be called **#{new_name}**.',
			'Better find your bearings.')
		await to_direct_listeners(
			embed,
			new_version.guild,
			new_version.id,
			occupants_only = True)

		embed, _ = await mbd(
			'Edited.',
			f'Renamed **#{place_name}** to {new_version.mention}.',
			'Another successful revision.')
		await new_version.send(embed = embed)

		return

	@commands.Cog.listener()
	async def on_guild_channel_delete(self, channel):

		GD = GuildData(
			channel.guild.id,
			load_places = True,
			load_characters = True)

		found_place = [(name, place) for name, place in GD.places.items() if place.channel_ID == channel.id]

		if found_place:

			place_name, place = found_place[0]

			if place.occupants:
				maker = ChannelMaker(channel.guild, 'places')
				await maker.initialize()
				remade_channel = await maker.create_channel(place_name)
				place.channel_ID = remade_channel.id
				GD.places[place_name] = place
				await GD.save()

				await replace_speaker(channel, remade_channel)

				names = await get_names(place.occupants, GD.characters)

				embed, _ = await mbd(
					'Not so fast.',
					"There's still people inside this place:" + \
						f" {await format_characters(names)}" + \
						" to be specific. Either delete them as players" + \
						" with `/delete character` or move them out with " + \
						" `/review character`.",
					'Either way, you can only delete empty places.')
				await remade_channel.send(embed = embed)
				return

			await GD.delete_place(place_name)
			await GD.save()

			#Inform neighbor places and occupants that the place is deleted now
			player_embed, _ = await mbd(
				'Misremembered?',
				f"Could you have been imagining **#{place_name}**? Strangely, there's no trace.",
				"Whatever the case, it's not here.")
			host_embed, _ = await mbd(
				'Neighbor location deleted.',
				f'Deleted **#{place_name}**--this place now has fewer neighbors.',
				"I'm sure it's for the best.")
			for neighbor_place_name in place.neighbors.keys():

				await to_direct_listeners(
					player_embed,
					channel.guild,
					GD.places[neighbor_place_name].channel_ID,
					occupants_only = True)

				neighbor_place_channel = await get_or_fetch(
					channel.guild,
					'channel',
					GD.places[neighbor_place_name].channel_ID,
					default = None)
				if neighbor_place_channel:
					await neighbor_place_channel.send(embed = host_embed)

			await remove_speaker(channel)
			return

		char_name = GD.characters.get(channel.id, None)
		if char_name:

			char_data, last_seen = await GD.delete_character(channel.id)
			await GD.save()

			await remove_speaker(channel)

			#Inform other occupants that character is deleted now
			player_embed, _ = await mbd(
				'Into thin air.',
				f"Where has *{char_name}* gone?",
				"You get the impression you won't be seeing them again.")
			await to_direct_listeners(
				player_embed,
				channel.guild,
				last_seen.channel_ID,
				occupants_only = False)

			avatar = (char_data.avatar, 'thumb') if char_data.avatar else None

			#As well as the location they were last seen in.
			host_embed, file = await mbd(
				'Character deleted.',
				f'Deleted *{char_name}*. This location now has fewer people.',
				"I'm sure it's for the best.",
				avatar)
			last_seen_channel = await get_or_fetch(
				channel.guild,
				'channel',
				last_seen.channel_ID,
				default = None)
			if last_seen_channel:
				await last_seen_channel.send(embed = host_embed, file = file)

			return

		return

	@commands.Cog.listener()
	async def on_webhooks_update(self, channel):

		if channel in broken_webhook_channels:
			return

		GD = GuildData(channel.guild.id,
			load_places = True,
			load_characters = True)

		if channel.id in GD.characters:
			broken_webhook_channels.add(channel)

		found_place = get(GD.places.values(), channel_ID = channel.id)
		if found_place:
			broken_webhook_channels.add(channel)

		return

def setup(prox):
	prox.add_cog(Autonomous(prox), override = True)
