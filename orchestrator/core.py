"""
Orchestrator — the brain of the assistant.

Conversational messages: load history, call Gemini with full context, and
(concurrently) extract any action items the user mentioned. Persist both
turns, store the extracted items, return the reply.

Commands (messages starting with '/'): handled directly, without the LLM, and
kept out of the conversation history — they are control, not conversation.
  /tasks       list open action items
  /done <id>   mark an action item complete
  /help        list commands

Future seams (not implemented):
  - Intent classification → act / ask / answer / stay-quiet
  - Tool dispatch: self._tools registry, looked up by intent
  - Pending-approval flow: tool wants to act → insert into pending_approvals,
            ask user to confirm, resume on approval
"""
import asyncio
import json
import logging
from datetime import datetime

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_FAST_MODEL
from db.conversations import get_recent, insert_turn
from db.action_items import insert_item, get_open, mark_done

logger = logging.getLogger(__name__)

# Structured-output schema for action-item extraction. Gemini is forced to
# return JSON matching this shape, so no brittle text parsing is needed.
_EXTRACTION_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "items": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "description": types.Schema(type=types.Type.STRING),
                    "due_at": types.Schema(type=types.Type.STRING, nullable=True),
                },
                required=["description"],
            ),
        ),
    },
    required=["items"],
)


class Orchestrator:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._client = genai.Client(api_key=GEMINI_API_KEY)

        # Tool registry — plug Tool instances in here later.
        # e.g. self._tools = {"gmail": GmailTool(), "news": NewsTool()}
        self._tools: dict = {}

    async def handle(self, user_id: str, message: str) -> str:
        logger.info("Orchestrator handling message from %s", user_id)

        # Commands are control, not conversation: handle them directly, with no
        # LLM call, and don't record them in the conversation history.
        if message.lstrip().startswith("/"):
            return self._handle_command(user_id, message)

        history = get_recent(self._db_path, user_id, limit=20)

        # --- Seam: intent classification goes here ---
        # intent = self._classify(message)  # act / ask / answer / stay-quiet

        # The reply and the action-item extraction are independent — the reply
        # needs the history, the extraction only needs this message — so run
        # them concurrently instead of paying for two serial round-trips.
        reply, items = await asyncio.gather(
            self._llm_reply(history, message),
            self._extract_action_items(message),
        )

        insert_turn(self._db_path, user_id, "user", message)
        insert_turn(self._db_path, user_id, "assistant", reply)

        for item in items:
            insert_item(self._db_path, user_id, item["description"], item["due_at"])
        if items:
            reply += self._format_capture(items)

        return reply

    # --- Commands -------------------------------------------------------

    def _handle_command(self, user_id: str, message: str) -> str:
        parts = message.strip().split()
        # Telegram may append "@botname" to commands in group chats — strip it.
        cmd = parts[0].split("@")[0].lstrip("/").lower()
        args = parts[1:]

        if cmd == "tasks":
            return self._cmd_tasks(user_id)
        if cmd == "done":
            return self._cmd_done(user_id, args)
        if cmd in ("help", "start"):
            return self._cmd_help()
        return f"Unknown command /{cmd}.\n{self._cmd_help()}"

    def _cmd_tasks(self, user_id: str) -> str:
        items = get_open(self._db_path, user_id)
        if not items:
            return "✅ No open tasks."
        lines = ["📋 Open tasks:"]
        for it in items:
            due = f" (due {it['due_at']})" if it["due_at"] else ""
            lines.append(f"[{it['id']}] {it['description']}{due}")
        lines.append("\nReply /done <id> to mark one complete.")
        return "\n".join(lines)

    def _cmd_done(self, user_id: str, args: list) -> str:
        if not args or not args[0].isdigit():
            return "Usage: /done <id>  (the number in brackets shown by /tasks)"
        item_id = int(args[0])
        if mark_done(self._db_path, user_id, item_id):
            return f"✅ Marked task [{item_id}] done."
        return f"No open task with id {item_id}."

    def _cmd_help(self) -> str:
        return (
            "Commands:\n"
            "/tasks — list open tasks\n"
            "/done <id> — mark a task complete"
        )

    # --- LLM calls ------------------------------------------------------

    async def _llm_reply(self, history: list, message: str) -> str:
        contents = []
        for turn in history:
            # Gemini uses "model" where the DB stores "assistant"
            role = "model" if turn["role"] == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

        response = await self._client.aio.models.generate_content(
            model=GEMINI_FAST_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are a concise personal assistant. "
                    "Reply helpfully and briefly."
                ),
            ),
        )
        return response.text

    async def _extract_action_items(self, message: str) -> list:
        """Best-effort: pull explicit tasks/reminders out of a user message.

        Extraction must never break the conversational reply, so any failure
        (API error, malformed JSON) is swallowed and treated as "no items".
        """
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            response = await self._client.aio.models.generate_content(
                model=GEMINI_FAST_MODEL,
                contents=[types.Content(role="user", parts=[types.Part(text=message)])],
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "Extract explicit tasks, reminders, or to-dos that the user "
                        "wants to remember from their message. Capture only genuine "
                        "action items the user is committing to or asking to track — "
                        "not questions, opinions, or small talk. If the user gives a "
                        f"deadline, set due_at to an ISO 8601 date (today is {today}); "
                        "otherwise leave due_at null. If there are no action items, "
                        "return an empty list."
                    ),
                    response_mime_type="application/json",
                    response_schema=_EXTRACTION_SCHEMA,
                ),
            )
            data = json.loads(response.text)
            raw = data.get("items", []) if isinstance(data, dict) else []
            return [
                {
                    "description": item["description"].strip(),
                    "due_at": (item.get("due_at") or None),
                }
                for item in raw
                if isinstance(item, dict) and item.get("description", "").strip()
            ]
        except Exception:
            logger.exception("Action-item extraction failed; continuing without")
            return []

    def _format_capture(self, items: list) -> str:
        """A short acknowledgment appended to the reply when tasks are captured."""
        if len(items) == 1:
            return f"\n\n📝 Noted: {items[0]['description']}"
        bullets = "\n".join(f"• {item['description']}" for item in items)
        return f"\n\n📝 Noted {len(items)} tasks:\n{bullets}"
