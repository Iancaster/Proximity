

#Import-ant Libraries
from discord import Bot
from discord.ext import commands, tasks


from data.listeners import direct_listeners, indirect_listeners, \
    outdated_guilds, updated_guild_IDs, broken_webhook_channels
from libraries.classes import ListenerManager
from libraries.universal import mbd

#Classes
class AutoCommands(commands.Cog):

    def __init__(self, bot: Bot):
        self.update_listeners.start()

    def cog_unload(self):
        self.update_listeners.cancel()

    @tasks.loop(seconds = 5.0)
    async def update_listeners(self):

        for guild in list(outdated_guilds):

            listener_manager = ListenerManager(guild)
            await listener_manager.clean_listeners()
            directs, indirects = await listener_manager.build_listeners()

            direct_listeners.update(directs)
            indirect_listeners.update(indirects)

            outdated_guilds.remove(guild)
            updated_guild_IDs.add(guild.id)

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

        # import json
        # printableListeners = {speakerID : [channel.name for channel, _ in listeners]
        #    for speakerID, listeners in direct_listeners.items()}
        # print(f"Direct listeners: {json.dumps(printableListeners, indent = 4)}")

        return


def setup(prox):
    prox.add_cog(AutoCommands(prox), override = True)
