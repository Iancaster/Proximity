
from asyncio import run
from discord import TextChannel, CategoryChannel, Message
from libraries.logger import get_logger
from libraries.classes import Roleplay, Location, \
    Relayable, Route, Path, Character, get_channel

from data.database_entries import (
    roleplay_repo, RoleplayData,
    location_repo, LocationData,
    character_repo, CharacterData)
from data.database_handler import initialize_db, CommitResult 

from main import set_post_ready, main as main_main
from PIL import Image

logger = get_logger(console_level = 0)

DEV_GUILD_ID = 1111152704279035954
DEV_LOG_CHANNEL_ID = 1495269561354948761

async def reset_test_server() -> Roleplay | CommitResult:

    rp = await Roleplay.load(DEV_GUILD_ID)
        
    if rp is not None:
        await rp.delete()

    prox_test_data = RoleplayData(
        roleplay_id = DEV_GUILD_ID,
        name = "Prox Test",
        log_channel_id = DEV_LOG_CHANNEL_ID,
        description = "You be proxin? yo this guy be proxin.",
        reference = "https://arktura.com/wp-content/uploads/2020/08/Arktura-Amtosphera-Analog-3D-Concord-CA_WEB_2-1600x1078.jpg")

    rp = await Roleplay.create(prox_test_data)

    
    return rp

async def create_wedding_hall() -> Location | CommitResult:
    
    channel_results = await Relayable().create_channel(
        channel_name = "Wedding Hall",
        guild_id = DEV_GUILD_ID,
        is_location = True)

    if not isinstance(channel_results, TextChannel):
        logger.error("Failed to create test location channel.")
        logger.debug(f"Channel creation result: {channel_results}")
        return CommitResult.UNKNOWN_ERR

    location_data = LocationData(
        location_id = channel_results.id,
        roleplay_id = DEV_GUILD_ID,
        name = "Wedding Hall",
        description = "How pretty!",
        reference = "https://arktura.com/wp-content/uploads/2020/08/Arktura-Amtosphera-Analog-3D-Concord-CA_WEB_2-1600x1078.jpg")

    return await Location.create(location_data)

async def main() -> None:

    WEDDING_HALL_ID = 1547486058722361434
    TEST_LOCATION_ID = 1547486523241537536

    rp_data = await roleplay_repo.fetch(DEV_GUILD_ID)
    if not isinstance(rp_data, RoleplayData):
        return None

    char_category = get_channel(rp_data.characters_cat)

    if char_category is None:

        result = await Relayable().create_category(
            guild_id = DEV_GUILD_ID,
            is_location_cat = False)

        if not isinstance(result, CategoryChannel):
            return None

        char_category = result


    BOB_CHANNEL_ID = 1571445070488535144

    char_channel = await get_channel(BOB_CHANNEL_ID)
    if not isinstance(char_channel, TextChannel):

        result = await Relayable().create_channel(
            channel_name = "Billy Bob",
            guild_id = DEV_GUILD_ID,
            is_location = False)

        if not isinstance(result, TextChannel):
            return None

        BOB_CHANNEL_ID = result.id

        await Character.create(CharacterData(
            character_id = BOB_CHANNEL_ID,
            location_id = WEDDING_HALL_ID,
            roleplay_id = DEV_GUILD_ID,
            name = "Billy Bob",
            description = "This is a test character.",
            reference = "https://arktura.com/wp-content/uploads/2020/08/Arktura-Amtosphera-Analog-3D-Concord-CA_WEB_2-1600x1078.jpg"))

    else:
        BOB_CHANNEL_ID = char_channel.id

    character = await Character.load(BOB_CHANNEL_ID)

    

    return

    rp = await Roleplay.load(DEV_GUILD_ID)

    if rp is None:
        rp = await reset_test_server()
        await create_wedding_hall()

        assert not isinstance(rp, CommitResult), "ayo?"


    #Image.open(data).show()

    logger.debug("Dev script concluded.")

    return

if __name__ == "__main__":
    logger.info("Running program.")
    set_post_ready(main)
    run(main_main())
    logger.info("Execution concluded.")
    quit()