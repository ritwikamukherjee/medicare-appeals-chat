#!/usr/bin/env bash
# One-command deploy: validate, deploy, run bootstrap job, deploy the app.
# Run from the repo root: `bash scripts/bootstrap.sh dev`

set -euo pipefail
TARGET="${1:-dev}"

echo "==> [1/4] Validate bundle for target=$TARGET"
databricks bundle validate --target "$TARGET"

echo "==> [2/4] Deploy bundle"
databricks bundle deploy --target "$TARGET"

echo "==> [3/4] Run bootstrap job (data + Genie + MAS) — this can take 10-20 min"
databricks bundle run bootstrap_job --target "$TARGET"

echo "==> [4/4] Deploy / restart the app"
databricks bundle run medicare_appeals_chat --target "$TARGET" --no-wait

echo
echo "Done."
echo "Open the app via: databricks bundle summary --target $TARGET | grep medicare-appeals-chat"
