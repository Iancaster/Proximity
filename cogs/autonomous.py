"""
This is the cog responsible for automatic
updates, like events and keeping the listeners
up to date.
"""

from discord import Bot, TextChannel
from discord.utils import get_or_fetch
from discord.ext import commands

from libraries.classes import RPServer, Location, Character


class Autonomous(commands.Cog):

    # @commands.Cog.listener()
    # async def on_message(self, message: Message):

    #     if message.webhook_id:
    #         return

    #     if message.author.id == 1114004384926421126 or message.author.id == 1161017761888219228: #Self.
    #         return

    #     if message.content and message.content[0] == '\\':
    #         return

    #     await relay(message, Character(message.channel.id))
    #     return

    # @commands.Cog.listener()
    # async def on_guild_join(self, guild: Guild):

    #     embed, _ = await mbd(
    #         'Nice server.',
    #         "Use the server link in `/help` to get your bearings.",
    #         "I look forward to seeing what we can do together.")

    #     for channel in await guild.fetch_channels():

    #         try:
    #             await channel.send(embed = embed)
    #             break
    #         except:
    #             continue

    #     return

    # @commands.Cog.listener()
    # async def on_member_join(self, member: Member):

    #     if member.guild.id != 1114005940392439899:
    #         return

    #     if member.bot:
    #         return

    #     embed, file = await mbd(
    #         f'Welcome to the Proximity server, {member.display_name}.',
    #         "Please make yourself at home. " +
    #             "\n- Bot information, including the dev log and status, is in the **#information** category." +
    #             "\n- You can ask question, chat, find support, and make suggestions in the **#discussion** category." +
    #             "\n- And just ask **David Lancaster** for a tour of the bot's features if you want a test run. ",
    #         "Just call `/help` if you want to learn more.",
    #         ('avatar.png', 'thumb'))

    #     await member.send(embed = embed, file = file)
    #     return

    # @commands.Cog.listener()
    # async def on_guild_channel_update(self, old_version, new_version):

    #     if old_version.name == new_version.name:
    #         return

    #     GD = GuildData(
    #         old_version.guild.id,
    #         load_places = True,
    #         load_characters = True)

    #     place_name, place_data = next(((name, place) \
    #         for name, place in GD.places.items() \
    #         if place.channel_ID == old_version.id), (None, None))

    #     if not place_data:
    #         return

    #     other_names = set(GD.places.keys())
    #     other_names.discard(place_name)
    #     new_name = await unique_name(new_version.name, other_names)
    #     if new_name != new_version.name:
    #         await new_version.edit(name = new_name)
    #         return
    #     elif old_version.name == new_name:
    #         return

    #     await GD.rename_place(place_name, new_name)
    #     await GD.save()

    #     embed, _ = await mbd(
    #         'Strange (auto).',
    #         f'This place was once named **#{place_name}**,' +
    #             f' but you now feel it should be called **#{new_name}**.',
    #         'Better find your bearings.')
    #     await to_direct_listeners(
    #         embed,
    #         new_version.guild,
    #         new_version.id,
    #         occupants_only = True)

    #     embed, _ = await mbd(
    #         'Edited.',
    #         f'Renamed **#{place_name}** to {new_version.mention}.',
    #         'Another successful revision.')
    #     await new_version.send(embed = embed)

    #     return

    @commands.Cog.listener() 
    async def on_guild_channel_delete(self, channel: TextChannel):

        server = RPServer(channel.guild.id)

        if not await server.exists:
            return
        
        await server.fetch()

        character = Character(channel.id)

        if await character.exists:
            return await character.delete()

        location = Location(channel.id)

        if not await location.exists:
            return

        if await location.character_count == 0:

            await location.fetch()

            log_channel = await get_or_fetch(
                channel.guild, 
                "channel", 
                server.log_channel_id or 0,
                default = None)

            await location.delete(
                log_channel = log_channel,
                location_channel = None)
 
            return

        # make a way to detect and prevent character deletion

        return

    # @commands.Cog.listener()
    # async def on_webhooks_update(self, channel):

    #     if channel in broken_webhook_channels:
    #         return

    #     GD = GuildData(channel.guild.id,
    #         load_places = True,
    #         load_characters = True)

    #     if channel.id in GD.characters:
    #         broken_webhook_channels.add(channel)

    #     found_place = get(GD.places.values(), channel_ID = channel.id)
    #     if found_place:
    #         broken_webhook_channels.add(channel)

    #     return

def setup(prox: Bot):
    prox.add_cog(Autonomous(prox), override = True)
