# Portugal Wage–Productivity Gap

A reproducible empirical project asking a narrow question:

> **Is Portugal's wage gap larger than its productivity gap?**

The repository separates three claims that are often collapsed into one:

1. productivity constrains the level of labour compensation an economy can sustain;
2. productivity gains need not pass through one-for-one into labour compensation;
3. Portugal may have an additional compensation shortfall after conditioning on productivity.

The first empirical target is therefore not a causal claim. It is a transparent measurement exercise followed by a cross-country conditional benchmark.

## Primary estimands

For year \(t\), relative to benchmark \(B\):

\[
 g^W_t = \log\!\left(\frac{W_{PT,t}}{W_{B,t}}\right),
 \qquad
 g^P_t = \log\!\left(\frac{P_{PT,t}}{P_{B,t}}\right),
\]

and the descriptive excess compensation gap is

\[
 \delta_t = g^W_t-g^P_t.
\]

A negative \(\delta_t\) means that Portugal's compensation gap is larger, proportionally, than its productivity gap.

The second estimand is a Portuguese conditional compensation residual from a comparator-country model:

\[
\log W_{it}=\alpha+\lambda_t+\beta\log P_{it}+\varepsilon_{it},
\]

estimated **without Portugal**, followed by a prediction for Portugal. The residual is descriptive and predictive, not causal.

## Primary Eurostat contract

The primary level comparison uses Eurostat `nama_10_lp_ulc` under one exact, validated source contract:

| Role | Code | Meaning |
|---|---|---|
| Frequency | `A` | Annual |
| Unit | `PC_EU27_2020_MPPS_CP` | Percentage of EU27, based on PPS at current prices |
| Compensation | `D1_SAL_PER` | Compensation per employee |
| Productivity | `NLPR_EMP` | Nominal labour productivity per person employed |
| Benchmark | `EU27_2020` | EU27 aggregate, expected to equal 100 in the selected unit |

The v0.1 design used an incorrect unit code (`CP_MPPS`) but its total-economy productivity code, `NLPR_EMP`, was in fact correct. v0.2.0 mistakenly replaced that code with `NLPR_PER` after reading a Eurostat methodological table for **regional** productivity indicators. v0.2.3 corrects that namespace error before any successful primary-data retrieval by this repository. The v0.1, v0.2.0, v0.2.1 and v0.2.2 locks remain archived, and the correction is documented in `artifacts/source_contract_audit_v0.2.3.json` rather than rewriting history.

The selected Eurostat unit is already an EU27=100 PPS index. The pipeline therefore verifies that the EU aggregate is approximately 100 for both primary series before allowing analysis.

### Denominator distinction

The two indicators are deliberately not treated as an accounting identity. `D1_SAL_PER` divides employee compensation by employees, while `NLPR_EMP` divides nominal GDP by all employed persons, including self-employed persons. Cross-country differences in self-employment can therefore affect the descriptive comparison. The paper records this explicitly and registers self-employment controls and hour-based measures as robustness checks.

## Cross-section versus time series

Purchasing Power Standards remove cross-country price-level differences and are suitable for cross-country comparisons in a given year. They are **not** a real within-country time series.

The project may show a sequence of annual relative positions, but changes in that sequence are interpreted as **relative convergence/divergence against the EU benchmark**, not as Portuguese real wage or productivity growth. Real growth and wage–productivity decoupling are handled in a separate AMECO/volume-measure layer.

## Repository layout

```text
.
├── configs/                  # Registered study and source specification
├── docs/                     # Design, sources, contracts and interpretation rules
├── paper/                    # LaTeX manuscript
├── src/pt_wage_gap/          # Typed Python package
├── tests/                    # Unit and synthetic econometric tests
├── scripts/                  # Thin reproducible entry points
├── data/                     # Raw/interim/processed data (ignored except placeholders)
├── results/                  # Tables, figures and machine-readable results
└── artifacts/                # Design locks, amendments and provenance records
```

## Quick start

```bash
poetry install
poetry run pytest
poetry run ruff check .
poetry run mypy src tests
```

Validate the exact Eurostat source contract:

```bash
poetry run pt-wage-gap validate-source-config --config configs/study.yml
```

Print the two complete registered API queries:

```bash
poetry run pt-wage-gap show-source-queries --config configs/study.yml
```

Fetch directly in a networked environment:

```bash
poetry run pt-wage-gap fetch-eurostat --config configs/study.yml
```

For a restricted execution environment, download either registered JSON-stat query elsewhere and import the exact bytes:

