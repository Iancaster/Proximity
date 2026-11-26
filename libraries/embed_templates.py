
from discord import Embed, File

from data.database_entries import CommitResult, \
    RoleplayData, LocationData, CharacterData, RouteData
from data.database_handler import _Unset, UNSET
from libraries.user_interface import text_embed, image_embed, \
    ImageSource, safe_send, get_channel, reference_validator, oxfordize

from datetime import datetime as dt
from io import BytesIO

class ErrorEmbeds:

    @staticmethod
    def non_admin() -> Embed:

        return text_embed(
            title = "No can do.",
            description = "To prevent abuse, only admins can call this command.",
            footer = "Sorry.")

    @staticmethod
    def non_text_channel() -> Embed:

        return text_embed(
            "Where am I?",
            "This command only works in a normal text channel.",
            "Try calling this command again, but from there instead.")

    @staticmethod
    def non_character() -> Embed:

        return text_embed(
            "This isn't a character channel.",
            "This command only works for characters.",
            "Try calling this command again there.")

    @staticmethod
    def non_prox_rp() -> Embed:

        return text_embed(
            "Hold your horses, cowboy.",
            "This command is for Proximity roleplay servers, which this is not."
                " You can make a server into a Prox RP by doing `/create Roleplay`"
                " in it, once I'm there too. Assuming you've got the permissions," \
                " of course.",
            "Or just head to your favorite roleplay and ask the staff switching over!")

    @staticmethod
    def channel_creation_err() -> Embed:

        return text_embed(
            "Hm, that didn't work.",
            "This only works with permission to create channels and/or webhooks." + \
                " See about getting that corrected first.",
            "Should just be as simple as granting a role with the permissions given.")

    @staticmethod
    def non_location() -> Embed:

        return text_embed(
            "Hold on, this isn't a Location.",
            "This command only works in Location channels." + \
                " Maybe the developer will change this, in time...",
            "Until then, just go to a Location channel and call this command again.")

    @staticmethod
    def no_locs_selected() -> Embed:

        return text_embed(
            title = "No Location selected.",
            description = "This command requires that you select a Location.",
            footer = "Try calling it again?")

