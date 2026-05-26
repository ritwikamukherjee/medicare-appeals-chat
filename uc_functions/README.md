# UC Functions

Two SQL functions registered in the appeals schema. Both are SECURITY DEFINER + READS_SQL_DATA + DETERMINISTIC so they're safe to expose to the MAS supervisor.

| Function | Args | Returns |
|---|---|---|
| `member_appeal_brief(member_id STRING)` | member_id | Multi-section brief: demographics, eligibility, claims totals, appeals + overturn rate, PA stats |
| `claim_investigation_summary(claim_id STRING)` | claim_id | Multi-section dossier: claim header, member, provider, PA link, appeal history, provider-vs-specialty denial-rate peer comparison |

Both follow the same pattern: WITH ctes joining base tables, then a single CONCAT-based string output the LLM can quote verbatim into its final answer. No procedural logic.

DDL is `${catalog}` / `${schema}` parameterized so the bundle deploy can target any catalog.
