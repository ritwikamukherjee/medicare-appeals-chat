# Databricks notebook source
# MAGIC %md
# MAGIC # Generate synthetic Medicare appeals data
# MAGIC
# MAGIC Run as part of the bootstrap_job. Lands parquet files in `/Volumes/${catalog}/raw/landing`
# MAGIC which the Lakeflow Declarative Pipeline then picks up via Auto Loader.

# COMMAND ----------

dbutils.widgets.text("catalog", "medicare_appeals_demo")  # noqa: F821
dbutils.widgets.text("schema", "appeals_review")  # noqa: F821

CATALOG = dbutils.widgets.get("catalog")  # noqa: F821
SCHEMA = dbutils.widgets.get("schema")  # noqa: F821

# COMMAND ----------

# MAGIC %pip install faker pandas pyarrow

# COMMAND ----------

dbutils.library.restartPython()  # noqa: F821

# COMMAND ----------

dbutils.widgets.text("catalog", "medicare_appeals_demo")  # noqa: F821
CATALOG = dbutils.widgets.get("catalog")  # noqa: F821
SCHEMA = dbutils.widgets.get("schema")  # noqa: F821

# Ensure catalog/schema/volume exist
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")  # noqa: F821
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")  # noqa: F821
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.raw")  # noqa: F821
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.raw.landing")  # noqa: F821

# COMMAND ----------

import sys, pathlib
sys.path.insert(0, str(pathlib.Path("../data").resolve()))
from generate_synthetic import write_all  # noqa: E402

write_all(pathlib.Path(f"/Volumes/{CATALOG}/raw/landing"))
print("OK")
