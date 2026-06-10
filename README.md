# moghe

A messaging-first personal assistant — inspired by poke, made personal.
Interact over Telegram. Powered by Google Gemini.

---

## Setup

### 1. Prerequisites

- Python 3.11+
- A Telegram bot token — create one via [@BotFather](https://t.me/BotFather) on Telegram
- A Google Gemini API key — from [Google AI Studio](https://aistudio.google.com)
- Your personal Telegram chat ID — message [@userinfobot](https://t.me/userinfobot)

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure secrets

```bash
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, and ALLOWED_CHAT_ID
```

### 4. Initialise the database (optional — main.py does this automatically)

```bash
python -m db.init_db
```

### 5. Run

```bash
python main.py
```

Send any message to your bot on Telegram. It will echo your message through Gemini and reply.

---

## Architecture

```
main.py
  ├── db.init_db          — creates SQLite DB and tables (idempotent)
  ├── Orchestrator        — the brain; owns the LLM client and tool registry
  └── TelegramChannel     — long-polling gateway; auth-gates on ALLOWED_CHAT_ID
```

### Layer map

| Layer | Location | Today | Future |
|---|---|---|---|
| **Gateway** | `gateway/` | Telegram long-polling | Swap for Slack, SMS, web |
| **Orchestrator** | `orchestrator/core.py` | Single-turn Gemini call | Intent routing, memory, tool dispatch |
| **Tools** | `tools/` | Stubs | Gmail, news, watchlist |
| **Scheduler** | `scheduler/core.py` | Stub | Morning digest, price alerts |
| **DB** | `db/` | Tables created | Conversation history, action items, approvals |

### Channel swap seam

`gateway/base.py` defines a two-method `Channel` ABC (`send`, `run`).
`main.py` constructs the concrete channel and passes it the orchestrator.
Swapping the channel never touches orchestrator code.

### Orchestrator intent seam

`Orchestrator.handle()` has labelled comment blocks for:
- loading conversation history from SQLite
- intent classification (act / ask / answer / stay-quiet)
- tool dispatch via `self._tools` registry
- persisting both turns back to the DB

### Tool plug-in seam

`tools/base.py` defines `Tool(ABC)` with `name`, `description`, and `run(**kwargs)`.
Register instances in `Orchestrator.__init__` under `self._tools`.

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | — | From @BotFather |
| `GEMINI_API_KEY` | yes | — | From Google AI Studio |
| `ALLOWED_CHAT_ID` | yes | — | Your personal Telegram chat ID |
| `GEMINI_FAST_MODEL` | no | `gemini-2.5-flash-lite-preview-06-17` | Routing / conversational calls |
| `GEMINI_STRONG_MODEL` | no | `gemini-2.5-pro` | Reserved for digests |
| `DB_PATH` | no | `data/assistant.db` | SQLite file path |

---

## Day-by-day plan

- **Day 1 (today)** — Scaffold: echo through Gemini works end-to-end
- **Day 2** — Conversation memory: read/write `conversations` table; multi-turn context
- **Day 3** — Action items: extraction, storage, listing via Telegram command
- **Day 4** — Gmail connector: OAuth, unread summary on demand
- **Day 5** — Scheduler: morning digest combining news + Gmail + action items
