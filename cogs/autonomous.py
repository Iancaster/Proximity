

#Import-ant Libraries
from discord import Bot, Message, Guild, Member
from discord.ext import commands, tasks
from discord.utils import get_or_fetch

from libraries.classes import ListenerManager, Character, GuildData, \
	ChannelMaker
from libraries.formatting import get_names, format_words, \
	format_characters
from libraries.universal import mbd
from data.listeners import direct_listeners, \
	indirect_listeners, broken_webhook_channels, \
	outdated_guilds, updated_guild_IDs, relay, \
	to_direct_listeners, queue_refresh, replace_speaker

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
		self.update_listeners.start()
		return

	def cog_unload(self):
		self.update_listeners.cancel()
		return

	@tasks.loop(seconds = 6.0)
	async def update_listeners(self):

		if not outdated_guilds and not broken_webhook_channels:
			print(next(self.loading), end = '\r')
			return

		print(f'Updating {len(outdated_guilds)} guild(s).')

		for guild in list(outdated_guilds):

			print(f'- {guild.name}...', end = '')

			listener_manager = ListenerManager(guild)
			await listener_manager.clean_listeners()
			directs, indirects = await listener_manager.build_listeners()

			direct_listeners.update(directs)
			indirect_listeners.update(indirects)

			outdated_guilds.remove(guild)
			updated_guild_IDs.add(guild.id)

			print(f'{len(directs) + len(indirects)} channels updated.')

		if broken_webhook_channels:

			for channel in broken_webhook_channels:

				webhooks = await channel.webhooks()
				if len(webhooks) == 1:
					first_hook = webhooks[0]
					if first_hook.user.id == 1114004384926421126:
						broken_webhook_channels.discard(channel)
						return

				for hook in webhooks:
					await hook.delete()

			if not broken_webhook_channels:
				return

			with open('avatar.png', 'rb') as file:
				avatar = file.read()

			embed, _ = await mbd(
				'Hey. Stop that.',
				"Don't mess with the webhooks on here.",
				"They're mine, got it?")

			for channel in broken_webhook_channels:

				await channel.create_webhook(name = 'Proximity', avatar = avatar)
				await channel.send(embed = embed)
				broken_webhook_channels.discard(channel)
				return

		print('Listeners updated.')
		return

	@commands.Cog.listener()
	async def on_ready(self):

		for guild in self.prox.guilds:
			outdated_guilds.add(guild)

		return

	@commands.Cog.listener()
	async def on_message(self, message: Message):
		if not message.webhook_id:
			await relay(message, Character)

	@commands.Cog.listener()
	async def on_guild_join(self, guild: Guild):

		embed, _ = await mbd(
			'Nice server.',
			"Fair warning, I'll get rebooted a lot while updating to 3.0." + \
				" Use the server link in `/help` to keep up with the changes" + \
				" and you'll know when it's safe to start.",
			"Or just call /help anyways to learn more about me.")

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
			"Please maker yourself at home. " + \
				"\n- Bot information, including the dev log and status, is in the **#information** category." + \
				"\n- You can ask question, chat, find support, and make suggestions in the **#discussion** category." + \
				"\n- And just ask **David Lancaster** for a tour of the bot's features if you want a test run. ",
			"Just call `/help` if you want to learn more.",
			('avatar.png', 'thumb'))

		dm_channel = await member.create_dm()
		await dm_channel.send(embed = embed, file = file)
		return

	@commands.Cog.listener()
	async def on_guild_channel_delete(self, channel):

		guild_data = GuildData(
			channel.guild.id,
			load_places = True,
			load_characters = True)

		found_place = [(name, place) for name, place in guild_data.places.items() if place.channel_ID == channel.id]

		if found_place:

			place_name, place = found_place[0]

			if place.occupants:
				maker = ChannelMaker(channel.guild, 'places')
				await maker.initialize()
				remade_channel = await maker.create_channel(place_name)
				place.channel_ID = remade_channel.id
				guild_data.places[place_name] = place
				await guild_data.save()

				await replace_speaker(place.channel_ID, remade_channel)

				names = await get_names(place.occupants, guild_data.characters)

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

			#Inform neighbor places and occupants that the place is deleted now
			for neighbor_place_name, neighbor_place in list(place.neighbors.items()):
				embed, _ = await mbd(
					'Misremembered?',
					f"Could you be imagining **#{name}**? Strangely, there's no trace.",
					"Whatever the case, it's gone now.")
				await to_direct_listeners(
					embed,
					channel.guild,
					neighbor_place.channel_ID,
					occupants_only = True)

				embed, _ = await mbd(
					'Neighbor place(s) deleted.',
					f'Deleted **#{name}**--this place now has fewer neighbors.',
					"I'm sure it's for the best.")
				neighbor_place_channel = await get_or_fetch(
					channel.guild,
					'channel',
					neighbor_place.channel_ID,
					None)
				if neighbor_place_channel:
					await neighbor_place_channel.send(embed = embed)

				await guild_data.delete_edge(name, neighbor_place_name)

			await guild_data.delete_place(place_name)
			await guild_data.save()
			return

def setup(prox):
	prox.add_cog(Autonomous(prox), override = True)
