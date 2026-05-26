-- Create the 3 external MCP server connections used by the MAS.
-- Replace ${pubmed_token}, ${partd_token}, ${clinicaltrials_token} with real bearer tokens
-- before running. The bootstrap job reads them from DAB variables.

-- 1. PubMed (openpharma on glama.ai)
CREATE CONNECTION IF NOT EXISTS conn_aichemy_pubmed
TYPE HTTP
OPTIONS (
  host 'glama.ai',
  port '443',
  base_path '/endpoints/mp1ke6xrpi/mcp',
  bearer_token '${pubmed_token}'
);
COMMENT ON CONNECTION conn_aichemy_pubmed IS
  'External PubMed MCP server (openpharma) for peer-reviewed clinical evidence';


-- 2. Medicare Part D MCP server
CREATE CONNECTION IF NOT EXISTS raven_medicare_mcp
TYPE HTTP
OPTIONS (
  host 'mcp-partd.medseal.app',
  port '443',
  base_path '/mcp',
  bearer_token '${partd_token}'
);
COMMENT ON CONNECTION raven_medicare_mcp IS
  'Medicare Part D MCP server for drug lookups (NDC, spending, prescribers)';


-- 3. ClinicalTrials.gov MCP server
-- Upstream typically allows auth.mode=none; placeholder bearer is fine.
CREATE CONNECTION IF NOT EXISTS conn_clinicaltrials
TYPE HTTP
OPTIONS (
  host 'clinicaltrials.caseyjhand.com',
  port '443',
  base_path '/mcp',
  bearer_token '${clinicaltrials_token}'
);
COMMENT ON CONNECTION conn_clinicaltrials IS
  'ClinicalTrials.gov MCP server for trial and treatment evidence';
