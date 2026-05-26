"""Lakeflow Declarative Pipeline (formerly DLT) for the Medicare Appeals demo.

Ingests parquet files dropped by data/generate_synthetic.py into a UC volume, lands them as
Delta tables in the configured catalog/schema, and builds the metric views + the WA state
corroboration MV used by the Genie space.

Pipeline parameters (set in resources/data_pipeline.yml):
  catalog               UC catalog name (e.g. medicare_appeals_demo)
  schema                Schema under that catalog (e.g. appeals_review)
  volume_path           UC volume path where the parquet files were written
                        (e.g. /Volumes/medicare_appeals_demo/raw/landing)
"""

from __future__ import annotations

import dlt
from pyspark.sql import functions as F


def _conf(key: str, default: str = "") -> str:
    """Read a pipeline configuration value."""
    return spark.conf.get(f"appeals.{key}", default)  # type: ignore[name-defined]


CATALOG = _conf("catalog", "medicare_appeals_demo")
SCHEMA = _conf("schema", "appeals_review")
VOLUME_PATH = _conf("volume_path", f"/Volumes/{CATALOG}/raw/landing")


# ---------------------------------------------------------------------------
# Bronze (Auto Loader from the UC Volume)
# ---------------------------------------------------------------------------

def _autoload(filename: str):
    """Stream-load a single parquet file via Auto Loader.

    For demo data this acts like a one-shot load; in a real pipeline the same code path
    handles incremental file drops.
    """
    return (
        spark.readStream  # type: ignore[name-defined]
        .format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.schemaLocation", f"{VOLUME_PATH}/_schemas/{filename}")
        .option("cloudFiles.inferColumnTypes", "true")
        .load(f"{VOLUME_PATH}/{filename}.parquet")
    )


@dlt.table(name="members", comment="Member master")
def members():
    return _autoload("members")


@dlt.table(name="providers", comment="Provider master")
def providers():
    return _autoload("providers")


@dlt.table(name="eligibility", comment="Member eligibility windows")
def eligibility():
    return _autoload("eligibility")


@dlt.table(name="prior_authorizations", comment="Prior auth requests + decisions")
def prior_authorizations():
    return _autoload("prior_authorizations")


@dlt.table(name="claims", comment="Claim header rows")
def claims():
    return _autoload("claims")


@dlt.table(name="appeals", comment="Appeals filed against denied claims")
def appeals():
    return _autoload("appeals")


@dlt.table(name="salesforce_cases", comment="Salesforce case records — PCI, CIR, GA, PA Appeal")
def salesforce_cases():
    return _autoload("salesforce_cases")


@dlt.table(name="fraud_reference", comment="Claims flagged for suspected fraud")
def fraud_reference():
    return _autoload("fraud_reference")


@dlt.table(name="cms_drug_spending", comment="CMS Medicare Part D drug spending by brand & period")
def cms_drug_spending():
    return _autoload("cms_drug_spending")


# ---------------------------------------------------------------------------
# Streaming table: WA HCA eligibility file drops
# ---------------------------------------------------------------------------

@dlt.table(name="wa_hca_eligibility_raw", comment="WA Health Care Authority eligibility file (raw Auto Loader stream)")
def wa_hca_eligibility_raw():
    return _autoload("wa_hca_eligibility_raw")


# ---------------------------------------------------------------------------
# Materialized view: WA state corroboration
# ---------------------------------------------------------------------------

@dlt.table(
    name="state_eligibility_corroboration",
    comment="Corroborates our internal eligibility table against WA HCA state file drops",
)
def state_eligibility_corroboration():
    internal = (
        dlt.read("eligibility").alias("e")
        .join(dlt.read("members").alias("m"), "member_id", "left")
        .filter(F.col("m.state") == "WA")
    )
    state = dlt.read("wa_hca_eligibility_raw").alias("s")
    return (
        internal.join(
            state,
            (F.col("m.state_member_id") == F.col("s.state_member_id"))
            & (F.col("m.date_of_birth") == F.col("s.date_of_birth")),
            "left",
        )
        .select(
            F.col("e.member_id"),
            F.col("e.eligibility_id"),
            F.col("e.coverage_start").alias("internal_coverage_start"),
            F.col("e.coverage_end").alias("internal_coverage_end"),
            F.col("e.is_active").alias("internal_is_active"),
            F.col("e.plan_type").alias("internal_plan_type"),
            F.col("s.state_member_id"),
            F.col("s.coverage_start").alias("state_coverage_start"),
            F.col("s.coverage_end").alias("state_coverage_end"),
            F.col("s.plan_type").alias("state_plan_type"),
            F.col("s.file_drop_date"),
            F.when(F.col("s.state_member_id").isNull(), F.lit("NOT_FOUND_IN_STATE_FILE"))
             .when(F.col("e.is_active") != F.lit(True), F.lit("INTERNAL_INACTIVE"))
             .when(F.col("e.plan_type") != F.col("s.plan_type"), F.lit("PLAN_MISMATCH"))
             .otherwise(F.lit("CORROBORATED")).alias("corroboration_status"),
            F.current_timestamp().alias("computed_at"),
        )
    )


