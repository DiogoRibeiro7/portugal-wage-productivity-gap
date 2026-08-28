# Data sources

## 1. Eurostat — primary level comparison

**Dataset:** `nama_10_lp_ulc` — Labour productivity and unit labour costs.

Primary source contract:

| Role | Eurostat code | Definition |
|---|---|---|
| Frequency | `A` | Annual |
| Compensation | `D1_SAL_PER` | Compensation per employee |
| Productivity | `NLPR_EMP` | Nominal labour productivity per person employed |
| Unit | `PC_EU27_2020_MPPS_CP` | Percentage of EU27 based on PPS at current prices |
| Benchmark | `EU27_2020` | EU27 aggregate, expected index 100 |

Eurostat's metadata for the total-economy labour-productivity collection identifies `NLPR_EMP` as nominal labour productivity per person employed and `D1_SAL_PER` as compensation per employee. A separate Eurostat methodological table uses `NLPR_PER` for regional productivity tables; v0.2.3 records this namespace distinction explicitly. The selected current-price PPS unit remains `PC_EU27_2020_MPPS_CP`.

The repository checks these codes in configuration and checks the resulting EU27=100 invariant in the canonical panel. This prevents a plausible but wrong unit or national-accounts item from silently entering the primary analysis.

### Denominator note

`D1_SAL_PER` is compensation per **employee**. `NLPR_EMP` is GDP per **employed person**, where employment includes employees and self-employed persons. The primary comparison therefore is not an accounting decomposition. Self-employment composition is registered as a robustness variable.

### PPS and time

Eurostat describes Purchasing Power Standards as units that remove cross-country price-level differences and recommends them for cross-country comparisons in a specific year rather than comparisons over time. The project accordingly treats each annual index as a cross-section. A historical plot represents relative position against the EU benchmark, not real Portuguese growth.

### API

The package uses the Eurostat Statistics API:

```text
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}
```

The API returns JSON-stat 2.0 and supports filters on dimensions plus `sinceTimePeriod` and `untilTimePeriod`.

For environments without network access, `pt-wage-gap show-source-queries` emits the exact registered URLs and `pt-wage-gap import-eurostat-json` validates and imports externally downloaded JSON-stat bytes.

### Official bulk fallback

Eurostat also exposes `nama_10_lp_ulc` through its SDMX 2.1 dataset download in TSV format:

```text
https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nama_10_lp_ulc/?compressed=true&format=TSV
```

`pt-wage-gap import-eurostat-bulk` accepts the provider file in plain TSV or gzip form. It preserves the original provider bytes and filters the complete flow down to the same registered primary contract used by the JSON-stat route. It is therefore an alternative acquisition transport, not an alternative empirical source.

## 2. AMECO — secondary real time-series layer

AMECO is the European Commission's annual macro-economic database. The registered secondary layer will use real compensation, productivity, adjusted wage share and related macro series for dynamic decoupling analysis.

AMECO is not required for the primary level estimand. It is registered before the mechanism analysis to reduce source shopping.

## 3. OECD — literature and contextual diagnostics

### Wage–productivity decoupling

Schwellnus, Kappeler and Pionnier (2017), *Decoupling of wages from productivity: Macro-level facts*, OECD Economics Department Working Papers No. 1373, documents decoupling between productivity and real median compensation across OECD economies.

### Portugal firm-level evidence

Mergulhão and Azevedo Pereira (2021), *Productivity-Wage Nexus at the firm-level in Portugal: Decoupling and Divergences*, OECD Productivity Working Papers 2021-28, uses Portuguese administrative firm data for 2010–2016 and reports substantial wage–productivity decoupling.

### Tax wedge

OECD *Taxing Wages 2026* is registered for the taxation sensitivity layer. The tax wedge is not used to define employer-paid compensation or productivity and must not substitute for either.

## Source hierarchy

1. Eurostat national accounts / productivity indicators for the primary harmonised comparison.
2. AMECO for Commission-produced long-run macro series and vintage checks.
3. OECD for replication, sensitivity and literature context.
4. National sources only when a variable is not available comparably at European level.

No social-media chart or secondary news graphic is an admissible empirical source.

## Registered source manifest

Machine-readable source URLs and their intended roles are stored in `configs/source_registry.yml`. Source metadata are part of the design lock.
