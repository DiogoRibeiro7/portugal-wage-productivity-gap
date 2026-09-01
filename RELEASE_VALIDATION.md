# Release validation — v0.2.4

Validation prepared on 2026-08-31.

## Release boundary

v0.2.4 is a **post-partial-acquisition source-contract correction**, not the empirical v0.3 release. During the first provider-backed execution, the wage request succeeded but the productivity request for `NLPR_EMP` returned no observations. No H1 gap, H2 residual or primary-release manifest was produced.

The research question, 2024 primary endpoint, EU27 benchmark, comparator-country universe, pooled log-level model, exclusion of Portugal from model fitting, 4,999-replication country bootstrap and non-causal interpretation remain unchanged.

## Provider-backed evidence

GitHub Actions run `33316491224`, attempt 3, executed commit `8c2faa422e2551c48302b234682c82ea69f0398f` on a GitHub-hosted Linux runner. Installation, design-lock verification and registered query capture completed successfully.

The Eurostat wage response (`D1_SAL_PER`) contained observations and has SHA-256:

```text
a570c6d6094732af27dd39e13d48fa61ae7350deea70d38c51bf3cdb935bc164
```

The productivity response requested `NLPR_EMP` under `PC_EU27_2020_MPPS_CP` and returned JSON-stat size `[1, 1, 0, 28, 25]`, with an empty `na_item` dimension and no productivity observations. Its SHA-256 is:

```text
e426db9b9cce2fa1eeb918d88d48645fc727a429ddd66cf98e4a752d5a3ee232
```

The workflow evidence bundle has artifact ID `9764195736` and SHA-256:

```text
092fd9132b0d4bd94027db5780b3f111b03816221b3536b23c5a0953ada1b391
```

## Corrected source contract

```text
dataset       nama_10_lp_ulc
frequency     A
unit          PC_EU27_2020_MPPS_CP
wage item     D1_SAL_PER
productivity  NLPR_PER
benchmark     EU27_2020
```

Eurostat's ESMS prose and its current indicator/unit table are inconsistent on the productivity identifier. The live provider response establishes that `NLPR_EMP` has no observations for the registered unit; the indicator/unit table maps the intended annual nominal productivity-per-person series to `NLPR_PER`. v0.2.4 therefore restores `NLPR_PER` and records the conflict explicitly.

The v0.2.3 source audit and exact v0.2.3 design lock remain preserved unchanged. The execution-based correction is stored in `artifacts/source_contract_execution_audit_v0.2.4.json`.

## Machine checks

- `python -m compileall -q src tests`: **passed locally**
- direct configuration/source-contract smoke check using `NLPR_PER`: **passed locally**
- explicit zero-sized JSON-stat regression smoke check: **passed locally**
- full `pytest`, `ruff` and `mypy`: **delegated to GitHub CI for this correction PR**
- primary empirical release manifest: **absent**

## Scientific status

The first live execution did not test either directional hypothesis because the productivity side of the source contract was empty. v0.2.4 changes only the provider identifier used to retrieve the already intended nominal productivity-per-person concept and adds an explicit parser failure for zero-sized provider responses.

v0.3 remains reserved for a provider-backed run that builds the canonical panel, completes the frozen analysis and passes the primary empirical release gate.
