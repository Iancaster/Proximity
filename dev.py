
from asyncio import run
from discord import TextChannel
from libraries.logger import get_logger
from libraries.classes import Roleplay, Location, Relayable
from data.database_entries import (
    roleplay_repo, RoleplayData,
    location_repo, LocationData)
from data.database_handler import initialize_db, CommitResult 
from main import set_post_ready, main as main_main

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

    rp = await Roleplay.load(DEV_GUILD_ID)

    if rp is None:
        rp = await reset_test_server()
        await create_wedding_hall()
    else:
        await (await Roleplay.load(DEV_GUILD_ID)).delete()

    logger.debug("Dev script concluded.")

    return

if __name__ == "__main__":
    logger.info("Running program.")
    set_post_ready(main)
    run(main_main())
    logger.info("Execution concluded.")
    quit()