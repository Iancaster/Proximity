"""
Commands entrusted only to the owner.
"""

from discord import ApplicationContext, Bot
from discord.ext import commands
from libraries.user_interface import text_embed, send_message, Dialogue

class OwnerCommands(commands.Cog):

    def __init__(self, bot: Bot):
        self.prox = bot

    @commands.is_owner()
    @commands.slash_command(
        description = 'Unload and reload all the cogs.',
        guild_ids = [1111152704279035954])
    async def refresh(self, ctx: ApplicationContext):

        loaded_cogs = list(self.prox.extensions.keys())

        for cog in loaded_cogs:
            self.prox.unload_extension(cog)
            self.prox.load_extension(cog)

        embed = text_embed(
            'Refreshed cogs.',
            'Hopefully this is faster than just restarting.',
            'Or at least provides better continuity.')
        dialogue = Dialogue(embed)
        await send_message(ctx.interaction, embed, dialogue.view, ephemeral = True)
        return

    @commands.is_owner()
    @commands.slash_command(
        description = 'Custom embed.',
        guild_ids = [1111152704279035954])
    async def update(self, ctx: ApplicationContext):

        embed = text_embed(
            "unused code!",
            "how did you find this?",
            "So, wish granted? This is as deleted as it gets.")
        dialogue = Dialogue(embed)
        dialogue.add_close()
        await send_message(ctx.interaction, embed, dialogue.view, ephemeral = True)
        return
    
    async def cog_command_error(self, ctx: ApplicationContext, error: Exception):
        
        if isinstance(error, commands.NotOwner):
            embed = text_embed(
                "Nice try.",
                "Only the bot owner can use this command.",
                "Permision denied.")
            
            await send_message(ctx.interaction, embed = embed, ephemeral = True)
        else:
            raise error
        
        return

def setup(prox):
    prox.add_cog(OwnerCommands(prox), override = True)

