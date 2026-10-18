# World Bank WDI: source, licence and preparation

**Source:** World Bank, [World Development Indicators](https://datacatalog.worldbank.org/search/dataset/0037712),
downloaded through the [World Bank API](https://api.worldbank.org/v2) on 18 October 2026.
The indicators were last updated by the World Bank on 8 October 2026.
**Licence:** [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
Cite as: World Bank (2026), World Development Indicators.

## What is loaded

`DATAMIND_DEMO.WORLDBANK.WDI_COUNTRY_YEAR_V1`: one row per economy and year, 217 economies,
1990–2024, **7,595 rows**. Key columns: `COUNTRY_CODE` (ISO3), `COUNTRY_NAME`, `REGION`,
`INCOME_GROUP` (World Bank classifications), `YEAR`.

| Column | WDI code | Rows with a value |
|---|---|---|
| `POPULATION` | SP.POP.TOTL | 7,595 |
| `GDP_USD` | NY.GDP.MKTP.CD | 7,215 |
| `GDP_PER_CAPITA_USD` | NY.GDP.PCAP.CD | 7,215 |
| `GDP_GROWTH_PCT` | NY.GDP.MKTP.KD.ZG | 7,110 |
| `INFLATION_PCT` | FP.CPI.TOTL.ZG | 6,024 |
| `UNEMPLOYMENT_PCT` | SL.UEM.TOTL.ZS (modelled ILO estimate) | 6,349 |
| `LIFE_EXPECTANCY_YEARS` | SP.DYN.LE00.IN | 7,595 |
| `INFANT_MORTALITY_PER_1000` | SP.DYN.IMRT.IN | 6,860 |
| `FERTILITY_RATE` | SP.DYN.TFRT.IN | 7,595 |
| `URBAN_POPULATION_PCT` | SP.URB.TOTL.IN.ZS | 7,595 |
| `INTERNET_USERS_PCT` | IT.NET.USER.ZS | 6,214 |
| `ELECTRICITY_ACCESS_PCT` | EG.ELC.ACCS.ZS | 6,747 |
| `RENEWABLE_ENERGY_PCT` | EG.FEC.RNEW.ZS | 6,746 |
| `CO2_PER_CAPITA_TONNES` | EN.GHG.CO2.PC.CE.AR5 | 7,105 |
| `HEALTH_SPENDING_PCT_GDP` | SH.XPD.CHEX.GD.ZS | 4,562 |
| `EDUCATION_SPENDING_PCT_GDP` | SE.XPD.TOTL.GD.ZS | 4,051 |
| `TRADE_PCT_GDP` | NE.TRD.GNFS.ZS | 5,996 |
| `ADULT_LITERACY_PCT` | SE.ADT.LITR.ZS | 1,013 (sparse) |

## Preparation

- World Bank aggregates (World, regions, income groups) are dropped; only the 217 economies are kept.
  Regional answers therefore aggregate countries, not the World Bank's own regional figures.
- Missing values stay `NULL`; nothing is filled or interpolated. Recent years are often incomplete.
- Values are rounded half-up to 6 decimal places.
- The World Bank's current regions are used, e.g. Afghanistan and Pakistan are in
  "Middle East, North Africa, Afghanistan & Pakistan", so "South Asia" has 6 economies.

## Reproduce

```bash
.venv/bin/python run.py --load-worldbank
```

This downloads the snapshot into ignored `data/worldbank/` (raw API responses, SHA-256 hashes in
`manifest.json`), loads it with an explicit ACCOUNTADMIN session, verifies every row against the
snapshot, and grants `SELECT` to the read-only API role. Re-running never overwrites a table that
differs from the snapshot. No data files are committed.
