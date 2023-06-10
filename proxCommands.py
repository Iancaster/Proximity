import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands
import functions as fn
import databaseFunctions as db
import networkx as nx

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
        description = await fn.formatWhitelist(allowedRoles, allowedPeople)

        #Formatting results
        embed, file = await fn.embed(
            f'New Node: {name}',
            description,
            'You can also limit who can visit this node.')

        #View

        async def changeRoles(interaction: discord.Interaction):

            nonlocal allowedRoles
            allowedRoles = [role.id for role in addRole.values]
            roleMentions = [f'<@&{role}>' for role in allowedRoles]

            nonlocal allowedPeople
            peopleMentions = [f'<@{person}>' for person in allowedPeople]
            
            whitelist = await fn.formatWhitelist(roleMentions, peopleMentions)

            embed, file = await fn.embed(
                f'New Node: {name}',
                whitelist,
                'No pings were made in the production of this message.')
            await interaction.response.edit_message(embed = embed)
            return
        
        async def changePeople(interaction: discord.Interaction):
            nonlocal allowedPeople
            allowedPeople = [person.id for person in addPerson.values]
            peopleMentions = [f'<@{person}>' for person in allowedPeople]

            nonlocal allowedRoles
            roleMentions = [f'<@&{role}>' for role in allowedRoles]
            
            whitelist = await fn.formatWhitelist(roleMentions, peopleMentions)

            embed, file = await fn.embed(
                f'New Node: {name}',
                whitelist,
                'No pings were made in the production of this message.')
            await interaction.response.edit_message(embed = embed)
            return
        
        async def submitPerms(interaction: discord.Interaction):

            await interaction.response.defer()
            
            nonlocal allowedRoles
            nonlocal allowedPeople

            peopleMentions = [f'<@{person}>' for person in allowedPeople]
            roleMentions = [f'<@&{role}>' for role in allowedRoles]
            
            nodeCategory = await fn.assertNodeCategory(interaction.guild)
      
            permissions = {interaction.guild.default_role : discord.PermissionOverwrite(read_messages = False),
            interaction.guild.me : discord.PermissionOverwrite(send_messages = True, read_messages =True)}
            newNodeChannel = await interaction.guild.create_text_channel(
                name,
                category = nodeCategory,
                overwrites = permissions)
            
            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)
            guildData.get('nodes', {}).update(await fn.newNode(name, newNodeChannel.id, allowedRoles, allowedPeople))
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
            \n\nAnyways, here's who is allowed:\n{description}\n\n Of course, this can change \
            with `/node edit`, which lets you view/change the whitelist, among other things.",
            "You can also set the location message for this node by doing /node message while you're here.")         
            await newNodeChannel.send(embed = embed)
    
            return
        
        callbacks = [changeRoles, changePeople, submitPerms]
        view, addRole, addPerson, submit, cancel = await fn.whitelistView(len(ctx.guild.roles), ctx.guild.member_count, callbacks)

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

        async def deleteNodes(nodeChannels: list, guildData: dict):

            #Sort channels into whether actually nodes
            nodeChannels, notNodesMessage = await fn.nodeChannelsFromChannels(nodeChannels, guildData)

            #If channels found that are nodes
            if nodeChannels:
                nodeNames = [channel.mention for channel in nodeChannels]
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

                nonlocal nodeChannels

                con = db.connectToGuild()
                guildData = db.getGuild(con, interaction.guild_id)

                for channel in nodeChannels:
                    await channel.delete()
                    del guildData.get('nodes', {})[channel.name]

                db.updateGuild(con, guildData)
                con.close()

                embed, file = await fn.embed(
                    'Deleted.',
                    f'Successfully deleted {len(nodeChannels)} node(s), their channel(s), and edge(s).',
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
                
                await deleteNodes([result], guildData)
            
            case 'noNodes': #No nodes in guild
            
                con = db.connectToGuild()
                db.deleteGuild(con, ctx.guild_id)
                con.close()

                embed, file = await fn.embed(
                    'Trick Question?',
                    'You have no nodes to delete.',
                    'So, cool, I guess.')

                await ctx.respond(embed = embed)
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
                    await deleteNodes(nodeSelect.values, guildData)
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

        return

    @node.command(
        name = 'edit',
        description = 'View/edit a node.')
    async def edit(
        self,
        ctx: discord.ApplicationContext,
        node: discord.Option(
            discord.TextChannel,
            'Either call this command inside a node or name it here.',
            required = False)):
        
        await ctx.defer(ephemeral = True)

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        con.close()

        async def editNodes(givenChannels: list, guildData: dict):

            #Sort channels into whether actually nodes
            givenChannelNames = [channel.name for channel in givenChannels]
            nodes = await fn.nodesFromNames(givenChannelNames, guildData['nodes'])
            notNodesMessage = f"{len(givenChannelNames) - len(nodes)} of the {len(givenChannelNames)} channel(s) you provided don't belong to any node(s)."
            
            if not nodes:

                embed, file = await fn.embed(
                'No nodes!',
                f"You didn't offer any nodes to edit! You can call the command again?",
                notNodesMessage)
                
                await ctx.respond(embed = embed, ephemeral = True)
                return

            async def changeRoles(interaction: discord.Interaction):
                nonlocal allowedRoles
                allowedRoles = [role.id for role in addRole.values]
                roleMentions = [f'<@&{role}>' for role in allowedRoles]

                nonlocal allowedPeople
                peopleMentions = [f'<@{person}>' for person in allowedPeople]
                
                whitelist = await fn.formatWhitelist(roleMentions, peopleMentions)

                if len(nodes) == 1:

                    for name, data in nodes.items():
                        nodeName = name
                        nodeData = data

                    embed = await fn.formatSingleNode(
                        nodeName,
                        whitelist,
                        await fn.listWords(nodeData['occupants']),
                        notNodesMessage)
                
                else:
                    embed = await fn.formatManyNodes(list(nodes.values()), notNodesMessage, whitelist)

                await interaction.response.edit_message(embed = embed)
                return
            
            async def changePeople(interaction: discord.Interaction):
                nonlocal allowedPeople
                allowedPeople = [person.id for person in addPerson.values]
                peopleMentions = [f'<@{person}>' for person in allowedPeople]

                nonlocal allowedRoles
                roleMentions = [f'<@&{role}>' for role in allowedRoles]
                
                whitelist = await fn.formatWhitelist(roleMentions, peopleMentions)

                if len(nodes) == 1:

                    for name, data in nodes.items():
                        nodeName = name
                        nodeData = data

                    embed = await fn.formatSingleNode(
                        nodeName,
                        whitelist,
                        await fn.listWords(nodeData['occupants']),
                        notNodesMessage)
                
                else:
                    embed = await fn.formatManyNodes(list(nodes.values()), notNodesMessage, whitelist)

                await interaction.response.edit_message(embed = embed)
                return
            
            async def submitPerms(interaction: discord.Interaction):
                
                nonlocal allowedRoles
                nonlocal allowedPeople

                updatedNodes = await fn.updateNodeWhitelists(nodes, allowedRoles, allowedPeople)
                
                con = db.connectToGuild()
                guildData = db.getGuild(con, interaction.guild_id)

                guildData['nodes'].update(updatedNodes)

                db.updateGuild(con, guildData)
                con.close()

                embed, file = await fn.embed(
                    f'{len(updatedNodes)} Node(s) updated!',
                    f"""Be aware that this didn't move any occupants. If someone is in a node\
                    that they don't have permission to be in anymore, they're still there, they\
                    just won't be able to get back in next time they leave and try to come back.\
                    If you want them out as soon as possible, you can `/teleport` them out.""",
                    'Best of luck.')        
                await interaction.response.edit_message(embed = embed, view = None)        
                return
        
            callbacks = [changeRoles, changePeople, submitPerms, fn.closeDialogue]
            view, addRole, addPerson, submit, cancel = await fn.whitelistView(len(ctx.guild.roles), ctx.guild.member_count, callbacks)

            if len(nodes) == 1:

                for name, data in nodes.items():
                    nodeName = name
                    nodeData = data

                allowedRoles = nodeData['allowedRoles']
                allowedPeople = nodeData['allowedPeople']

                roleMentions = [f'<@&{role}>' for role in allowedRoles]
                peopleMentions = [f'<@{person}>' for person in allowedPeople]

                whitelist = await fn.formatWhitelist(roleMentions, peopleMentions)

                embed = await fn.formatSingleNode(
                    nodeName,
                    whitelist,
                    await fn.listWords(nodeData['occupants']),
                    notNodesMessage)

                await ctx.respond(embed = embed, view = view, ephemeral = True)
                return

            else:

                allowedRoles = allowedPeople = []

                embed = await fn.formatManyNodes(list(nodes.values()), notNodesMessage)

                await ctx.respond(embed = embed, view = view, ephemeral = True)
                return
                
        result = await fn.identifyNodeChannel(guildData, node, ctx.channel)
        match result:
            
            case channel if isinstance(result, discord.TextChannel): 
                
                await editNodes([result], guildData)
            
            case 'noNodes': #No nodes in guild
            
                con = db.connectToGuild()
                db.deleteGuild(con, ctx.guild_id)
                con.close()

                embed, file = await fn.embed(
                    'Slow down, cowboy.',
                    "You have no nodes to edit. You can't alter something that's not there.",
                    'Make some first with /node new.')

                await ctx.respond(embed = embed)
                return

            case 'namedNotNode': #"Node" channel given isnt a node

                embed, file = await fn.embed(
                'What?',
                f"{node.mention} isn't a node channel. Did you select the wrong one?",
                'View the dropdown list of nodes you can edit by doing /node edit without the #node.')
                await ctx.respond(embed = embed)
                return

            case 'channelsNotNodes': #Multi select
            
                embed, file = await fn.embed(
                    'Edit Nodes?',
                    "You can edit a node three ways:\n\
                    • Call this command inside of a node channel.\n\
                    • Do `/node edit #node-channel`.\n\
                    • Select multiple node channels with the list below.",
                    'This will allow you to edit the permissions of all the nodes you select at once.')

                view = discord.ui.View()
                
                async def submitNodes(interaction: discord.Interaction):
                    await fn.closeDialogue(interaction)
                    await editNodes(nodeSelect.values, guildData)
                    return

                nodeSelect = discord.ui.Select(
                    placeholder = 'Which nodes to edit?',
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
     
        return

    @node.command(
        name = 'rename',
        description = 'Rename a node.')
    async def rename(
        self,
        ctx: discord.ApplicationContext,
        node: discord.Option(
            discord.TextChannel,
            'Either call this command inside a node or name it here.',
            required = False)):
        
        await ctx.defer(ephemeral = True)

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        con.close()

        async def renameNode(givenChannel: discord.TextChannel, guildData: dict):

            #Sort channel into whether actually node
            result = await fn.identifyNodeChannel(guildData, givenChannel)
            if isinstance(result, discord.TextChannel):
                nodeChannel = result

            else:
                embed, file = await fn.embed(
                'Not a node!',
                f"What you provided, {givenChannel.mention}, isn't a node.",
                'You can call the command again?')
                
                await ctx.respond(embed = embed, ephemeral = True)
                return

            oldName = nodeChannel.name
            newName = ''

            async def choose(interaction: discord.Interaction):

                modal = discord.ui.Modal(title = f'Rename {oldName}')

                newNodeName = discord.ui.InputText(
                    label = 'new name',
                    style = discord.InputTextStyle.short,
                    min_length = 1,
                    max_length = 20,
                    placeholder = "What's the new name?")
                modal.add_item(newNodeName)

                async def updateNewName(interaction: discord.Interaction):

                    await interaction.response.defer()

                    nonlocal newName
                    newName = await fn.formatNodeName(newNodeName.value)
                    await refreshEmbed()

                    return
                    
                modal.callback = updateNewName
                await interaction.response.send_modal(modal)
                return

                return
            
            async def confirmName(interaction: discord.Interaction):

                nonlocal oldName
                nonlocal newName
                nonlocal nodeChannel

                await nodeChannel.edit(name = newName)
                guildData['nodes'][newName] = guildData['nodes'].pop(oldName)

                con = db.connectToGuild()
                db.updateGuild(con, guildData)
                con.close()

                embed, file = await fn.embed(
                    'Renamed.',
                    f'Say goodbye to #{oldName} and hello to {nodeChannel.mention}.',
                    'Everything else about it has been untouched, like the whitelist, edges, and occupants.')

                await interaction.response.edit_message(embed = embed, view = None)

                return
            
            async def refreshEmbed():

                nonlocal oldName
                nonlocal newName
                nonlocal nodeChannel

                embed, file = await fn.embed(
                    f'Rename?',
                    f"Rename {nodeChannel.mention} to {f'#{newName}' if newName else 'something new'}?",
                    'Use the button below to input a new name for it.')

                callbacks = []
                view = discord.ui.View()
                chooseName = discord.ui.Button(
                    label = 'Choose Name',
                    style = discord.ButtonStyle.success)
                chooseName.callback = choose
                view.add_item(chooseName)

                if newName:
                    submit = discord.ui.Button(
                        label = 'Submit',
                        style = discord.ButtonStyle.success)
                    submit.callback = confirmName
                    view.add_item(submit)

                cancel = discord.ui.Button(
                    label = 'Cancel',
                    style = discord.ButtonStyle.secondary)
                cancel.callback = fn.closeDialogue
                view.add_item(cancel)

                await ctx.edit(embed = embed, view = view)

            #View
            embed, file = await fn.embed(
                'Loading.',
                'One moment...',
                'This should get edited.')

            await ctx.respond(embed = embed, ephemeral = True)
            await refreshEmbed()

            return
                
        result = await fn.identifyNodeChannel(guildData, node, ctx.channel)
        match result:
            
            case channel if isinstance(result, discord.TextChannel): 
                
                await renameNode(result, guildData)
            
            case 'noNodes': #No nodes in guild
            
                con = db.connectToGuild()
                db.deleteGuild(con, ctx.guild_id)
                con.close()

                embed, file = await fn.embed(
                    'Easy, bronco.',
                    "You have no nodes to rename. You can't change something that's not there.",
                    'Make some first with /node new.')

                await ctx.respond(embed = embed)
                return

            case 'namedNotNode': #"Node" channel given isnt a node

                embed, file = await fn.embed(
                'What?',
                f"{node.mention} isn't a node channel. Did you select the wrong one?",
                'View the dropdown list of nodes you can edit by doing /node edit without the #node.')
                await ctx.respond(embed = embed)
                return

            case 'channelsNotNodes': #Single select
            
                embed, file = await fn.embed(
                    'Rename a node?',
                    "You can rename a node three ways:\n\
                    • Call this command inside of a node channel.\n\
                    • Do `/node rename #node-channel`.\n\
                    • Select a node channel from the list below.",
                    'Either way, the node gets renamed.')

                view = discord.ui.View()
                
                async def submitNode(interaction: discord.Interaction):
                    await fn.closeDialogue(interaction)
                    await renameNode(nodeSelect.values[0], guildData)
                    return

                nodeSelect = discord.ui.Select(
                    placeholder = 'Which node to rename?',
                    select_type = discord.ComponentType.channel_select,
                    min_values = 1,
                    max_values = 1)
                nodeSelect.callback = submitNode
                view.add_item(nodeSelect)

                cancel = discord.ui.Button(
                    label = 'Cancel',
                    style = discord.ButtonStyle.secondary)
                cancel.callback = fn.closeDialogue
                view.add_item(cancel)

                await ctx.respond(embed = embed, view = view)

                embed, file = await fn.embed(
                    'Woah.',
                    'You just unlocked a new error: Err. 2, Node Editing.',
                    'Please bring this to the attention of the developer, David Lancaster.')

                await ctx.respond(embed = embed)
                return
        
        return

class edgeCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    edge = SlashCommandGroup(
        name = 'edge',
        description = 'edge controls.',
        guild_only = True,
        guild_ids = [1114005940392439899])

    @edge.command(
        name = 'new',
        description = 'Connect nodes.')
    async def new(
        self,
        ctx: discord.ApplicationContext,
        origin: discord.Option(
            discord.TextChannel,
            'Either call this command inside a node or name it here.',
            required = False)):
        
        await ctx.defer(ephemeral = True)

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        con.close()

        async def newEdge(givenChannel: discord.TextChannel, guildData: dict):

            #Sort channel into whether actually node
            result = await fn.identifyNodeChannel(guildData, givenChannel)
            if isinstance(result, discord.TextChannel):
                origin = result

            else:
                embed, file = await fn.embed(
                'Not a node!',
                f"What you provided, {givenChannel.mention}, isn't a node.",
                'You can call the command again?')
                
                await ctx.respond(embed = embed, ephemeral = True)
                return

            twoWay = True

            #Formatting results
            async def refreshEmbed():
                nonlocal twoWay
                nonlocal addRole
                nonlocal addPerson
                nonlocal addDestinations

                roleMentions = [role.mention for role in addRole.values]
                peopleMentions = [person.mention for person in addPerson.values]
                destinationMentions = [channel.mention for channel in addDestinations.values]

                whitelistDescription = await fn.formatWhitelist(roleMentions, peopleMentions)
                destinationDescription = await fn.listWords(destinationMentions)
                if twoWay:
                    directionalityMessage = 'People will be able to move back and forth along the new edge(s).'
                else:
                    directionalityMessage = f'The new edge(s) will be **one-way,** from {origin.mention} to the destination(s).'

                description = f"""
                    • Whitelist: {whitelistDescription}\n\
                    • Destination(s): {destinationDescription}\n\
                    • Directionality: {directionalityMessage}"""
                embed, file = await fn.embed(
                    f'New Edge(s), Origin: {origin.name}',
                    description,
                    'This command overwrites/edits existing edges with the same origin and destination.')

                return embed

            async def changeDestinations(interaction: discord.Interaction):
                await interaction.response.edit_message(embed = await refreshEmbed())
                return

            async def changeDirectionality(interaction: discord.Interaction):

                nonlocal twoWay
                twoWay = not twoWay
                
                await interaction.response.edit_message(embed = await refreshEmbed())
                return

            async def changeRoles(interaction: discord.Interaction):
                await interaction.response.edit_message(embed = await refreshEmbed())
                return
            
            async def changePeople(interaction: discord.Interaction):
                await interaction.response.edit_message(embed = await refreshEmbed())
                return
            
            async def submitEdge(interaction: discord.Interaction):

                await interaction.response.defer()

                nonlocal twoWay

                con = db.connectToGuild()
                guildData = db.getGuild(con, ctx.guild_id)

                destinationNodes, notNodesMessage = await fn.nodeChannelsFromChannels(addDestinations.values, guildData)
                
                if origin in destinationNodes:
                    destinationNodes.remove(origin)

                if not destinationNodes:

                    embed, file = await fn.embed(
                        'No destinations?',
                        f"Out of the {len(addDestinations.values)} channels you selected, none are node\
                            channels eligible to be connected. Just so you know-- it's impossible to\
                            create an edge from a node to itself.",
                        'You can always call the command again.')        
                    await interaction.followup.send(embed = embed, ephemeral = True)
                    return    

                allowedRoles =  [role.id for role in addRole.values]
                allowedPeople = [person.id for person in addPerson.values]

                for destination in destinationNodes:

                    guildData['edges'].update(
                        {(origin.name, destination.name) :{
                            'allowedRoles' : allowedRoles,
                            'allowedPeople' : allowedPeople}})
                
                    if twoWay:
                        guildData['edges'].update(
                            {(destination.name, origin.name) :{
                            'allowedRoles' : allowedRoles,
                            'allowedPeople' : allowedPeople}})
                
                db.updateGuild(con, guildData)
                con.close()

                embed, file = await fn.embed(
                    'Nodes connected!',
                    f"You can view the graph with `/server view`.",
                    'I hope you like it.')        
                await interaction.followup.send(embed = embed, ephemeral = True)    
                return
            
            view = discord.ui.View()
            addDestinations = discord.ui.Select(
                placeholder = 'Where should these edges point towards?',
                select_type = discord.ComponentType.channel_select,
                min_values = 1,
                max_values = len(ctx.guild.channels))
            addDestinations.callback = changeDestinations
            view.add_item(addDestinations)

            callbacks = [changeRoles, changePeople, submitEdge, fn.closeDialogue]
            view, addRole, addPerson, submit, cancel = await fn.whitelistView(len(ctx.guild.roles), ctx.guild.member_count, callbacks, view)
            
            toggleDirectionality = discord.ui.Button(
                label = 'Toggle Two-Way',
                style = discord.ButtonStyle.secondary)
            toggleDirectionality.callback = changeDirectionality
            view.add_item(toggleDirectionality)

            embed, file = await fn.embed(
                'Loading.',
                'One moment...',
                'This should get edited.')

            await ctx.respond(embed = await refreshEmbed(), view = view, ephemeral = True)
            return
        
        result = await fn.identifyNodeChannel(guildData, origin, ctx.channel)
        match result:

            case 'noNodes': #No nodes in guild
            
                con = db.connectToGuild()
                db.deleteGuild(con, ctx.guild_id)
                con.close()

                embed, file = await fn.embed(
                    'Hold on.',
                    "You don't have any nodes to connect.",
                    'Make some first with /node new.')

                await ctx.respond(embed = embed)
                return
                        
            case fewNodes if len(guildData['nodes']) < 2: #Too few nodes

                embed, file = await fn.embed(
                    'Hold it.',
                    "You don't have enough nodes to form a connection. You need at least two; an origin and a destination.",
                    'Make some first with /node new.')

                await ctx.respond(embed = embed)
                return

            case channel if isinstance(result, discord.TextChannel): 
                
                await newEdge(result, guildData)

            case 'namedNotNode': #"Node" channel given isnt a node

                embed, file = await fn.embed(
                'What?',
                f"{origin.mention} isn't a node channel. Did you select the wrong one?",
                'View the dropdown list of nodes you can start with by doing /edge new without the #node.')
                await ctx.respond(embed = embed)
                return

            case 'channelsNotNodes': #Single select
            
                embed, file = await fn.embed(
                    'Edit Nodes?',
                    "You can edit a node three ways:\n\
                    • Call this command inside of a node channel.\n\
                    • Do `/node edit #node-channel`.\n\
                    • Select multiple node channels with the list below.",
                    'This will allow you to edit the permissions of all the nodes you select at once.')

                view = discord.ui.View()
                
                async def submitNode(interaction: discord.Interaction):
                    await fn.closeDialogue(interaction)
                    await newEdge(nodeSelect.values[0], guildData)
                    return

                nodeSelect = discord.ui.Select(
                    placeholder = 'Which node to originate from?',
                    select_type = discord.ComponentType.channel_select,
                    min_values = 1,
                    max_values = 1)
                nodeSelect.callback = submitNode
                view.add_item(nodeSelect)

                cancel = discord.ui.Button(
                    label = 'Cancel',
                    style = discord.ButtonStyle.secondary)
                cancel.callback = fn.closeDialogue
                view.add_item(cancel)

                await ctx.respond(embed = embed, view = view, ephemeral = True)

        return

    @edge.command(
        name = 'delete',
        description = 'See/remove the connections of a given node.')
    async def delete(
        self,
        ctx: discord.ApplicationContext,
        origin: discord.Option(
            discord.TextChannel,
            'Either call this command inside a node or name it here.',
            required = False)):
        
        await ctx.defer(ephemeral = True)

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        con.close()

        async def removeEdges(givenChannel: discord.TextChannel, guildData: dict):

            #Sort channel into whether actually node
            result = await fn.identifyNodeChannel(guildData, givenChannel)
            if isinstance(result, discord.TextChannel):
                nodeChannel = result

            else:
                embed, file = await fn.embed(
                'Not a node!',
                f"What you provided, {givenChannel.mention}, isn't a node.",
                'You can call the command again?')
                
                await ctx.respond(embed = embed, ephemeral = True)
                return

            allRelations = []

            async def refreshEmbed():

                edgesDescription = 'This node has the following connections:'
                graph = await fn.makeGraph(guildData)
                ancestors, neighbors, successors = await fn.getNodeRelations(graph, nodeChannel.name)

                nonlocal allRelations
                allRelations = ancestors + neighbors + successors

                subgraph = graph.subgraph(allRelations + [nodeChannel.name])
                graphView = ('full', await fn.showGraph(subgraph))

                for ancestor in ancestors:
                    edgesDescription += f'\n-> {ancestor}'

                for neighbor in neighbors:
                    edgesDescription += f'\n<-> {neighbor}'
                
                for successor in successors:
                    edgesDescription += f'\n<- {successor}'

                if not ancestors and not neighbors and not successors:
                    edgesDescription = 'This node has no connections with any other node.'
                    graphView = None                  

                embed, file = await fn.embed(
                    f"{nodeChannel.name}'s Edges",
                    edgesDescription,
                    'That about sums it up.',
                    graphView)

                return embed, file

            async def submitEdges(interaction: discord.Interaction):

                return

            #View
            embed, file = await refreshEmbed()
            if file:

                view = discord.ui.View()

                addEdges = discord.ui.Select(
                    placeholder = 'Which edges to delete?',
                    min_values = 0,
                    max_values = len(allRelations))
                addEdges.callback = fn.nullResponse
                view.add_item(addEdges)

                submit = discord.ui.Button(
                    label = 'Delete',
                    style = discord.ButtonStyle.danger)
                submit.callback = callbacks[2]
                view.add_item(submit)

                cancel = discord.ui.Button(
                    label = 'Cancel',
                    style = discord.ButtonStyle.secondary)
                cancel.callback = callbacks[3]
                view.add_item(cancel)

                await ctx.respond(embed = embed, file = file, view = view, ephemeral = True)
            else: 
                await ctx.respond(embed = embed, ephemeral = True)
            return
                
        result = await fn.identifyNodeChannel(guildData, origin, ctx.channel)
        match result:

            case 'noNodes':
            
                con = db.connectToGuild()
                db.deleteGuild(con, ctx.guild_id)
                con.close()

                embed, file = await fn.embed(
                    'Easy there.',
                    "You don't have any nodes, which means you have no connections between\
                    nodes, either. Make some nodes with `/node new`.",
                    'Then you can connect them with /edge new.')

                await ctx.respond(embed = embed)
                return
            
            case noEdges if len(guildData['nodes']) < 2:

                embed, file = await fn.embed(
                    'Slow down.',
                    "You don't have enough nodes for an edge to exist. Make some nodes with `/node new`.",
                    'Then you can connect them with /edge new.')

                await ctx.respond(embed = embed)
                return
            
            case channel if isinstance(result, discord.TextChannel): 
                
                await removeEdges(result, guildData)

            case 'namedNotNode': #"Node" channel given isnt a node

                embed, file = await fn.embed(
                'What?',
                f"{node.mention} isn't a node channel. Did you select the wrong one?",
                'View the dropdown list of nodes you can edit by doing /node edit without the #node.')
                await ctx.respond(embed = embed)
                return

            case 'channelsNotNodes': #Single select
            
                embed, file = await fn.embed(
                    'Rename a node?',
                    "You can rename a node three ways:\n\
                    • Call this command inside of a node channel.\n\
                    • Do `/node rename #node-channel`.\n\
                    • Select a node channel from the list below.",
                    'Either way, the node gets renamed.')

                view = discord.ui.View()
                
                async def submitNode(interaction: discord.Interaction):
                    await fn.closeDialogue(interaction)
                    await removeEdges(nodeSelect.values[0], guildData)
                    return

                nodeSelect = discord.ui.Select(
                    placeholder = 'Which node to rename?',
                    select_type = discord.ComponentType.channel_select,
                    min_values = 1,
                    max_values = 1)
                nodeSelect.callback = submitNode
                view.add_item(nodeSelect)

                cancel = discord.ui.Button(
                    label = 'Cancel',
                    style = discord.ButtonStyle.secondary)
                cancel.callback = fn.closeDialogue
                view.add_item(cancel)

                await ctx.respond(embed = embed, view = view)
    
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
        print(guildData)
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
    
    @server.command(
        name = 'view',
        description = 'View the entire graph or just a portion.')
    async def view(
        self,
        ctx: discord.ApplicationContext,
        node: discord.Option(
            discord.TextChannel,
            'Specify a node to highlight?',
            required = False)):
        
        await ctx.defer(ephemeral = True)

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        con.close()

        async def viewEgo(guildData: dict, givenChannel: str = None):

            #Nothing provided
            if not givenChannel:
                graph = await fn.makeGraph(guildData)
                graphView = await fn.showGraph(graph)

                embed, file = await fn.embed(
                    'Complete Graph',
                    "Here is a view of every node and edge.\
                    You can narrow it down to just one node and any neighbors if you specify\
                    a node with `/server view #node` or if you call this command from within\
                    a node channel.",
                    'Enjoy.',
                    ('full', graphView))

                await ctx.respond(embed = embed, file = file, ephemeral = True)
                return

            #If something provided
            if givenChannel.name in guildData['nodes']:

                nodeName = givenChannel.name
                graph = await fn.makeGraph(guildData)
                
                nodeExits = list(graph.successors(nodeName))
                nodeEntrances = list(graph.predecessors(nodeName))
                nodeNeighbors = list(set(nodeExits + nodeEntrances))
                nodeNeighbors.append(nodeName)
                subgraph = graph.subgraph(nodeNeighbors)

                graphView = await fn.showGraph(subgraph)

                embed, file = await fn.embed(
                    f'Subgraph of: {givenChannel.mention}',
                    "Here is the given node, as well as any neighbors.",
                    'Enjoy.',
                    ('full', graphView))

                await ctx.respond(embed = embed, file = file, ephemeral = True)
                return

            else:
                embed, file = await fn.embed(
                'Not a node!',
                f"What you provided, {givenChannel.mention}, isn't a node.",
                'You can call the command again?')
                
                await ctx.respond(embed = embed, ephemeral = True)
                return    
                
        result = await fn.identifyNodeChannel(guildData, node, ctx.channel)
        match result:
            
            case channel if isinstance(result, discord.TextChannel): 
                
                await viewEgo(guildData, result)
            
            case 'noNodes': #No nodes in guild
            
                con = db.connectToGuild()
                db.deleteGuild(con, ctx.guild_id)
                con.close()

                embed, file = await fn.embed(
                    'Hey now.',
                    "You have no nodes or anything. So here's your graph view, I guess.",
                    'Make some nodes first with /node new.',
                    ('full', 'assets/blank.png'))

                await ctx.respond(embed = embed, file = file)
                return

            case 'namedNotNode': #"Node" channel given isnt a node

                embed, file = await fn.embed(
                'What?',
                f"{node.mention} isn't a node channel. Did you select the wrong one?",
                'View the dropdown list of nodes you can edit by doing /node edit without the #node.')
                await ctx.respond(embed = embed)
                return

            case 'channelsNotNodes': #Multi select
                await viewEgo(guildData)
                return

            case _:

                embed, file = await fn.embed(
                    'Woah.',
                    'You just unlocked a new error: Err. 3, Graph viewing.',
                    'Please bring this to the attention of the developer, David Lancaster.')

                await ctx.respond(embed = embed)
                return
        
        return

    @server.command(
        name = 'fix',
        description = 'Fix certain issues with the server.')
    async def fix(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        con = db.connectToGuild()
        guildData = db.getGuild(con, ctx.guild_id)
        con.close()

        graph = await fn.makeGraph(guildData)

        isolates = list(nx.isolates(graph))
        if isolates:
            isolatedMentions = [f"<#{graph.nodes[isolatedNode]['channelID']}>" for isolatedNode in isolates]
            isolatesMessage = f'The following nodes have no edges, meaning \
                **no way in or out:** {await fn.listWords(isolatedMentions)}.\n\n'

        else:
            isolatesMessage = "Every node has at least one way in and/or out. Keep in\
                mind that this is only looking for ways in *or* out-- not both.\
                Because, you know, maybe you want someplace that you can't escape\
                from, or that you can't access.\n\n"
            
        async def regenChannels(interaction: discord.Interaction):
            
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

        embed, file = await fn.embed(
        f'Fix Server',
        f'{isolatesMessage}',
        'Also this ig')

        await ctx.respond(embed = embed)
        
        return
 
class helpCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    help = SlashCommandGroup(
        name = 'help',
        description = "Understand what's going on.",
        guild_only = True,
        guild_ids = [1114005940392439899])

    @help.command(
        name = 'me',
        description = 'Basic help.')
    async def clear( ##Come back here and include a purge for player channels + db
        self,
        ctx: discord.ApplicationContext,
        word: discord.Option(
            str,
            'Get help on a specific term?',
            required = False)):

        await ctx.defer(ephemeral = True)
        word = word.lower() if word else ''

        allHelp = {
            'graph' : "A __graph__ (a.k.a. __network__), is a math thing: basically, there's\
                dots (__nodes__) and there may or may not be connections between those dots\
                (__edges__). That's basically it.\n\nFor us, though, all that matters is that\
                __nodes__ are __locations__ and __edges__ are connections between them.",
            'network' : "See __graph__.",
            'node' : "A __node__ is a dot on a __graph__. If it's connected to any other\
            __node__s, that's called an __edge__. For us, a \"__node__\" has a couple things--\
            the __location__ is represents, the __permissions__ for it, and the Discord channel\
            for that __node__, which isn't visible to the players.",
            'location' : "The actual place represented by a __node__, like a kitchen. These\
            must be big enough to fit the __player__s, and small enough that anyone in one part of\
            the node can reasonably be expected to hear/see anything in any other part of the\
            __location__. Every __player__ is located in some __location__ at any point in time.",
            'permissions' : "Who's allowed to travel into/through a __node__ or an __edge__.\
            This mostly affects __movement__, where a __player__ is denied access to a place\
            because there's no route to their destination after accounting for their __permissions__.",
            'edges' : "Connections between __node__s on a __graph__. Any time two __locations__ are\
            connected for __movement__ or __sound__, an __edge__ should exist. Usually a door,\
            but it can be a hallway, bridge, elevator, portal... Can only let people through who\
            satisfy the __permissions__, but sound can travel freely.",
            'movement' : "The way that __player__s change which __location__ along the __graph__\
            their __presence__ is in. When they try to move to a new __location__, they need a\
            path along the __edges__ from where they are to their destination __node__, such that\
            they have permission to access every node and edge along the way.",
            'presence' : "The __location__ that a __player__ will hear all __sound__ in. Anytime\
            someone speaks in the same __location__, the __player__s who are present will hear.\
            __Presence__ also means that you'll see everyone in a room when you walk in, and\
            they'll see you.",
            'sound' : "Everything that __player__s are notified of. Includes everything spoken\
            by a __player__ in the same __location__, but may include __indirect__ sound from\
            __neighbor__ __node__s. Note that you trasmit all the same kind of noise as they do.",
            'indirect' : "As opposed to __sound__ that is __direct__, __indirect__ sound can only\
            by faintly made out, and only voices or small segments of the speech may be heard.\
            __Indirect__ sound is usually heard through __edges__ to __neighbor__ __nodes__,\
            and can be heard __direct__ly by __eavesdropping__.",
            'direct' : "As opposed to __sound__ that is __indirect__, __direct__ sound can be\
            fully heard, including identifying the speaker and what they're saying. Usually heard\
            through the __player__ being in the same __location__ as the speaker, or by __eavesdropping__.",
            'neighbor' : "A __node__ that is connected to another __node__ along one of its __edges__.\
            Fun fact: if a __node__ has an edge that points *to* another one, and it's only one-way,\
            they're not technically neighbors (even though this `/help` command defines them as such).\
            Instead, the origin would be the \"ancestor\" and the destination would be its \"successor.\"",
            'player' : 'People who have __presence__ at a __location__, can hear __sound__ from __node__s\
            they __neighbor__ as well as from other people in the same place. Capable of __movement__\
            and __eavesdropping__. In short, everyone who is placed in the __graph__.',
            'underlined' : "What-- no, \"__underlined__\" was so you can see what an __underlined__\
            word looked like, you're not supposed to actually search it. Goof."}
        
        if word in allHelp:
            embed, file = await fn.embed(
            f'Help for "{word}"',
            allHelp[word],
            "Clear things up, I hope?")

            await ctx.respond(embed = embed)
            return

        embed, file = await fn.embed(
        'Hello!',
        f"This command will help you understand any __underlined__ words\
        in `/help player`, or if you're a server owner, `/help admin`.\
        When you find an underlined word you want to know more about,\
        just do `/help me <word>`. :)",
        "I'll be here if/when you need me.")

        await ctx.respond(embed = embed)
        return
    
def setup(prox):

    prox.add_cog(nodeCommands(prox), override = True)
    prox.add_cog(edgeCommands(prox), override = True)
    prox.add_cog(serverCommands(prox), override = True)
    prox.add_cog(helpCommands(prox), override = True)