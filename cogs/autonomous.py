

#Import-ant Libraries
from discord import Bot, Message
from discord.ext import commands
from asyncio import sleep

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
        return

    async def update_listeners(self):

        for guild in list(outdated_guilds):

            listener_manager = ListenerManager(guild)
            await listener_manager.clean_listeners()
            directs, indirects = await listener_manager.build_listeners()

            direct_listeners.update(directs)
            indirect_listeners.update(indirects)

            outdated_guilds.remove(guild)
            updated_guild_IDs.add(guild.id)

            print(f'Updated {len(direct_listeners) + len(indirect_listeners)} channels in {guild.name}!')

        if broken_webhook_channels:

            print(f'Fixing webhooks for {len(broken_webhook_channels)} channels.')

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
        await sleep(5)
        return await self.update_listeners()

    @commands.Cog.listener()
    async def on_ready(self):

        for guild in self.prox.guilds:
            outdated_guilds.add(guild)
            print(f'Added {guild.name} to the queue of servers needing updated listeners.')

        return await self.update_listeners()

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if not message.webhook_id:
            await relay(message)

def setup(prox):
    prox.add_cog(Autonomous(prox), override = True)
