# Release validation — v0.3.0

Validation performed on 2026-09-01.

## Release boundary

v0.3.0 is the first **provider-backed empirical primary release**. It is based on the exact successful GitHub Actions execution at commit:

```text
59573374ae25d8cc17b9e7a4ca4f956f36dd5109
```

Workflow run:

```text
33470285773
```

Evidence bundle artifact:

```text
9786339357
```

Artifact SHA-256:

```text
e20565d29ed6a0240a9c2ca0ed11ce1bcadae264fb7991def374f0060ce40d7f
```

## Release gate

All primary empirical checks passed:

- design lock: **passed**;
- canonical panel and EU27=100 invariant: **passed**;
- panel receipt: **passed**;
- preserved Eurostat source bytes and receipt chain: **passed**;
- 2024 primary-year coverage: **passed**, with 26 comparator countries and no missing required geographies;
- analysis-manifest hashes: **passed**;
- deterministic gap and conditional-residual recalculation: **passed**;
- bootstrap gate: **4,999/4,999 successful replications**.

The release gate reported:

```text
status        ready_for_primary_release
evidence_tier registered_eurostat_snapshot
passed        true
```

The final primary manifest reported:

```text
status empirical_primary
```

## 2024 headline estimates

| Quantity | Estimate |
|---|---:|
| Compensation index, EU27=100 | 81.9 |
| Productivity index, EU27=100 | 81.2 |
| Compensation shortfall | 18.1% |
| Productivity shortfall | 18.8% |
| Excess compensation log gap | +0.0085837 |
| Excess compensation ratio | +0.8621% |
| Conditional Portuguese log residual | +0.0566411 |
| Conditional Portuguese residual | +5.8276% |
| Bootstrap 95% interval, log scale | [0.01913, 0.09374] |
| Bootstrap 95% interval, percentage scale | [1.93%, 9.83%] |

## Directional hypotheses

The registered proposition that Portugal's compensation gap is larger than its productivity gap is **not supported**:

```text
wage_gap_larger_than_productivity_gap = false
```

The registered proposition that Portugal has a negative conditional compensation residual is also **not supported**:

```text
conditional_residual_negative = false
```

The bootstrap interval excludes zero, but on the positive side:

```text
bootstrap_interval_excludes_zero = true
```

## Scientific interpretation

The primary result is narrower than the broader wage–productivity debate. It shows that, under the registered Eurostat cross-country PPS specification for 2024, Portugal's compensation shortfall is slightly smaller than its productivity shortfall and the registered comparator-country model yields a positive rather than negative Portuguese compensation residual.

It does not establish a one-to-one causal relationship between productivity and wages. It also does not answer the separate dynamic question of how productivity growth passes through to real compensation through time. That remains the next empirical layer.

## Engineering note

The provider-backed empirical workflow passed end to end. The ordinary repository CI on the same main commit failed at Ruff because the environment resolved a newer Ruff version whose `UP` rules flag pre-existing typing imports and a few existing unused imports. Those style diagnostics did not affect the locked empirical execution or the primary release gate. They should be repaired in a separate post-release engineering PR so that v0.3 remains bound to the exact successfully executed analysis state rather than silently altering the locked analysis code after observing the result.
