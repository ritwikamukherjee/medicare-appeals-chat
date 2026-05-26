# MAS stage

Two scripts:

- `create_mcp_connections.sql` — DDL for the 3 external HTTP+BEARER UC connections (PubMed, Medicare Part D, ClinicalTrials.gov). The DAB substitutes the bearer tokens at deploy time.
- `create_mas.py` — POSTs to `/api/2.0/multi-agent-supervisors` to create or update the MAS with 6 workers:
  1. Genie worker (appeals data)
  2. UC function: `member_appeal_brief`
  3. UC function: `claim_investigation_summary`
  4. MCP server: PubMed
  5. MCP server: Medicare Part D
  6. MCP server: ClinicalTrials.gov

Routing instructions are baked into `INSTRUCTIONS` at the top of `create_mas.py`.

## Routing matrix

| Question shape | Routes to |
|---|---|
| "How many...", "trends...", "top denials..." | Genie worker |
| "Brief on member X" | `member_appeal_brief` UC fn |
| "Investigate claim Y" | `claim_investigation_summary` UC fn |
| "PubMed evidence for..." | PubMed MCP |
| "Is drug X covered under Part D" | Medicare Part D MCP |
| "Clinical trials for..." | ClinicalTrials.gov MCP |

## Updating the MAS

Edit `create_mas.py` (instructions, descriptions, or worker list) then rerun the script. It looks up the existing MAS by name and PATCHes instead of creating a duplicate.
