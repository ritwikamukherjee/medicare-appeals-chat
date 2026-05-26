# Architecture

## Stages

```
+----------------+   +-------------+   +-------------------+   +---------------------+
| 1. Data        |   | 2. Genie    |   | 3. MAS (AB tile)  |   | 4. Chat App         |
|                |   |             |   |                   |   |                     |
| Faker/parquet  |-->| Claims Ops  |<--+ Supervisor LLM    |-->| FastAPI /api/chat   |
| + Lakeflow LDP |   | Genie space |   | + 6 workers:      |   | + React frontend    |
| + AutoLoader   |   | (15 tables) |   |   - Genie         |   |                     |
| + MV + Views   |   |             |   |   - 2 UC fns      |   |                     |
+----------------+   +-------------+   |   - 3 MCP servers |   +---------------------+
                                       +-------------------+
```

## Data flow (request time)

1. User asks a question in the React UI (Databricks App, OAuth'd).
2. Frontend POSTs to `/api/chat` (FastAPI in `app/server/routes/chat.py`).
3. FastAPI uses the App's service principal to call `mas-<id>-endpoint/invocations`.
4. The MAS supervisor LLM analyzes the question and emits either:
   - A `function_call` for a Genie / UC-function worker (handled in-tile)
   - An `mcp_approval_request` for an external MCP tool (chat.py auto-approves + loops up to 10 rounds)
5. Worker responses are folded back into the conversation; the supervisor synthesizes a final answer.
6. FastAPI extracts the final message + intermediate steps and returns to the frontend.

## Why this shape

- **MAS native > custom orchestration.** Agent Bricks MAS gives us prompt tuning, model routing across foundation models, worker-level evals, and a UI for non-engineers to edit instructions. A code-only orchestrator (LangChain, custom ResponsesAgent) gets none of that.
- **MCP servers attached at supervisor level**, not as wrapped endpoints, so `mcp_approval_request` round-tripping fires natively. Lets you swap auth modes, approval policies, and rate limits without touching code.
- **UC functions for "narrative" outputs.** `member_appeal_brief` and `claim_investigation_summary` are SQL functions that return formatted strings. The LLM treats them as deterministic "give me the dossier" tools. Same data the Genie space sees, just pre-aggregated for case-worker consumption.
- **Lakeflow Declarative Pipeline** keeps the data assets reproducible. Bronze (Auto Loader) → Silver (Delta) → Gold (metric views) all in one pipeline definition.
- **Streaming WA HCA file drops** + a materialized view (`state_eligibility_corroboration`) demonstrates the regulatory-corroboration pattern.

## Permissions

The bundle deploy creates a Databricks Apps service principal with:
- `CAN_QUERY` on the MAS serving endpoint
- `CAN_RUN` on the Genie space
- `USE_CONNECTION` on the 3 UC MCP connections

The MAS tile uses `EMBEDDED_CREDENTIALS` mode, so its own service principal needs:
- `USE_CATALOG` + `USE_SCHEMA` on the appeals schema
- `SELECT` on the tables the Genie space and UC functions touch
- `EXECUTE` on the two UC functions

If the MAS endpoint returns errors like `MessageStatus.FAILED` from the Genie tool, the embedded SP is the first thing to check.

## Known issues and how to debug

| Symptom | Probable cause | Fix |
|---|---|---|
| UC function calls time out (>60s) | Cold warehouse OR table missing | Warm the warehouse; verify tables exist with `SHOW TABLES IN <catalog>.<schema>` |
| `MessageStatus.FAILED` from Genie | Embedded SP missing SELECT or USE_SCHEMA | Grant on the schema + warehouse to the MAS SP |
| MCP tool 401/403 | Bearer token expired or wrong | Re-set via `ALTER CONNECTION <name> SET OPTIONS (bearer_token = 'NEW')` |
| App stuck in "Preparing source code" | Apps backend snapshot lag | Wait 10-15 min; tail with `databricks apps logs medicare-appeals-chat` |
| MAS endpoint not found | Tile created but endpoint not yet ready | Wait ~2-5 min after `create_or_update_mas`; check `serving-endpoints get` |
