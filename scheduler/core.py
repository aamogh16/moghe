"""
Scheduler — runs Tool workers on a timed basis (morning digest, price alerts, …).

Today: stub only.

Future: use APScheduler or a simple asyncio loop.
Each job specifies a cron expression, a Tool, and kwargs to pass to tool.run().
The scheduler needs a reference to Channel.send() so it can push proactive messages.
"""
from tools.base import Tool


class Scheduler:
    def add_job(self, cron: str, tool: Tool, **kwargs) -> None:
        # TODO: register a cron job that calls tool.run(**kwargs)
        raise NotImplementedError("Scheduler not yet implemented")

    async def start(self) -> None:
        # TODO: start the scheduler loop alongside the gateway
        raise NotImplementedError("Scheduler not yet implemented")
