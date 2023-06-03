import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands
import functions as fn
import databaseFunctions as db

class genCommands(commands.Cog):

    def __init__(self, bot: discord.Bot):
        self.prox = bot

    gen = SlashCommandGroup(
        name = 'general',
        description = 'General stuff, at least for now.',
        guild_only = True,
        guild_ids = [1114005940392439899])

    @gen.command( ##Register this not unlike Teacher Bot!
        name = 'register',
        description = 'Get in the system.')
    async def register(
        self,
        ctx: discord.ApplicationContext):

        await ctx.defer(ephemeral = True)

        con = db.connectToGuild()
        db.newGuild(con, ctx.guild_id)
        con.close()

        #Formatting results
        embed, file = await fn.embed(
            f'Done.',
            'Asshole.',
            'Is that good enough?')

        await ctx.respond(embed = embed)

        return

    @gen.command(
        name = 'newnode',
        description = 'Create a new node/channel.')
    async def newNode(
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
        description = await fn.formatWhitelist(allowedRoles, allowedPeople)

        #Formatting results
        embed, file = await fn.embed(
            f'New Node: {name}',
            description,
            'Is that good?')

        #View
        addRole, addPerson, submit = await fn.initWhitelist(len(ctx.guild.roles), len(ctx.guild.members))

        async def changeRoles(interaction: discord.Interaction):
            nonlocal allowedRoles
            allowedRoles = addRole.values

            description = await fn.formatWhitelist(allowedRoles, allowedPeople)
            embed, file = await fn.embed(
                f'New Node: {name}',
                description,
                'Got that?')
            await interaction.response.edit_message(embed = embed)
            return
        
        async def changePeople(interaction: discord.Interaction):
            nonlocal allowedPeople
            allowedPeople = addPerson.values

            description = await fn.formatWhitelist(allowedRoles, allowedPeople)
            embed, file = await fn.embed(
                f'New Node: {name}',
                description,
                'Got that?')
            await interaction.response.edit_message(embed = embed)
            return
        
        async def submitPerms(interaction: discord.Interaction):
            
            nonlocal allowedRoles
            nonlocal allowedPeople

            allowedRoles = list(role.id for role in allowedRoles)
            allowedPeople = list(person.id for person in allowedPeople)


            nodesList = list(category for category in interaction.guild.categories if category.name == 'nodes')
            if not nodesList:
                nodesCategory = await interaction.guild.create_category('nodes')
            else:
                nodesCategory = nodesList[0]

            
            permissions = {
                interaction.guild.default_role: discord.Permissions(read_messages = False),
                interaction.guild.me: discord.Permissions(send_messages=True, read_messages=True)
    }
            newNodeChannel = await interaction.guild.create_text_channel(
                name,
                category = nodesCategory,
                overwrites = )
            newNodePerms = 


            con = db.connectToGuild()
            guildData = db.getGuild(con, interaction.guild_id)
            guildData['nodes'].update(await fn.newNode(name, newNodeChannel.id, allowedRoles, allowedPeople))
            db.updateGuild(con, interaction.guild_id, guildData['nodes'])
            con.close()

            embed, file = await fn.embed(
                'Node created!',
                f'You can find it at {newNodeChannel.mention}. Enjoy.',
                'Just try not to touch the permissions I set for it.'
            )
    
            return
        
        callbacks = [changeRoles, changePeople, submitPerms]
        view = await fn.refineWhitelist(addRole, addPerson, submit, callbacks)

        await ctx.respond(embed = embed, view = view)

        return

def setup(prox):

    prox.add_cog(genCommands(prox), override = True)
