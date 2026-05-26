"""Generate synthetic Medicare appeals data using Faker.

Produces 8 core tables sized for a small/medium demo:
  members (5,000)
  providers (500)
  eligibility (5,000 — one row per member)
  prior_authorizations (15,000)
  claims (50,000)
  appeals (8,000 — subset of denied claims that were appealed)
  salesforce_cases (2,000)
  fraud_reference (300)
  cms_drug_spending (1,500)
  wa_hca_eligibility_raw (4,500 — used as Auto Loader source for state_eligibility_corroboration MV)

Run via Databricks Connect or inside a notebook. Writes parquet files to a UC volume that the
Lakeflow Declarative Pipeline then ingests via Auto Loader.
"""

from __future__ import annotations

import argparse
import logging
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

logger = logging.getLogger(__name__)
fake = Faker("en_US")
Faker.seed(42)
random.seed(42)

STATES = ["WA", "CA", "TX", "MS", "MI", "UT", "NM", "FL", "ID", "OH"]
PLAN_TYPES = ["Medicare Advantage HMO", "Medicare Advantage PPO", "Medicaid Managed Care", "Dual Special Needs"]
PROVIDER_TYPES = ["Individual", "Group", "Hospital", "ASC", "Lab", "DME", "Pharmacy"]
SPECIALTIES = [
    "Internal Medicine", "Cardiology", "Endocrinology", "Oncology", "Family Medicine",
    "Orthopedics", "Radiology", "Behavioral Health", "Nephrology", "Ophthalmology",
]
SERVICE_TYPES = ["Office Visit", "Surgery", "Imaging", "Lab", "DME", "Pharmacy", "ER", "Inpatient", "Outpatient"]
CPT_CODES = ["99213", "99214", "99203", "93000", "73721", "27447", "70551", "80053", "G0438", "J0696"]
HCPCS_CODES = ["E0601", "E0143", "K0001", "A4253", "L3260", "J3490", "J0696", "J1885"]
NDC_CODES = ["00378-3853-93", "00591-2238-30", "00093-1058-01", "00069-2587-30", "00006-0277-31"]
DIAGNOSIS_CODES = ["E11.9", "I10", "J45.40", "M54.5", "Z00.00", "F32.9", "N18.3", "I50.32", "K21.9", "H40.11"]
DENIAL_REASONS = [
    ("PAR_001", "Prior auth required", "Authorization"),
    ("MED_002", "Not medically necessary", "Medical Necessity"),
    ("ELG_003", "Member not eligible on DOS", "Eligibility"),
    ("COD_004", "Invalid CPT/diagnosis pairing", "Coding"),
    ("DUP_005", "Duplicate claim", "Duplicate"),
    ("TIM_006", "Timely filing exceeded", "Administrative"),
    ("BEN_007", "Service not covered under plan", "Benefit"),
    ("PRV_008", "Provider not in network", "Network"),
]
APPEAL_STATUSES = ["Submitted", "Under Review", "Overturned", "Upheld", "Closed"]


def _member_id(i: int) -> str:
    return f"MEM-{i:06d}"


def _provider_id(i: int) -> str:
    return f"PRV-{i:05d}"


def _claim_id(i: int) -> str:
    return f"CLM-{i:08d}"


def _appeal_id(i: int) -> str:
    return f"APL-{i:07d}"


def _pa_id(i: int) -> str:
    return f"PA-{i:07d}"


def gen_members(n: int = 5_000) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({
            "member_id": _member_id(i),
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=95),
            "gender": random.choice(["M", "F"]),
            "ssn": fake.ssn(),
            "address": fake.street_address(),
            "city": fake.city(),
            "state": random.choices(STATES, weights=[40, 8, 8, 6, 5, 5, 5, 5, 4, 14], k=1)[0],
            "zip_code": fake.zipcode(),
            "phone": fake.phone_number(),
            "email": fake.email(),
            "plan_type": random.choice(PLAN_TYPES),
            "state_member_id": fake.bothify("##########") if random.random() < 0.6 else None,
            "created_at": fake.date_time_between(start_date="-3y", end_date="now"),
            "updated_at": datetime.utcnow(),
        })
    return pd.DataFrame(rows)