class _UserLook:

    @staticmethod
    async def overview(
        loc_data: LocationData,
        occupants: list[CharacterData],
        neighbors: list[LocationData]
    ) -> tuple[Embed, File | None]:

        title = f"Looking around {loc_data.char_mention}"
        description = "You look around and "
        footer = "Take a closer look at something?"

        if len(occupants) > 0:
            occ_names = [occ.char_mention for occ in occupants]
            description += f"see {oxfordize(occ_names)} here with you."

        else:
            description += "don't see anyone else in here with you."  

        if neighbors:
            neigh_names = [neigh.char_mention for neigh in neighbors]
            description += f"\n\nThis Location is adjacent to {oxfordize(neigh_names)}."
        else:
            description += "\n\nYou don't see any other way in or out. Uh oh."   

        if loc_data.reference:

            embed, file = await image_embed(
                title = title,
                description = description,
                footer = footer,
                thumbnail = True,
                source = ImageSource.URL,
                asset_str =  loc_data.reference)

        else:

            embed = text_embed(
                title = title,
                description = description,
                footer = footer)
            file = None

        return embed, file

    @staticmethod
    def examine_char_undecided() -> Embed:

        return text_embed(
                "Someone catch your eye?",
                f"Who would you take a closer look at?",
                "They probably won't mind.")

    @staticmethod
    async def examine_char(
        examined_char_data: CharacterData
    ) -> tuple[Embed, File | None]:

        title = f"Looking at {examined_char_data.char_mention}"
        description = examined_char_data.description or "This character" + \
            " doesn't have much known about them."

        if examined_char_data.reference:
            embed, file = await image_embed(
                title = title,
                description = description,
                footer = "Pretty cool reference pic, right?",
                thumbnail = False,
                source = ImageSource.URL,
                asset_str = examined_char_data.reference)
            
        else:

            embed = text_embed(
                title = title,
                description = description,
                footer = "P.S., if they had a reference pic, it would" + \
                    " be included here.")
            file = None

        return embed, file

    @staticmethod
    async def shown_while_focusing(
        focusing_char_data: CharacterData
    ) -> tuple[Embed, File | None]:

        return await image_embed(
            "Like what you see?",
            f"{focusing_char_data.char_mention} stole a glance at you.",
            "Maybe they thought you wouldn't notice.",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = focusing_char_data.reference)

    @staticmethod
    async def examine_location(loc_data: LocationData) -> tuple[Embed, File | None]:

        title = f"Looking around {loc_data.char_mention}"
        description = loc_data.description if loc_data.description \
            else "Not much to say about this place."
        footer = "Find what you were looking for?"

        if loc_data.reference:

            embed, file = await image_embed(
                title = title,
                description = description,
                footer = footer,
                thumbnail = False,
                source = ImageSource.URL,
                asset_str = loc_data.reference)

        else:

            embed = text_embed(title, description, footer)
            file = None

        return embed, file

    @staticmethod
    def examine_routes(
        loc_data: LocationData,
        neighbors: list[LocationData],
        inlets: list[RouteData],
        outlets: list[RouteData]
    ) -> Embed:

        if inlets:

            inlet_ids = [route.from_id for route in inlets]
            inlet_neighs = [n for n in neighbors if n.location_id in inlet_ids]

            description = "You can access this Location from " + \
                oxfordize([inl.char_mention for inl in inlet_neighs]) + ", and "

        else:
            description = "There's no way in here except...well, maybe " + \
                "teleportation. That said, "

        if outlets:

            outlet_ids = [route.to_id for route in outlets]
            outlet_neighs = [n for n in neighbors if n.location_id in outlet_ids]

            description += "you can leave this place to go to " + \
                oxfordize([outl.char_mention for outl in outlet_neighs]) + "."

        else:
            description += " that's where the good news ends. There's no way " + \
                "out except, like, teleportation."

        if not neighbors:
            description = "This place has no way in and no way out. Oh dear."

        embed = text_embed(
            f"Routes to/from {loc_data.char_mention}", 
            description, 
            "Hoping for a secret passageway?")

        return embed

class _UserMove:

    @staticmethod
    def no_exit() -> Embed:

        return text_embed(
            "Uh oh.",
            "There doesn't seem to be any way out from here.",
            "Hopefully someone can hear you from here?")       

    @staticmethod
    async def where_to(
        loc_data: LocationData, 
        render: BytesIO
    ) -> tuple[Embed, File]:

        return await image_embed(
            title = "Where to?",
            description = f"You can leave {loc_data.char_mention} to access" + \
                " any of the places below.",
            footer = "Just pick your destination and you'll take the" + \
                " shortest path there.",
            thumbnail = False,
            source = ImageSource.BYTES,
            asset_bytes = render) # pyright: ignore[reportReturnType]

    @staticmethod
    def propose_route(path_mentions: list[str]) -> Embed:

        return text_embed(
            f"Travel to {path_mentions[-1]}?",
            f"You can reach {path_mentions[-1]} by going along this route:\n" + \
                " -> ".join(path_mentions),
            "If there's multiple ways to get there, you choose to take a different path" + \
                " by splitting your movement into multiple smaller steps.")

    @staticmethod
    async def exit_location(
        char_mention: str, 
        char_ref: str | None, 
        neigh_mention: str
    ) -> tuple[Embed, File | None]:

        return await image_embed(
            "See you around.",
            f"You notice {char_mention} leave in the direction of {neigh_mention}.",
            "I'm sure you'll see them around again soon.",
            thumbnail = True, 
            source = ImageSource.URL,
            asset_str = char_ref)

    @staticmethod
    async def pass_location(
        char_mention: str, 
        char_ref: str | None, 
        prev_loc_mention: str,
        next_loc_mention: str
    ) -> tuple[Embed, File | None]:

        return await image_embed(
            "Passing through.",
            f"You notice {char_mention} pass through. They came from" + \
                f" the direction of {prev_loc_mention}, and kept going" + \
                f" towards the direction of {next_loc_mention}.",
            "Maybe you can catch up to them, if you'd like?",
            thumbnail = True, 
            source = ImageSource.URL,
            asset_str = char_ref)

    @staticmethod
    async def enter_location(
        char_mention: str, 
        char_ref: str | None, 
        neigh_mention: str
    ) -> tuple[Embed, File | None]:

        return await image_embed(
            "An arrival.",
            f"You notice {char_mention} enter from the direction of {neigh_mention}.",
            "Greet them?",
            thumbnail = True, 
            source = ImageSource.URL,
            asset_str = char_ref)

    @staticmethod
    async def arrive(
        loc_mention: str, 
        loc_ref: str | None, 
        occupants: list[CharacterData]
    ) -> tuple[Embed, File | None]:

        if occupants:
            description = f"You notice {oxfordize([occ.char_mention for occ in occupants])} here with you."
        else:
            description = "You seem to be the only one here right now."

        return await image_embed(
            f"You arrive at {loc_mention}.",
            description,
            "What next?",
            thumbnail = True, 
            source = ImageSource.URL,
            asset_str = loc_ref)

    @staticmethod
    async def passed_by(
        char_mention: str,
        char_ref: str,
        path_mentions: list[str]
    ) -> tuple[Embed, File | None]:

        return await image_embed(
            "Movement.",
            f"{char_mention} moved from/through/to here along their path:" + \
                " -> ".join(path_mentions),
            "You can view their travel from their point of view via their character channel.",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = char_ref)

