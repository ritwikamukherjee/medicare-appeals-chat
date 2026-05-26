"""Create the Medicare Appeals Multi-Agent Supervisor.

Wires together:
  - 1 Genie worker (the Claims Ops Genie space)
  - 2 UC function workers (member_appeal_brief, claim_investigation_summary)
  - 3 external MCP server workers (PubMed, Medicare Part D, ClinicalTrials.gov)

Usage (env vars override defaults; bootstrap job sets all of them):
  DATABRICKS_HOST              (workspace host)
  DATABRICKS_TOKEN or profile  (CLI / SDK auth)
  CATALOG                      UC catalog name
  SCHEMA                       UC schema name (UC funcs live here)
  GENIE_SPACE_ID               Genie space ID (created by genie/create_genie_space.py)
  MAS_NAME                     Name for the MAS (default: medicare-appeals-supervisor)
"""

from __future__ import annotations

import json
import os
import sys

import requests
from databricks.sdk import WorkspaceClient

MAS_NAME = os.environ.get("MAS_NAME", "medicare-appeals-supervisor")
CATALOG = os.environ.get("CATALOG", "medicare_appeals_demo")
SCHEMA = os.environ.get("SCHEMA", "appeals_review")
GENIE_SPACE_ID = os.environ["GENIE_SPACE_ID"]


def _agents(catalog: str, schema: str, genie_space_id: str) -> list[dict]:
    return [
        {
            "name": "appeals_data_worker",
            "agent_type": "genie-space",
            "description": (
                "Queries Molina's internal claims and appeals data via the Claims Ops Genie space. "
                "Use for any question about specific claims, members, denial reasons, appeals statuses, "
                "eligibility, state corroboration, or aggregate counts and trends from claims data."
            ),
            "genie_space": {"id": genie_space_id},
        },
        {
            "name": f"ucf-{catalog}-{schema}-member_appeal_brief",
            "agent_type": "unity-catalog-function",
            "description": (
                "Generate a comprehensive appeal brief for a member including demographics, eligibility, "
                "claims history, denials, appeals, and prior authorization status."
            ),
            "unity_catalog_function": {
                "uc_path": {"catalog": catalog, "schema": schema, "name": "member_appeal_brief"}
            },
        },
        {
            "name": f"ucf-{catalog}-{schema}-claim_investigation_summary",
            "agent_type": "unity-catalog-function",
            "description": (
                "Generate a full investigation dossier for a single claim including claim details, member info, "
                "provider info, prior auth status, appeal history, and provider peer comparison."
            ),
            "unity_catalog_function": {
                "uc_path": {"catalog": catalog, "schema": schema, "name": "claim_investigation_summary"}
            },
        },
        {
            "name": "conn-conn_aichemy_pubmed",
            "agent_type": "external-mcp-server",
            "description": "PubMed MCP server (openpharma on glama.ai) for peer-reviewed clinical evidence",
            "external_mcp_server": {"connection_name": "conn_aichemy_pubmed"},
        },
        {
            "name": "conn-raven_medicare_mcp",
            "agent_type": "external-mcp-server",
            "description": "Medicare Part D MCP server for drug lookups (NDC, spending, prescribers)",
            "external_mcp_server": {"connection_name": "raven_medicare_mcp"},
        },
        {
            "name": "conn-conn_clinicaltrials",
            "agent_type": "external-mcp-server",
            "description": "ClinicalTrials.gov MCP server (auth.mode=none; placeholder token)",
            "external_mcp_server": {"connection_name": "conn_clinicaltrials"},
        },
    ]


INSTRUCTIONS = """You are the Medicare Appeals Triage supervisor. You help case workers resolve cases about claim denials, appeals, eligibility, and member benefits.

Your tools:

1. appeals_data_worker (Genie) - Aggregate/population-level questions about internal claims and appeals data: counts, trends, top denial reasons, eligibility distributions, state-by-state breakdowns.
2. ucf-...-member_appeal_brief - Per-member brief: demographics, eligibility, claims history, denials, appeals, prior auth status. Use when the user wants a member-level summary.
3. ucf-...-claim_investigation_summary - Per-claim investigation dossier: claim details, member, provider, prior auth, appeal history, provider peer comparison. Use when the user wants a claim-level dossier.
4. conn-conn_aichemy_pubmed (PubMed MCP) - Peer-reviewed clinical evidence for medical-necessity appeals.
5. conn-raven_medicare_mcp (Medicare Part D MCP) - Drug coverage, NDC lookups, prescriber, formulary, and spending questions.
6. conn-conn_clinicaltrials (ClinicalTrials.gov MCP) - Clinical-trial and treatment-evidence questions.

Routing rules:
- 'How many...', 'trends...', 'top denials...', 'distributions...' -> appeals_data_worker.
- 'Brief on member X', 'summarize this member' -> member_appeal_brief.
- 'Investigate claim X', 'why was claim Y denied' -> claim_investigation_summary.
- 'PubMed evidence for...', medical-necessity evidence -> conn-conn_aichemy_pubmed.
- 'Is drug X covered under Part D' -> conn-raven_medicare_mcp.
- 'Active clinical trials for...' -> conn-conn_clinicaltrials.
- Complex cases may need multiple tools - call them in sequence then synthesize one answer.

Style: professional, empathetic, healthcare-appropriate. Reference claim IDs, member IDs, dates, and appeals statuses verbatim. Be concise."""


def create_or_update_mas() -> dict:
    w = WorkspaceClient()
    headers = w.config.authenticate()
    headers["Content-Type"] = "application/json"
    host = w.config.host

    payload = {
        "name": MAS_NAME,
        "description": (
            "Medicare Appeals Triage supervisor. Routes case-worker questions about claim denials, "
            "appeals, eligibility, member benefits, and clinical evidence to the right Genie space, "
            "UC function, or MCP server."
        ),
        "instructions": INSTRUCTIONS,
        "agents": _agents(CATALOG, SCHEMA, GENIE_SPACE_ID),
    }

    # Check whether a MAS by this name already exists
    list_resp = requests.get(
        f"{host}/api/2.0/tiles", headers=headers, timeout=30
    )
    list_resp.raise_for_status()
    tiles = list_resp.json().get("tiles", [])
    existing = next((t for t in tiles if t.get("tile_type") == "MAS" and t.get("name") == MAS_NAME), None)

    if existing:
        tile_id = existing["tile_id"]
        print(f"Updating existing MAS '{MAS_NAME}' (tile_id={tile_id})")
        payload["tile_id"] = tile_id
        r = requests.patch(
            f"{host}/api/2.0/multi-agent-supervisors/{tile_id}",
            headers=headers, json=payload, timeout=60,
        )
    else:
        print(f"Creating new MAS '{MAS_NAME}'")
        r = requests.post(
            f"{host}/api/2.0/multi-agent-supervisors",
            headers=headers, json=payload, timeout=60,
        )

    if r.status_code >= 400:
        print(f"HTTP {r.status_code}: {r.text}", file=sys.stderr)
        r.raise_for_status()

    result = r.json()
    mas = result.get("multi_agent_supervisor", {})
    tile = mas.get("tile", {})
    print(json.dumps(
        {
            "tile_id": tile.get("tile_id"),
            "serving_endpoint_name": tile.get("serving_endpoint_name"),
            "agents_count": len(mas.get("agents", [])),
            "mlflow_experiment_id": tile.get("mlflow_experiment_id"),
        },
        indent=2,
    ))
    return result


if __name__ == "__main__":
    create_or_update_mas()
