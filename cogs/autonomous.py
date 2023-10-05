

#Import-ant Libraries
from discord import Bot, Message, Guild, Member
from discord.ext import commands, tasks

from data.listeners import direct_listeners, indirect_listeners, \
    outdated_guilds, updated_guild_IDs, broken_webhook_channels, \
    relay
from libraries.classes import ListenerManager
from libraries.universal import mbd

#Classes
class Autonomous(commands.Cog):
    """
    This is the cog responsible for keeping they
    Listeners up to date. When someone speaks, the
    bot needs to know who to relay the message to.
    """

    def __init__(self, bot: Bot):
        self.prox = bot
        self.update_listeners.start()
        return

    def cog_unload(self):
        self.update_listeners.cancel()

    @tasks.loop(seconds = 6.0)
    async def update_listeners(self):

        for guild in list(outdated_guilds):

            listener_manager = ListenerManager(guild)
            await listener_manager.clean_listeners()
            directs, indirects = await listener_manager.build_listeners()

            direct_listeners.update(directs)
            indirect_listeners.update(indirects)

            outdated_guilds.remove(guild)
            updated_guild_IDs.add(guild.id)

            print(f'Updated {len(directs) + len(indirects)} channels in {guild.name}!')

        if broken_webhook_channels:

            #print(f'Fixing webhooks for {len(broken_webhook_channels)} channels.')

            with open('assets/avatar.png', 'rb') as file:
                avatar = file.read()

            embed, _ = await mbd(
                'Hey. Stop that.',
                "Don't mess with the webhooks on here.",
                "They're mine, got it?")

            for channel in broken_webhook_channels:

                webhooks = await channel.webhooks()
                if len(webhooks) != 1:
                    pass
                else:
                    first_hook = webhooks[0]
                    if first_hook.user == self.prox.user:
                        broken_webhook_channels.discard(channel)
                        return

                for hook in webhooks:
                    await hook.delete()

                await channel.create_webhook(name = 'Proximity', avatar = avatar)
                await channel.send(embed = embed)
                broken_webhook_channels.discard(channel)
                return

        # print('Direct listeners:' + ''.join(f'\nSpeaker: ...{str(speaker_ID)[-3:]}, Listener(s): ' + \
        #     f' {[channel.name for channel, _ in listeners]}' \
        #     for speaker_ID, listeners in direct_listeners.items()))
        return

    @commands.Cog.listener()
    async def on_ready(self):

        print('ready!')

        for guild in self.prox.guilds:
            outdated_guilds.add(guild)
            print(f'Added {guild.name} to the queue of servers needing updated listeners.')

        return await self.update_listeners()

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if not message.webhook_id:
            await relay(message)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild):

        embed, _ = await mbd(
            'Nice server.',
            "Fair warning, I'll get rebooted a lot while updating to 2.0." + \
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

        embed, file = await mbd(
            f'Welcome to the Proximity server, {member.display_name}.',
            "Please maker yourself at home. " + \
                "\n- Bot information, including the dev log and status, is in the **#information** category." + \
                "\n- You can ask question, chat, find support, and make suggestions in the **#discussion** category." + \
                "\n- And just ask **David Lancaster** for a tour of the bot's features if you want a test run. ",
            "And please, call `/help` if you want to learn more.",
            ('avatar.png', 'thumb'))

        dm_channel = await member.create_dm()
        await dm_channel.send(embed = embed, file = file)
        return


def setup(prox):
    prox.add_cog(Autonomous(prox), override = True)
