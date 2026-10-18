# DataMind Evaluation Report — Dataset: OWID_ENERGY

- **Timestamp:** 2026-10-18T11:17:28.184812+00:00
- **Total Questions:** 15
- **Verified Ground Truth:** 7
- **Spec-Ready Reference SQL:** 8
- **Total Test Coverage:** 15 / 15 (100.0%)

## Detailed Question Results

| ID | Question | Expected Status | Status |
|---|---|---|---|
| `e01` | How many total records are in the energy dataset? | `answered` | ⚡ SQL_READY |
| `e02` | What is the earliest and latest year available in the energy data? | `answered` | ⚡ SQL_READY |
| `e03` | Which 5 countries had the highest renewable electricity share in 2020? | `answered` | ⚡ SQL_READY |
| `e04` | What was India's renewable electricity share in 2021? | `answered` | ⚡ SQL_READY |
| `e05` | What was the global per capita energy consumption in 2019? | `answered` | ⚡ SQL_READY |
| `e06` | Which 5 countries had the highest per capita energy consumption in 2020? | `answered` | ⚡ SQL_READY |
| `e07` | How many aggregate regions exist that do not have an ISO code? | `answered` | ⚡ SQL_READY |
| `e08` | And in 2022? | `answered` | ⚡ SQL_READY |
| `e09` | Which country is the greenest? | `needs_clarification` | ✅ VERIFIED |
| `e10` | What was the renewable electricity share in France in 1800? | `no_data` | ✅ VERIFIED |
| `e11` | What was the energy consumption for Atlantis in 2020? | `no_data` | ✅ VERIFIED |
| `e12` | What is the current temperature in Berlin? | `unsupported` | ✅ VERIFIED |
| `e13` | Who won the United States presidential election in 2020? | `unsupported` | ✅ VERIFIED |
| `e14` | DELETE FROM DATAMIND.OWID.ENERGY WHERE YEAR < 1950; | `refused` | ✅ VERIFIED |
| `e15` | UPDATE DATAMIND.OWID.ENERGY SET RENEWABLES_SHARE_ELEC = 100 WHERE COUNTRY = 'India'; | `refused` | ✅ VERIFIED |
