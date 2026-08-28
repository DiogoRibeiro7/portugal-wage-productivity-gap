# Reproducibility and provenance

## Design history

The first release created `artifacts/design_lock_v0.1.0.json`. That lock is retained verbatim.

During the pre-retrieval source audit for v0.2, the intended Eurostat variables were found to have been named with two incorrect configuration codes. The correction is documented in `artifacts/design_amendment_v0.2.0.json` and a new current `artifacts/design_lock.json` is generated after the corrected source contract is incorporated.

This is preferable to silently replacing the original lock: the project preserves both what was specified and why the source implementation changed.

v0.2.1 does not amend the scientific specification. It adds a second provider-native acquisition route for the same dataset and a verifier for the existing lock. The v0.2 lock is archived before the implementation lock is regenerated.

## Design lock

`pt-wage-gap freeze-design` hashes the files that define the current empirical specification, including:

- `configs/study.yml`;
- `configs/source_registry.yml`;
- `docs/empirical_design.md`;
- `docs/data_sources.md`;
- `docs/data_contracts.md`;
- `src/pt_wage_gap/source_contract.py`;
- the CLI lock-file registry plus configuration, Eurostat, JSON-stat snapshot and bulk-TSV acquisition implementation;
- the metric and econometric implementation.

The lock is a **follow-up specification lock**, not a preregistration claim.

`pt-wage-gap verify-design-lock` independently recomputes the manifest digest and every locked file digest. It rejects missing files, modified files, manifest tampering and unsafe manifest paths.

## Source contract

Configuration loading validates the exact primary Eurostat dataset, frequency, unit, indicators and EU benchmark. The canonical panel additionally validates the EU27=100 invariant implied by the selected unit.

This creates two distinct protections:

1. a syntactic contract against wrong provider codes;
2. an empirical-scale contract against a correctly formatted but scientifically wrong extract.

## Raw data receipts

Each Eurostat retrieval writes a JSON receipt next to the raw file. The receipt records the complete query and SHA-256 digest. Re-running the preparation stage verifies the digest before parsing.

The offline import path preserves and hashes the exact downloaded JSON-stat bytes and stores the canonical registered query URL in its receipt.

The official bulk fallback follows the same rule: the complete Eurostat TSV/gzip bytes are preserved before filtering, and a separate receipt records the provider URL, digest, byte count and compression mode. The canonical panel receipt binds the bulk source by hash.

## Determinism

- Bootstrap seed is fixed in `configs/study.yml`.
- Output tables are sorted before writing.
- JSON outputs use sorted keys.
- Generated figures are functions of canonical processed data only.

## Vintage discipline

The primary endpoint remains 2024 even if the current Eurostat dataset contains later observations. A later-year update must be a separately identified analysis or release. Provider revisions to 2000–2024 are recorded through retrieval dates and raw-byte hashes rather than silently treated as identical data.

## Non-goals

The repository does not vendor Eurostat or AMECO data in the source distribution. It does not claim a primary empirical result until the exact registered inputs have been successfully imported or retrieved and the full validation pipeline has passed.

## Execution-lock discipline in v0.2.2

The earlier convenience runner began by calling `freeze-design`. That was operationally unsafe for a prospectively locked follow-up: if a locked file had changed, running the study could have replaced the old lock immediately before data retrieval.

v0.2.2 removes that behaviour. `scripts/run_pipeline.sh` now starts with `verify-design-lock`, and all empirical CLI commands independently verify the existing lock before they retrieve, import, prepare, analyse, plot or finalise primary evidence. `freeze-design` remains available only as an explicit design-management command.

The exact v0.2.1 lock is archived before the v0.2.2 implementation lock is created. The scientific estimands, endpoint, comparator universe, model and bootstrap are unchanged.

## Result provenance and promotion

A successful analysis writes `results/estimates/analysis_manifest.json`, which binds the canonical input panel, its receipt, the study configuration, the design lock and every primary output by SHA-256.

`pt-wage-gap release-status` then evaluates the full source-to-result chain without promoting the result. The gate also recomputes the deterministic gap and conditional-residual outputs from the canonical panel and checks the stored bootstrap draw count and quantiles against the summary. `pt-wage-gap finalise-primary-release` can create `results/primary_release_manifest.json` only if every gate passes, including the 95% bootstrap-success requirement.

This distinction is intentional:

```text
analysis execution != primary empirical release
```

A locally produced or partially verified result may be useful for debugging, but it is not an authorised headline result.
