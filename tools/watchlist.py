from tools.base import Tool


class WatchlistTool(Tool):
    name = "watchlist"
    description = "Track and alert on prices or events for a user-defined watchlist."

    async def run(self, **kwargs) -> str:
        # TODO: implement watchlist storage + price/event polling
        raise NotImplementedError("WatchlistTool not yet implemented")
