"""GET /api/summary — Molina Claims Ops dashboard data (KPIs, cases, state corroboration, trends)."""

import asyncio
import logging
import os

import aiohttp
from fastapi import APIRouter, HTTPException

from server.config import get_serving_credentials

logger = logging.getLogger(__name__)
router = APIRouter()

WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "")
CATALOG = os.environ.get("CATALOG", "medicare_appeals_demo")
SCHEMA_NAME = os.environ.get("SCHEMA", "appeals_review")
# Backtick both to tolerate dashes or reserved words in either identifier.
SCHEMA = f"`{CATALOG}`.`{SCHEMA_NAME}`"
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")

QUERIES = {
    "kpis": f"""
        SELECT
          (SELECT COUNT(*) FROM {SCHEMA}.salesforce_cases WHERE status IN ('Open','In Progress')) AS open_cases,
          (SELECT COUNT(*) FROM {SCHEMA}.claims WHERE status='Denied' AND (denial_category='Eligibility' OR denial_reason LIKE '%not active%')) AS eligibility_denials,
          (SELECT COUNT(*) FROM {SCHEMA}.state_eligibility_corroboration WHERE corroboration_status LIKE 'discrepancy%%' OR corroboration_status = 'missing_from_state') AS discrepancy_count,
          (SELECT COUNT(*) FROM {SCHEMA}.members WHERE state_member_id IS NOT NULL) AS wa_medicaid_members,
          (SELECT COUNT(*) FROM {SCHEMA}.claims) AS total_claims,
          (SELECT COUNT(*) FROM {SCHEMA}.claims WHERE status='Denied') AS denied_claims,
          (SELECT MAX(source_file_date) FROM {SCHEMA}.wa_hca_eligibility_raw) AS latest_state_file
    """,
    "incoming_cases": f"""
        SELECT case_id, case_type, status, state, lob, claim_id, member_id, denial_remit_code,
               provider_inquiry, priority, created_at
        FROM {SCHEMA}.salesforce_cases
        WHERE status IN ('Open','In Progress')
        ORDER BY
          CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,
          created_at DESC
        LIMIT 25
    """,
    "corroboration_breakdown": f"""
        SELECT corroboration_status, COUNT(*) AS c
        FROM {SCHEMA}.state_eligibility_corroboration
        GROUP BY corroboration_status
        ORDER BY c DESC
    """,
    "recent_state_drops": f"""
        SELECT source_file_date, COUNT(*) AS rows_ingested
        FROM {SCHEMA}.wa_hca_eligibility_raw
        GROUP BY source_file_date
        ORDER BY source_file_date DESC
        LIMIT 8
    """,
    "monthly_denials": f"""
        SELECT DATE_TRUNC('MONTH', service_date) AS month,
               COUNT(*) AS denial_count,
               SUM(CASE WHEN denial_category='Eligibility' THEN 1 ELSE 0 END) AS eligibility_denials
        FROM {SCHEMA}.claims
        WHERE status='Denied' AND service_date >= '2024-01-01'
        GROUP BY DATE_TRUNC('MONTH', service_date)
        ORDER BY month
    """,
    "denial_categories": f"""
        SELECT denial_category, COUNT(*) AS c
        FROM {SCHEMA}.claims
        WHERE status='Denied' AND denial_category IS NOT NULL
        GROUP BY denial_category
        ORDER BY c DESC
    """,
    "cases_by_state_lob": f"""
        SELECT state, lob, COUNT(*) AS case_count
        FROM {SCHEMA}.salesforce_cases
        WHERE status IN ('Open','In Progress')
        GROUP BY state, lob
        ORDER BY case_count DESC
    """,
    "discrepancies": f"""
        SELECT member_id, state_member_id, state, corroboration_status,
               internal_is_active, state_status,
               internal_coverage_end, state_coverage_end,
               latest_state_file_date
        FROM {SCHEMA}.state_eligibility_corroboration
        WHERE corroboration_status LIKE 'discrepancy%%' OR corroboration_status = 'missing_from_state'
        ORDER BY
          CASE corroboration_status
            WHEN 'discrepancy_internal_inactive_state_active' THEN 0
            WHEN 'discrepancy_internal_active_state_inactive' THEN 1
            WHEN 'missing_from_state' THEN 2
          END,
          member_id
    """,
}

_cache: dict[str, list[dict]] = {}


async def _run_one(session, host, headers, key, sql):
    url = f"{host}/api/2.0/sql/statements/"
    payload = {"statement": sql, "warehouse_id": WAREHOUSE_ID, "wait_timeout": "30s"}
    async with session.post(url, headers=headers, json=payload) as r:
        body = await r.json()
    if body.get("status", {}).get("state") != "SUCCEEDED":
        logger.warning(f"summary query {key} failed: {body.get('status')}")
        return key, []
    cols = [c["name"] for c in body["manifest"]["schema"]["columns"]]
    rows = body.get("result", {}).get("data_array", []) or []
    return key, [dict(zip(cols, row)) for row in rows]


@router.get("/summary")
async def summary() -> dict:
    if _cache:
        return {"dashboard_url": DASHBOARD_URL, **_cache}

    host, token = get_serving_credentials()
    if not host or not token:
        raise HTTPException(500, "Databricks credentials not available")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *[_run_one(session, host, headers, k, sql) for k, sql in QUERIES.items()]
        )
    out = {k: v for k, v in results}
    _cache.update(out)
    return {"dashboard_url": DASHBOARD_URL, **out}


@router.post("/summary/refresh")
async def refresh() -> dict:
    _cache.clear()
    return await summary()
