"""
Gmail connector — read the user's unread mail so the assistant can summarise it.

Setup (one time):
  1. In Google Cloud Console, enable the Gmail API and create an OAuth 2.0
     Client ID of type "Desktop app". Download the client-secret JSON.
  2. Save it at GMAIL_CREDENTIALS_PATH (default: data/gmail_credentials.json).
  3. Authorize once, from a terminal on a machine with a browser:
         python -m tools.gmail
     A browser opens for consent; the resulting token (with refresh token) is
     cached at GMAIL_TOKEN_PATH (default: data/gmail_token.json).

After that the bot uses the cached token, refreshing it automatically, with no
further interaction. Both files live under data/, which is git-ignored — they
are secrets, so keep them out of version control.

Scope is read-only (gmail.readonly): the assistant can read and summarise mail,
never send or delete. Widen SCOPES below if that ever changes (delete the
cached token afterward so re-consent picks up the new scope).
"""
import asyncio
import logging
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
from tools.base import Tool

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def is_configured() -> bool:
    """True if a cached token exists (cheap file check — no network, no parse)."""
    return os.path.exists(GMAIL_TOKEN_PATH)


def _save_token(creds: Credentials) -> None:
    Path(GMAIL_TOKEN_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(GMAIL_TOKEN_PATH, "w") as fh:
        fh.write(creds.to_json())


def _load_credentials():
    """Load cached credentials, refreshing if expired. None if not authorized."""
    if not os.path.exists(GMAIL_TOKEN_PATH):
        return None
    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, SCOPES)
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
        return creds
    return None


def authorize() -> None:
    """Interactive first-time consent. Run from a terminal: python -m tools.gmail"""
    if not os.path.exists(GMAIL_CREDENTIALS_PATH):
        raise SystemExit(
            f"Missing OAuth client secret at {GMAIL_CREDENTIALS_PATH}.\n"
            "Download it from Google Cloud Console (Gmail API → Desktop app "
            "client) and save it there first."
        )
    flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    print(f"[gmail] authorized; token cached at {GMAIL_TOKEN_PATH}")


def _build_service():
    """Build an authenticated Gmail client, or None if not authorized yet."""
    creds = _load_credentials()
    if not creds:
        return None
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _fetch_unread(service, max_results: int) -> list:
    """Blocking: list unread messages with their key headers and snippet."""
    listing = (
        service.users()
        .messages()
        .list(userId="me", q="is:unread", maxResults=max_results)
        .execute()
    )
    messages = []
    for ref in listing.get("messages", []):
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=ref["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )
        headers = {
            h["name"]: h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }
        messages.append(
            {
                "from": headers.get("From", "(unknown sender)"),
                "subject": headers.get("Subject", "(no subject)"),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", ""),
            }
        )
    return messages


def _format_summary(messages: list) -> str:
    """Plain-text digest the model can relay or summarise further."""
    if not messages:
        return "No unread emails."
    lines = [f"You have {len(messages)} unread email(s):"]
    for m in messages:
        snippet = m["snippet"].strip()
        if len(snippet) > 140:
            snippet = snippet[:137] + "..."
        line = f"- From {m['from']} — {m['subject']}"
        if snippet:
            line += f"\n  {snippet}"
        lines.append(line)
    return "\n".join(lines)


class GmailTool(Tool):
    name = "check_unread_email"
    description = (
        "Read the user's unread Gmail messages (sender, subject, and a short "
        "snippet of each). Use when the user asks about their email, inbox, or "
        "whether they have new messages."
    )
    parameters = {
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "description": "Maximum number of unread messages to fetch (default 10).",
            }
        },
    }

    async def run(self, user_id: str = None, max_results: int = 10, **kwargs) -> str:
        try:
            max_results = max(1, min(int(max_results), 25))
        except (TypeError, ValueError):
            max_results = 10

        # googleapiclient is synchronous/blocking — keep it off the event loop.
        service = await asyncio.to_thread(_build_service)
        if service is None:
            return "Gmail isn't connected yet. Authorize with: python -m tools.gmail"
        try:
            messages = await asyncio.to_thread(_fetch_unread, service, max_results)
        except Exception:
            logger.exception("Gmail fetch failed")
            return "Sorry, I couldn't reach Gmail just now."
        return _format_summary(messages)


if __name__ == "__main__":
    authorize()