class UserEmbeds:
    look = _UserLook
    move = _UserMove

class _CharDelete:

    @staticmethod
    async def user(name: str, reference: str | None) -> tuple[Embed, File | None]:

        return await image_embed(
            f"Character Deleted: {name}",
            ("Character removed by user. They no longer exists."
                " Please verify that the channel was"
                " deleted properly, because sometimes it can fail due to"
                " external factors or lack of permissions."),
            "Rest in peace. They can never be replaced...but you can always make a new one.",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = reference)
    
    @staticmethod
    async def auto(char_name: str, reference: str | None) -> tuple[Embed, File | None]:

        return await image_embed(
            f"Character Deleted: {char_name}",
            ("Character deleted by deleting their Character channel."
                " If this was an accident, you can just recreate the"
                " Character with `/create Character`. No worries."),
            "Unless it wasn't an accident at all. In which case...rest in peace.",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = reference)

#class _CharCreate:

class _CharReview:
    ...

class CharEmbeds:
    delete = _CharDelete
    #create =
    review = _CharReview 

class _RouteCreate:

    @staticmethod
    def set_neighbors(selected_direction: str) -> Embed:

        dir_expls = {
            "<->" : "Goes both ways",
            "->" : "Only goes from here to the other Location",
            "<-" : "Only allows travel *from* those Locations *to* here"}

        description = ("What other Location(s) should this be connected to? Select" + 
            " one or more Locations you want to ensure are connected" + 
            " and choose what direction the pathways go.")

        for dir, expl in dir_expls.items():
           
            if dir == selected_direction:
                description += f"\n**- {dir} {expl}**"
            else:
                description += f"\n- {dir} {expl}"

        return text_embed(
            title = "Where to?",
            description = description,
            footer = "Most of the time, you want your Routes to be two-ways, not one-way.")

    @staticmethod
    def no_new_neighbors() -> Embed:

        return text_embed(
            title = "No new connections.",
            description = ("`/create Route` is only for creating new Routes-- if you" +
                " already have a Route between this Location and another," +
                " then this command won't affect it. If you want to overwrite" +
                " a Route, you can use `/review Route` or just `/delete" +
                " Route` and recreate."),
            footer = "Feel free to call the command again.")

    @staticmethod
    async def log(
        origin: LocationData,
        destinations: list[LocationData],
        directionality: str
    ) -> Embed:

        dest_mentions = ", ".join(d.mention for d in destinations)

        description = f"Connected {origin.mention} to {dest_mentions}. It's "

        if directionality == "<->":
            description += "both-ways-- there and back. Characters can move" + \
                " along the Route in either direction."
        elif directionality == "->":
            description += "one-way-- Characters can go there, but not back."
        elif directionality == "<-":
            description += "one-way-- Characters can come from there, but" + \
                " not the other way around."

        return text_embed(
            f"{origin.name} connected.",
            description,
            "As a reminder, Characters can be heard through nearby Routes.")
        
    @staticmethod
    async def user(
        origin: LocationData,
        destinations: list[LocationData],
        directionality: str
    ) -> Embed:

        description = f"Connected {len(destinations)} other Location/s to" + \
            f" {origin.mention}. It's "

        if directionality == "<->":
            description += "both-ways-- there and back. Characters can move" + \
                " along the route in either direction."
        elif directionality == "->":
            description += "one-way-- Characters can go there, but not back."
        elif directionality == "<-":
            description += "one-way-- Characters can come from there, but" + \
                " not the other way around."

        description += ("\n\n >>> *Notice: some channels you selected on the" +
            " menu might have been dropped, if you selected channels that" +
            " don't go to a Location, or if there's already a Route between" +
            " that Location and here.*")

        return text_embed(
            f"{origin.name} connected.",
            description,
            "As a reminder, Characters can be heard through nearby Routes.")

    @staticmethod
    async def channel(
        origin: LocationData,
        destinations: list[LocationData],
        directionality: str
    ) -> Embed:
        
        dest_mentions = ", ".join(d.mention for d in destinations)

        description = f"{origin.mention} is now connected to {len(destinations)}" + \
            f" other Location/s: {dest_mentions}. It's "

        if directionality == "<->":
            description += "both-ways-- there and back. Characters can move" + \
                " along the routes in either direction."
        elif directionality == "->":
            description += "one-way-- Characters can go there, but not back."
        elif directionality == "<-":
            description += "one-way-- Characters can come from there, but" + \
                " not the other way around."

        return text_embed(
            f"{origin.name} connected.",
            description,
            "As a reminder, Characters can be heard across nearby Routes.")                                                 

