"""
Tool interface — the plug-in seam for all tool workers.

Each tool encapsulates one capability (read email, fetch news, …).
The orchestrator calls tool.run(**kwargs) and gets back a plain string
it can pass to the LLM or relay to the user.
"""
from abc import ABC, abstractmethod


class Tool(ABC):
    name: str        # short identifier used in the orchestrator's registry
    description: str # one-liner fed to the LLM so it knows when to invoke this tool

    @abstractmethod
    async def run(self, **kwargs) -> str:
        """Execute the tool and return a plain-text result."""
