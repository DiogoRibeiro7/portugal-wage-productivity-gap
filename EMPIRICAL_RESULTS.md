# Empirical primary results — v0.3.0

The first provider-backed primary analysis completed successfully on 1 September 2026 using the registered Eurostat snapshot, the v0.2.4 source contract and the pre-existing empirical release gate.

The successful GitHub Actions run was `33470285773` at commit `59573374ae25d8cc17b9e7a4ca4f956f36dd5109`. The complete evidence bundle was uploaded as artifact `9786339357` with SHA-256:

```text
e20565d29ed6a0240a9c2ca0ed11ce1bcadae264fb7991def374f0060ce40d7f
```

## 2024 primary level comparison

Eurostat's EU27=100 PPS indices are:

| Quantity | Portugal | EU27 benchmark | Shortfall |
|---|---:|---:|---:|
| Compensation per employee (`D1_SAL_PER`) | 81.9 | 100.0 | 18.1% |
| Nominal labour productivity per person employed (`NLPR_PER`) | 81.2 | 100.0 | 18.8% |

The registered descriptive estimand is

\[
\delta_{2024}
=\log(81.9/100)-\log(81.2/100)
=0.0085837.
\]

Equivalently, Portuguese compensation is about **0.86% higher relative to the EU benchmark than Portuguese productivity is**.

Therefore the registered directional proposition

\[
H_1:\delta_{2024}<0
\]

is **not supported**. The observed sign is positive.

## Conditional Portuguese compensation residual

The pooled comparator-country model with year fixed effects was estimated on 26 comparator countries over 2000–2024, excluding Portugal from model fitting. For 2024, the Portuguese conditional log residual is

\[
r_{PT,2024}=0.0566411,
\]

which corresponds to

\[
100\{\exp(r_{PT,2024})-1\}=5.83\%.
\]

Thus Portuguese compensation in 2024 is approximately **5.83% above**, not below, the level predicted by the registered comparator-country productivity relationship.

A country-cluster bootstrap with 4,999 requested replications completed successfully in all 4,999 replications. The 95% empirical interval for the log residual is

\[
[0.01913,\;0.09374],
\]

or approximately

\[
[1.93\%,\;9.83\%]
\]

on the percentage scale.

Therefore the registered directional proposition

\[
H_2:r_{PT,2024}<0
\]

is also **not supported**. The observed residual is positive and its registered 95% bootstrap interval excludes zero on the positive side.

## Release gate

Every primary release check passed:

- current design lock verified;
- canonical panel and the EU27=100 invariant verified;
- panel receipt verified;
- preserved Eurostat bytes and source receipts verified;
- the 2024 endpoint contained Portugal, the EU27 benchmark and all 26 registered comparators;
- analysis input/output hashes verified;
- the gap and conditional residual reproduced deterministically from the canonical panel;
- 4,999/4,999 bootstrap replications succeeded.

The evidence tier is `registered_eurostat_snapshot` and the primary release manifest status is `empirical_primary`.

## Interpretation boundary

These results reject the specific descriptive claim that Portugal's 2024 compensation gap is larger than its productivity gap under the registered Eurostat definitions. They also reject the specific predictive claim that Portugal has a negative conditional compensation residual in the registered European comparator model.

They do **not** establish that Portuguese wages are high, that productivity fully determines wages, or that productivity growth necessarily passes through to labour compensation. The primary analysis concerns cross-country levels in one registered measurement system. Dynamic wage–productivity pass-through, labour share, sectoral composition, hours, self-employment composition, taxation and institutional mechanisms remain separate empirical questions and planned robustness layers.
