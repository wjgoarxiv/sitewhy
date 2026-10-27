-- SiteWhy Unified Semantic Layer DDL.
-- Generated and executed by scripts/zetaris_usl.py against local Zetaris.
-- Tables moratoria/state_legislation are pre-existing seed tables, re-registered
-- here so setup is automated. curated_rules/county_sources come from
-- data/layers/*.yaml via data/seed/*.csv. Plain Spark CREATE VIEW/CTAS does not
-- persist across SQL-editor proxy requests on this instance, so the USL is a
-- materialized join table built by the SELECT below (DuckDB) and registered as
-- a Lightning filestore table.

CREATE LIGHTNING DATABASE SITEWHY DESCRIBE BY "SiteWhy seed layers";

DROP LIGHTNING DATABASE TABLE SITEWHY.moratoria;
CREATE LIGHTNING FILESTORE TABLE moratoria FROM SITEWHY FORMAT CSV OPTIONS (
  path "file:///home/zetaris/customer-data/shared/sitewhy/moratorium_inventory.csv", header "true",
  inferSchema "false", multiLine "true", escape '"');

DROP LIGHTNING DATABASE TABLE SITEWHY.state_legislation;
CREATE LIGHTNING FILESTORE TABLE state_legislation FROM SITEWHY FORMAT CSV OPTIONS (
  path "file:///home/zetaris/customer-data/shared/sitewhy/state_legislation.csv", header "true",
  inferSchema "false", multiLine "true", escape '"');

DROP LIGHTNING DATABASE TABLE SITEWHY.curated_rules;
CREATE LIGHTNING FILESTORE TABLE curated_rules FROM SITEWHY FORMAT CSV OPTIONS (
  path "file:///home/zetaris/customer-data/shared/sitewhy/curated_rules.csv", header "true",
  inferSchema "false", multiLine "true", escape '"');

DROP LIGHTNING DATABASE TABLE SITEWHY.county_sources;
CREATE LIGHTNING FILESTORE TABLE county_sources FROM SITEWHY FORMAT CSV OPTIONS (
  path "file:///home/zetaris/customer-data/shared/sitewhy/county_sources.csv", header "true",
  inferSchema "false", multiLine "true", escape '"');

DROP LIGHTNING DATABASE TABLE SITEWHY.usl_site_screen;
CREATE LIGHTNING FILESTORE TABLE usl_site_screen FROM SITEWHY FORMAT CSV OPTIONS (
  path "file:///home/zetaris/customer-data/shared/sitewhy/usl_site_screen.csv", header "true",
  inferSchema "false", multiLine "true", escape '"');

-- USL build query (materialized to data/seed/usl_site_screen.csv):

SELECT
  m.moratorium_id AS moratorium_id,
  m.state AS state,
  m.state_abbrev AS state_abbrev,
  m.jurisdiction AS jurisdiction,
  m.jurisdiction_type AS jurisdiction_type,
  m.enacted_status AS enacted_status,
  m.current_end_date_iso AS current_end_date_iso,
  COALESCE(b.state_bill_count, 0) AS state_bill_count,
  COALESCE(b.state_bills_enacted, 0) AS state_bills_enacted,
  (SELECT STRING_AGG(rule_id, '|' ORDER BY rule_id)
     FROM read_csv_auto('~/Desktop/00_INBOX/2026-10_Open Agent Hackathon 2026 (GenAI Works)/data/seed/curated_rules.csv', all_varchar=true)
    WHERE layer = 'federal') AS federal_rules,
  COALESCE(r.state_rules, '') AS state_rules,
  COALESCE(s.county_source_count, 0) AS county_source_count,
  COALESCE(s.county_source_titles, '') AS county_source_titles
FROM read_csv_auto('~/Desktop/00_INBOX/2026-10_Open Agent Hackathon 2026 (GenAI Works)/data/seed/moratorium_nation/moratorium_inventory.csv', all_varchar=true) m
LEFT JOIN (
  SELECT state_abbrev,
         COUNT(*) AS state_bill_count,
         SUM(CASE WHEN bill_status_category = 'enacted' THEN 1 ELSE 0 END)
           AS state_bills_enacted
    FROM read_csv_auto('~/Desktop/00_INBOX/2026-10_Open Agent Hackathon 2026 (GenAI Works)/data/seed/moratorium_nation/state_legislation.csv', all_varchar=true)
   GROUP BY state_abbrev
) b ON b.state_abbrev = m.state_abbrev
LEFT JOIN (
  SELECT CASE scope_iso WHEN 'ERCOT' THEN 'TX' ELSE scope_iso END AS state_abbrev,
         STRING_AGG(rule_id, '|' ORDER BY rule_id) AS state_rules
    FROM read_csv_auto('~/Desktop/00_INBOX/2026-10_Open Agent Hackathon 2026 (GenAI Works)/data/seed/curated_rules.csv', all_varchar=true)
   WHERE scope_iso <> ''
   GROUP BY 1
) r ON r.state_abbrev = m.state_abbrev
LEFT JOIN (
  SELECT moratorium_id,
         COUNT(*) AS county_source_count,
         STRING_AGG(title, ' || ' ORDER BY title) AS county_source_titles
    FROM read_csv_auto('~/Desktop/00_INBOX/2026-10_Open Agent Hackathon 2026 (GenAI Works)/data/seed/county_sources.csv', all_varchar=true)
   GROUP BY moratorium_id
) s ON s.moratorium_id = m.moratorium_id
ORDER BY m.state_abbrev, m.jurisdiction, m.moratorium_id;

-- Data-quality rule (passes when zero rows come back):
SELECT moratorium_id, state_abbrev FROM SITEWHY.usl_site_screen WHERE moratorium_id IS NULL OR moratorium_id = '' OR state_abbrev IS NULL OR state_abbrev = '';
