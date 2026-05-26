# Genie stage

`create_genie_space.py` POSTs to `/api/2.0/genie/spaces` to create the Claims Ops Genie space and attach the 14 tables/views the supervisor needs.

`sample_questions.yaml` has the sample questions + curation instructions. The REST endpoints for `/instructions` and `/certified-queries` are UI-only at time of writing, so the bootstrap script seeds the space and prints its URL; you complete curation in the UI.

Attached tables:
- `appeals`, `claims`, `prior_authorizations`, `members`, `providers`, `eligibility`, `salesforce_cases`, `fraud_reference`
- `state_eligibility_corroboration` (MV)
- `appeals_metrics`, `claim_denials_metrics`, `provider_risk_metrics`
- `pbi_appeals_metrics`, `pbi_claims_metrics`
