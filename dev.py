from asyncio import run
from data.database_handler import CommitResult, initialize_db
from libraries.classes import RPServer
from libraries.logger import get_logger

logger = get_logger(console_level = 0)

async def main() -> None:

    await initialize_db()

    prox_dev_server_id = 1111152704279035954
    server = RPServer(prox_dev_server_id)
    if await server.exists:
        await server.fetch()
        await server.delete()
    else:
        await server.create(
            69420,
            "Prox Chat",
            "This guy be proxin his profen.")

    return

if __name__ == "__main__":
    logger.info("Running program.")
    run(main())
    logger.info("Execution concluded.")
    quit()