# Databricks notebook source
# MAGIC %md # Create the Claims Ops Genie space

# COMMAND ----------

dbutils.widgets.text("catalog", "medicare_appeals_demo")  # noqa: F821
dbutils.widgets.text("schema", "appeals_review")  # noqa: F821
dbutils.widgets.text("warehouse_id", "")  # noqa: F821

import os
os.environ["CATALOG"] = dbutils.widgets.get("catalog")  # noqa: F821
os.environ["SCHEMA"] = dbutils.widgets.get("schema")  # noqa: F821
os.environ["WAREHOUSE_ID"] = dbutils.widgets.get("warehouse_id")  # noqa: F821

# COMMAND ----------

import sys, pathlib
sys.path.insert(0, str(pathlib.Path("../genie").resolve()))

# COMMAND ----------

import importlib, create_genie_space
importlib.reload(create_genie_space)

# Run the script — it prints the resulting space_id
import io, contextlib, json
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    create_genie_space.main()
output = buf.getvalue()
print(output)

# Surface the space_id so downstream tasks can pull it via dbutils.jobs.taskValues
result = json.loads(output.strip().split("\n", 1)[-1] if output.strip().startswith("{") else output)
if "space_id" in result:
    dbutils.jobs.taskValues.set(key="genie_space_id", value=result["space_id"])  # noqa: F821
    print(f"Set task value genie_space_id = {result['space_id']}")
