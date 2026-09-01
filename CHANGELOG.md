# Changelog

## 0.2.4 — 2026-08-31

- Run the first provider-backed Eurostat execution after GitHub-hosted runners became available.
- Record successful `D1_SAL_PER` retrieval and the zero-sized `na_item` response for `NLPR_EMP` under the registered PPS unit.
- Restore `NLPR_PER` for the intended live `nama_10_lp_ulc` nominal productivity-per-person contract.
- Classify the correction as post-partial-acquisition: wage observations were available, productivity observations and H1/H2 results were not.
- Preserve the v0.2.3 audit and design lock unchanged and add a machine-readable execution audit.
- Reject zero-sized JSON-stat cubes explicitly at the parser boundary.
- Keep the research question, 2024 endpoint, comparator universe, model and 4,999-country bootstrap unchanged.

## 0.2.3 — 2026-08-26

- Re-audit the primary `nama_10_lp_ulc` source contract against Eurostat's total-economy productivity metadata.
- Restore the correct total-economy nominal labour productivity identifier, `NLPR_EMP`.
- Document that `NLPR_PER`, introduced in v0.2.0, came from a regional productivity-code table and was incorrectly applied to the total-economy dataset.
- Preserve the v0.2.0 amendment and every prior design lock unchanged as part of the audit trail.
- Add a machine-readable source-contract audit note binding the correction to the archived v0.2.2 lock.
- Keep the corrected PPS unit `PC_EU27_2020_MPPS_CP` and every substantive design element unchanged.
- Add an explicit regression test that rejects the regional `NLPR_PER` code in the primary total-economy contract.
- Continue to withhold v0.3 because no registered primary Eurostat snapshot has yet been successfully ingested.

## 0.2.2 — 2026-08-25

- Add a machine-enforced primary empirical release gate spanning the design lock, source receipts, canonical panel, primary-year coverage, analysis manifest and bootstrap-success threshold.
- Add `analysis_manifest.json`, binding the current panel, panel receipt, study configuration, design lock and every primary analysis output by SHA-256.
- Add `release-status` for non-promoting preflight inspection and `finalise-primary-release` for authorised headline-result promotion.
- Add a hash-bound `primary_release_manifest.json` containing the primary-year estimates only after every release check passes.
- Extend processed-data receipts so both JSON-stat and bulk acquisition routes bind their raw source files and source receipts explicitly.
- Require every empirical CLI execution command to verify the pre-existing scientific lock.
- Fix the convenience runner so it verifies the design lock instead of re-freezing the design immediately before data retrieval.
- Wrap Eurostat transport failures in a domain-specific error and return a concise CLI failure instead of an unhandled network traceback.
- Archive the exact v0.2.1 design lock and record the change as provenance/release hardening with no change to the scientific estimands.

## 0.2.1 — 2026-08-25

- Add a provider-native Eurostat SDMX 2.1 bulk TSV/gzip import for `nama_10_lp_ulc` as a one-file offline fallback.
- Preserve exact bulk provider bytes and record source URL, SHA-256, byte count and compression mode before preparation.
- Filter the bulk flow against the unchanged registered frequency, unit, indicators, geographies and study window.
- Retain Eurostat observation flags and keep missing observations distinct from zero.
- Bind the canonical level-panel receipt to the imported bulk file and its receipt.
- Add independent design-lock verification with manifest, file-digest and path-safety checks.
- Replace implicit configuration coercion and leaked missing-key errors with typed, field-specific validation.
- Keep the research question, estimands, primary endpoint, comparator universe, model and bootstrap unchanged.

## 0.2.0 — 2026-08-25

- Correct the primary Eurostat unit from `CP_MPPS` to `PC_EU27_2020_MPPS_CP`.
- Correct nominal labour productivity per person from the invalid `NLPR_EMP` identifier to `NLPR_PER`.
- Add an exact typed source contract so the primary dataset, frequency, unit, indicators and EU benchmark cannot drift silently.
- Add an EU27=100 scale invariant to the processed-data validation layer.
- Preserve the v0.1 design lock and record the correction as an explicit pre-retrieval design amendment.
- Add canonical query generation for both primary series.
- Add validated offline JSON-stat import for restricted execution environments, preserving exact bytes and SHA-256 receipts.
- Document the employee versus employed-person denominator distinction and register self-employment/hour-based robustness checks.
- Keep 2024 as the frozen primary endpoint despite the availability of newer Eurostat observations.

## 0.1.0 — 2026-08-25

- Establish the primary question: whether Portugal's wage gap exceeds its productivity gap.
- Register a same-source Eurostat PPS level comparison using `nama_10_lp_ulc`.
- Add exact raw-byte receipts and a follow-up design lock.
- Implement a generic typed JSON-stat 2.0 parser.
- Implement annual wage/productivity gaps.
- Implement a comparator-country log-level model estimated without Portugal.
- Implement country-cluster bootstrap inference for the Portuguese conditional wage residual.
- Add publication figures, tests, CI and a LaTeX paper skeleton.
- Explicitly separate cross-sectional PPS levels from real time-series growth.
