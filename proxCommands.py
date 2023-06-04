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
            required = True
            )):

        await ctx.defer(ephemeral = True)

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
    async def new(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(
            discord.TextChannel,
            'Either call this command inside a node or name it here.',
            required = False)):
        
        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)

        if not guildData['nodes']:
            db.deleteGuild(con, ctx.guild_id)
            con.close()
            return

        if name:
            #delete the named node
            return
        
        #get all node IDs
        nodeIDLIST = []
        if ctx.channel_id in nodeIDLIST:
            #Delete current node
            return

        #Tell them how to use the command, have a view with text_channel_select for it
        await ctx.defer(ephemeral = True)
        #Formatting results
        embed, file = await fn.embed(
            f'Delete Node?',
            'You can delete a node three ways:\
                1. Call this command inside of a node channel.\
                2. Do `/node delete #node-channel`.\
                3. Select a node channel with the list below.',
            'This will remove the node, all its edges, and its channel.')

        await ctx.respond(embed = embed)

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

            await interaction.response.defer()
            
            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)

            for node in guildData['nodes'].values():

                nodeChannel = await discord.utils.get_or_fetch(interaction.guild, 'channel', node['channelID'])
                await nodeChannel.delete()

            db.deleteGuild(con, interaction.guild_id)
            con.close()

            embed, file = await fn.embed(
                'See you.',
                'All guild data and channels and nodes and edges and everything is deleted.',
                'Sad to see you go.')
            
            await interaction.followup.send(embed = embed, ephemeral = True)

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
