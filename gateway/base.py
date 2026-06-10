"""
Channel interface — the swap seam between the orchestrator and any messaging platform.

To add a new channel (Slack, SMS, web, …):
  1. Subclass Channel
  2. Implement send() and run()
  3. Swap it into main.py — the orchestrator never imports gateway directly
"""
from abc import ABC, abstractmethod


class Channel(ABC):
    @abstractmethod
    async def send(self, chat_id: int | str, text: str) -> None:
        """Deliver text to the user identified by chat_id."""

    @abstractmethod
    async def run(self) -> None:
        """Start listening for inbound messages (blocking)."""
