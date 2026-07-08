"""
Tasks tool — lets the LLM read the user's open action items mid-conversation.

This is read-only on purpose: task *capture* happens in the orchestrator's
extraction step, so a create-task tool here would double-insert. Completion
and the deterministic list live in the /tasks and /done commands; this tool
exists so the model can pull tasks into a natural-language answer, e.g.
"what's on my plate?" or "anything about the dentist?".
"""
from tools.base import Tool
from db.action_items import get_open


class TasksTool(Tool):
    name = "list_open_tasks"
    description = (
        "List the user's open to-do tasks / action items. Use this whenever the "
        "user asks what they need to do, what's on their list, or about their "
        "tasks or reminders. Optionally filter to tasks matching a keyword."
    )
    parameters = {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "Optional case-insensitive substring to filter task descriptions by.",
            }
        },
    }

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def run(self, user_id: str, keyword: str | None = None, **kwargs) -> str:
        items = get_open(self._db_path, user_id)
        if keyword:
            needle = keyword.lower()
            items = [it for it in items if needle in it["description"].lower()]

        if not items:
            return (
                f"No open tasks matching '{keyword}'."
                if keyword
                else "No open tasks."
            )

        lines = []
        for it in items:
            due = f" (due {it['due_at']})" if it["due_at"] else ""
            lines.append(f"- [{it['id']}] {it['description']}{due}")
        return "\n".join(lines)
