"""
Tool interface — the plug-in seam for all tool workers.

Each tool encapsulates one capability (read email, fetch news, …).
The orchestrator calls tool.run(**kwargs) and gets back a plain string
it can pass to the LLM or relay to the user.

A tool advertises its arguments via `parameters`, a provider-agnostic JSON
Schema object (or None for no arguments). The orchestrator translates that
into whatever the LLM's function-calling API expects. The orchestrator also
injects `user_id` into every run() call as context — it is never something
the model chooses — so concrete tools should accept it (or **kwargs).
"""
from abc import ABC, abstractmethod
from typing import Optional


class Tool(ABC):
    name: str                       # identifier + function-call name (e.g. "list_open_tasks")
    description: str                # one-liner fed to the LLM so it knows when to invoke this
    parameters: Optional[dict] = None  # JSON-Schema object for the args; None = no args

    @abstractmethod
    async def run(self, **kwargs) -> str:
        """Execute the tool and return a plain-text result."""
