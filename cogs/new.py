


from libraries.classes import RPServer, Location
from libraries.user_interface import Dialogue, Popup, ImageSource, \
    text_embed, image_embed, send_message, reference_validator

from discord import ApplicationContext, InteractionContextType, \
    ButtonStyle, InputTextStyle, Interaction
from discord.ext import commands
from discord.commands import SlashCommandGroup
#from types import MethodType

from libraries.classes import in_text_channel, is_administrator, in_prox_rp, RPServer

# from libraries.new_classes import GuildData, ChannelManager, Path, Location, \
# 	DialogueView, Character, ListenerManager
# from libraries.universal import mbd, loading, no_redundancies, \
# 	send_message, identify_place_channel, character_change
# from libraries.formatting import format_words, discordify, unique_name, \
# 	format_whitelist, format_new_neighbors, embolden, \
# 	format_channels, format_roles, format_avatar
# from libraries.autocomplete import complete_places, exclusionary_places
# from data.listeners import direct_listeners, queue_refresh, \
# 	to_direct_listeners

class NewCommands(commands.Cog):

    new_group = SlashCommandGroup(
        name = "new",
        description = "Create new Roleplays, Locations, Routes, and Characters-- in that order.",
        contexts = [InteractionContextType.guild],
        checks = [in_text_channel, is_administrator])

    @new_group.command(
        name = "location", 
        description = "Create a new location for Characters to roleplay in.",
        checks = [in_prox_rp])
    async def location(self, ctx: ApplicationContext):

        server = RPServer(ctx.guild_id)
        await server.fetch()

        if server.location_limit is not None \
            and await server.location_count >= server.location_limit:

            embed = text_embed(
                "Easy there.",
                f"Looks like you're already at your limit of {server.location_limit}" \
                    " locations. If you'd like more, think about a subscription.", 
                "Proceeds go straight for server costs and feature improvements.")
            
            await ctx.respond(embed = embed, ephemeral = True)
            return

        embed = text_embed(
            "Someplace new?",
            "Technically, all you need to provide is a name, and"
                " I can make the location and its channel. But you can" \
                " also set a description and a reference photo.", 
            "All of this can be edited later with /review location.")
        
        dialogue = Dialogue(embed, disable_timeout = True)
        details_popup = Popup(title = "New location details")

        details_popup.add_text(
            label = "Name", 
            placeholder = "What should the location be named?", 
            min_length = 1, 
            max_length = 100)
        
        details_popup.add_text(
            label = "Description", 
            placeholder = "Share some lore, maybe, or the sounds or scents of a scene?", 
            min_length = 0, 
            max_length = 300,
            required = False,
            style = InputTextStyle.paragraph)
        
        details_popup.add_text(
            label = "Reference photo URL",
            placeholder = "You can paste an Imgur link for reference images or original art.",
            min_length = 1,
            max_length = 300,
            required = False,
            style = InputTextStyle.paragraph)

        details_button = dialogue.add_button(label = "Set location details", style = ButtonStyle.blurple)
        dialogue.add_modal(details_popup, details_button)

        submit_button = dialogue.add_button(label = "Submit", style = ButtonStyle.success)
        submit_button.should_disable = lambda : not dialogue.is_valid
        dialogue.add_close()      

        async def submit(interaction: Interaction):
                
            description = "Created the location (and its channel). Don't" \
                " forget to connect it to its neighbors!"
            description, ref_url = await reference_validator(
                description, 
                dialogue.fields["Reference photo URL"].get_value())
            
            location = Location(0) # Hacky deferred PK assignment, but what can you do.
            await location.create(
                guild_id = server.id,
                name = dialogue.fields["Name"].get_value(),
                description = dialogue.fields["Description"].get_value(),
                reference = ref_url,
                interaction = interaction)            
            
            dialogue.current_embed, dialogue.current_file = await image_embed(
                "Very nice.",
                description = description,
                footer = "Use /new route. And like everything " \
                    " else, you can always /review this location later.",
                thumbnail = True,
                source = ImageSource.URL if ref_url else ImageSource.ASSET,
                asset_str = ref_url if ref_url else "logo.png")
            dialogue.view.clear_items()
            return await dialogue.refresh(interaction)

        submit_button.callback = submit

        await dialogue.view.refresh_children()
        return await send_message(ctx.interaction, embed, dialogue.view, ephemeral = True)

    @new_group.command(
        name = "route", 
        description = "Lets characters travel (and be heard) between locations.", 
        checks = [in_prox_rp])
    async def route(self, ctx: ApplicationContext):

        server = RPServer(ctx.guild_id)

        return

    @new_group.command(name = 'character', description = 'A new actor onstage.')
    # async def character(self, ctx: ApplicationContext):

    #     server = RPServer(ctx.guild_id)

    #     async def refresh():

    #         nonlocal valid_url, name, place_name, allowed_people

    #         description = '\n• Character name: '
    #         name = view.name() or name
    #         description += f'*{name}*' if name else 'Not set yet. What will they be called?'

    #         description += '\n• Starting location: '
    #         if view.places():
    #             place_name = view.places()[0]

    #         if place_name:
    #             place = GD.places[place_name]
    #             description += f"<#{place.channel_ID}>"
    #         else:
    #             description += "Use the dropdown to choose where they'll join."

    #         description += '\n• Player(s): '
    #         if view.people():
    #             allowed_people = view.people()
    #             description += await format_words([person.mention for person in view.people()])
    #         else:
    #             allowed_people = [ctx.author]
    #             description += 'At a minimum, you and admins have access to this character.'

    #         description += '\n• Role(s): '
    #         if view.roles():
    #             description += await format_roles(view.roles())
    #         else:
    #             description += 'Use the dropdown to give the character some roles.'

    #         avatar, valid_url, avatar_message = await format_avatar(view.url())
    #         description += f'\n• Avatar: {avatar_message}'

    #         embed, file = await mbd(
    #             'New character?',
    #             description,
    #             "You can always change these things later with /review character.",
    #             (avatar, 'thumb'))
    #         return embed, file

    #     def checks():
    #         nonlocal name, place_name
    #         return not (name and place_name)

    #     async def submit(interaction: Interaction):

    #         await loading(interaction)

    #         nonlocal GD, valid_url, name, place_name, allowed_people

    #         #Inform character
    #         CM = ChannelManager(interaction.guild)
    #         character_channel = await CM.create_channel('characters', await discordify(name), allowed_people)

    #         embed, _ = await mbd(
    #             f'Welcome to your Character Channel, {name}.',
    #             "Roleplay with others by talking here. Nearby characters will hear." + \
    #             f"\n• Other people who can send messages here can also RP as {name}." + \
    #             f"\n• Start the message with `\\` if you don't want it to leave this chat." + \
    #             f"\n• You can `/look` around. {name} is at **#{place_name}** right now." + \
    #             "\n• Do `/move` to go to other places you can reach." + \
    #             "\n• You can `/eavesdrop` on nearby characters." + \
    #             "\n• Other people can't see your `/commands` directly..." + \
    #             "\n• ...Until you hit Submit, and start moving or eavesdropping.",
    #             'You can always type /help to get more help.')
    #         await character_channel.send(embed = embed)

    #         char_data = Character(character_channel.id)
    #         char_data.channel_ID = character_channel.id
    #         char_data.location = place_name
    #         char_data.roles = view.roles()
    #         char_data.name = name

    #         if view.url() and valid_url:
    #             char_data.avatar = view.url()

    #         await char_data.save()

    #         #Inform the node occupants
    #         place = GD.places[place_name]
    #         player_embed, _ = await mbd(
    #             'Someone new.',
    #             f"*{char_data.name}* is here.",
    #             'Perhaps you should greet them.',
    #             (char_data.avatar, 'thumb'))
    #         await to_direct_listeners(
    #             player_embed,
    #             interaction.guild,
    #             place.channel_ID,
    #             occupants_only = True)

    #         #Add the players to the guild nodes as occupants
    #         await GD.insert_character(char_data, place_name)
    #         GD.characters[char_data.id] = char_data.name
    #         await GD.save()

    #         await character_change(character_channel, char_data)

    #         #Inform admins node
    #         description = f"• Added <#{char_data.id}> as a character. " + \
    #             f"\n• They're starting at <#{place.channel_ID}>."
    #         if char_data.roles:
    #             description += f"\n• They have the role(s) of {await format_roles({char_data.roles})}"
    #         embed, _ = await mbd(
    #             f'Hello, **{char_data.name}**.',
    #             description,
    #             'You can view all characters and where they are with /review server.',
    #             (char_data.avatar, 'thumb'))
    #         place_channel = await get_or_fetch(interaction.guild, 'channel', place.channel_ID)
    #         await place_channel.send(embed = embed)

    #         LM = ListenerManager(interaction.guild, GD)
    #         await LM.load_channels()
    #         await LM.insert_character(char_data, skip_eaves = True)

    #         return await no_redundancies(
    #             (interaction.channel.name == place_name),
    #             embed,
    #             interaction)


    #     dialogue = Dialogue()
        
    #     async def refresh(interaction: Interaction):
    #         character_name = "New Character"
    #         description = ( 
    #             "Create a new character! Here's what we need: " 
    #             f" - Name: {character_name}"
    #             f" - Starting Location: ")
            
    #         await 
        
    #     embed, file = await image_embed(
    #         title = f"{character_name} inbound.",
    #         description = description,
    #     )

    #     # view = DialogueView(refresh, checks)
    #     # await view.add_places(GD.places.keys())
    #     # await view.add_people()
    #     # await view.add_roles()
    #     # await view.add_submit(submit)
    #     # await view.add_rename()
    #     # await view.add_URL()
    #     # await view.add_cancel()
    #     # embed, file = await refresh()
    #     # await send_message(ctx.respond, embed, view, file)
    #     return

    @new_group.command(name = "roleplay", description = "Make this server a new Proximity roleplay!")
    async def roleplay(self, ctx: ApplicationContext):

        server = RPServer(ctx.guild_id)

        if await server.exists:

            embed = text_embed(
                "Way ahead of you.",
                "This server is already registered for roleplay. If you want to start over," \
                " delete the existing data with `/delete roleplay` and then call this" \
                " command again.",
                "But if you just want a /new place or a /new character, call those instead.")
            
            return await send_message(ctx.interaction, embed, ephemeral = True)
            
        embed = text_embed(
            "Let's do this.",
            "First things first, your roleplay needs a name. Plus,"
                " you need to designate a channel for admin logs (like" \
                " character creation, place creation, and so on)." \
                " And if you're feeling fancy, you can also set a" \
                " description and/or reference photo. ", 
            "You can change all these things later with /review roleplay.")
        
        dialogue = Dialogue(embed, disable_timeout = True)
        dialogue.add_channel_select(
            label = "logging", 
            purpose = " for admin logs",
            min_values = 1)

        details_popup = Popup(title = "Roleplay details")

        details_popup.add_text(
            label = "Title", 
            placeholder = "What should we call this roleplay?", 
            min_length = 1, 
            max_length = 64)
        
        details_popup.add_text(
            label = "Description", 
            placeholder = "Share something interesting about your setting!", 
            min_length = 0, 
            max_length = 300,
            required = False,
            style = InputTextStyle.paragraph)
        
        details_popup.add_text(
            label = "Reference photo URL",
            placeholder = "You can paste an Imgur link for your reference art or advert.",
            min_length = 1,
            max_length = 300,
            required = False,
            style = InputTextStyle.paragraph)
        
        details_popup.add_text(
            label = "Maximum player count",
            placeholder = "10 - Subscribe to increase this limit!",
            required = False)

        details_popup.add_text(
            label = "Maximum location count",
            placeholder = "10 - Subscribe to increase this limit!",
            required = False)

        details_button = dialogue.add_button(label = "Set roleplay details", style = ButtonStyle.blurple)
        dialogue.add_modal(details_popup, details_button)

        submit_button = dialogue.add_button(label = "Submit", style = ButtonStyle.success)
        submit_button.should_disable = lambda : not dialogue.is_valid
        dialogue.add_close()

        async def submit(interaction: Interaction):

            description = "This server is now registered. First" \
                " things first: set up a `/new location`."

            description, ref_url = await reference_validator(
                description, 
                dialogue.fields["Reference photo URL"].get_value())

            await server.create(
                log_channel_id = dialogue.fields["logging"].get_value(),
                name = dialogue.fields["Title"].get_value(),
                description = dialogue.fields["Description"].get_value(),
                reference = ref_url,
                character_limit = 10,
                location_limit = 10,
                subscription_end = None)
            
            dialogue.current_embed = text_embed(
                "All set!",
                description = description,
                footer = "And if you ever change your mind about" \
                    " the deets, you can just do /review roleplay.")
            dialogue.view.clear_items()
            await dialogue.refresh(interaction)

            return

        submit_button.callback = submit

        await dialogue.view.refresh_children()
        return await send_message(ctx.interaction, embed, dialogue.view, ephemeral = True)
    
def setup(prox):
    prox.add_cog(NewCommands(prox), override = True)