class RouteEmbeds:
    create = _RouteCreate

class _LocDelete:

    @staticmethod
    def blocked(mention: str) -> Embed:

        return text_embed(
            title = "Can't delete this Location.",
            description = f"{mention} still has characters in it. Please move" + \
                " them somewhere else first with `/review Character`.",
            footer = "This is to prevent Characters from being stranded in " + \
                "a nonexistant Location. Just imagine...")

    @staticmethod
    def selection() -> Embed:

        return text_embed(
            title = "Which Location?",
            description = ("Choose which Location you want to delete" +
                " by selecting its channel in dropdown below. You'll" +
                " be asked to confirm whether you're sure if you want"
                " to delete."),
            footer = "Or you can also call this command in a Location" + \
                " channel to select it automatically.")
        

    @staticmethod
    def confirmation(mention: str) -> Embed:

        return text_embed(
            title = "Delete this location?",
            description = (f"You're about to delete {mention} and all" + 
                " Routes to and from it. Side note: it has to be empty" + 
                " of Characters."),
            footer = "This is irreversible, so make sure you really" + \
                " want to do this.")

    @staticmethod
    async def log(loc_name: str, reference: str | None) -> tuple[Embed, File | None]:

        return await image_embed(
            f"Location Deleted: {loc_name}",
            ("Location removed by user and now it no longer exists."
                " All Routes connected to it have been deleted."
                " Please verify that the channel was"
                " deleted properly, because sometimes it can fail due to"
                " external factors or lack of permissions."),
            "Feel free to make other Locations in its stead!",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = reference)

    @staticmethod
    async def user(name: str, reference: str | None) -> tuple[Embed, File | None]:

        return await image_embed(
            "Location deleted.",
            f"You've deleted **{name}** and all routes connected to it.",
            "This can't be undone, but you can always make a new Location.",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = reference)

    @staticmethod
    async def channel() -> Embed:
        ...

    @staticmethod
    async def auto(name: str, reference: str | None) -> tuple[Embed, File | None]:

        return await image_embed(
            f"Location Deleted: {name}",
            ("Deleted by deleting the Location channel."
                " If this was an accident, you can just recreate the"
                " Location with `/create Location`. No worries."),
            "Unless it wasn't an accident at all. In which case...rest in peace.",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = reference)

