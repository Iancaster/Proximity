

#Import-ant Libraries
from discord import Guild, Message, Embed, Interaction
from asyncio import sleep
from libraries.universal import mbd

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

async def relay(msg: Message):

    if msg.author.id == 1114004384926421126: #Self.
        return

    if msg.guild.id not in updated_guild_IDs:
        print(f'Waiting for updated listeners in server: {msg.guild.name}.')
        updated_guild_IDs.add(msg.guild)
        while msg.guild.id not in updated_guild_IDs:
            await sleep(1)
        print(f'Updated {msg.guild.name}!')

    try:
        from libraries.classes import Player
        speaker = Player(msg.author.id, msg.guild.id)
    except ImportError:
        speaker = None
        print('Uh oh, cjeck relay() plese')

    speaker_name = speaker.name if speaker.name else msg.author.display_name
    speaker_avatar = speaker.avatar if speaker.avatar else msg.author.display_avatar.url

    directs = direct_listeners.get(msg.channel.id, [])
    for channel, eavesdropping in directs:

        if eavesdropping:
            webhook = (await channel.webhooks())[0]
            embed, _ = await mbd(
                f'{speaker_name}:',
                msg.content[:2000],
                'You hear everything.')
            await webhook.send(
                username = speaker_name,
                avatar_url = speaker_avatar,
                embed = embed)

            if len(msg.content) > 1999:
                embed, _ = await mbd(
                    'Continued.',
                    msg.content[2000:4000],
                    'And wow, is that a lot to say.')
                await webhook.send(
                    username = speaker_name,
                    avatar_url = speaker_avatar,
                    embed = embed)

        else:
            webhook = (await channel.webhooks())[0]
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

    indirects = indirect_listeners.get(msg.channel.id, [])
    for speaker_location, channel in indirects:
        embed, _ = await mbd(
            'Hm?',
            f"You think you hear {speaker_name} in **#{speaker_location}**.",
            'Perhaps you can /move over to them.')
        await channel.send(embed = embed)

    return

async def to_direct_listeners(embed: Embed, guild: Interaction, channel_ID: int, exclude: int = 0, occupants_only: bool = False):

    if guild.id not in updated_guild_IDs:
        print(f'Waiting for updated listeners in server: {guild.name}.')
        outdated_guilds.add(guild)
        while guild.id not in updated_guild_IDs:
            await sleep(1)
        print(f'Updated {guild.name}!')

    directs = direct_listeners.get(channel_ID, [])
    for channel, eavesdropping in directs:

        if channel.id == exclude: #To prevent echos
            continue

        if eavesdropping and occupants_only: #Cant be overheard
            continue

        try:
            await channel.send(embed = embed)
        except: #Whenever this triggers it is NOT probably fine, don't fall for it Gray

            if not channel.webhooks:
                print(f'#{channel.name} is missing its webhook!')
                continue

            raise ConnectionRefusedError("Tried to send a message to a channel" + \
                f" with some weird error, #{channel.name}, within" + \
                f" {channel.guild.name}. It's probably fine.")

    return

