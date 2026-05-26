# Reproduce step-by-step

For someone who's never seen this repo. Assumes:
- A Databricks workspace you have admin (or close to it) on
- Databricks CLI v0.260+ authenticated against that workspace
- A SQL warehouse (any size — XS works, Serverless preferred)
- Permission to create UC catalogs and connections

## 0. Clone + install CLI

```bash
git clone https://github.com/ritwikamukherjee/medicare-appeals-chat.git
cd medicare-appeals-chat

# Databricks CLI (if you don't already have it)
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sudo sh
databricks auth login --host https://your-workspace.cloud.databricks.com
```

## 1. Configure DAB variables

Edit `databricks.yml`. Required:

```yaml
variables:
  catalog: { default: medicare_appeals_demo }      # any catalog you can create
  schema:  { default: appeals_review }             # NO DASHES (we differ from the source schema)
  warehouse_id: { default: <your-warehouse-id> }   # find via: databricks warehouses list
  pubmed_mcp_token: { default: <bearer> }          # get from glama.ai
  partd_mcp_token: { default: <bearer> }           # from medseal.app
  clinicaltrials_mcp_token: { default: placeholder } # auth=none usually works

targets:
  dev:
    workspace:
      host: https://your-workspace.cloud.databricks.com
```

## 2. Bootstrap

```bash
bash scripts/bootstrap.sh dev
```

What this does, in order:
1. `databricks bundle validate --target dev`
2. `databricks bundle deploy --target dev` (uploads source, creates pipeline + job + app resources)
3. `databricks bundle run bootstrap_job --target dev`
   - Task 1: `generate_synthetic_data` — runs `scripts/notebook_generate_data.py` on a single-node m5d.large cluster. Lands ~85k rows of parquet in `/Volumes/<catalog>/raw/landing/`.
   - Task 2: `run_pipeline` — full-refresh the Lakeflow Declarative Pipeline; lands 9 bronze tables + 6 gold views + 1 MV.
   - Task 3+4: `register_uc_functions` — applies `uc_functions/01_*.sql` and `02_*.sql`.
   - Task 5: `create_mcp_connections` — applies `mas/create_mcp_connections.sql` (uses the 3 bearer tokens).
   - Task 6: `create_genie_space` — POSTs `/api/2.0/genie/spaces`, attaches 14 tables, prints the URL.
   - Task 7: `create_mas` — POSTs `/api/2.0/multi-agent-supervisors` with 6 workers + the supervisor instructions.
4. App deploy — uploads `app/` and starts the FastAPI server. The MAS endpoint name is wired in via the DAB.

Expect ~15-25 min total. The pipeline run is the longest phase.

## 3. Verify

```bash
# Find the app URL
databricks bundle summary --target dev | grep medicare-appeals-chat

# Hit the MAS endpoint directly
databricks api post /serving-endpoints/<mas-endpoint>/invocations \
  --json '{"input":[{"role":"user","content":"How many open appeals cases do we have?"}]}'

# Should route to appeals_data_worker and return a count.
```

## 4. Curate the Genie space (UI step)

The REST endpoints for Genie instructions + certified queries aren't public, so the bootstrap script can only seed the space. To finish:

1. Open the URL printed by Task 6 in the workspace UI.
2. Add the curation instructions from `genie/sample_questions.yaml` (the `curation_instructions:` block).
3. Add each sample question and mark it certified once Genie returns the right SQL.

## 5. Tear down

```bash
bash scripts/tear_down.sh dev
```

This removes the bundle resources but leaves the catalog/schema/volume + MCP connections + MAS tile in place (so you don't lose them by accident). Drop those manually if you want a complete wipe — script prints the exact commands.

## Troubleshooting

See [`architecture.md`](architecture.md#known-issues-and-how-to-debug) for the common failure modes and fixes.
