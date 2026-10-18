-- DataMind: one-time Snowflake setup. Run in a Snowsight worksheet as ACCOUNTADMIN.
-- Creates a least-privilege, read-only role for the app, a tiny auto-suspending
-- warehouse, and a credit cap so a trial account survives until judging.
--
-- STATUS: written against Snowflake docs; not yet executed by the maintainers.
-- Run it, then record the outcome in docs/COMPLIANCE.md.

USE ROLE ACCOUNTADMIN;

-- 1. Sample data. Most accounts already have it; if not, create it from the share.
CREATE DATABASE IF NOT EXISTS SNOWFLAKE_SAMPLE_DATA FROM SHARE SFC_SAMPLES.SAMPLE_DATA;

-- 2. Warehouse: smallest size, suspends after 60 s idle.
CREATE WAREHOUSE IF NOT EXISTS DATAMIND_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  STATEMENT_TIMEOUT_IN_SECONDS = 120;

-- 3. Credit cap (adjust to your remaining trial credit).
CREATE RESOURCE MONITOR IF NOT EXISTS DATAMIND_MONITOR
  WITH CREDIT_QUOTA = 20
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS ON 80 PERCENT DO NOTIFY
           ON 100 PERCENT DO SUSPEND;
ALTER WAREHOUSE DATAMIND_WH SET RESOURCE_MONITOR = DATAMIND_MONITOR;

-- 4. Read-only role. The app never needs write access to the data it answers from.
CREATE ROLE IF NOT EXISTS DATAMIND_READER;
GRANT USAGE ON WAREHOUSE DATAMIND_WH TO ROLE DATAMIND_READER;
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE_SAMPLE_DATA TO ROLE DATAMIND_READER;

-- 5. App database for additional datasets (see 10_load_owid_energy.sql).
CREATE DATABASE IF NOT EXISTS DATAMIND;
CREATE SCHEMA IF NOT EXISTS DATAMIND.OWID;
GRANT USAGE ON DATABASE DATAMIND TO ROLE DATAMIND_READER;
GRANT USAGE ON SCHEMA DATAMIND.OWID TO ROLE DATAMIND_READER;
GRANT SELECT ON ALL TABLES IN SCHEMA DATAMIND.OWID TO ROLE DATAMIND_READER;
GRANT SELECT ON FUTURE TABLES IN SCHEMA DATAMIND.OWID TO ROLE DATAMIND_READER;

-- 6. Service user. Replace the password, or better, use key-pair auth:
--    https://docs.snowflake.com/en/user-guide/key-pair-auth
CREATE USER IF NOT EXISTS DATAMIND_APP
  PASSWORD = '<choose-a-strong-password>'
  DEFAULT_ROLE = DATAMIND_READER
  DEFAULT_WAREHOUSE = DATAMIND_WH
  MUST_CHANGE_PASSWORD = FALSE;
GRANT ROLE DATAMIND_READER TO USER DATAMIND_APP;

-- 7. Smoke test as the app role. Expected: 150000 (TPC-H SF1 spec).
USE ROLE DATAMIND_READER;
USE WAREHOUSE DATAMIND_WH;
SELECT COUNT(*) AS customers FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER;
