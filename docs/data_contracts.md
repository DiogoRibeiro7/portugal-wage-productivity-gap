# Data contracts

## Registered primary source

The configured Eurostat source must match all of the following exactly:

```text
dataset       nama_10_lp_ulc
frequency     A
unit          PC_EU27_2020_MPPS_CP
wage item     D1_SAL_PER
productivity  NLPR_EMP
benchmark     EU27_2020
```

The application fails at configuration load if any code differs.

## Raw Eurostat JSON

Each live retrieval is stored exactly as returned by the API, together with a receipt containing:

- dataset;
- query parameters;
- retrieval timestamp in UTC;
- SHA-256 of the raw response bytes;
- source URL.

No transformation is allowed before the raw bytes have been hashed.

## Offline JSON-stat snapshot

A manually downloaded snapshot is accepted only if:

- `freq` contains exactly `A`;
- `unit` contains exactly `PC_EU27_2020_MPPS_CP`;
- `na_item` contains the exact item expected for its role;
- Portugal, the EU27 benchmark and every registered comparator geography are present;
- the full registered 2000–2024 window is covered;
- the payload parses as a non-empty JSON-stat cube.

Imported bytes are preserved exactly and hashed before preparation. The receipt also stores the canonical API URL that the imported cube is expected to represent.

## Offline Eurostat bulk TSV

The one-file fallback accepts Eurostat's official `nama_10_lp_ulc` SDMX bulk TSV, either plain or gzip-compressed. Before any file is promoted to the canonical raw area, the importer requires:

- the series-key dimensions to be exactly `freq,unit,na_item,geo`;
- annual time columns to be present;
- the registered frequency `A`;
- the registered unit `PC_EU27_2020_MPPS_CP`;
- both `D1_SAL_PER` and `NLPR_EMP`;
- Portugal, `EU27_2020` and every registered comparator geography;
- coverage reaching both ends of the registered 2000–2024 study window.

Eurostat observation flags are retained separately from numeric values. Missing observations remain missing during parsing and are never converted to zero. The exact source bytes are preserved under `data/raw/eurostat/bulk/` with their SHA-256 digest, source URL, byte count and compression mode. The processed-panel receipt records that the acquisition mode was `bulk_tsv` and binds the raw bulk file and its receipt by hash.

## Canonical level panel

`data/processed/level_panel.csv` must contain:

| Column | Type | Constraint |
|---|---|---|
| `geo` | string | Eurostat geography code |
| `year` | integer | within configured study window |
| `wage` | float | finite and strictly positive |
| `productivity` | float | finite and strictly positive |
| `wage_status` | string/nullable | Eurostat observation status |
| `productivity_status` | string/nullable | Eurostat observation status |

The key `(geo, year)` must be unique.

### EU27 index invariant

Because the primary unit is a percentage-of-EU27 index, benchmark observations must satisfy

\[
W_{EU27,t}\simeq100,
\qquad
P_{EU27,t}\simeq100.
\]

The implementation allows only a small rounding tolerance. A violation is treated as evidence of a wrong unit, wrong benchmark or incorrectly combined source extract and stops the pipeline.

## Gap table

`results/tables/pt_gap_by_year.csv` contains:

- Portuguese compensation index;
- benchmark compensation index;
- Portuguese productivity index;
- benchmark productivity index;
- compensation log gap;
- productivity log gap;
- excess compensation log gap;
- percentage shortfalls derived from the ratios.

## Conditional residual table

`results/estimates/pt_conditional_residuals.csv` contains one Portuguese prediction per available year:

- observed log compensation;
- predicted log compensation;
- log residual;
- multiplicative residual `exp(residual)-1`;
- model sample size;
- number of comparator countries.

## Failure rules

The primary year is ineligible if any of the following hold:

- Portugal or the EU benchmark is missing for either primary indicator;
- the EU27 benchmark does not satisfy the index-100 invariant;
- either primary value is non-positive;
- fewer than the configured minimum number of comparator countries have complete data;
- the regression design matrix is rank deficient;
- fewer than 95% of requested bootstrap replications complete successfully.

## Analysis manifest

Every successful primary analysis writes `results/estimates/analysis_manifest.json`. It binds:

- the exact canonical-panel SHA-256;
- the canonical-panel receipt SHA-256;
- the current `configs/study.yml` SHA-256;
- the current design-lock SHA-256;
- the registered primary year;
- each generated primary table, residual file, bootstrap summary and bootstrap-draw file by SHA-256.

Changing a result file after estimation therefore invalidates the release gate even if the altered file still has a valid CSV or JSON structure.

## Primary empirical release contract

`results/primary_release_manifest.json` is a privileged artefact. It may be created only by `pt-wage-gap finalise-primary-release` after all required checks pass. The gate requires:

1. a valid current design lock;
2. a valid canonical level panel and EU27=100 invariant;
3. a panel hash that matches its processed-data receipt;
4. a complete and hash-consistent registered Eurostat source chain;
5. Portugal, the EU27 benchmark and the minimum comparator count in 2024;
6. an analysis manifest bound to the current data, receipts, configuration, design lock and outputs;
7. deterministic recomputation of the gap table and conditional residuals from the canonical panel;
8. internal agreement between the bootstrap draw file and the reported point estimate, draw count, success rate and 95% empirical quantiles;
9. the exact registered bootstrap replication count and a success rate of at least 95%.

A blocked gate writes no primary empirical manifest. Synthetic integration data may exercise the same code path in tests, but they are not shipped as evidence and cannot be substituted for provider data in the release repository.

### Provenance limitation

SHA-256 receipts protect byte integrity after ingestion. For manually imported files, they do not cryptographically prove that the bytes were downloaded from the provider URL recorded in the receipt. The repository therefore calls the passing evidence tier a `registered_eurostat_snapshot`, not an authenticated remote response. Provider origin remains an acquisition-provenance claim that must be supported by the retrieval record.
