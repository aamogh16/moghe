# moghe — Claude Code context

Personal Telegram assistant powered by Google Gemini. Single-user, messaging-first.
Built incrementally — Day 1 scaffold is the current state.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in the three required values
python main.py
```

Required `.env` values: `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID`.

## Architecture

```
main.py
  ├── db.init_db          idempotent — creates data/assistant.db and tables
  ├── Orchestrator        the brain; owns LLM client and tool registry
  └── TelegramChannel     long-poll gateway; auth-gates on ALLOWED_CHAT_ID
```

### Layers and their files

| Layer | Files | State |
|---|---|---|
| Config | `config.py` | Done |
| DB schema | `db/schema.sql`, `db/init_db.py` | Tables created; not yet read/written |
| Gateway | `gateway/base.py`, `gateway/telegram.py` | Working |
| Orchestrator | `orchestrator/core.py` | Single-turn Gemini call; seams commented |
| Tools | `tools/base.py`, `tools/{gmail,news,watchlist}.py` | Stubs — `NotImplementedError` |
| Scheduler | `scheduler/core.py` | Stub — `NotImplementedError` |

### The one working end-to-end path (Day 1)

```
Telegram message → auth gate → Orchestrator.handle() → Gemini API → reply
```

### Key seams (where future features plug in)

**Swap the channel** — `gateway/base.py` defines `Channel(ABC)` with `send()` and `run()`.
`main.py` constructs `TelegramChannel` and nothing else imports it. Replace with any
`Channel` subclass (Slack, SMS, web) without touching the orchestrator.

**Add tools** — subclass `tools/base.py::Tool`, implement `run(**kwargs) -> str`.
Register in `Orchestrator.__init__` under `self._tools`. The orchestrator will
dispatch to them once tool-use/ReAct loop is wired (Day N).

**Add memory** — `Orchestrator.handle()` has commented blocks marking exactly where
to read recent rows from `conversations` and write both turns back.

**Add scheduling** — `scheduler/core.py::Scheduler` is stubbed. Wire it into `main.py`
alongside `channel.run()` using `asyncio.gather`.

**Add approvals** — `pending_approvals` table exists. Before any consequential tool
action, insert a row and ask the user to confirm; resume on approval message.

### Intended evolution (not yet built)

1. **Memory** — pass recent `conversations` rows as context to every Gemini call
2. **Action items** — extract and store tasks; `/tasks` command to list them
3. **Tool use loop** — Gemini native function calling; ReAct loop in `Orchestrator.handle()`
4. **Gmail connector** — OAuth + read/summarise unread
5. **Scheduler** — morning digest: Gmail summary + news + open action items
6. **Watchlist** — price/event alerts pushed proactively via `Channel.send()`

## DB tables

| Table | Purpose |
|---|---|
| `conversations` | One row per message turn (`role`: user \| assistant) |
| `action_items` | Extracted tasks with status and optional due date |
| `pending_approvals` | Actions awaiting explicit user confirmation |

## Models

| Constant | Default | Use |
|---|---|---|
| `GEMINI_FAST_MODEL` | `gemini-2.5-flash-lite-preview-06-17` | All current calls |
| `GEMINI_STRONG_MODEL` | `gemini-2.5-pro` | Reserved for digests |

Both overridable via `.env`.

## Conventions

- No ORM — raw `sqlite3` with explicit SQL
- No framework for the orchestrator — plain `async def`, grow complexity inside `handle()` as needed
- One `Channel` in production — the `ALLOWED_CHAT_ID` gate is architectural, not a config detail
- Secrets only via `.env` / `config.py` — never hardcoded
