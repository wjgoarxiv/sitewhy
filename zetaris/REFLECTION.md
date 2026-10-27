# Zetaris USL reflection — SiteWhy lane `zetaris`

What the USL is: `SITEWHY.usl_site_screen` (1,291 rows, one per moratorium
instrument) joins four registered sources — `moratoria`, `state_legislation`,
`curated_rules` (from `data/layers/rules.yaml`), `county_sources` (from
`data/layers/county_sources.yaml`). DDL in `zetaris/usl.sql`, automation in
`scripts/zetaris_usl.py`, outputs in `zetaris/evidence/`. One data-quality rule
(`null_join_keys`) executes on every build and passes when zero rows come back.

## 1. Time saved vs a hand-coded approach

Without the USL, every SiteWhy question would re-implement the same joins by hand:
load two CSVs plus two YAML files, normalize keys (`moratorium_id`,
`state_abbrev`), aggregate bills per state, map ERCOT scope to Texas, and check
county-source coverage. That would be roughly 60 lines of throwaway pandas/DuckDB in
each future consumer (screener, portfolio table, eval script), and every
copy would drift — one forgets the `enacted` vs `active` distinction, another
drops the federal rule that applies everywhere. (Forecast: the agent loop does
not query the USL yet, so no duplicated join code has been removed today.)

The USL offers one registered table and one build query instead. Adding a
source becomes a YAML edit plus a CSV export instead of a code change in three
places. Concretely, the hand-coded equivalent of the USL build is the
`usl_build_sql()` function in `scripts/zetaris_usl.py` (~45 lines of SQL);
without the USL, answering "which active moratoria in Texas carry ERCOT rules
and how many state bills back them?" would require joining all four sources inline.
With the USL it is one `SELECT ... WHERE state_abbrev = 'TX'` (see
`zetaris/evidence/usl_queries.json`, `texas_ercot_rules`). Forecast saving:
half a day of join debugging and parity checks between the app
path and the eval path, once consumers are pointed at the layer.

## 2. Would the USL help in my work, and where else

Yes, where the data is wider than one person can hold in their head and the
questions repeat. SiteWhy asks the same jurisdiction → moratoria → bills →
rules question for every site; a shared layer answers it identically every
time, which is exactly what a screening product must guarantee. It would not
help where the data is a single static file read once, or where the query
pattern changes every run — there the layer is pure overhead (registration,
staging, refresh discipline).

A project that would benefit: a county-permitting tracker that follows every
US ordinance from proposal to expiry. Sources (clerk PDFs, Legistar feeds,
meeting minutes) arrive weekly in different shapes; the USL would fix the
grain at one row per ordinance-instrument with `enacted_status` as the shared
vocabulary, and every downstream view (map, alerts, expiry watch) would read
the same table. Forecast: the first month costs ~20% extra (layer design,
build query, one DQ rule), then each new source lands in hours instead of days
— roughly a 2–3× speedup per source onboarded after the third.

## 3. Requirement to make the USL stronger

**Problem.** On this instance, only `CREATE LIGHTNING FILESTORE TABLE` persists
across SQL-editor proxy requests. Plain Spark `CREATE VIEW` and CTAS accept
the statement and then vanish (`Not exist` on the next request), so the USL
had to be a materialized CSV re-registered on every build. There is no way to
declare a *logical* layer — a named, versioned SELECT over registered tables
— which is what a semantic layer should be.

**Requirement (PM wording).** As a data-layer user, I want `CREATE LIGHTNING
VIEW <db>.<name> AS <select over Lightning tables>` to persist like filestore
tables do, with `DESCRIBE LIGHTNING VIEW` showing the definition and
`DROP LIGHTNING VIEW` for cleanup, so that a USL is a definition, not a data
copy. Acceptance: create the view in one proxy request, query it in the next,
drop it in a third; the definition survives a driver restart; stale views
fail loudly against dropped source tables instead of serving old rows.

**Mock of the improvement.** With persistent views, `zetaris/usl.sql` would end
with:

```sql
CREATE LIGHTNING VIEW SITEWHY.usl_site_screen AS
SELECT m.moratorium_id, m.state_abbrev, m.jurisdiction, m.enacted_status,
       b.state_bill_count, r.state_rules, s.county_source_count
  FROM SITEWHY.moratoria m
  LEFT JOIN (... per-state bill counts ...) b USING (state_abbrev)
  LEFT JOIN (... ERCOT-to-TX rules ...) r USING (state_abbrev)
  LEFT JOIN (... county sources ...) s USING (moratorium_id);
```

and `scripts/zetaris_usl.py` would register only the four source tables, then
create the view and run the same 12 + 3 + 1 queries against it — no 137 KB
CSV copy, no rebuild step, no drift between the build query and the served
data.
