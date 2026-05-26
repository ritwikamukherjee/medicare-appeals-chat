# Data stage

Two files:

- `generate_synthetic.py` — Faker-based generator. Produces 9 parquet files. Run from a notebook or DAB job (see `scripts/notebook_generate_data.py`).
- `pipeline.py` — Lakeflow Declarative Pipeline. Auto Loader streams the parquet files into Delta tables, builds metric views + the `state_eligibility_corroboration` materialized view.

Tables produced (bronze):

| Table | Rows | Notes |
|---|---|---|
| `members` | 5,000 | Demographic, plan, state |
| `providers` | 500 | NPI, specialty, taxonomy |
| `eligibility` | 5,000 | One row per member |
| `prior_authorizations` | 15,000 | ~72% approval rate |
| `claims` | 50,000 | ~18% denial rate |
| `appeals` | 8,000 | Subset of denied claims, ~42% overturn rate |
| `salesforce_cases` | 2,000 | PCI/CIR/GA/PA Appeal types |
| `fraud_reference` | 300 | Suspected fraud lookups |
| `cms_drug_spending` | 1,500 | CMS Part D spending by brand × period |
| `wa_hca_eligibility_raw` | 4,500 | Streaming Auto Loader source |

Gold (metric views + MV):
- `appeals_metrics`, `claim_denials_metrics`, `provider_risk_metrics`, `glp1_utilization_metrics`
- `pbi_appeals_metrics`, `pbi_claims_metrics` (flat views for PowerBI)
- `state_eligibility_corroboration` (materialized view — WA HCA state corroboration)

Seed is fixed at 42 so the same data lands every time.