```bash
poetry run pt-wage-gap import-eurostat-json \
  --role wage \
  --file /path/to/wage.json \
  --config configs/study.yml

poetry run pt-wage-gap import-eurostat-json \
  --role productivity \
  --file /path/to/productivity.json \
  --config configs/study.yml
```

The importer rejects the snapshot unless its frequency, unit, indicator, geography set and study-window coverage satisfy the registered design. It then hashes the exact imported bytes and writes the same canonical raw-file locations used by the live API path.

### One-file Eurostat bulk fallback

v0.2.1 also supports Eurostat's provider-native SDMX bulk TSV download for the same `nama_10_lp_ulc` dataset. This is useful when the two filtered Statistics API calls cannot be made from the analysis environment. Print the registered provider URL with:

```bash
poetry run pt-wage-gap show-bulk-source-url --config configs/study.yml
```

Download that file without modifying it, then run:

```bash
poetry run pt-wage-gap import-eurostat-bulk \
  --file /path/to/nama_10_lp_ulc.tsv.gz \
  --config configs/study.yml
```

The command validates the provider's wide-series schema, selects only the exact registered frequency, unit, indicators, geographies and 2000–2024 study window, preserves the original bytes, records a SHA-256 receipt, and builds the canonical level panel. The same EU27=100 invariant is then applied. The bulk route therefore changes the transport path, not the estimand or source dataset.

Prepare and analyse after the JSON-stat route, or analyse directly after the bulk route:

```bash
poetry run pt-wage-gap prepare --config configs/study.yml
poetry run pt-wage-gap analyse --config configs/study.yml
poetry run pt-wage-gap figures --config configs/study.yml
```

Verify that the current scientific lock still matches every registered design file:

```bash
poetry run pt-wage-gap verify-design-lock --config configs/study.yml
```

### Primary empirical release gate

v0.2.2 separates **running an analysis** from **promoting its output as the primary empirical result**. The latter is permitted only when a machine-readable gate verifies all of the following:

- the prospectively created design lock still matches;
- the canonical panel and its EU27=100 invariant validate;
- the processed-panel hash matches its receipt;
- the preserved Eurostat raw bytes and source receipts form a complete hash chain;
- the registered 2024 endpoint has Portugal, the EU27 benchmark and sufficient comparators;
- the analysis manifest binds the current panel, panel receipt, study configuration, design lock and every output file;
- the descriptive gaps and conditional Portuguese residual reproduce deterministically from the canonical panel;
- the bootstrap summary agrees with the stored draw count, success rate, point estimate and empirical quantiles;
- the registered 4,999-replication bootstrap has at least a 95% success rate.

Inspect the gate without creating an empirical release:

```bash
poetry run pt-wage-gap release-status --config configs/study.yml
```

Only after every check passes can the headline result be promoted:

```bash
poetry run pt-wage-gap finalise-primary-release --config configs/study.yml
```

That command writes `results/primary_release_manifest.json`, including the 2024 compensation and productivity indices, their shortfalls, the excess compensation gap, the conditional Portuguese residual, its bootstrap interval and the hashes required to reproduce the result. A blocked gate cannot write this file.

The hash chain establishes integrity **after acquisition** and consistency with the registered Eurostat request. It does not cryptographically authenticate a manually supplied file as having originated from Eurostat; provider origin must still be established by the acquisition record.

The repository runner now verifies the existing design lock before any empirical command. It never calls `freeze-design` immediately before retrieval. Creating or replacing a design lock is therefore an explicit design-management action rather than part of execution.

## Scientific status

The project question was motivated by already observed Portuguese wage/productivity comparisons. This is therefore a prospectively locked **follow-up analysis**, not a pristine preregistration or an out-of-sample hypothesis test.

v0.2.0 correctly fixed the PPS unit but incorrectly changed the total-economy productivity identifier from `NLPR_EMP` to the regional-table code `NLPR_PER`. v0.2.3 repairs that source-contract mistake after a direct audit of Eurostat's metadata for `nama_10_lp_ulc`. No primary Eurostat observations had been successfully retrieved by this repository before the repair, so no empirical result was available to influence the correction. v0.2.1 added the official bulk TSV route and independent lock verification, while v0.2.2 hardened the prospective execution and result-release boundary. The research question, estimands, comparator universe, 2024 primary endpoint, model and bootstrap remain unchanged.

## Language

Documentation and prose use British English. Code identifiers follow conventional English technical usage.

## Licence

MIT for the code. Source data remain subject to the terms of their original providers.

## Paper roadmap

The intended article structure, including taxation, labour-share and institutional decompositions, is in [`docs/article_map.md`](docs/article_map.md).
