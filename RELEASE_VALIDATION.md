# Release validation — v0.2.3

Validation performed on 2026-08-26.

## Release boundary

v0.2.3 is a **pre-retrieval source-contract audit release**. It does not contain primary Eurostat observations and it does not claim an empirical result. v0.3 remains reserved for the first registered Eurostat snapshot that passes the existing empirical release gate.

The research question, H1/H2 estimands, 2024 primary endpoint, EU27 benchmark, comparator-country universe, pooled log-level model, exclusion of Portugal from model fitting, 4,999-replication country bootstrap and non-causal interpretation are unchanged.

## Source-contract correction

A direct audit of Eurostat's metadata for the total-economy productivity collection identified a namespace mistake introduced in v0.2.0.

The correct total-economy contract is:

```text
dataset       nama_10_lp_ulc
frequency     A
unit          PC_EU27_2020_MPPS_CP
wage item     D1_SAL_PER
productivity  NLPR_EMP
benchmark     EU27_2020
```

Eurostat's total-economy productivity metadata defines `NLPR_EMP` as nominal labour productivity per person employed. The `NLPR_PER` identifier used in v0.2.0 appears in Eurostat's regional productivity tables and was incorrectly transferred to `nama_10_lp_ulc`.

The v0.2.0 amendment is deliberately preserved unchanged. The correction is recorded separately in `artifacts/source_contract_audit_v0.2.3.json`, which is itself included in the new design lock. The exact v0.2.2 design lock is archived at `artifacts/design_lock_v0.2.2.json`.

No successful primary-data retrieval or primary empirical release occurred before this correction.

## Machine checks

- `python -m compileall -q src tests`: **passed**
- `PYTHONPATH=src pytest -q`: **40/40 tests passed**
- `PYTHONPATH=src pytest --cov=pt_wage_gap --cov-report=term -q`: **40/40 passed; 80% statement coverage**
- repository configuration loads with `NLPR_EMP`: **passed**
- literal source-contract test pins `NLPR_EMP` independently of YAML: **passed**
- `NLPR_PER` is rejected by the total-economy source contract: **passed**
- obsolete `CP_MPPS` unit is rejected: **passed**
- canonical productivity API query contains `na_item=NLPR_EMP`: **confirmed**
- current design-lock manifest and all locked file hashes: **passed**
- current release status: **blocked, evidence tier `none`**
- source/test Python lines longer than the configured 100-character limit: **none**
- primary Eurostat raw observations included in the release: **none**
- primary empirical release manifest included in the release: **none**

`ruff` and `mypy` remain configured in `pyproject.toml` but are not installed in this execution runtime, so neither is reported as a pass.

## Current design lock

The v0.2.3 lock contains **17 files**, including the machine-readable source-contract audit note.

```text
manifest_sha256 = 50dcbac6c7a8b93a93f496a4b00cdb9f807006edb8ee6fb69ead75421bf5d426
file_sha256     = e0d8e297b3e2dfaaf2bfbd1950f1c4f0c65ff8b2c34f5053de620ddbefe8cf6b
```

The archived v0.2.2 lock has SHA-256:

```text
4f08e2370e5c5cc0261ecde2e70ce4ef5aeec9fa07952322b511198b9bd88e99
```

The v0.2.3 source-contract audit note has SHA-256:

```text
282d47f964943a52924a776c9018ec6911c52cfd2d657788e8df19a9092d13c0
```

## Acquisition status

After the new lock was created and verified, the registered live Eurostat acquisition was retried. The runtime still fails at DNS resolution for `ec.europa.eu`; the CLI returns the controlled Eurostat transport error with exit code 2. No raw file was created and no secondary or manually copied observation was substituted.

The primary results release therefore remains blocked by construction.

## Scientific status

The important result of v0.2.3 is not a number. It is that the repository now asks Eurostat for the intended **total-economy** productivity series rather than a regional-code analogue. Because the mistake was caught before a successful primary retrieval, the statistical design can remain unchanged while the source namespace is repaired transparently.

The next scientific version remains v0.3.x and requires a registered provider snapshot followed by successful execution of the existing 2000–2024 analysis and primary-release gate.