# ---------------------------------------------------------------------------
# Metric views (gold)
# ---------------------------------------------------------------------------

@dlt.view(name="appeals_metrics", comment="Headline appeals metrics by month")
def appeals_metrics():
    return (
        dlt.read("appeals")
        .withColumn("appeal_month", F.date_format("appeal_date", "yyyy-MM"))
        .groupBy("appeal_month")
        .agg(
            F.count("*").alias("total_appeals"),
            F.sum(F.when(F.col("is_overturned"), 1).otherwise(0)).alias("overturned"),
            F.sum(F.when(F.col("has_documentation"), 1).otherwise(0)).alias("with_documentation"),
        )
        .withColumn("overturn_rate", F.col("overturned") / F.col("total_appeals"))
    )


@dlt.view(name="claim_denials_metrics", comment="Denial rate by denial_category and month")
def claim_denials_metrics():
    return (
        dlt.read("claims")
        .withColumn("service_month", F.date_format("service_date", "yyyy-MM"))
        .groupBy("service_month", "denial_category")
        .agg(F.count("*").alias("claim_count"), F.sum("billed_amount").alias("billed_total"))
    )


@dlt.view(name="provider_risk_metrics", comment="Per-provider denial / appeal / overturn rates")
def provider_risk_metrics():
    claims_agg = dlt.read("claims").groupBy("provider_id").agg(
        F.count("*").alias("claim_count"),
        F.sum(F.when(F.col("status") == "Denied", 1).otherwise(0)).alias("denied_count"),
    )
    appeals_agg = dlt.read("appeals").groupBy("provider_id").agg(
        F.count("*").alias("appeal_count"),
        F.sum(F.when(F.col("is_overturned"), 1).otherwise(0)).alias("overturned_count"),
    )
    return (
        dlt.read("providers")
        .join(claims_agg, "provider_id", "left")
        .join(appeals_agg, "provider_id", "left")
        .fillna(0, ["claim_count", "denied_count", "appeal_count", "overturned_count"])
        .withColumn(
            "denial_rate",
            F.when(F.col("claim_count") > 0, F.col("denied_count") / F.col("claim_count")).otherwise(F.lit(0.0)),
        )
        .withColumn(
            "overturn_rate",
            F.when(F.col("appeal_count") > 0, F.col("overturned_count") / F.col("appeal_count")).otherwise(F.lit(0.0)),
        )
    )


@dlt.view(name="glp1_utilization_metrics", comment="GLP-1 drug utilization signal across PA, claims, and CMS spending")
def glp1_utilization_metrics():
    glp1_brands = ["Ozempic", "Mounjaro", "Trulicity", "Wegovy"]
    cms = dlt.read("cms_drug_spending").filter(F.col("brand_name").isin(glp1_brands))
    pa = (
        dlt.read("prior_authorizations")
        .filter(F.col("drug").isin(glp1_brands))
        .groupBy("drug")
        .agg(
            F.count("*").alias("pa_requests"),
            F.sum(F.when(F.col("is_approved"), 1).otherwise(0)).alias("pa_approved"),
        )
        .withColumn("pa_approval_rate", F.col("pa_approved") / F.col("pa_requests"))
        .withColumnRenamed("drug", "brand_name")
    )
    return cms.join(pa, "brand_name", "left")


@dlt.view(name="pbi_appeals_metrics", comment="PowerBI-facing flat view of appeals metrics")
def pbi_appeals_metrics():
    return (
        dlt.read("appeals").alias("a")
        .join(dlt.read("claims").alias("c"), "claim_id", "left")
        .join(dlt.read("members").alias("m"), F.col("a.member_id") == F.col("m.member_id"), "left")
        .select(
            "a.appeal_id", "a.appeal_status", "a.is_overturned", "a.appeal_date",
            "c.denial_category", "c.billed_amount", "c.allowed_amount",
            F.col("m.state").alias("member_state"), F.col("m.plan_type"),
        )
    )


@dlt.view(name="pbi_claims_metrics", comment="PowerBI-facing flat view of claim denials")
def pbi_claims_metrics():
    return (
        dlt.read("claims").alias("c")
        .join(dlt.read("members").alias("m"), "member_id", "left")
        .join(dlt.read("providers").alias("p"), "provider_id", "left")
        .select(
            "c.claim_id", "c.service_date", "c.status", "c.denial_category", "c.denial_reason",
            "c.billed_amount", "c.allowed_amount", "c.paid_amount",
            F.col("m.state").alias("member_state"), F.col("m.plan_type"),
            F.col("p.specialty").alias("provider_specialty"),
        )
    )
