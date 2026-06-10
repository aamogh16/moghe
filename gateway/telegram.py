"""
Telegram channel — long-polling implementation of Channel.

Responsibilities:
  - Receive updates from Telegram
  - Gate on ALLOWED_CHAT_ID (silently drop everything else)
  - Hand the text to the orchestrator
  - Send the orchestrator's reply back
"""
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from gateway.base import Channel
from config import TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_ID

logger = logging.getLogger(__name__)


class TelegramChannel(Channel):
    def __init__(self, orchestrator) -> None:
        # orchestrator.handle(user_id, text) -> str
        self._orchestrator = orchestrator
        self._app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message)
        )

    async def send(self, chat_id: int | str, text: str) -> None:
        await self._app.bot.send_message(chat_id=chat_id, text=text)

    async def run(self) -> None:
        logger.info("Telegram long-polling started")
        await self._app.run_polling()

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id

        # Auth gate — silently ignore anyone who isn't us.
        if chat_id != ALLOWED_CHAT_ID:
            logger.warning("Ignoring message from unknown chat_id=%s", chat_id)
            return

        user_text = update.message.text
        logger.info("Received message from %s: %r", chat_id, user_text)

        reply = await self._orchestrator.handle(str(chat_id), user_text)
        await self.send(chat_id, reply)