class _LocCreate:

    @staticmethod
    async def hit_limit(location_limit: int, end_date: dt) -> Embed:

        return text_embed(
            "Easy there.",
            f"Looks like you're already at your limit of {location_limit}" \
                " Locations. If you'd like more, think about a subscription." \
                " Each roleplay starts with a free week of subscription-- this" \
                f" one ended on {end_date.isoformat()}.", 
            "Proceeds go straight towards server costs and feature improvements.")

    @staticmethod
    def set_details() -> Embed:
        return text_embed(
            "Someplace new?",
            "All you need to provide is a name, and"
                " I can make the Location and its channel. But if you like," \
                " you can include a description and a reference photo.", 
            "All of this can be edited later with /review Location.")

    @staticmethod
    async def log(
        name: str, 
        description: str | None, 
        reference: str | None
    ) -> tuple[Embed, File | None]:

        embed_description = "Location made."

        if not description:
            embed_description += " No description is attached--yet."

        else:
            embed_description += (" This Location has the following" 
                " description, which is visible to Characters who `/look` around:"
                "\n>>> ") + description # pyright: ignore[reportOperatorIssue]

        embed_description += ("\n\n_As a reminder, Location channels aren't for roleplaying"
            " inside of. It's basically a log. Although there are some"
            " interesting things Hosts can do by posting in a Location"
            " channel directly..._")
        
        if reference is None:
            footer = "This Location has no reference photo attached."
        
        elif await reference_validator(reference) != CommitResult.SUCCESS:
            footer = ("The reference photo provided wasn't valid.")
        
        else:
            footer = "Pretty nifty reference photo."

        footer += " Be sure to connect it to other Locations with /create Route."
        
        return await image_embed(
            f"New Location: {name}",
            description = embed_description,
            footer = footer,
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = reference)

    @staticmethod
    async def user(
        description: str | None, 
        reference: str | None
    ) -> tuple[Embed, File | None]:

        embed_description = ("Looking good! Connect this Location with a"
            " `/create Route` so characters can move here-- unless you want"
            " it only to be accessible when a Host uses `/review Character`"
            " to place them here.\n\n")

        if not description:
            embed_description += ("This Location has no description" 
                " yet, but you can add one with `/review Location`.")
            
        else:
            embed_description += ("This Location has the following" 
                " description, which is visible to players who `/look` around:"
                "\n>>> ") + description

        embed_description += ("\n\n_As a reminder, Location channels aren't for roleplaying"
            " inside of. It's basically a log. Use the"
            " Character channels for roleplay. (Probably the only time"
            " you'll be posting in a Location channel directly is if"
            " you're posting as the Location itself...which could be cool, actually._)")

        if reference is None:
            footer = "You can add a reference photo later with /review Location."
        elif await reference_validator(reference) != CommitResult.SUCCESS:
            footer = ("Unfortunately, the reference photo you provided isn't valid.")
        else:
            footer = "Love the reference you chose."
        
        return await image_embed(
            "Location made!",
            description = embed_description,
            footer = footer,
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = reference)

    @staticmethod
    async def channel(
        description: str | None, 
        reference: str | None
    ) -> tuple[Embed, File | None]:

        embed_description = ("Check out the new digs.\n\n")

        if not description:
            embed_description += ("This Location has no description" 
                " yet, but a Host can add one with `/review Location`.")
            
        else:
            embed_description += ("This Location has the following" 
                " description, which is visible to players who `/look` around:"
                "\n>>> ") + description

        embed_description += ("\n\n_As a reminder, Location channels aren't for roleplaying"
            " inside of. It's basically a log. Although there are some"
            " interesting things Hosts can do by posting in a Location"
            " channel directly..._")
        
        if reference is None:
            footer = "This Location has no reference photo attached, currently."
        elif await reference_validator(reference) != CommitResult.SUCCESS:
            footer = ("Unfortunately, the reference photo passed in isn't valid.")
        else:
            footer = "Pretty nifty reference photo."
        
        return await image_embed(
            f"New Location!",
            description = embed_description,
            footer = footer,
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = reference)

