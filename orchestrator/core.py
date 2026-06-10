"""
Orchestrator — the brain of the assistant.

Today: receives a message, forwards it to Gemini, returns the reply.

Future seams (not implemented):
  - Intent classification → act / ask / answer / stay-quiet
  - Tool dispatch: self._tools registry, looked up by intent
  - Memory: read recent conversation rows from DB before each call;
            write both turns back afterwards
  - Pending-approval flow: tool wants to act → insert into pending_approvals,
            ask user to confirm, resume on approval
"""
import logging
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_FAST_MODEL

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path  # reserved for memory/history queries later
        self._client = genai.Client(api_key=GEMINI_API_KEY)

        # Tool registry — plug Tool instances in here later.
        # e.g. self._tools = {"gmail": GmailTool(), "news": NewsTool()}
        self._tools: dict = {}

    async def handle(self, user_id: str, message: str) -> str:
        """
        Entry point for every inbound message.

        Today: single-turn Gemini call with no memory or tool use.
        """
        logger.info("Orchestrator handling message from %s", user_id)

        # --- Seam: load conversation history from DB here ---
        # history = db.get_recent(user_id, limit=20)

        # --- Seam: intent classification goes here ---
        # intent = self._classify(message)  # act / ask / answer / stay-quiet

        reply = await self._llm_reply(message)

        # --- Seam: persist both turns to conversations table here ---
        # db.insert(user_id, "user", message)
        # db.insert(user_id, "assistant", reply)

        return reply

    async def _llm_reply(self, message: str) -> str:
        response = self._client.models.generate_content(
            model=GEMINI_FAST_MODEL,
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are a concise personal assistant. "
                    "Reply helpfully and briefly."
                ),
            ),
        )
        return response.text
