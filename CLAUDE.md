# moghe — Claude Code context

Personal Telegram assistant powered by Google Gemini. Single-user, messaging-first.
Built incrementally — through Day 3: conversation memory and action-item tracking
are live; tools and scheduler are still stubs.

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
| DB schema | `db/schema.sql`, `db/init_db.py` | Tables created |
| DB access | `db/conversations.py`, `db/action_items.py` | `conversations` + `action_items` read/written |
| Gateway | `gateway/base.py`, `gateway/telegram.py` | Working; forwards commands to orchestrator |
| Orchestrator | `orchestrator/core.py` | Memory + extraction + `/`-commands + tool-use loop |
| Tools | `tools/base.py`, `tools/tasks.py` | `TasksTool` live and registered |
| Tools (stubs) | `tools/{gmail,news,watchlist}.py` | Stubs — `NotImplementedError`; not registered |
| Scheduler | `scheduler/core.py` | Stub — `NotImplementedError` |

### Working end-to-end paths

```
# Conversation (memory + tool-use loop + action-item capture)
Telegram message → auth gate → Orchestrator.handle()
    ├── load last 20 turns from conversations
    ├── gather(                                                  # concurrent
    │     reply  = ReAct loop: Gemini ⇄ tools until a text answer ,
    │     items  = Gemini action-item extraction )
    ├── persist both turns; store extracted items
    └── reply (+ "📝 Noted: …" when tasks were captured)

# ReAct loop (inside the reply branch, manual function calling)
generate_content(contents, tools) → if function_calls: run each tool,
append the model turn + a user turn of function responses, repeat
(capped at _MAX_TOOL_ROUNDS) → else return the text.

# Command (no LLM, not recorded in history)
Telegram "/tasks" or "/done <id>" → Orchestrator.handle() → direct DB read/write → reply
```

### Key seams (where future features plug in)

**Swap the channel** — `gateway/base.py` defines `Channel(ABC)` with `send()` and `run()`.
`main.py` constructs `TelegramChannel` and nothing else imports it. Replace with any
`Channel` subclass (Slack, SMS, web) without touching the orchestrator.

**Add tools** — subclass `tools/base.py::Tool`: set `name` (also the
function-call name), `description`, an optional `parameters` JSON-Schema dict,
and implement `async run(user_id, **kwargs) -> str` (`user_id` is injected by
the orchestrator, never model-chosen). Register the instance in
`Orchestrator.__init__`'s `self._tools`; the ReAct loop builds the Gemini
`FunctionDeclaration` (via `_to_gemini_schema`) and dispatches automatically.
Only register working tools — the model is never offered a stub. `TasksTool`
(`tools/tasks.py`) is the reference example.

**Add commands** — any message starting with `/` is routed by
`Orchestrator._handle_command()` (no LLM, not stored in history). Add a branch
there and a `_cmd_*` helper. The gateway forwards commands like any other text,
so new channels inherit them for free.

**Add scheduling** — `scheduler/core.py::Scheduler` is stubbed. Wire it into `main.py`
alongside `channel.run()` using `asyncio.gather`.

**Add approvals** — `pending_approvals` table exists. Before any consequential tool
action, insert a row and ask the user to confirm; resume on approval message.

### Intended evolution

1. ~~**Memory** — pass recent `conversations` rows as context to every Gemini call~~ ✅ Day 2
2. ~~**Action items** — extract and store tasks; `/tasks` command to list them~~ ✅ Day 3
   (`/done <id>` completes one; extraction runs concurrently with the reply on every turn)
3. ~~**Tool use loop** — Gemini native function calling; ReAct loop in `Orchestrator.handle()`~~ ✅ Day 4
   (manual function calling, `_MAX_TOOL_ROUNDS` cap; `TasksTool` is the first registered tool)
4. **Gmail connector** — OAuth + read/summarise unread ← next
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
