"""
Entry point — wires all layers together and starts the bot.

Startup sequence:
  1. Ensure DB exists (idempotent)
  2. Build Orchestrator
  3. Build TelegramChannel (or swap for another Channel subclass here)
  4. Start long-polling
"""
import asyncio
import logging

from config import DB_PATH
from db.init_db import init_db
from orchestrator.core import Orchestrator
from gateway.telegram import TelegramChannel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main() -> None:
    init_db(DB_PATH)

    orchestrator = Orchestrator(db_path=DB_PATH)

    # Swap TelegramChannel for any other Channel subclass here without
    # touching the orchestrator.
    channel = TelegramChannel(orchestrator=orchestrator)

    await channel.run()


if __name__ == "__main__":
    asyncio.run(main())
