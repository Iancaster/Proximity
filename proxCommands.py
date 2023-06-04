import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands
from discord import utils
import functions as fn
import databaseFunctions as db

class nodeCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    node = SlashCommandGroup(
        name = 'node',
        description = 'Node controls.',
        guild_only = True,
        guild_ids = [1114005940392439899])

    @node.command(
        name = 'new',
        description = 'Create a new node.')
    async def new(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(
            str,
            'What should it be called?',
            required = True)):

        await ctx.defer(ephemeral = True)

        name = await fn.formatNodeName(name)

        allowedRoles = []
        allowedPeople = []
        roleMentions = []
        peopleMentions = []
        description = await fn.formatWhitelist(allowedRoles, allowedPeople)

        #Formatting results
        embed, file = await fn.embed(
            f'New Node: {name}',
            description,
            'You can also limit who can visit this node.')

        #View
        addRole, addPerson, submit = await fn.initWhitelist(len(ctx.guild.roles), len(ctx.guild.members))

        async def changeRoles(interaction: discord.Interaction):
            nonlocal allowedRoles
            nonlocal peopleMentions
            nonlocal roleMentions
            allowedRoles = addRole.values

            roleMentions = [f'<@&{role.id}>' for role in allowedRoles]

            description = await fn.formatWhitelist(roleMentions, peopleMentions)
            embed, file = await fn.embed(
                f'New Node: {name}',
                description,
                'No pings were made in the production of this message.')
            await interaction.response.edit_message(embed = embed)
            return
        
        async def changePeople(interaction: discord.Interaction):
            nonlocal allowedPeople
            nonlocal roleMentions
            nonlocal peopleMentions
            allowedPeople = addPerson.values
            
            peopleMentions = [f'<@{person.id}>' for person in allowedPeople]

            description = await fn.formatWhitelist(roleMentions, peopleMentions)
            embed, file = await fn.embed(
                f'New Node: {name}',
                description,
                'No pings were made in the production of this message.')
            await interaction.response.edit_message(embed = embed)
            return
        
        async def submitPerms(interaction: discord.Interaction):

            await interaction.response.defer()
            
            nonlocal allowedRoles
            nonlocal allowedPeople
            nonlocal peopleMentions
            nonlocal roleMentions

            allowedRoles = list(role.id for role in allowedRoles)
            allowedPeople = list(person.id for person in allowedPeople)


            nodesList = list(category for category in interaction.guild.categories if category.name == 'nodes')
            if not nodesList:
                nodesCategory = await interaction.guild.create_category('nodes')
            else:
                nodesCategory = nodesList[0]

            
            permissions = {interaction.guild.default_role : discord.PermissionOverwrite(read_messages = False),
            interaction.guild.me : discord.PermissionOverwrite(send_messages = True, read_messages =True)}
            newNodeChannel = await interaction.guild.create_text_channel(
                name,
                category = nodesCategory,
                overwrites = permissions)
            
            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)
            guildData['nodes'].update(await fn.newNode(name, newNodeChannel.id, roleMentions, peopleMentions))
            db.updateGuild(con, interaction.guild_id, guildData['nodes'])
            con.close()

            embed, file = await fn.embed(
                'Node created!',
                f"You can find it at {newNodeChannel.mention}. \
                    The permissions you requested are set-- just not in the channel's Discord \
                    settings. No worries, it's all being kept track of by me.",
                'I hope you like it.')
            
            await interaction.followup.send(embed = embed, ephemeral = True)

            description = await fn.formatWhitelist(roleMentions, peopleMentions)

            embed, file = await fn.embed(
                'Cool, new node.',
                f"Here's who is allowed: \n{description} \n\n Of course, this can change \
                    with `/node restrict`. I haven't added that command yet, but when I do,\
                    you can double check who's allowed in with `/node view`, also not added.",
                'Yup.')
            
            await newNodeChannel.send(embed = embed)
    
            return
        
        callbacks = [changeRoles, changePeople, submitPerms]
        view = await fn.refineWhitelist(addRole, addPerson, submit, callbacks)

        await ctx.respond(embed = embed, view = view)

        return
    
    @node.command(
        name = 'delete',
        description = 'Delete a node.')
    async def delete(
        self,
        ctx: discord.ApplicationContext,
        node: discord.Option(
            discord.TextChannel,
            'Either call this command inside a node or name it here.',
            required = False)):
        
        await ctx.defer(ephemeral = True)

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        deletingNodes = []

        #If no nodes exist
        if not guildData['nodes']:
            db.deleteGuild(con, ctx.guild_id)
            con.close()

            embed, file = await fn.embed(
                'Trick Question?',
                'You have no nodes to delete.',
                'So, cool, I guess.')

            await ctx.respond(embed = embed, ephemeral = True)
            return
       
        #place deleting function here

        #If channel is a node
        if ctx.channel.name in guildData['nodes']:
            deletingNodes = [ctx.channel]
            return

        #If a node is given in the command
        if node:

            if node.name in guildData['nodes']:
                deletingNodes = [node]

            else:
                embed, file = await fn.embed(
                'Huh?',
                f"{node.mention} isn't a node channel. Did you select the wrong one?",
                'You can view all the nodes you can delete by just doing /node delete without the #node.')

                await ctx.respond(embed = embed)

                return
 
        #Multi Select
        if not deletingNodes:
            
            embed, file = await fn.embed(
                'Delete Node?',
                "You can delete a node three ways:\n\
                • Call this command inside of a node channel.\n\
                • Do `/node delete #node-channel`.\n\
                • Select any node channels with the list below.",
                'This will remove the node, all its edges, and its channel.')

            view = discord.ui.View()
            
            async def submitNodes(interaction: discord.Interaction):
                await fn.closeDialogue(interaction)
                await fn.deleteNodes(interaction.channel, nodeSelect.values, ctx.guild_id)
                return

            nodeSelect = discord.ui.Select(
                placeholder = 'Which nodes to delete?',
                select_type = discord.ComponentType.channel_select,
                min_values = 1,
                max_values = len(ctx.guild.channels))
            nodeSelect.callback = submitNodes
            view.add_item(nodeSelect)

            cancel = discord.ui.Button(
                label = 'Cancel',
                style = discord.ButtonStyle.secondary)
            cancel.callback = fn.closeDialogue
            view.add_item(cancel)

            await ctx.respond(embed = embed, view = view)

        con.close()

        return

class serverCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    server = SlashCommandGroup(
        name = 'server',
        description = 'Server controls.',
        guild_only = True,
        guild_ids = [1114005940392439899])

    @server.command(
        name = 'clear',
        description = 'Delete all server data.')
    async def clear( ##Come back here and include a purge for player channels + db
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        if not guildData['nodes'] and not guildData['edges']:
            db.deleteGuild(con, ctx.guild_id)
            con.close()

            embed, file = await fn.embed(
            f'No data to delete!',
            'Data is only made when you create a node or an edge.',
            'Wish granted?')

            await ctx.respond(embed = embed)
            return

        con.close()
 
        async def deleteData(interaction: discord.Interaction):
            
            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)

            for node in guildData['nodes'].values():

                nodeChannel = await discord.utils.get_or_fetch(interaction.guild, 'channel', node['channelID'])
                await nodeChannel.delete()

            db.deleteGuild(con, interaction.guild_id)
            con.close()

            embed, file = await fn.embed(
                'See you.',
                'All guild data, nodes, and edges, have been deleted, alongside player info. \
                Player and node channels have been deleted, and location messages are gone, too.'
                'You can always make them again if you change your mind.')
            
            await interaction.response.edit_message(embed = embed, view = None)

            return

        callbacks = [deleteData]
        embed, file, view = await fn.dialogue(
        f'Delete all data?',
        f"You're about to delete {len(guildData['nodes'].keys())} nodes \
            and {len(guildData['edges'].keys())} edges.",
        'This will also delete all node and player channels.',
        callbacks)

        await ctx.respond(embed = embed, view = view)
        
        return
    
def setup(prox):

    prox.add_cog(nodeCommands(prox), override = True)
    prox.add_cog(serverCommands(prox), override = True)
