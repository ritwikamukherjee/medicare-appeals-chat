#!/usr/bin/env bash
# Remove all bundle-managed resources. Does NOT delete the UC catalog/schema or the
# raw landing volume — drop those manually if you want a complete wipe.

set -euo pipefail
TARGET="${1:-dev}"

echo "==> Destroying bundle resources for target=$TARGET"
databricks bundle destroy --target "$TARGET" --auto-approve

cat <<EOF

Manual cleanup (optional):
  - Drop the catalog: databricks api post /api/2.1/unity-catalog/catalogs/<catalog>/delete
  - Delete MCP connections: DROP CONNECTION conn_aichemy_pubmed CASCADE; (and the other two)
  - Delete the MAS tile: databricks api delete /api/2.0/multi-agent-supervisors/<tile_id>
  - Delete the Genie space in the workspace UI
EOF
