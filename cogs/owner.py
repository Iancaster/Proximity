"""
Commands entrusted only to the owner.
"""

from discord import ApplicationContext, Bot, TextChannel
from discord.ext import commands
from discord.utils import find
from libraries.user_interface import text_embed, image_embed, \
    send_message, Dialogue, ImageSource
from libraries.classes import Roleplay, Location, Character, \
    Route, Relayable, in_text_channel
from data.database_entries import RoleplayData, LocationData, \
    CharacterData, RouteData

from pathlib import Path

class OwnerCommands(commands.Cog):

    def __init__(self, bot: Bot):
        self.prox = bot

    @commands.is_owner()
    @commands.slash_command(
        description = "Generate a trial server for testing.",
        checks = [in_text_channel])
    async def generate_trial_rp(self, ctx: ApplicationContext):

        await ctx.interaction.response.defer(ephemeral = False)

        log_channel = find(lambda c : c.name == "system", ctx.guild.channels)
        assert log_channel is not None

        rp_data = RoleplayData(
            roleplay_id = ctx.guild.id,
            name = "Generic Star Wars RP",
            log_channel_id = log_channel.id,
            description = ("This is a trial roleplay meant to appear as a generic" 
                " Star Wars server. Please, feel free to have fun with it, but"
                " don't forget that you're here to test out the new feature!"),
            reference = "https://cdn.britannica.com/24/259724-050-5F1007C0/" + \
                "Star-Wars-movie-poster-Episode-IV-A-New-Hope-1977.jpg")
            
        roleplay = await Roleplay.create(rp_data)
        assert isinstance(roleplay, Roleplay)

        async def make_loc(loc_data: LocationData) -> Location:

            loc_channel = await Relayable.create_channel(
                channel_name = loc_data.name,
                guild_id = loc_data.roleplay_id,
                is_location = True)
            assert isinstance(loc_channel, TextChannel)

            loc_data = LocationData(
                location_id = loc_channel.id,
                roleplay_id = loc_data.roleplay_id,
                name = loc_data.name,
                description = loc_data.description,
                reference = loc_data.reference)

            location = await Location.create(loc_data)
            assert isinstance(location, Location)

            return location
        
        cantina_data = LocationData(
            location_id = 0,
            roleplay_id = roleplay.data.roleplay_id,
            name = "Oga's Cantina",
            description = "A more wretched hive of scum and villainy you will" + \
                " never find. Here especially.",
            reference = "https://offloadmedia.feverup.com/secretlosangeles.com/" + \
                "wp-content/uploads/2018/10/22101807/Decor.jpg")
        cantina = await make_loc(cantina_data)

        eisley_data = LocationData(
            location_id = 0,
            roleplay_id = roleplay.data.roleplay_id,
            name = "Mos Eisley",
            description = ("A lawless, bustling spaceport town. One of the few" 
                " places in Tatooine that you can find people with money-- not" 
                " their own, mind you, but money nevertheless."),
            reference = "https://i.etsystatic.com/17727358/r/il/679e67/3407634480/" + \
                "il_fullxfull.3407634480_kgp0.jpg")
        eisely = await make_loc(eisley_data)

        to_cantina = RouteData(
            from_id = eisely.data.location_id,
            to_id = cantina.data.location_id,
            roleplay_id = roleplay.data.roleplay_id)
        await Route.create(to_cantina)

        from_cantina = RouteData(
            from_id = cantina.data.location_id,
            to_id = eisely.data.location_id,
            roleplay_id = roleplay.data.roleplay_id)
        await Route.create(from_cantina)

        spaceport_data = LocationData(
            location_id = 0,
            roleplay_id = roleplay.data.roleplay_id,
            name = "The Spaceport",
            description = ("A merchant haggling with customs regarding the"
                " legality of his imports. A shiphand capitalizing on the"
                " distraction to toss some packets of Spice between some"
                " crates for later recollection. This place would almost"
                " be charming if it didn't reek of rocket fuel and larceny."),
            reference = "https://static.wikia.nocookie.net/starwars/images/e/" + \
                "ef/HoundsTooth_Mos_Eisley_XWM.jpg")
        spaceport = await make_loc(spaceport_data)

        from_spaceport = RouteData(
            from_id = spaceport.data.location_id,
            to_id = eisely.data.location_id,
            roleplay_id = roleplay.data.roleplay_id)
        await Route.create(from_spaceport)

        to_spaceport = RouteData(
            from_id = eisely.data.location_id,
            to_id = spaceport.data.location_id,
            roleplay_id = roleplay.data.roleplay_id)
        await Route.create(to_spaceport)

        async def make_char(char_data: CharacterData) -> Character:

            char_channel = await Relayable.create_channel(
                channel_name = char_data.name,
                guild_id = char_data.roleplay_id,
                is_location = False)
            assert isinstance(char_channel, TextChannel)

            char_data = CharacterData(
                character_id = char_channel.id,
                location_id = char_data.location_id,
                roleplay_id = char_data.roleplay_id,
                name = char_data.name,
                description = char_data.description,
                reference = char_data.reference)

            character = await Character.create(char_data)
            assert isinstance(character, Character)

            return character

        momaw_data = CharacterData(
            character_id = 0,
            location_id = cantina.data.location_id,
            roleplay_id = roleplay.data.roleplay_id,
            name = "Momaw Nadon",
            description = "The alien who traded their freedom for a planet" + \
                " who lives to hate him.",
            reference = "https://img.lum.dolimg.com/v1/images/momaw-nadon_2f33c366.jpeg")
        await make_char(momaw_data)

        muftak_data = CharacterData(
            character_id = 0,
            location_id = cantina.data.location_id,
            roleplay_id = roleplay.data.roleplay_id,
            name = "The Muftak",
            description = ("Well, actually, Muftak is just his name, and he's" 
                " \"the\" Talz on Tatooine (perhaps the only one). There are, in"
                " fact, many other Talz. They wisely stay on arctic planets that"
                " they're best suited for. Perhaps if baby Muftak had the wherewithal"
                " to tell his mother to abandon him someplace less sunny, Tatooine"
                " would not know the furry touch of this Talz or any other."),
            reference = "https://static.wikia.nocookie.net/starwars/images/8/" + \
                "8e/Muftak-ANH.png/revision/latest")
        await make_char(muftak_data)

        general_chat = find(lambda c : c.name == "conversation", ctx.guild.channels)
        assert general_chat is not None

        invite = general_chat.create_invite(
            reason = "For testing.",
            max_age = 0,
            max_uses = 10,
            temporary = False)

        embed, image = await image_embed(
            "Trial server generated!",
            f"Find it [here]({await invite}).",
            "Happy bug-hunting.",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = roleplay.data.reference)

        await send_message(ctx.interaction, embed, file = image)
        return


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

