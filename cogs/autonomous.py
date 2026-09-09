"""
This is the cog responsible for automatic
updates, like events and keeping the listeners
up to date.
"""

from discord import Bot, TextChannel
from discord.utils import get_or_fetch
from discord.ext import commands

from data.database_handler import CommitResult
from data.database_entries import (
    roleplay_repo, RoleplayData,
    location_repo, LocationData,
    character_repo, CharacterData
)
from libraries.embed_templates import notify_log, LocEmbeds, CharacterEmbeds
from libraries.classes import Relayable, Roleplay, Location, Character


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

# make a way to detect and prevent character deletion
    @commands.Cog.listener() 
    async def on_guild_channel_delete(self, channel: TextChannel):

        rp_data = await roleplay_repo.fetch(channel.guild.id)

        if not isinstance(rp_data, RoleplayData):
            return

        character = await Character.load(channel.id)
        if character is not None:            
            await character.delete()
            embed, file = await CharacterEmbeds.delete.auto(
                character.data.name, 
                character.data.reference)
            await notify_log(rp_data, embed, file)
            return

        location = await Location.load(channel.id)
        if location is None:
            return

        if await location.occupant_count == 0:

            await location.delete()
            embed, file = await LocEmbeds.delete.auto(
                location.data.name, 
                location.data.reference)
            await notify_log(rp_data, embed, file)
 
            return

        return

        replacement_channel = await Relayable.create_channel(
            location.data.name,
            channel.guild.id,
            is_location = True)
        replacement_data = LocationData(
            location_id = replacement_channel.id,
            roleplay_id = replacement_channel.guild.id,
            name = location.data.name,
            reference = location.data.reference)
        replacement_location = await Location.create(replacement_data)

        # for char_data in await location.occupants:
        #     character = Character(char_data)
        #     await character.update()

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
