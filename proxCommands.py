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
            guildData.get('nodes', {}).update(await fn.newNode(name, newNodeChannel.id, roleMentions, peopleMentions))
            db.updateGuild(con, guildData)
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
                f"**Important!** Don't mess with the settings for this channel! \
                    That means no editing the permissions, the name, or deleting it! Use \
                    `/node edit`, `/node rename`, or `/node delete`, or your network will be broken! \
                    \n\n Anyways, here's who is allowed: \n{description} \n\n Of course, this can change \
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

        async def deleteNodes(nodeChannels):

            realNodes = []
            notNodes = 0    

            con = db.connectToGuild()
            guildData = db.getGuild(con, ctx.guild_id)
            con.close()

            #Sort channels into whether actually nodes
            for channel in nodeChannels:

                result = await fn.identifyNodeChannel(guildData, nodeChannel = channel)

                if isinstance(result, discord.TextChannel):
                    realNodes.append(result)
                
                else:
                    notNodes += 1

            #If channels found that aren't nodes
            if notNodes:
                notNodesMessage = f"\n\nYou listed {notNodes} channel(s) that don't belong to any nodes."
            else:
                notNodesMessage = ''

            #If channels found that are nodes
            if realNodes:
                nodeNames = [channel.mention for channel in realNodes]
                nodesMessage = f'Delete the node(s) {await fn.listWords(nodeNames)}?'
            else:
                embed, file = await fn.embed(
                'No nodes!',
                f"You didn't offer any nodes to delete!{notNodesMessage}",
                'You can call the command again?')
                
                await ctx.respond(embed = embed, ephemeral = True)
                return

            #Delete found channels if confirmed
            async def confirmDelete(interaction:discord.Interaction):

                await interaction.response.defer()

                nonlocal realNodes

                con = db.connectToGuild()
                guildData = db.getGuild(con, interaction.guild_id)

                for channel in realNodes:
                    await channel.delete()
                    del guildData.get('nodes', {})[channel.name]

                db.updateGuild(con, guildData)
                con.close()

                embed, file = await fn.embed(
                    'Deleted.',
                    f'Successfully deleted {len(realNodes)} node(s), their channel(s), and edge(s).',
                    'That was a lot of parentheses.')
                try:
                    await interaction.followup.send(embed = embed, ephemeral = True)
                except:
                    pass
                return

            embed, file, view = await fn.dialogue(
                'Confirm Deletion?',
                f'{nodesMessage}{notNodesMessage}',
                'This cannot be reversed.',
                [confirmDelete])
                
            await ctx.respond(embed = embed, view = view, ephemeral = True)
            return

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        con.close()

        result = await fn.identifyNodeChannel(guildData, node, ctx.channel)
        match result:
            
            case channel if isinstance(result, discord.TextChannel): 
                
                await deleteNodes([result])
            
            case 'noNodes': #No nodes in guild
            
                con = db.connectToGuild()
                db.deleteGuild(con, ctx.guild_id)
                con.close()

                embed, file = await fn.embed(
                    'Trick Question?',
                    'You have no nodes to delete.',
                    'So, cool, I guess.')

                await ctx.respond(embed = embed, ephemeral = True)
                return

            case 'namedNotNode': #"Node" channel given isnt a node

                embed, file = await fn.embed(
                'Huh?',
                f"{node.mention} isn't a node channel. Did you select the wrong one?",
                'You can view all the nodes you can delete by just doing /node delete without the #node.')
                await ctx.respond(embed = embed)
                return

            case 'channelsNotNodes': #Multi select
            
                embed, file = await fn.embed(
                    'Delete Node(s)?',
                    "You can delete a node three ways:\n\
                    • Call this command inside of a node channel.\n\
                    • Do `/node delete #node-channel`.\n\
                    • Select multiple node channels with the list below.",
                    'This will remove the node(s), all its edges, and any corresponding channels.')

                view = discord.ui.View()
                
                async def submitNodes(interaction: discord.Interaction):
                    await fn.closeDialogue(interaction)
                    await deleteNodes(nodeSelect.values)
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

            case _:

                print(f'Delete command caught result to be {result}')

                embed, file = await fn.embed(
                    'How? What?',
                    'You just unlocked a new error: Err. 1, Node Deletion.',
                    'Please bring this to the attention of the developer, David Lancaster.')

                await ctx.respond(embed = embed, ephemeral = True)
                return
        
        return

    @node.command(
        name = 'view',
        description = 'View/edit a node.')
    async def view(
        self,
        ctx: discord.ApplicationContext,
        node: discord.Option(
            discord.TextChannel,
            'Either call this command inside a node or name it here.',
            required = False)):
        
        await ctx.defer(ephemeral = True)

        async def deleteNodes(nodeChannels):

            realNodes = []
            notNodes = 0    

            con = db.connectToGuild()
            guildData = db.getGuild(con, ctx.guild_id)
            con.close()

            #Sort channels into whether actually nodes
            for channel in nodeChannels:

                result = await fn.identifyNodeChannel(guildData, nodeChannel = channel)

                if isinstance(result, discord.TextChannel):
                    realNodes.append(result)
                
                else:
                    notNodes += 1

            #If channels found that aren't nodes
            if notNodes:
                notNodesMessage = f"\n\nYou listed {notNodes} channel(s) that don't belong to any nodes."
            else:
                notNodesMessage = ''

            #If channels found that are nodes
            if realNodes:
                nodeNames = [channel.mention for channel in realNodes]
                nodesMessage = f'Delete the node(s) {await fn.listWords(nodeNames)}?'
            else:
                embed, file = await fn.embed(
                'No nodes!',
                f"You didn't offer any nodes to delete!{notNodesMessage}",
                'You can call the command again?')
                
                await ctx.respond(embed = embed, ephemeral = True)
                return

            #Delete found channels if confirmed
            async def confirmDelete(interaction:discord.Interaction):

                await interaction.response.defer()

                nonlocal realNodes

                con = db.connectToGuild()
                guildData = db.getGuild(con, interaction.guild_id)

                for channel in realNodes:
                    await channel.delete()
                    del guildData.get('nodes', {})[channel.name]

                db.updateGuild(con, guildData)
                con.close()

                embed, file = await fn.embed(
                    'Deleted.',
                    f'Successfully deleted {len(realNodes)} node(s), their channel(s), and edge(s).',
                    'That was a lot of parentheses.')
                try:
                    await interaction.followup.send(embed = embed, ephemeral = True)
                except:
                    pass
                return

            embed, file, view = await fn.dialogue(
                'Confirm Deletion?',
                f'{nodesMessage}{notNodesMessage}',
                'This cannot be reversed.',
                [confirmDelete])
                
            await ctx.respond(embed = embed, view = view, ephemeral = True)
            return

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        con.close()

        result = await fn.identifyNodeChannel(guildData, node, ctx.channel)
        match result:
            
            case channel if isinstance(result, discord.TextChannel): 
                
                await deleteNodes([result])
            
            case 'noNodes': #No nodes in guild
            
                con = db.connectToGuild()
                db.deleteGuild(con, ctx.guild_id)
                con.close()

                embed, file = await fn.embed(
                    'Trick Question?',
                    'You have no nodes to delete.',
                    'So, cool, I guess.')

                await ctx.respond(embed = embed, ephemeral = True)
                return

            case 'namedNotNode': #"Node" channel given isnt a node

                embed, file = await fn.embed(
                'Huh?',
                f"{node.mention} isn't a node channel. Did you select the wrong one?",
                'You can view all the nodes you can delete by just doing /node delete without the #node.')
                await ctx.respond(embed = embed)
                return

            case 'channelsNotNodes': #Multi select
            
                embed, file = await fn.embed(
                    'Delete Node(s)?',
                    "You can delete a node three ways:\n\
                    • Call this command inside of a node channel.\n\
                    • Do `/node delete #node-channel`.\n\
                    • Select multiple node channels with the list below.",
                    'This will remove the node(s), all its edges, and any corresponding channels.')

                view = discord.ui.View()
                
                async def submitNodes(interaction: discord.Interaction):
                    await fn.closeDialogue(interaction)
                    await deleteNodes(nodeSelect.values)
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

            case _:

                print(f'Delete command caught result to be {result}')

                embed, file = await fn.embed(
                    'How? What?',
                    'You just unlocked a new error: Err. 1, Node Deletion.',
                    'Please bring this to the attention of the developer, David Lancaster.')

                await ctx.respond(embed = embed, ephemeral = True)
                return
        
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
        if not guildData.get('nodes', {}) and not guildData.get('edges', {}):
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

            for node in guildData.get('nodes', {}).values():

                try:
                    nodeChannel = await discord.utils.get_or_fetch(interaction.guild, 'channel', node['channelID'])
                    await nodeChannel.delete()
                except:
                    pass

            db.deleteGuild(con, interaction.guild_id)
            con.close()

            embed, file = await fn.embed(
                'See you.',
                'All guild data, nodes, and edges, have been deleted, alongside player info. \
                Player and node channels have been deleted, and location messages are gone, too.',
                'You can always make them again if you change your mind.')
            
            await interaction.response.edit_message(embed = embed, view = None)

            return

        callbacks = [deleteData]
        embed, file, view = await fn.dialogue(
        f'Delete all data?',
        f"You're about to delete {len(guildData.get('nodes', {}).keys())} nodes \
            and {len(guildData.get('edges', {}).keys())} edges.",
        'This will also delete all node and player channels.',
        callbacks)

        await ctx.respond(embed = embed, view = view)
        
        return
    
