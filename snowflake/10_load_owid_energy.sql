-- DataMind: load the second dataset (Our World in Data energy, CC BY 4.0).
-- Run after 00_setup.sql, as ACCOUNTADMIN (or a role owning DATAMIND.OWID).
--
-- STATUS: written against Snowflake docs; not yet executed by the maintainers.
--
-- Step 0 (outside Snowflake): download the CSV. Do NOT commit it (gate G4).
--   curl -L -o data/owid-energy-data.csv \
--     https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv
-- Step 2 below uploads it with PUT (Snowflake CLI `snow sql`/SnowSQL), or use
-- Snowsight: Data > Databases > DATAMIND > OWID > Stages > OWID_STAGE > + Files.

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE DATAMIND_WH;
USE SCHEMA DATAMIND.OWID;

-- 1. Format and stage.
CREATE FILE FORMAT IF NOT EXISTS OWID_CSV_HEADER
  TYPE = CSV PARSE_HEADER = TRUE FIELD_OPTIONALLY_ENCLOSED_BY = '"' NULL_IF = ('');
CREATE STAGE IF NOT EXISTS OWID_STAGE FILE_FORMAT = OWID_CSV_HEADER;

-- 2. Upload (CLI only; skip if you uploaded through Snowsight).
-- PUT file://data/owid-energy-data.csv @OWID_STAGE AUTO_COMPRESS = TRUE OVERWRITE = TRUE;

-- 3. Create the table from the inferred schema, upper-casing column names so
--    queries do not need quoted lower-case identifiers.
CREATE OR REPLACE TABLE ENERGY USING TEMPLATE (
  SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
           'COLUMN_NAME', UPPER(COLUMN_NAME),
           'TYPE', TYPE,
           'NULLABLE', TRUE))
         WITHIN GROUP (ORDER BY ORDER_ID)
  FROM TABLE(INFER_SCHEMA(LOCATION => '@OWID_STAGE', FILE_FORMAT => 'OWID_CSV_HEADER'))
);

-- 4. Load.
COPY INTO ENERGY FROM @OWID_STAGE
  FILE_FORMAT = (FORMAT_NAME = 'OWID_CSV_HEADER')
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ON_ERROR = ABORT_STATEMENT;

-- 5. Checks. Record row count and max(YEAR) in docs/DATASETS.md.
SELECT COUNT(*) AS rows_loaded, MIN(YEAR) AS first_year, MAX(YEAR) AS last_year FROM ENERGY;
SELECT COUNT(*) AS aggregate_rows FROM ENERGY WHERE ISO_CODE IS NULL;

GRANT SELECT ON TABLE ENERGY TO ROLE DATAMIND_READER;
