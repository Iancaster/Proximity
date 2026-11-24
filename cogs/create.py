
from discord import ApplicationContext, InteractionContextType, \
    ButtonStyle, InputTextStyle, Interaction, TextChannel, Embed
from discord.ext import commands
from discord.commands import SlashCommandGroup

from libraries.classes import (in_text_channel, \
    is_administrator, in_prox_rp, in_location, \
    Roleplay, Location, Route, Character, Relayable)
from libraries.user_interface import Dialogue, Popup, \
    send_message, reference_validator, LOGO, safe_send
from data.database_entries import ( 
    roleplay_repo, RoleplayData,
    location_repo, LocationData,
    character_repo, CharacterData,
    route_repo, RouteData)
from data.database_handler import CommitResult
from libraries.embed_templates import RoleplayEmbeds, \
    LocEmbeds, CharEmbeds, ErrorEmbeds, RouteEmbeds

class CreateCommands(commands.Cog):

    create_group = SlashCommandGroup(
        name = "create",
        description = "Create new Roleplays, Locations, Routes, and Characters-- in that order.",
        contexts = [InteractionContextType.guild],
        checks = [in_text_channel, is_administrator])

    @create_group.command(
        name = "location", 
        description = "Create a new Location for Characters to roleplay in.",
        checks = [in_prox_rp])
    async def location(self, ctx: ApplicationContext):

        rp = await Roleplay.ensure_load(ctx.guild_id)
        
        if rp.data.location_limit is not None \
            and await rp.location_count >= rp.data.location_limit:

            embed = await LocEmbeds.create.hit_limit(
                location_limit = rp.data.location_limit, 
                end_date = rp.data.subscription_end)

            return await send_message(
                ctx.interaction, 
                embed, 
                ephemeral = True)

        embed = LocEmbeds.create.set_details() 
        
        dialogue = Dialogue(embed, disable_timeout = True)
        details_popup = Popup(title = "New location details")

        details_popup.add_text(
            label = "Name", 
            placeholder = "What should the Location be named?", 
            min_length = 1, 
            max_length = 100)
        
        details_popup.add_text(
            label = "Description", 
            placeholder = "Share some lore! Or how it sounds, maybe how it smells?", 
            min_length = 0, 
            max_length = 300,
            required = False,
            style = InputTextStyle.paragraph)
        
        details_popup.add_text(
            label = "Reference photo URL",
            placeholder = "Right click an Imgur image and select 'Copy Link'.",
            min_length = 1,
            max_length = 300,
            required = False,
            style = InputTextStyle.paragraph)

        details_button = dialogue.add_button(
            label = "Set Location details", 
            style = ButtonStyle.blurple)
        dialogue.add_modal(details_popup, details_button)

        submit_button = dialogue.add_button(
            label = "Submit", 
            style = ButtonStyle.success)
        submit_button.should_disable = lambda : not dialogue.is_valid
        dialogue.add_close()  

        async def submit(interaction: Interaction):

            await interaction.response.defer()

            loc_name = dialogue.fields["Name"].get_value()
            reference_url = dialogue.fields["Reference photo URL"].get_value()
            url_result = await reference_validator(reference_url)

            if url_result != CommitResult.SUCCESS:
                reference_url = None

            loc_channel = await Relayable.create_channel(
                channel_name = loc_name, 
                guild_id = interaction.guild_id, # pyright: ignore[reportArgumentType]
                is_location = True)
            
            if not isinstance(loc_channel, TextChannel):

                embed = ErrorEmbeds.channel_creation_err()
                dialogue.current_embed, dialogue.current_file = embed, None
                dialogue.view.clear_items()
                dialogue.add_close()
                return await dialogue.refresh(interaction)

            loc_data = LocationData(
                location_id = loc_channel.id,
                roleplay_id = loc_channel.guild.id,
                name = loc_name,
                description = dialogue.fields["Description"].get_value(),
                reference = reference_url)

            dialogue.view.clear_items()
            dialogue.current_embed, dialogue.current_file = \
                await LocEmbeds.create.user(
                    description = loc_data.description,
                    reference = reference_url)
            dialogue.add_close()
            await dialogue.refresh(interaction)

            location = await Location.create(loc_data)  
            if not isinstance(location, Location):
                return

            await rp.notify_log(*await LocEmbeds.create.log(
                name = loc_data.name,
                description = loc_data.description,
                reference = reference_url))

            return await location.notify_log(*await LocEmbeds.create.channel(
                description = loc_data.description,
                reference = reference_url))

        submit_button.callback = submit

        await dialogue.view.refresh_children()
        return await send_message(
            ctx.interaction, 
            embed, 
            dialogue.view, 
            ephemeral = True)
    
    # Rework this to simply disallow no-new-neighbor submissions
    @create_group.command(
        name = "route", 
        description = "Lets Characters travel between Locations.", 
        checks = [in_location])
    async def route(self, ctx: ApplicationContext):

        location = await Location.load(ctx.channel_id) 
        assert location is not None

        rp = await Roleplay.load(ctx.guild_id)
        assert isinstance(rp, RoleplayData)

        curr_dir = "<->"
        dir_to_recip = {
            "<->" : "<->",
            "->" : "<-",
            "<-" : "->"}       

        dialogue = Dialogue(RouteEmbeds.create.set_neighbors(curr_dir))

        async def submit(interaction: Interaction):

            neighbors = dialogue.fields["Neighbors"].get_channel_ids() # pyright: ignore[reportAttributeAccessIssue]
            neighbors = [await location_repo.fetch(n) for n in neighbors]
            neighbors = [n for n in neighbors if not isinstance(n, CommitResult)]

            if not neighbors:

                dialogue.current_embed = ErrorEmbeds.no_locs_selected()
                dialogue.view.clear_items()
                return await dialogue.refresh(interaction)

            existing_routes = [end for route in await location.connections for end in (route.to_id, route.from_id)]
            neighbors = [n for n in neighbors if n.location_id not in existing_routes]

            if not neighbors:
                dialogue.current_embed = RouteEmbeds.create.no_new_neighbors()
                dialogue.view.clear_items()
                return await dialogue.refresh(interaction)

            for neigh in neighbors:

                if ">" in curr_dir:
                    data = RouteData(
                        from_id = location.data.location_id,
                        to_id = neigh.location_id,
                        roleplay_id = rp.data.roleplay_id)
                    await Route.create(data)

                if "<" in curr_dir:
                    data = RouteData(
                        from_id = neigh.location_id,
                        to_id = location.data.location_id,
                        roleplay_id = rp.data.roleplay_id)
                    await Route.create(data)

                embed = await RouteEmbeds.create.channel(
                    origin = neigh,
                    destinations = [location.data],
                    directionality = dir_to_recip[curr_dir])
                
                await safe_send(embed, [neigh.location_id], silent = True)

            embed = await RouteEmbeds.create.log(
                location.data, 
                neighbors, 
                curr_dir)
            await rp.notify_log(embed)

            embed = await RouteEmbeds.create.channel(
                location.data,
                neighbors,
                curr_dir)
            await safe_send(embed, [location.data.location_id], silent = True)

            embed = await RouteEmbeds.create.user(
                location.data, 
                neighbors,
                curr_dir)

            dialogue.current_embed = embed
            dialogue.view.clear_items()
            return await dialogue.refresh(interaction)
            
        dialogue.add_channel_select(
            "Neighbors",
            "Neighbor selection",
            "#the-courtyard",
            min_values = 1,
            max_values = 5)

        async def cycle_direction(interaction: Interaction):
            nonlocal curr_dir
            all_dirs = list(dir_to_recip.keys())
            next_dir_index = all_dirs.index(curr_dir) + 1
            curr_dir = all_dirs[next_dir_index] if \
                next_dir_index <= len(all_dirs) else all_dirs[0] 
            dialogue.current_embed = RouteEmbeds.create.set_neighbors(curr_dir)
            return await dialogue.refresh(interaction)
        
        dir_button = dialogue.add_button("Change direction", style = ButtonStyle.secondary)
        dir_button.callback = cycle_direction

        submit_button = dialogue.add_button("Submit", style = ButtonStyle.success)
        submit_button.callback = submit
        submit_button.should_disable = lambda : not dialogue.is_valid
        submit_button.disabled = True

        dialogue.add_close()

        return await send_message(
            ctx.interaction,
            dialogue.current_embed,
            dialogue.view,
            ephemeral = True)

    @create_group.command(
            name = "roleplay", 
            description = "Make this server a new Proximity roleplay!")
    async def roleplay(self, ctx: ApplicationContext):

        if await roleplay_repo.exists(ctx.guild_id) == CommitResult.SUCCESS:
            embed = RoleplayEmbeds.create.exists_already()
            return await send_message(
                ctx.interaction, 
                embed, 
                ephemeral = True)
            
        embed = RoleplayEmbeds.create.set_initial_details()
        
        dialogue = Dialogue(embed, disable_timeout = True)

        dialogue.add_channel_select(
            label = "Logging", 
            purpose = " for admin logs",
            min_values = 1)

        # Details modal
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

        details_button = dialogue.add_button(
            label = "Set roleplay details", 
            style = ButtonStyle.blurple)
        
        dialogue.add_modal(details_popup, details_button)
        # End Modal

        async def submit(interaction: Interaction):

            url = dialogue.fields["Reference photo URL"].get_value()
            url_result = await reference_validator(url)

            rp_data = RoleplayData(
                roleplay_id = ctx.guild_id,
                name = dialogue.fields["Title"].get_value(),
                log_channel_id = dialogue.fields["Logging"].get_value(),
                description = dialogue.fields["Description"].get_value(),
                reference = url if url_result == CommitResult.SUCCESS else None)

            rp = await Roleplay.create(rp_data)
            if not isinstance(rp, Roleplay):
                return
            
            embed, file = await RoleplayEmbeds.create.log(
                rp_data.name, 
                rp_data.reference)
            await rp.notify_log(embed, file)
            
            dialogue.current_embed, dialogue.current_file = \
                await RoleplayEmbeds.create.user(rp_data.reference, url_result)
            dialogue.view.clear_items()
            return await dialogue.refresh(interaction)

        submit_button = dialogue.add_button(label = "Submit", style = ButtonStyle.success)
        submit_button.should_disable = lambda : not dialogue.is_valid
        submit_button.callback = submit
        dialogue.add_close()

        await dialogue.view.refresh_children()
        return await send_message(
            ctx.interaction, 
            embed, 
            dialogue.view, 
            ephemeral = True)
    
def setup(prox):
    prox.add_cog(CreateCommands(prox), override = True)
