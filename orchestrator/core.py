"""
Orchestrator — the brain of the assistant.

Conversational messages: load history, then run a ReAct loop — call Gemini
with the registered tools, execute any function calls it requests, feed the
results back, and repeat until it produces a text answer. Concurrently (it
only needs the raw message) extract any action items. Persist both turns,
store the extracted items, return the reply.

Commands (messages starting with '/'): handled directly, without the LLM, and
kept out of the conversation history — they are control, not conversation.
  /tasks       list open action items
  /done <id>   mark an action item complete
  /help        list commands

Future seams (not implemented):
  - Intent classification → act / ask / answer / stay-quiet
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
from tools.tasks import TasksTool

logger = logging.getLogger(__name__)

# Cap on ReAct rounds, so a misbehaving model can't loop on tools forever.
_MAX_TOOL_ROUNDS = 5

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

_JSON_TYPE_TO_GEMINI = {
    "object": types.Type.OBJECT,
    "string": types.Type.STRING,
    "integer": types.Type.INTEGER,
    "number": types.Type.NUMBER,
    "boolean": types.Type.BOOLEAN,
    "array": types.Type.ARRAY,
}


def _to_gemini_schema(js: dict) -> types.Schema:
    """Translate a provider-agnostic JSON-Schema object into a genai Schema."""
    kwargs: dict = {}
    if "type" in js:
        kwargs["type"] = _JSON_TYPE_TO_GEMINI[js["type"]]
    if "description" in js:
        kwargs["description"] = js["description"]
    if "enum" in js:
        kwargs["enum"] = js["enum"]
    if "nullable" in js:
        kwargs["nullable"] = js["nullable"]
    if "properties" in js:
        kwargs["properties"] = {k: _to_gemini_schema(v) for k, v in js["properties"].items()}
    if "required" in js:
        kwargs["required"] = js["required"]
    if "items" in js:
        kwargs["items"] = _to_gemini_schema(js["items"])
    return types.Schema(**kwargs)


class Orchestrator:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._client = genai.Client(api_key=GEMINI_API_KEY)

        # Tool registry — only working tools are registered, so the model is
        # never offered a capability that would just error. Keyed by tool.name,
        # which is also the function-call name Gemini sends back.
        self._tools: dict = {t.name: t for t in (TasksTool(db_path),)}
        self._tool_decls = self._build_tool_declarations()

    def _build_tool_declarations(self):
        """One genai Tool wrapping a FunctionDeclaration per registered tool."""
        decls = [
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=_to_gemini_schema(tool.parameters) if tool.parameters else None,
            )
            for tool in self._tools.values()
        ]
        return [types.Tool(function_declarations=decls)] if decls else None

    async def handle(self, user_id: str, message: str) -> str:
        logger.info("Orchestrator handling message from %s", user_id)

        # Commands are control, not conversation: handle them directly, with no
        # LLM call, and don't record them in the conversation history.
        if message.lstrip().startswith("/"):
            return self._handle_command(user_id, message)

        history = get_recent(self._db_path, user_id, limit=20)

        # --- Seam: intent classification goes here ---
        # intent = self._classify(message)  # act / ask / answer / stay-quiet

        # The reply (which may run a multi-round tool loop) and the action-item
        # extraction are independent, so run them concurrently.
        reply, items = await asyncio.gather(
            self._llm_reply(user_id, history, message),
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

    # --- LLM: reply with a tool-use (ReAct) loop ------------------------

    async def _llm_reply(self, user_id: str, history: list, message: str) -> str:
        contents = []
        for turn in history:
            # Gemini uses "model" where the DB stores "assistant"
            role = "model" if turn["role"] == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

        config = types.GenerateContentConfig(
            system_instruction=(
                "You are a concise personal assistant. Reply helpfully and "
                "briefly. You can call tools to look things up (such as the "
                "user's open tasks); use them when relevant instead of guessing."
            ),
            tools=self._tool_decls,
            # Manual function calling — we run the loop ourselves so we can
            # inject user_id and handle tool errors.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        response = None
        for _ in range(_MAX_TOOL_ROUNDS):
            response = await self._client.aio.models.generate_content(
                model=GEMINI_FAST_MODEL, contents=contents, config=config
            )
            calls = response.function_calls or []
            if not calls:
                break

            # Append the model's function-call turn, then one user turn holding
            # a response part per call (mirrors the genai SDK's own AFC loop).
            contents.append(response.candidates[0].content)
            response_parts = [
                types.Part.from_function_response(
                    name=fc.name, response=await self._dispatch_tool(user_id, fc)
                )
                for fc in calls
            ]
            contents.append(types.Content(role="user", parts=response_parts))

        return (response.text if response else None) or (
            "Sorry, I couldn't complete that."
        )

    async def _dispatch_tool(self, user_id: str, fc) -> dict:
        """Run the requested tool; return a {'result'|'error': ...} dict."""
        tool = self._tools.get(fc.name)
        if tool is None:
            return {"error": f"unknown tool {fc.name}"}
        try:
            result = await tool.run(user_id=user_id, **dict(fc.args or {}))
            return {"result": result}
        except Exception:
            logger.exception("Tool %s failed", fc.name)
            return {"error": f"tool {fc.name} failed"}

    # --- LLM: action-item extraction ------------------------------------

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