def gen_providers(n: int = 500) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({
            "provider_id": _provider_id(i),
            "npi": fake.bothify("##########"),
            "name": fake.company(),
            "type": random.choice(PROVIDER_TYPES),
            "specialty": random.choice(SPECIALTIES),
            "address": fake.street_address(),
            "city": fake.city(),
            "state": random.choice(STATES),
            "zip_code": fake.zipcode(),
            "phone": fake.phone_number(),
            "email": fake.company_email(),
            "taxonomy_code": fake.bothify("########X"),
            "medicaid_id": fake.bothify("########") if random.random() < 0.8 else None,
            "enrollment_state": random.choice(STATES),
            "enrollment_effective_date": fake.date_between(start_date="-10y", end_date="-1y"),
            "enrollment_status": random.choice(["Active", "Pending", "Terminated"]),
            "created_at": fake.date_time_between(start_date="-5y", end_date="now"),
            "updated_at": datetime.utcnow(),
        })
    return pd.DataFrame(rows)


def gen_eligibility(members: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for i, m in enumerate(members.itertuples()):
        start = fake.date_between(start_date="-3y", end_date="-1y")
        end = start + timedelta(days=random.randint(180, 1500))
        is_active = end > date.today()
        rows.append({
            "eligibility_id": f"ELG-{i:08d}",
            "member_id": m.member_id,
            "coverage_start": start,
            "coverage_end": end if not is_active else None,
            "is_active": is_active,
            "plan_type": m.plan_type,
            "created_at": datetime.utcnow(),
        })
    return pd.DataFrame(rows)


def gen_prior_authorizations(members: pd.DataFrame, providers: pd.DataFrame, n: int = 15_000) -> pd.DataFrame:
    rows = []
    member_ids = members["member_id"].tolist()
    provider_ids = providers["provider_id"].tolist()
    for i in range(n):
        request_date = fake.date_between(start_date="-2y", end_date="today")
        is_approved = random.random() < 0.72
        denial_reason = None
        denial_category = None
        denial_code = None
        if not is_approved:
            denial_code, denial_reason, denial_category = random.choice(DENIAL_REASONS)
        rows.append({
            "prior_auth_id": _pa_id(i),
            "member_id": random.choice(member_ids),
            "provider_id": random.choice(provider_ids),
            "service_type": random.choice(SERVICE_TYPES),
            "service_description": fake.sentence(nb_words=6),
            "cpt_code": random.choice(CPT_CODES) if random.random() < 0.7 else None,
            "hcpcs_code": random.choice(HCPCS_CODES) if random.random() < 0.2 else None,
            "ndc_code": random.choice(NDC_CODES) if random.random() < 0.2 else None,
            "primary_diagnosis_code": random.choice(DIAGNOSIS_CODES),
            "secondary_diagnosis_codes": ",".join(random.sample(DIAGNOSIS_CODES, random.randint(0, 3))),
            "request_date": request_date,
            "decision_date": request_date + timedelta(days=random.randint(1, 14)),
            "is_approved": is_approved,
            "authorization_number": fake.bothify("AUTH-########") if is_approved else None,
            "denial_reason": denial_reason,
            "denial_code": denial_code,
            "denial_category": denial_category,
            "drug": fake.word().capitalize() if random.random() < 0.15 else None,
            "submitted_date": request_date,
            "processed_date": request_date + timedelta(days=random.randint(1, 14)),
            "created_at": datetime.utcnow(),
        })
    return pd.DataFrame(rows)


def gen_claims(members: pd.DataFrame, providers: pd.DataFrame, prior_auths: pd.DataFrame, n: int = 50_000) -> pd.DataFrame:
    rows = []
    member_ids = members["member_id"].tolist()
    provider_ids = providers["provider_id"].tolist()
    pa_ids = prior_auths["prior_auth_id"].tolist()
    for i in range(n):
        service_date = fake.date_between(start_date="-2y", end_date="today")
        billed = round(random.uniform(50, 25_000), 2)
        is_denied = random.random() < 0.18
        status = "Denied" if is_denied else random.choices(["Paid", "Partially Paid", "Pending"], weights=[80, 12, 8])[0]
        denial_reason = None
        denial_code = None
        denial_category = None
        edit_code = None
        if is_denied:
            denial_code, denial_reason, denial_category = random.choice(DENIAL_REASONS)
            edit_code = fake.bothify("E###")
        paid = 0 if is_denied else round(billed * random.uniform(0.3, 0.85), 2)
        allowed = paid if status == "Paid" else round(billed * random.uniform(0.4, 0.9), 2)
        rows.append({
            "claim_id": _claim_id(i),
            "member_id": random.choice(member_ids),
            "provider_id": random.choice(provider_ids),
            "prior_auth_id": random.choice(pa_ids) if random.random() < 0.3 else None,
            "service_type": random.choice(SERVICE_TYPES),
            "service_description": fake.sentence(nb_words=6),
            "cpt_code": random.choice(CPT_CODES) if random.random() < 0.85 else None,
            "hcpcs_code": random.choice(HCPCS_CODES) if random.random() < 0.15 else None,
            "ndc_code": random.choice(NDC_CODES) if random.random() < 0.1 else None,
            "primary_diagnosis_code": random.choice(DIAGNOSIS_CODES),
            "secondary_diagnosis_codes": ",".join(random.sample(DIAGNOSIS_CODES, random.randint(0, 3))),
            "service_date": service_date,
            "billed_amount": billed,
            "allowed_amount": allowed,
            "paid_amount": paid,
            "status": status,
            "denial_reason": denial_reason,
            "denial_code": denial_code,
            "denial_category": denial_category,
            "edit_code": edit_code,
            "was_member_active": random.random() < 0.95,
            "submitted_date": service_date + timedelta(days=random.randint(1, 30)),
            "processed_date": service_date + timedelta(days=random.randint(2, 45)),
            "created_at": datetime.utcnow(),
        })
    return pd.DataFrame(rows)


def gen_appeals(claims: pd.DataFrame, n: int = 8_000) -> pd.DataFrame:
    denied = claims[claims["status"] == "Denied"].sample(n=min(n, (claims["status"] == "Denied").sum()), random_state=42)
    rows = []
    for i, c in enumerate(denied.itertuples()):
        appeal_date = c.processed_date + timedelta(days=random.randint(1, 60))
        is_overturned = random.random() < 0.42
        rows.append({
            "appeal_id": _appeal_id(i),
            "appeal_type": random.choice(["Member", "Provider", "Authorized Representative"]),
            "appeal_source": random.choice(["Salesforce", "Member Portal", "Provider Portal", "Mail"]),
            "member_id": c.member_id,
            "provider_id": c.provider_id,
            "prior_auth_id": c.prior_auth_id,
            "claim_id": c.claim_id,
            "original_denial_reason": c.denial_reason,
            "appeal_date": appeal_date,
            "appeal_status": random.choice(APPEAL_STATUSES),
            "is_overturned": is_overturned,
            "has_documentation": random.random() < 0.78,
            "appeal_context": fake.paragraph(nb_sentences=2),
            "reviewer_notes": fake.paragraph(nb_sentences=3) if random.random() < 0.6 else None,
            "created_at": datetime.utcnow(),
        })
    return pd.DataFrame(rows)


def gen_salesforce_cases(members: pd.DataFrame, claims: pd.DataFrame, n: int = 2_000) -> pd.DataFrame:
    rows = []
    member_ids = members["member_id"].tolist()
    sample_claims = claims.sample(n=min(n, len(claims)), random_state=11)
    for i, c in enumerate(sample_claims.itertuples()):
        dos_start = c.service_date
        dos_end = dos_start + timedelta(days=random.randint(0, 5))
        rows.append({
            "case_id": f"500{i:08d}",
            "case_type": random.choice(["PCI", "CIR", "GA", "PA Appeal", "Eligibility"]),
            "status": random.choice(["New", "Working", "Resolved", "Escalated", "Closed"]),
            "subject": fake.sentence(nb_words=8),
            "member_id": random.choice(member_ids),
            "claim_id": c.claim_id,
            "provider_id": c.provider_id,
            "denial_remit_code": c.denial_code,
            "lob": random.choice(["MA", "MMP", "Medicaid", "DSNP"]),
            "dos_start": dos_start,
            "dos_end": dos_end,
            "provider_inquiry": fake.paragraph(nb_sentences=3) if random.random() < 0.5 else None,
            "case_summary": fake.paragraph(nb_sentences=4),
            "priority": random.choice(["Low", "Medium", "High", "Critical"]),
            "created_date": fake.date_time_between(start_date="-1y", end_date="now"),
            "closed_date": fake.date_time_between(start_date="-1y", end_date="now") if random.random() < 0.4 else None,
            "owner_email": fake.email(),
        })
    return pd.DataFrame(rows)


def gen_fraud_reference(claims: pd.DataFrame, n: int = 300) -> pd.DataFrame:
    sample = claims.sample(n=min(n, len(claims)), random_state=7)
    fraud_types = ["Upcoding", "Phantom Billing", "Unbundling", "Duplicate Billing", "Provider Identity Theft"]
    rows = []
    for c in sample.itertuples():
        rows.append({
            "claim_id": c.claim_id,
            "fraud_type": random.choice(fraud_types),
            "fraud_reason": fake.sentence(nb_words=10),
        })
    return pd.DataFrame(rows)


def gen_cms_drug_spending(n: int = 1_500) -> pd.DataFrame:
    brands = ["Ozempic", "Mounjaro", "Trulicity", "Lipitor", "Lyrica", "Eliquis", "Xarelto", "Humira", "Enbrel", "Wegovy"]
    rows = []
    for i in range(n):
        brand = random.choice(brands)
        period = random.choice(["2024 Q1", "2024 Q2", "2024 Q3", "2024 Q4", "2025 Q1", "2025 Q2", "2025 Q3", "2025 Q4"])
        total_spending = round(random.uniform(50_000, 50_000_000), 2)
        beneficiaries = random.randint(500, 200_000)
        rows.append({
            "brand_name": brand,
            "generic_name": brand.lower() + "_generic",
            "period": period,
            "total_spending": total_spending,
            "total_beneficiaries": beneficiaries,
            "total_dosage_units": beneficiaries * random.randint(20, 365),
            "total_claims": beneficiaries * random.randint(2, 12),
            "avg_spending_per_beneficiary": round(total_spending / beneficiaries, 2),
            "avg_spending_per_dosage_unit": round(random.uniform(0.5, 250), 2),
            "manufacturer": fake.company(),
            "drug_class": random.choice(["GLP-1", "Statin", "Anticoagulant", "Biologic", "SSRI", "ARB"]),
        })
    return pd.DataFrame(rows)


def gen_wa_hca_eligibility_raw(members: pd.DataFrame, n: int = 4_500) -> pd.DataFrame:
    wa_members = members[members["state"] == "WA"].sample(n=min(n, (members["state"] == "WA").sum()), random_state=3)
    rows = []
    for m in wa_members.itertuples():
        rows.append({
            "state_member_id": m.state_member_id or fake.bothify("##########"),
            "first_name": m.first_name,
            "last_name": m.last_name,
            "date_of_birth": m.date_of_birth,
            "ssn_last4": str(m.ssn)[-4:],
            "address_line1": m.address,
            "city": m.city,
            "state": "WA",
            "zip_code": m.zip_code,
            "phone": m.phone,
            "plan_type": m.plan_type,
            "coverage_start": fake.date_between(start_date="-2y", end_date="-3m"),
            "coverage_end": fake.date_between(start_date="today", end_date="+1y"),
            "file_drop_date": fake.date_between(start_date="-30d", end_date="today"),
        })
    return pd.DataFrame(rows)


def write_all(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Writing parquet files to {output_dir}")

    members = gen_members()
    members.to_parquet(output_dir / "members.parquet", index=False)
    logger.info(f"  members: {len(members)}")

    providers = gen_providers()
    providers.to_parquet(output_dir / "providers.parquet", index=False)
    logger.info(f"  providers: {len(providers)}")

    eligibility = gen_eligibility(members)
    eligibility.to_parquet(output_dir / "eligibility.parquet", index=False)
    logger.info(f"  eligibility: {len(eligibility)}")

    pas = gen_prior_authorizations(members, providers)
    pas.to_parquet(output_dir / "prior_authorizations.parquet", index=False)
    logger.info(f"  prior_authorizations: {len(pas)}")

    claims = gen_claims(members, providers, pas)
    claims.to_parquet(output_dir / "claims.parquet", index=False)
    logger.info(f"  claims: {len(claims)}")

    appeals = gen_appeals(claims)
    appeals.to_parquet(output_dir / "appeals.parquet", index=False)
    logger.info(f"  appeals: {len(appeals)}")

    sf_cases = gen_salesforce_cases(members, claims)
    sf_cases.to_parquet(output_dir / "salesforce_cases.parquet", index=False)
    logger.info(f"  salesforce_cases: {len(sf_cases)}")

    fraud = gen_fraud_reference(claims)
    fraud.to_parquet(output_dir / "fraud_reference.parquet", index=False)
    logger.info(f"  fraud_reference: {len(fraud)}")

    drugs = gen_cms_drug_spending()
    drugs.to_parquet(output_dir / "cms_drug_spending.parquet", index=False)
    logger.info(f"  cms_drug_spending: {len(drugs)}")

    wa = gen_wa_hca_eligibility_raw(members)
    wa.to_parquet(output_dir / "wa_hca_eligibility_raw.parquet", index=False)
    logger.info(f"  wa_hca_eligibility_raw: {len(wa)}")

    logger.info("Done.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True, help="Local or UC Volume path where parquet files land")
    args = p.parse_args()
    write_all(Path(args.output_dir))