class _LocReview:

    @staticmethod
    def select_location() -> Embed:
        return text_embed(
            title = "Which Location?",
            description = ("Please select a Location channel from the dropdown below" +
                " to review its details. You can also call this command" +
                " in a Location channel to select it automatically."),
            footer = "This will show you everything about the place.")

    @staticmethod
    async def user(
        description: str | None, 
        reference: str | None
    ) -> tuple[Embed, File | None]:

        ...

class LocEmbeds:
    delete = _LocDelete
    create = _LocCreate
    review = _LocReview

class _RoleplayDelete:

    @staticmethod
    def confirm_delete() -> Embed:
        return text_embed(
            "Delete all data?",
            "You're about to delete all roleplay data, including"
                " all Locations and Characters. Any associated" 
                " channels will be deleted, apart from the"
                " log channel you set when you registered the server.",
            "This is irreversible, so make sure you're certain you want this.")

    @staticmethod
    async def log(reference: str | None) -> tuple[Embed, File | None]:

        return await image_embed(
            "Roleplay Deleted.",
            "The following has been deleted: " 
                "\n - All server data (name, description, reference, etc)."
                "\n - All Locations, their channels, and all Routes between them."
                "\n - All Characters and their Location channels.",
            "Sorry to see you go.",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = reference)

    @staticmethod
    async def user(rp_name: str, reference: str | None) -> tuple[Embed, File | None]:

        return await image_embed(
            "Roleplay Deleted.",
            f"There's nothing left of **{rp_name}**. That's all she wrote.",
            "Sorry to see you go.",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = reference)

class _RoleplayCreate:

    @staticmethod
    def exists_already() -> Embed:

        return text_embed(
            title = "Way ahead of you.",
            description = ("This server is already registered for roleplay. "
                "If you want to start over, delete the existing data with "
                "`/delete roleplay` and then call this command again."),
            footer ="But if you just want a /create location or a /create " \
                "character, call those instead.")

    @staticmethod
    def set_initial_details() -> Embed:

        return text_embed(
            "Let's do this.",
            "First things first, your roleplay needs a name. You'll,"
                " also need to set a log channel to record things like" \
                " creating or editing the roleplay." \
                " And if you're feeling fancy, you can also add a" \
                " description or even a reference photo. ", 
            "You can change all these things later with /review roleplay.")

    @staticmethod
    async def log(rp_name: str, reference: str | None) -> tuple[Embed, File | None]:

        return await image_embed(
            title = f"Roleplay Created: **{rp_name}**",
            description = ("Success! This server is now a Proximity Roleplay." +
                " Start with `/create Location`. Do that a few times, then use" +
                " `/create Route` so people can travel between the Locations." +
                " Finally, use `/create Character` for each of your NPCs and players." + 
                " And don't be afraid to ask for `/help`."),
            footer = "Let's get started!",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = reference)

    @staticmethod
    async def user(reference: str | None, url_result: CommitResult) -> tuple[Embed, File | None]:

        description = (f"This server is now registered for roleplay! First" 
            " things first: you've got to give your Characters some place to" 
            " go. Start with `/create Location`.")

        match url_result:

            case CommitResult.SUCCESS:
                description += "\n\nP.S. The reference pic looks great."

            case CommitResult.FOREIGN_KEY_FAIL:
                description += "\n\nP.S. The URL for the reference wasn't valid." + \
                    " Maybe `/review roleplay` to resubmit a new one?"

            case CommitResult.NO_UPDATE:
                description += "\n\nP.S. Feel free to `/review roleplay`" + \
                    " to submit a reference photo when you've got the time."

            case _:
                pass

        return await image_embed(
            "All set!",
            description = description,
            footer = "And if you ever change your mind about" \
                " the deets, you can just do /review roleplay.",
            source = ImageSource.URL,
            asset_str = reference)

