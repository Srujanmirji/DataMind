# UCI Wine Quality: source, licence and preparation

**Dataset citation:** Cortez, P., Cerdeira, A., Almeida, F., Matos, T., & Reis, J.
(2009). *Wine Quality* [Dataset]. UCI Machine Learning Repository.
[DOI: 10.24432/C56S3T](https://doi.org/10.24432/C56S3T).

**Official source:** [UCI Wine Quality](https://archive.ics.uci.edu/dataset/186/wine+quality).
**Data licence:** [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
The backend MIT licence does not replace the data licence.

**Original paper:** P. Cortez, A. Cerdeira, F. Almeida, T. Matos and J. Reis.
*Modeling wine preferences by data mining from physicochemical properties.*
Decision Support Systems 47(4), 547–553, 2009.
[DOI: 10.1016/j.dss.2009.05.016](https://doi.org/10.1016/j.dss.2009.05.016).

## Acquisition

Downloaded on 18 October 2026 from the official UCI ZIP URL:
`https://archive.ics.uci.edu/static/public/186/wine+quality.zip`.

Archive SHA-256:
`3ed56667f4b828242bd732d7d1dd7f2861e54432239d7fa63877014cbb0304d4`.
The loader pins this hash; unexpected changes cause an error rather than a silent import.

The archive contains `winequality-red.csv`, `winequality-white.csv`, and
`winequality.names`. It remains unchanged in ignored `data/uci/wine-quality.zip`.
The loader reads known members directly, avoiding arbitrary ZIP extraction paths.

## Adaptations and preparation

- Combined the complete red (1,599 rows) and white (4,898 rows) files: 6,497 total.
- Added `wine_type` (RED/WHITE) and a stable source-row ID (`red-00001`, etc.).
- Retained all eleven original physicochemical features and the quality score.
- Parsed measurements as Decimal and loaded NUMBER(38,17), preserving original precision.
- Did not impute, deduplicate, sample, or drop observations. Source repeated measurements remain.
- Renamed source columns to SQL-friendly uppercase underscores; `pH` becomes `PH`.
- Wrote a normalized CSV and provenance manifest under ignored `data/uci/`.
- Load/verification code checks every imported source and working value against the archive.

## Demonstration-specific modification

`WINE_QUALITY_SOURCE_V1` retains original observations. The labelled
`WINE_QUALITY_WORKING_V1` is the API's editable demonstration copy.
During the explicit `--demo` run, one sample originally scored 6 is temporarily
assigned score 7 **only in the working copy**, then restored. This artificial
test change is not represented as a research correction or original UCI fact.
Source observations and the downloaded archive are never updated by the demo.

The count of scores >= 7 is 1,277 in the downloaded original. We define that
threshold for this analysis; UCI provides an ordinal quality score, not this
binary "high-quality" classification. A successful live demonstration should
show 1,277 -> 1,278 -> 1,277 with distinct Snowflake query IDs and identical query
semantics. Check the generated proof for observed, rather than expected, results.

When redistributing the data or adapted extracts, retain the dataset attribution,
CC BY 4.0 link and a description of modifications. The public UCI measurements
contain no names, contact details, brands or customer identifiers.
