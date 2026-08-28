# Empirical design

## Research question

The paper asks whether Portugal's labour-compensation shortfall, relative to a European benchmark, is larger than its productivity shortfall.

The design is deliberately layered. It does **not** treat the proposition “productivity matters for wages” as equivalent to “productivity fully explains Portugal's wage level”.

## Hypotheses

### H1 — Descriptive excess compensation gap

For the primary year and for the historical sequence of annual cross-sections:

\[
\delta_t
=\log(W_{PT,t}/W_{B,t})
-\log(P_{PT,t}/P_{B,t}).
\]

The directional hypothesis is

\[
H_1:\quad \delta_t<0,
\]

meaning that the Portuguese compensation gap is proportionally larger than the Portuguese productivity gap.

### H2 — Conditional Portuguese compensation residual

Estimate, on comparator countries only,

\[
\log W_{it}=\alpha+\lambda_t+\beta\log P_{it}+\varepsilon_{it}.
\]

The primary conditional penalty in year \(t\) is

\[
r_{PT,t}=\log W_{PT,t}-\widehat{\log W}_{PT,t}.
\]

The directional hypothesis is

\[
H_2:\quad r_{PT,t}<0.
\]

This is a conditional residual, **not** an estimate of a causal treatment effect.

## Primary measurement choice

The first analysis uses Eurostat `nama_10_lp_ulc` for both quantities under the following exact source contract:

- frequency: `A`;
- compensation: `D1_SAL_PER`, compensation per employee;
- productivity: `NLPR_EMP`, nominal labour productivity per person employed;
- unit: `PC_EU27_2020_MPPS_CP`, percentage of EU27 based on PPS at current prices;
- benchmark: `EU27_2020`.

In this unit the EU27 benchmark should equal 100, subject only to provider rounding. The pipeline treats that property as a data invariant rather than an assumption.

### Source-code audit through v0.2.3

The v0.1 specification used the wrong PPS unit code (`CP_MPPS`) but the correct **total-economy** nominal-productivity item (`NLPR_EMP`). v0.2.0 correctly replaced the unit with `PC_EU27_2020_MPPS_CP`, but it also replaced `NLPR_EMP` with `NLPR_PER`. That second change was a namespace error: the cited Eurostat CAPI methodological table defines `NLPR_PER` for regional productivity tables, whereas Eurostat's metadata for the total-economy `nama_10_lp_ulc` collection defines nominal labour productivity per person employed as `NLPR_EMP`.

v0.2.3 therefore restores `NLPR_EMP`. The historical v0.2.0 amendment is retained unchanged as an audit record rather than rewritten. No successful primary-data retrieval by this repository occurred before the v0.2.3 correction.

This correction changes only **how the already intended total-economy estimand is retrieved**. It does not change the research question, directional hypotheses, primary year, comparator set, model or bootstrap specification.

### v0.2.1 acquisition patch

v0.2.1 adds import of Eurostat's official SDMX bulk TSV for the same `nama_10_lp_ulc` flow. The imported bytes are validated against the unchanged primary contract before the canonical panel is built. This is a transport and provenance change only; no hypothesis, endpoint, comparator, model or inference setting is changed.

## Denominators and interpretation

The compensation and productivity numerators and denominators are not identical:

\[
W = \frac{\text{compensation of employees}}{\text{employees}},
\qquad
P = \frac{\text{nominal GDP}}{\text{all employed persons}}.
\]

The productivity denominator includes self-employed persons. Consequently, \(\delta_t\) is a comparison of two economically meaningful country indices, not a decomposition identity. Cross-country self-employment differences are a possible confounder and must be examined in robustness analysis.

Registered robustness checks include:

1. employee/self-employment composition where comparable data are available;
2. hour-based compensation and productivity indicators;
3. alternative comparator groups;
4. AMECO real compensation/productivity measures for the dynamic layer.

## PPS interpretation

PPS is used for **cross-country comparisons within a year**. A sequence of annual PPS-relative indices may describe a country's changing position relative to the EU benchmark, but it is not interpreted as a real growth series.

Long-run within-country growth and decoupling therefore use real/volume measures in a separate analysis.

## Benchmark

The primary descriptive benchmark is the Eurostat EU-27 aggregate (`EU27_2020`). Sensitivities should include:

1. the unweighted median of EU-27 countries excluding Portugal;
2. an employment-weighted comparator mean where the necessary weights are available;
3. euro-area countries;
4. Southern European comparators;
5. leave-one-large-economy-out checks.

The conditional regression is fitted to the country panel excluding Portugal. Portugal is predicted after estimation.

## Primary model

The primary model is a pooled log-level regression with year fixed effects:

\[
\log W_{it}=\alpha+\lambda_t+\beta\log P_{it}+\varepsilon_{it}.
\]

Country fixed effects are **not** included in the primary level model because the object of interest is a persistent cross-country level residual. A Portugal fixed effect would mechanically absorb the quantity the paper is trying to measure.

Country-clustered standard errors are reported as a diagnostic. The preferred uncertainty calculation for the Portuguese residual is a non-parametric country-cluster bootstrap that resamples entire comparator-country histories and re-estimates the model.

## Secondary growth model

A separate growth specification will estimate wage pass-through:

\[
\Delta\log W_{it}
=\alpha_i+\lambda_t+\beta\Delta\log P_{it}+u_{it}.
\]

This model answers a different question: how strongly productivity growth is associated with compensation growth. It must not be used to back-fill the level-residual interpretation.

## Mechanism layer

Only after H1/H2 are measured should the project investigate possible explanations. Candidate variables include:

- adjusted wage share;
- capital intensity and capital deepening;
- sectoral composition;
- self-employment share;
- firm-size distribution;
- collective bargaining coverage and labour-market institutions;
- temporary/non-standard contracts;
- tax wedge;
- educational and skill composition.

A variable entering this layer is not automatically a causal mechanism. The paper should use “associated with”, “accounts for conditionally”, or similarly bounded language unless identification is separately justified.

## Frozen interpretation rules

The following claims are prohibited by the design without additional identification:

- “low productivity causes the entire Portuguese wage gap”;
- “the excess gap is captured by capital”;
- “taxation causes the compensation penalty”;
- “a negative Portuguese residual proves employer monopsony”;
- “raising productivity by x% would raise Portuguese wages by beta times x%”.

## Status of the design

The project was motivated by prior exposure to Portuguese wage/productivity comparisons and therefore starts as a prospectively locked **follow-up analysis**, not a clean confirmatory test. v0.2 is a documented source-code correction to that follow-up design. It does not erase prior exposure and it does not convert the study into a preregistration.
