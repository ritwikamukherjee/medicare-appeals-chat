"""Create the Claims Ops Genie space and attach the appeals data tables.

The Genie REST API only exposes a subset of the curation surface (instructions and certified
queries are UI-only). This script handles what's automatable; the rest is documented in
genie/curation_steps.md so you can finish manually after the bundle deploy.

Env vars:
  DATABRICKS_HOST              workspace host
  DATABRICKS_TOKEN or profile  auth
  CATALOG                      UC catalog name
  SCHEMA                       UC schema name
  WAREHOUSE_ID                 SQL warehouse the Genie space will use
"""

from __future__ import annotations

import json
import os
import sys

import requests
from databricks.sdk import WorkspaceClient

GENIE_TITLE = os.environ.get("GENIE_TITLE", "Claims Ops Genie")
CATALOG = os.environ.get("CATALOG", "medicare_appeals_demo")
SCHEMA = os.environ.get("SCHEMA", "appeals_review")
WAREHOUSE_ID = os.environ["WAREHOUSE_ID"]

ATTACHED_TABLES = [
    "appeals",
    "claims",
    "prior_authorizations",
    "members",
    "providers",
    "eligibility",
    "salesforce_cases",
    "fraud_reference",
    "state_eligibility_corroboration",
    "appeals_metrics",
    "claim_denials_metrics",
    "provider_risk_metrics",
    "pbi_appeals_metrics",
    "pbi_claims_metrics",
]

DESCRIPTION = (
    "Explore Molina-style claims operations data: denials, appeals, prior authorizations, "
    "eligibility, Salesforce PCI/CIR cases, fraud signals, and WA HCA state file corroboration. "
    "Used by the Medicare Appeals Triage supervisor."
)


def main() -> None:
    w = WorkspaceClient()
    headers = w.config.authenticate()
    headers["Content-Type"] = "application/json"
    host = w.config.host

    payload = {
        "title": GENIE_TITLE,
        "description": DESCRIPTION,
        "warehouse_id": WAREHOUSE_ID,
        "table_identifiers": [f"{CATALOG}.{SCHEMA}.{t}" for t in ATTACHED_TABLES],
    }

    r = requests.post(
        f"{host}/api/2.0/genie/spaces",
        headers=headers,
        json=payload,
        timeout=60,
    )
    if r.status_code >= 400:
        print(f"Genie create failed HTTP {r.status_code}: {r.text}", file=sys.stderr)
        r.raise_for_status()

    body = r.json()
    space_id = body.get("space_id") or body.get("id")
    print(json.dumps({
        "space_id": space_id,
        "title": GENIE_TITLE,
        "tables_attached": len(ATTACHED_TABLES),
        "warehouse_id": WAREHOUSE_ID,
        "ui_url": f"{host}/genie/rooms/{space_id}",
    }, indent=2))


if __name__ == "__main__":
    main()