def setup(prox):

    prox.add_cog(nodeCommands(prox), override = True)
    prox.add_cog(serverCommands(prox), override = True)


    # @node.command(
    #     name = 'delete',
    #     description = 'Delete a node.')
    # async def delete(
    #     self,
    #     ctx: discord.ApplicationContext,
    #     node: discord.Option(
    #         discord.TextChannel,
    #         'Either call this command inside a node or name it here.',
    #         required = False)):
        
    #     await ctx.defer(ephemeral = True)

    #     con = db.connectToGuild()
    #     guildData = db.getGuild(con, ctx.guild_id)
    #     deletingNodes = []

    #     #If no nodes exist
    #     if not guildData['nodes']:
    #         db.deleteGuild(con, ctx.guild_id)
    #         con.close()

    #         embed, file = await fn.embed(
    #             'Trick Question?',
    #             'You have no nodes to delete.',
    #             'So, cool, I guess.')

    #         await ctx.respond(embed = embed, ephemeral = True)
    #         return
       
    #     #Channels given for deletion
    #     async def deleteNodes(nodeChannels):

    #         realNodes = []
    #         notNodes = []

    #         #Sort channels into whether actually nodes
    #         for channel in nodeChannels:

    #             if channel.name in guildData['nodes']:

    #                 realNodes.append(channel)
                
    #             else:

    #                 notNodes.append(channel)
            
    #         #If channels found that aren't nodes
    #         if notNodes:
    #             notNodesMessage = f"\n\nYou listed {len(notNodes)} channel(s) that don't belong to a node."
    #         else:
    #             notNodesMessage = ''

    #         #If channels found that are nodes
    #         if realNodes:
    #             nodeNames = [channel.mention for channel in realNodes]
    #             nodesMessage = f'Delete the node(s) {await fn.listWords(nodeNames)}?'
    #         else:
    #             embed, file = await fn.embed(
    #             'No nodes!',
    #             f"You didn't offer any nodes to delete!{notNodesMessage}",
    #             'You can call the command again?')
                
    #             await ctx.respond(embed = embed)
    #             return

    #         #Delete found channels if confirmed
    #         async def confirmDelete(interaction:discord.Interaction):

    #             await interaction.response.defer()

    #             nonlocal realNodes

    #             con = db.connectToGuild()
    #             guildData = db.getGuild(con, interaction.guild_id)

    #             for channel in realNodes:
    #                 await channel.delete()
    #                 del guildData['nodes'][channel.name]

    #             db.updateGuild(con, guildData)
    #             con.close()

    #             embed, file = await fn.embed(
    #                 'Deleted.',
    #                 f'Successfully deleted {len(realNodes)} nodes and their channel(s).',
    #                 'Closed the book on those places, eh?')
    #             try:
    #                 await interaction.followup.send(embed = embed, ephemeral = True)
    #             except:
    #                 pass
    #             return

    #         embed, file, view = await fn.dialogue(
    #             'Confirm Deletion?',
    #             f'{nodesMessage}{notNodesMessage}',
    #             'This cannot be reversed.',
    #             [confirmDelete])
                
    #         await ctx.respond(embed = embed, view = view)
    #         return

    #     #If channel is a node
    #     if ctx.channel.name in guildData['nodes']:
    #         deletingNodes = [ctx.channel]
    #         await deleteNodes(deletingNodes)

    #     #If a node is given in the command
    #     elif node:

    #         if node.name in guildData['nodes']:
    #             deletingNodes = [node]
    #             await deleteNodes(deletingNodes)

    #         else:
    #             embed, file = await fn.embed(
    #             'Huh?',
    #             f"{node.mention} isn't a node channel. Did you select the wrong one?",
    #             'You can view all the nodes you can delete by just doing /node delete without the #node.')
    #             await ctx.respond(embed = embed)
 
    #     #Multi Select - Channel is not a node and no node given in command
    #     else:
            
    #         embed, file = await fn.embed(
    #             'Delete Node?',
    #             "You can delete a node three ways:\n\
    #             • Call this command inside of a node channel.\n\
    #             • Do `/node delete #node-channel`.\n\
    #             • Select any node channels with the list below.",
    #             'This will remove the node, all its edges, and its channel.')

    #         view = discord.ui.View()
            
    #         async def submitNodes(interaction: discord.Interaction):
    #             await fn.closeDialogue(interaction)
    #             await deleteNodes(nodeSelect.values)
    #             return

    #         nodeSelect = discord.ui.Select(
    #             placeholder = 'Which nodes to delete?',
    #             select_type = discord.ComponentType.channel_select,
    #             min_values = 1,
    #             max_values = len(ctx.guild.channels))
    #         nodeSelect.callback = submitNodes
    #         view.add_item(nodeSelect)

    #         cancel = discord.ui.Button(
    #             label = 'Cancel',
    #             style = discord.ButtonStyle.secondary)
    #         cancel.callback = fn.closeDialogue
    #         view.add_item(cancel)

    #         await ctx.respond(embed = embed, view = view)

    #     con.close()
    #     return
