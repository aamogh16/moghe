from tools.base import Tool


class GmailTool(Tool):
    name = "gmail"
    description = "Read, summarise, or draft Gmail messages."

    async def run(self, **kwargs) -> str:
        # TODO: implement OAuth flow + Gmail API
        raise NotImplementedError("GmailTool not yet implemented")
