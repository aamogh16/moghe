"""
Orchestrator — the brain of the assistant.

Today: receives a message, loads conversation history, calls Gemini with
full context, persists both turns, returns the reply.

Future seams (not implemented):
  - Intent classification → act / ask / answer / stay-quiet
  - Tool dispatch: self._tools registry, looked up by intent
  - Pending-approval flow: tool wants to act → insert into pending_approvals,
            ask user to confirm, resume on approval
"""
import logging
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_FAST_MODEL
from db.conversations import get_recent, insert_turn

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._client = genai.Client(api_key=GEMINI_API_KEY)

        # Tool registry — plug Tool instances in here later.
        # e.g. self._tools = {"gmail": GmailTool(), "news": NewsTool()}
        self._tools: dict = {}

    async def handle(self, user_id: str, message: str) -> str:
        logger.info("Orchestrator handling message from %s", user_id)

        history = get_recent(self._db_path, user_id, limit=20)

        # --- Seam: intent classification goes here ---
        # intent = self._classify(message)  # act / ask / answer / stay-quiet

        reply = await self._llm_reply(history, message)

        insert_turn(self._db_path, user_id, "user", message)
        insert_turn(self._db_path, user_id, "assistant", reply)

        return reply

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
