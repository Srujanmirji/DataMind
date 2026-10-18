# Datasets, licences and preparation (S5)

No dataset files are committed to this repository (gate G4). `data/` and
`*.csv` are git-ignored.

## 1. TPC-H SF1 (primary)

| | |
|---|---|
| Source | Snowflake sample data — <https://docs.snowflake.com/en/user-guide/sample-data> |
| Location | `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1` (shared into every account; no storage cost) |
| Licence | No open licence stated. Used in place inside the Snowflake account; never copied or redistributed. |
| Preparation | None. `snowflake/00_setup.sql` creates the database from the share if missing and grants read access. |
| Caveats | Synthetic benchmark data; dates 1992–1998; read-only (cannot demo data changes). |

## 2. Our World in Data — energy (second dataset, config-only switch)

| | |
|---|---|
| Source | <https://github.com/owid/energy-data> (`owid-energy-data.csv`) |
| Location | `DATAMIND.OWID.ENERGY` |
| Licence | CC BY 4.0. Attribution: "Our World in Data — Energy dataset", plus the underlying sources named in OWID's codebook. |
| Preparation | Download the CSV to `data/`, then run `snowflake/10_load_owid_energy.sql`. |
| Caveats | Sparse: many null country-years; includes aggregate rows (World, continents, income groups) with null `ISO_CODE`. |
| Loaded snapshot | _TODO: record download date, row count and max YEAR after loading._ |

## Adding a dataset

1. Load it into Snowflake (a script under `snowflake/`), grant `SELECT` to `DATAMIND_READER`.
2. Add `config/datasets/<name>.yaml` (copy `owid_energy.yaml`): database, schema,
   allowlisted tables, relationships, glossary, guardrails, source + licence.
3. Add `eval/questions_<name>.yaml` with hand-written reference SQL.
4. Run with `DATAMIND_DATASET=<name>`. No code changes.
