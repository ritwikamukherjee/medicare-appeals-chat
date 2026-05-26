# Databricks notebook source
# MAGIC %md # Create the Medicare Appeals MAS

# COMMAND ----------

dbutils.widgets.text("catalog", "medicare_appeals_demo")  # noqa: F821
dbutils.widgets.text("schema", "appeals_review")  # noqa: F821

import os
os.environ["CATALOG"] = dbutils.widgets.get("catalog")  # noqa: F821
os.environ["SCHEMA"] = dbutils.widgets.get("schema")  # noqa: F821

# Pull GENIE_SPACE_ID from the previous task's output
os.environ["GENIE_SPACE_ID"] = dbutils.jobs.taskValues.get(  # noqa: F821
    taskKey="create_genie_space", key="genie_space_id"
)

# COMMAND ----------

import sys, pathlib
sys.path.insert(0, str(pathlib.Path("../mas").resolve()))

import importlib, create_mas
importlib.reload(create_mas)
result = create_mas.create_or_update_mas()
mas = result.get("multi_agent_supervisor", {}).get("tile", {})
dbutils.jobs.taskValues.set(  # noqa: F821
    key="mas_endpoint_name", value=mas.get("serving_endpoint_name", "")
)
print(f"MAS endpoint: {mas.get('serving_endpoint_name')}")
