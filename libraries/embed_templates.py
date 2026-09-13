
from discord import Embed, File
from typing import Coroutine

from data.database_entries import CommitResult, \
    RoleplayData, LocationData
from data.database_handler import _Unset, UNSET
from libraries.user_interface import text_embed, image_embed, \
    ImageSource, safe_send, get_channel, reference_validator

from datetime import datetime as dt

async def notify_log(
    rp_data: RoleplayData, 
    embed: Embed,
    file: File | None = None
) -> bool:
    """Returns bool that says whether it found the log channel."""

    log_channel = await get_channel(rp_data.log_channel_id)

    if log_channel is None:
        return False

    await safe_send(embed, [log_channel], silent = True, file = file)
    return True

class ErrorEmbeds:

    @staticmethod
    def non_text_channel() -> Embed:

        return text_embed(
            "Where am I?",
            "This command only works in a normal text channel.",
            "Try calling this command again, but from there instead.")

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
            "No location selected.",
            "This command requires that you select a location.",
            "Try calling it again?")

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

class CharacterEmbeds:
    delete = _CharDelete

class _RouteCreate:

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
    async def log(loc_name: str, reference: str | None) -> tuple[Embed, File | None]:

        return await image_embed(
            f"Location Deleted: {loc_name}",
            ("Location removed by user and now it no longer exists."
                " All Routes connected to it have been deleted."
                " Please verify that the channel was"
                " deleted properly, because sometimes it can fail due to"
                " external factors or lack of permissions."),
            "Feel free to make other locations in its stead!",
            thumbnail = True,
            source = ImageSource.URL,
            asset_str = reference)

    @staticmethod
    async def user(name: str, reference: str | None) -> tuple[Embed, File | None]:

        return await image_embed(
            "Location deleted.",
            f"You've deleted **{name}** and all routes connected to it.",
            "This can't be undone, but you can always make a new location.",
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
                " locations. If you'd like more, think about a subscription." \
                " Each roleplay starts with a free week of subscription-- this" \
                f" one ended on {end_date.isoformat()}.", 
            "Proceeds go straight towards server costs and feature improvements.")

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

        footer = "Be sure to connect it to other locations with /create Route."
        
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
            embed_description = ("This Location has no description" 
                " yet, but you can add one with `/review Location`.")
            
        else:
            embed_description = ("This Location has the following" 
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
            embed_description = ("This location has no description" 
                " yet, but a Host can add one with `/review location`.")
            
        else:
            embed_description = ("This location has the following" 
                " description, which is visible to players who `/look` around:"
                "\n>>> ") + description

        embed_description += ("\n\n_As a reminder, Location channels aren't for roleplaying"
            " inside of. It's basically a log. Although there are some"
            " interesting things Hosts can do by posting in a Location"
            " channel directly..._")
        
        if reference is None:
            footer = "This location has no reference photo attached, currently."
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
    async def log(reference: str | None) -> tuple[Embed, File | None]:

        return await image_embed(
            "Roleplay Deleted.",
            "The following has been deleted: " 
                "\n - All server data (name, description, reference, etc)."
                "\n - All Locations, their channels, and all Routes between them."
                "\n - All Characters and their location channels.",
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
    async def log(rp_name: str, reference: str | None) -> tuple[Embed, File | None]:

        return await image_embed(
            f"Roleplay Created: **{rp_name}**",
            ("Success! This server is now a Proximity roleplay."
                " Start with `/create Location`, then you can `/create Route`."
                " Finally, `/create Character`s. Don't be afraid to ask for `/help`."),
            "Let's get started!",
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

class _RoleplayUpdate:

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
            embed_description += f"\n - Changed the locations category to *<#{acc_diffs["locations_cat"]}>*."

        if "characters_cat" in acc_diffs:
            embed_description +=  f"\n - Changed the characters category to *<#{acc_diffs["characters_cat"]}>*."

        if "name" in acc_diffs:
            embed_description += f"\n - Changed roleplay name to {acc_diffs["name"]}."

        if "character_limit" in acc_diffs:
            embed_description += f"\n - New character limit: **{acc_diffs["character_limit"]}**."

        if "location_limit" in acc_diffs:
            embed_description += f"\n - New location limit: **{acc_diffs["location_limit"]}**."

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

        return await _RoleplayUpdate.log(
            old_rp_data, 
            prop_diffs, 
            new_rp_data) 

class RoleplayEmbeds:
    delete = _RoleplayDelete
    create = _RoleplayCreate
    update = _RoleplayUpdate