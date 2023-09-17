

#Import-ant Libraries
from discord import ApplicationContext, Option, Interaction#, Embed
from discord.ext import commands
from discord.commands import SlashCommandGroup
#from discord.utils import get

from libraries.classes import GuildData, DialogueView, ChannelMaker
from libraries.universal import mbd, loading
from libraries.formatting import discordify, unique_name, format_whitelist
#from libraries.autocomplete import complete_nodes
#from data.listeners import broken_webhook_channels, to_direct_listeners, \
#    direct_listeners, queue_refresh


#Classes
class NodeCommands(commands.Cog):

    node = SlashCommandGroup(
        name = 'node',
        description = 'Manage the nodes of your graph.',
        guild_only = True)

    @node.command(
        name = 'new',
        description = 'Create a new node.')
    async def new(
        self,
        ctx: ApplicationContext,
        name: Option(
            str,
            description = 'What should it be called?',
            default = 'new-node')):

        await ctx.defer(ephemeral = True)

        guild_data = GuildData(ctx.guild_id)

        submitted_name = discordify(name)
        name = submitted_name if submitted_name else 'new-node'
        name = await unique_name(name, guild_data.nodes.keys())

        async def refresh_embed():

            nonlocal name
            name = view.name() if view.name() else name
            name = await unique_name(name, guild_data.nodes.keys())

            description = f'Whitelist: {await format_whitelist(view.roles(), view.players())}'

            embed, _ = await mbd(
                f'New node: {name}',
                description,
                'You can also create a whitelist to limit who can visit this node.')
            return embed

        async def submit_node(interaction: Interaction):

            await loading(interaction)

            nonlocal name

            maker = ChannelMaker(interaction.guild, 'nodes')
            await maker.initialize()
            new_channel = await maker.new_channel(name)

            await guild_data.newNode(
                name = name,
                channelID = new_channel.id,
                new_channel = view.roles(),
                allowed_players = view.players())
            await guild_data.save()

            embed, _ = await mbd(
                f'{new_channel.mention} created!',
                "The permissions you requested are set-- just not in the channel's Discord" + \
                " settings.",
                "No worries, it's all being kept track of by me.")
            await interaction.followup.edit_message(
                message_id = interaction.message.id,
                embed = embed,
                view = None)

            whitelist = await format_whitelist(view.roles(), view.players())
            embed, _ = await mbd(
                'Cool, new node.',
                "Here's who's allowed:" + \
                    f"\n{whitelist}" + \
                    "\n\nDon't forget to connect it to other nodes with `/edge new`.",
                "You can also change the whitelist with /node review.")
            await new_channel.send(embed = embed)
            return

        view = DialogueView(guild = ctx.guild, refresh = refresh_embed)
        await view.addRoles()
        await view.addPlayers(guild_data.players)
        await view.addSubmit(submit_node)
        await view.addName('new-node')
        await view.addCancel()

        embed = await refresh_embed()
        await ctx.respond(embed = embed, view = view)
        return

def setup(prox):
    prox.add_cog(NodeCommands(prox), override = True)
