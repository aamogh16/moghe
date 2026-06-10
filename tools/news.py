from tools.base import Tool


class NewsTool(Tool):
    name = "news"
    description = "Fetch and summarise recent news headlines."

    async def run(self, **kwargs) -> str:
        # TODO: implement news API connector
        raise NotImplementedError("NewsTool not yet implemented")