class _RoleplayReview:

    @staticmethod
    async def overview(
        rp_data: RoleplayData, 
        character_count: int,
        location_count: int) -> tuple[Embed, File | None]:

        return await image_embed(
            f"Reviewing {rp_data.name}",
            f"**Character Count:** {character_count} / {rp_data.character_limit}"
                f"\n**Character Category:** " +
                    (f"{rp_data.char_mention}" if rp_data.characters_cat is not None else "None yet.") +
                f"\n**Location Count:** {location_count} / {rp_data.location_limit}"
                f"\n**Location Category:** " +
                    (f"{rp_data.loc_mention}" if rp_data.locations_cat is not None else "None yet.") +
                f"\n**Log Channel:** {rp_data.log_mention}"
                f"\n**Description:** {rp_data.description}"
                "\n**Reference:** " +
                    ("See below." if rp_data.reference else "None (yet). You should add one!"),
            "Would you perhaps like to change these things?",
            thumbnail = rp_data.reference is None,
            source = ImageSource.URL if rp_data.reference is not None else ImageSource.ASSET,
            asset_str = rp_data.reference or "")

    @staticmethod
    async def log(
        old_rp_data: RoleplayData,
        prop_diffs: dict,
        new_rp_data: RoleplayData
    ) -> tuple[Embed, File | None]:

        old_dict = old_rp_data.__dict__
        new_dict = new_rp_data.__dict__

        acc_diffs = {k : v for k, v in new_dict.items() if v != old_dict[k]}
        
        embed_description = ""

        if "log_channel_id" in prop_diffs:

            if "log_channel_id" in acc_diffs:
                embed_description += \
                    "\n - Changed the log channel to" + \
                        f" <#{acc_diffs["log_channel_id"]}>."      
                
            else:
                embed_description += ("\n - Couldn't change the log channel to"
                    f" <#{prop_diffs["log_channel_id"]}>. Make sure the channel"
                    " doesn't restrict logging messages from being sent.")

        if "locations_cat" in acc_diffs:
            embed_description += f"\n - Changed the Locations category to *<#{acc_diffs["locations_cat"]}>*."

        if "characters_cat" in acc_diffs:
            embed_description +=  f"\n - Changed the characters category to *<#{acc_diffs["characters_cat"]}>*."

        if "name" in acc_diffs:
            embed_description += f"\n - Changed roleplay name to {acc_diffs["name"]}."

        if "character_limit" in acc_diffs:
            embed_description += f"\n - New character limit: **{acc_diffs["character_limit"]}**."

        if "location_limit" in acc_diffs:
            embed_description += f"\n - New Location limit: **{acc_diffs["location_limit"]}**."

        if "reference" in prop_diffs:

            proposed_url = prop_diffs["reference"]
            url_result = await reference_validator(proposed_url)

            if proposed_url == old_rp_data.reference:
                pass

            elif proposed_url == None:
                embed_description += f"\n - Removed photo reference."

            elif url_result == CommitResult.SUCCESS:
                embed_description += \
                    f"\n - Changed photo reference to what you see on the thumbnail."

            else:
                embed_description += \
                    f"\n - Couldn't change the photo reference because the URL was invalid."

        if "subscription_end" in acc_diffs:

            end = acc_diffs["subscription_end"]

            if end is None:
                embed_description += f"\n - Subscription is now eternal!"

            else:
                embed_description += f"\n - Subscription now ends on" + \
                    f" **{dt.fromtimestamp(end).isoformat()}**."   

        if "description" in acc_diffs:
            embed_description += "\n - Changed description to the following:" + \
                f"\n>>> {acc_diffs["description"]}"

        return await image_embed(
            f"{new_rp_data.name} changed!" if acc_diffs else "Changes failed.",
            description = embed_description,
            footer = "You can always change these things later, by the by.",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = new_rp_data.reference)

    @staticmethod
    async def user( #Can't be fucked
        old_rp_data: RoleplayData,
        prop_diffs: dict,
        new_rp_data: RoleplayData
    ) -> tuple[Embed, File | None]: 

        return await _RoleplayReview.log(
            old_rp_data, 
            prop_diffs, 
            new_rp_data) 

class RoleplayEmbeds:
    delete = _RoleplayDelete
    create = _RoleplayCreate
    review = _RoleplayReview