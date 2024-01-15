

#Import-ant Libraries
from discord import Guild, Message, Embed, TextChannel
from discord.utils import get, get_or_fetch
from asyncio import sleep

from libraries.formatting import format_words
from libraries.universal import mbd, NO_AVATAR_URL

#Variables
updated_guild_IDs = set()
outdated_guilds = set()
direct_listeners = dict()
indirect_listeners = dict()
broken_webhook_channels = set()

#Functions
async def queue_refresh(guild: Guild):
	updated_guild_IDs.discard(guild.id)
	outdated_guilds.add(guild)
	return

async def wait_for_listeners(guild: Guild):

	outdated_guilds.add(guild)
	while guild.id not in updated_guild_IDs:
		await sleep(1)
	return

async def relay(msg: Message, character_class):

	if msg.guild.id not in updated_guild_IDs:
		await wait_for_listeners(msg.guild)

	speaker = character_class(msg.channel.id)

	speaker_name = speaker.name
	speaker_avatar = speaker.avatar or NO_AVATAR_URL

	directs = direct_listeners.get(msg.channel.id, set())
	for channel, eavesdropping in directs:

		webhook = (await channel.webhooks())[0]

		if eavesdropping:
			embed, _ = await mbd(
				'From nearby...',
				msg.content[:2000],
				'You can hear it all from here.')
			await webhook.send(
				username = speaker_name,
				avatar_url = speaker_avatar,
				embed = embed)

			if len(msg.content) > 1999:
				embed, _ = await mbd(
					'Continued.',
					msg.content[2000:4000],
					'What a lot to say.')
				await webhook.send(
					username = speaker_name,
					avatar_url = speaker_avatar,
					embed = embed)

		else:
			files = [await attachment.to_file() for attachment in msg.attachments]
			await webhook.send(
				msg.content[:2000],
				username = speaker_name,
				avatar_url = speaker_avatar,
				files = files)
			if len(msg.content) > 1999:
				await webhook.send(
					msg.content[2000:4000],
					username = speaker_name,
					avatar_url = speaker_avatar)

	indirects = indirect_listeners.get(msg.channel.id, set())
	for channel, speaker_location in indirects:
		embed, _ = await mbd(
			'Hm?',
			f"You think you hear *{speaker_name}* in **#{speaker_location}**.",
			'Perhaps you can /move over to them.')
		await channel.send(embed = embed)

	return

async def remove_speaker(speaker_channel: TextChannel):

	for listener_dict in [direct_listeners, indirect_listeners]:

		own_listeners = listener_dict.pop(speaker_channel.id, set())

		for listener_channel, secondary in own_listeners:

			their_listeners = listener_dict.get(listener_channel.id, dict())

			their_listeners.discard((speaker_channel, secondary))

	return

async def replace_speaker(old_channel: TextChannel, new_channel: TextChannel):

	for listener_dict in [direct_listeners, indirect_listeners]:

		own_listeners = listener_dict.pop(old_channel.id, set())

		for listener_channel, secondary in own_listeners:

			their_listeners = listener_dict[listener_channel.id]

			their_listeners.discard((old_channel, secondary))
			their_listeners.add((new_channel, secondary))

		if own_listeners:
			listener_dict[new_channel.id] = own_listeners

	return

async def to_direct_listeners(embed: Embed, guild: Guild, channel_ID: int, exclude: int = 0, occupants_only: bool = False):

	if guild.id not in updated_guild_IDs:
		await wait_for_listeners(guild)

	directs = direct_listeners.get(channel_ID, set())
	for channel, eavesdropping in list(directs):

		if channel.id == exclude:
			continue

		if eavesdropping and occupants_only:
			continue

		try:
			await channel.send(embed = embed)
		except:

			if not channel.webhooks:
				print(f'#{channel.name} is missing its webhook!')
				continue

			raise ConnectionRefusedError("Tried to send a message to a channel" + \
				f" with some weird error, #{channel.name}, within" + \
				f" {channel.guild.name}. It's probably fine.")

	return

