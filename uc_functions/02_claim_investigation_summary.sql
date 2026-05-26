-- UC function: claim_investigation_summary
-- Full investigation dossier for a single claim, used by the MAS supervisor.

CREATE OR REPLACE FUNCTION ${catalog}.${schema}.claim_investigation_summary(claim_id STRING)
RETURNS STRING
LANGUAGE SQL
SECURITY DEFINER
READS SQL DATA
DETERMINISTIC
COMMENT 'Generate a full investigation dossier for a single claim including claim details, member info, provider info, prior auth status, appeal history, and provider peer comparison.'
RETURN (
  WITH c AS (
    SELECT * FROM ${catalog}.${schema}.claims WHERE claim_id = claim_investigation_summary.claim_id LIMIT 1
  ),
  m AS (
    SELECT m.*
    FROM ${catalog}.${schema}.members m
    JOIN c ON c.member_id = m.member_id
  ),
  p AS (
    SELECT p.*
    FROM ${catalog}.${schema}.providers p
    JOIN c ON c.provider_id = p.provider_id
  ),
  pa AS (
    SELECT pa.*
    FROM ${catalog}.${schema}.prior_authorizations pa
    JOIN c ON c.prior_auth_id = pa.prior_auth_id
  ),
  appeals_agg AS (
    SELECT
      COUNT(*) AS appeal_count,
      SUM(CASE WHEN is_overturned THEN 1 ELSE 0 END) AS overturned_count
    FROM ${catalog}.${schema}.appeals a
    JOIN c ON a.claim_id = c.claim_id
  ),
  peer_comparison AS (
    SELECT
      ROUND(
        SUM(CASE WHEN ca.status = 'Denied' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2
      ) AS provider_denial_rate_pct,
      ROUND(
        SUM(CASE WHEN ca_spec.status = 'Denied' THEN 1 ELSE 0 END) / NULLIF(COUNT(ca_spec.claim_id), 0) * 100, 2
      ) AS specialty_denial_rate_pct
    FROM ${catalog}.${schema}.claims ca
    LEFT JOIN ${catalog}.${schema}.providers pa_p ON pa_p.provider_id = ca.provider_id
    LEFT JOIN ${catalog}.${schema}.claims ca_spec ON ca_spec.provider_id IN (
      SELECT provider_id FROM ${catalog}.${schema}.providers
      WHERE specialty = (SELECT specialty FROM p)
    )
    WHERE ca.provider_id = (SELECT provider_id FROM c)
  )
  SELECT
    CASE WHEN (SELECT COUNT(*) FROM c) = 0
      THEN CONCAT('Claim ', claim_investigation_summary.claim_id, ' not found.')
      ELSE CONCAT(
        '=== Claim Investigation Dossier ===\n',
        'Claim: ', (SELECT claim_id FROM c),
          ' | Service: ', (SELECT service_type FROM c),
          ' | DOS: ', CAST((SELECT service_date FROM c) AS STRING), '\n',
        'Status: ', (SELECT status FROM c),
          ' | Billed: $', CAST((SELECT billed_amount FROM c) AS STRING),
          ' | Allowed: $', CAST((SELECT allowed_amount FROM c) AS STRING),
          ' | Paid: $', CAST((SELECT paid_amount FROM c) AS STRING), '\n',
        'Denial code/reason: ', COALESCE((SELECT denial_code FROM c), 'n/a'),
          ' / ', COALESCE((SELECT denial_reason FROM c), 'n/a'), '\n\n',
        '--- Member ---\n',
        (SELECT first_name FROM m), ' ', (SELECT last_name FROM m),
          ' (', (SELECT member_id FROM m), ') | ', (SELECT plan_type FROM m),
          ' | State: ', (SELECT state FROM m), '\n\n',
        '--- Provider ---\n',
        (SELECT name FROM p), ' | NPI ', (SELECT npi FROM p),
          ' | Specialty: ', (SELECT specialty FROM p),
          ' | State: ', (SELECT state FROM p), '\n\n',
        '--- Prior Authorization ---\n',
        CASE WHEN (SELECT prior_auth_id FROM c) IS NULL THEN 'No prior auth linked.'
          ELSE CONCAT(
            'PA: ', (SELECT prior_auth_id FROM pa),
            ' | Approved: ', CAST((SELECT is_approved FROM pa) AS STRING),
            ' | Decision: ', CAST((SELECT decision_date FROM pa) AS STRING)
          )
        END, '\n\n',
        '--- Appeal History ---\n',
        'Appeals filed: ', (SELECT appeal_count FROM appeals_agg),
          ' | Overturned: ', (SELECT overturned_count FROM appeals_agg), '\n\n',
        '--- Provider Peer Comparison ---\n',
        'Provider denial rate: ', CAST((SELECT provider_denial_rate_pct FROM peer_comparison) AS STRING),
          '% | Specialty denial rate: ', CAST((SELECT specialty_denial_rate_pct FROM peer_comparison) AS STRING), '%\n',
        CASE
          WHEN (SELECT provider_denial_rate_pct FROM peer_comparison)
               > (SELECT specialty_denial_rate_pct FROM peer_comparison) * 1.5
            THEN 'FLAG: SIGNIFICANTLY ABOVE PEERS'
          WHEN (SELECT provider_denial_rate_pct FROM peer_comparison)
               > (SELECT specialty_denial_rate_pct FROM peer_comparison) * 1.1
            THEN 'FLAG: ABOVE PEERS'
          ELSE 'WITHIN NORMAL RANGE'
        END
      )
    END
);
