-- UC function: member_appeal_brief
-- Builds a comprehensive per-member brief used by the MAS supervisor.
-- Parameters: ${catalog}, ${schema}

CREATE OR REPLACE FUNCTION ${catalog}.${schema}.member_appeal_brief(member_id STRING)
RETURNS STRING
LANGUAGE SQL
SECURITY DEFINER
READS SQL DATA
DETERMINISTIC
COMMENT 'Generate a comprehensive appeal brief for a member including demographics, eligibility, claims history, denials, appeals, and prior authorization status.'
RETURN (
  WITH m AS (
    SELECT * FROM ${catalog}.${schema}.members WHERE member_id = member_appeal_brief.member_id LIMIT 1
  ),
  e AS (
    SELECT
      COUNT(*) AS eligibility_periods,
      MAX(CASE WHEN is_active THEN 'ACTIVE' ELSE 'INACTIVE' END) AS current_status,
      MIN(coverage_start) AS earliest_coverage,
      MAX(COALESCE(coverage_end, CURRENT_DATE())) AS latest_coverage
    FROM ${catalog}.${schema}.eligibility
    WHERE member_id = member_appeal_brief.member_id
  ),
  c AS (
    SELECT
      COUNT(*) AS total_claims,
      SUM(CASE WHEN status = 'Denied' THEN 1 ELSE 0 END) AS denied_claims,
      SUM(CASE WHEN status = 'Paid' THEN 1 ELSE 0 END) AS paid_claims,
      SUM(billed_amount) AS total_billed,
      SUM(paid_amount) AS total_paid
    FROM ${catalog}.${schema}.claims
    WHERE member_id = member_appeal_brief.member_id
  ),
  a AS (
    SELECT
      COUNT(*) AS total_appeals,
      SUM(CASE WHEN is_overturned THEN 1 ELSE 0 END) AS overturned_appeals,
      SUM(CASE WHEN has_documentation THEN 1 ELSE 0 END) AS with_documentation
    FROM ${catalog}.${schema}.appeals
    WHERE member_id = member_appeal_brief.member_id
  ),
  pa AS (
    SELECT
      COUNT(*) AS total_prior_auths,
      SUM(CASE WHEN is_approved THEN 1 ELSE 0 END) AS approved_prior_auths,
      SUM(CASE WHEN NOT is_approved THEN 1 ELSE 0 END) AS denied_prior_auths
    FROM ${catalog}.${schema}.prior_authorizations
    WHERE member_id = member_appeal_brief.member_id
  )
  SELECT
    CASE WHEN (SELECT COUNT(*) FROM m) = 0
      THEN CONCAT('Member ', member_appeal_brief.member_id, ' not found.')
      ELSE CONCAT(
        '=== Member Appeal Brief ===\n',
        'Member: ', (SELECT first_name FROM m), ' ', (SELECT last_name FROM m),
          ' (', (SELECT member_id FROM m), ')\n',
        'Plan: ', (SELECT plan_type FROM m), ' | State: ', (SELECT state FROM m), '\n',
        'DOB: ', CAST((SELECT date_of_birth FROM m) AS STRING), ' | Gender: ', (SELECT gender FROM m), '\n\n',
        '--- Eligibility ---\n',
        'Periods: ', (SELECT eligibility_periods FROM e),
          ' | Current: ', (SELECT current_status FROM e), '\n',
        'Coverage window: ', CAST((SELECT earliest_coverage FROM e) AS STRING),
          ' through ', CAST((SELECT latest_coverage FROM e) AS STRING), '\n\n',
        '--- Claims ---\n',
        'Total: ', (SELECT total_claims FROM c),
          ' | Denied: ', (SELECT denied_claims FROM c),
          ' | Paid: ', (SELECT paid_claims FROM c), '\n',
        'Billed: $', CAST((SELECT total_billed FROM c) AS STRING),
          ' | Paid: $', CAST((SELECT total_paid FROM c) AS STRING), '\n\n',
        '--- Appeals ---\n',
        'Total: ', (SELECT total_appeals FROM a),
          ' | Overturned: ', (SELECT overturned_appeals FROM a),
          ' | With documentation: ', (SELECT with_documentation FROM a), '\n\n',
        '--- Prior Authorizations ---\n',
        'Total: ', (SELECT total_prior_auths FROM pa),
          ' | Approved: ', (SELECT approved_prior_auths FROM pa),
          ' | Denied: ', (SELECT denied_prior_auths FROM pa)
      )
    END
);
