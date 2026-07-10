# Pipeline

The pipeline is implemented in Snakemake (`workflow/snakefile`) and covers
five stages.

```
0_raw → 1_munged → 2_trimmed → 3_flagged → 4_merged → 5_network
```

All intermediate and final outputs are NetCDF4 files compliant with the
CF-1.8 convention, indexed by `(sensor, datetime)` with datetime in UTC.
The original local timezone is stored in the global attribute `timezone_local`.

---

## Stage 1 — Munge (`munge.smk`)

**Input:** Raw instrument files in `0_raw/{instrument}/`
**Output:** `1_munged/{instrument}.nc`, `1_munged/{instrument}_summary.csv`

Each instrument has a dedicated script that:

1. Reads all raw files for that instrument
2. Standardizes datetime to UTC and strips timezone info
3. Renames variables to project conventions (e.g. `PM2_5MC` → `upas_pm25_mc`)
4. Deduplicates on `(sensor, datetime)` — keeping the row with the fewest NaN values when duplicates exist
5. Attaches CF-1.8 global attributes (`Conventions`, `campaign`, `instrument`, `creator_name`, etc.)
6. Attaches variable-level attributes (`long_name`, `units`)
7. Writes compressed NetCDF4 (`zlib=True, complevel=4`) and a summary CSV

HHB and UPAS use a **two-step munge**: an R script (`hhb.R` / `upas.R`) using the
`astr` package first decodes the proprietary log format into a tidy intermediate CSV,
then a Python script converts that CSV to NetCDF4.

**Synthetic mode:** When `config.yaml` includes `synthetic: 'true'`, the global
attribute `SYNTHETIC: true` is stamped on all output files.

---

## Stage 2 — Trim (`trim.smk`)

**Input:** `1_munged/{instrument}.nc`
**Output:** `2_trimmed/{instrument}.nc`

A single generic script (`workflow/scripts/trim.py`) runs for all instruments.
It clips the timeseries to the campaign window defined in `config.yaml`
(`campaign.start` / `campaign.end`) and drops any sensor IDs listed in
`exclude.{instrument}`.

```yaml
campaign:
  start: '2022-09-01'
  end:   '2023-03-31'

exclude:
  aranet: ['16A28']   # sensor ID to drop
  upas:   []
```

---

## Stage 3 — Flag (`flag.smk`)

**Input:** `2_trimmed/{instrument}.nc`
**Output:** `3_flagged/{instrument}.nc`, `3_flagged/{instrument}_flags.csv`

Each instrument has a dedicated flag script. Flags are stored as bitmask integer
variables alongside the original data — **records are never dropped**, only marked.
A `flag_global` variable is computed as the bitwise OR of all instrument flag variables.

**Flag bit conventions** (instrument-specific bits start at 4):

| Bit | Meaning |
|---|---|
| 1 | Out of range (universal threshold) |
| 4 | Instrument-specific condition A |
| 8 | Instrument-specific condition B |
| 16 | Instrument-specific condition C |

All thresholds are defined in `config.yaml` under `flag.{instrument}.thresholds`
and `flag.universal` — no values are hard-coded in scripts.

**Instrument-specific flags:**

| Instrument | Bit 4 | Bit 8 | Bit 16 |
|---|---|---|---|
| Anemometer | `low_flow` | — | — |
| Aranet4 | `co2_low` | `co2_high` | — |
| Lascar | `co_negative` | `co_high` | — |
| Atmotube | `pm_negative` | `voc_negative` | — |
| Aulifants | `voltage_negative` | `voltage_high` | — |
| HHB | `pm_negative` | `electrochemical_warmup` | — |
| UPAS | `pm_negative` | `low_battery` | `pm_zero_run` |

The UPAS `pm_zero_run` flag identifies sustained runs of zero PM readings
exceeding `pm_zero_run_mins` (default 10 minutes), which indicate the pump
was not running.

The HHB `electrochemical_warmup` flag masks the first N minutes of each
deployment (default 5 minutes) to exclude electrochemical sensor warm-up.

---

## Stage 4 — Merge (`merge.smk`)

**Input:** `3_flagged/{instrument}.nc` (all instruments) + `campaign_metadata.csv`
**Output:** `4_merged/merge.nc`

`workflow/scripts/merge/merge.py` joins all flagged per-instrument datasets into
a single NetCDF indexed by `(household_id, datetime)`.

Key steps:

1. Reads `campaign_metadata.csv` to build a `{sensor}_sensor_id → household_id` lookup
2. Maps each flagged NetCDF to its metadata column by filename stem (order-independent)
3. Swaps the `sensor` dimension to `household_id` for each dataset
4. Renames all variables to `{instrument}_{var}` to avoid collisions across instruments (e.g. multiple instruments measuring `temperature`)
5. Outer-joins all datasets on `(household_id, datetime)`, preserving each instrument's native time resolution
6. Writes compressed NetCDF4 with `stage = "merged"` global attribute

---

## Stage 5 — Network (`network.smk`)

**Input:** `4_merged/merge.nc`
**Output:** `5_network/network_{period}.nc`

`workflow/scripts/network/network.py` aggregates the merged dataset to a fixed
time period, gated by a completeness threshold. The rule is parameterized by
`period` wildcard — valid values are `5min`, `1hour`, `1day`, and `campaign`.

| Period | Pandas frequency |
|---|---|
| `5min` | `5min` |
| `1hour` | `1h` |
| `1day` | `1D` |
| `campaign` | campaign-integrated (single value per household) |

**Processing steps:**

1. **Select measurement variables** — numeric non-flag variables are retained; `_flag_` variables are used then discarded
2. **Apply flags** — per-variable flag (or `flag_global` fallback) masks bad records to NaN; any set bit is treated as bad
3. **Aggregate with completeness gating** — each bin is set to NaN if the fraction of non-null samples falls below `network.completeness` (default 0.75); for the `campaign` period, completeness is computed over the full campaign span
4. **Write output** — compressed NetCDF4 with `stage = "network"`, `network_period`, `completeness_threshold`, and per-variable `native_interval_s` attributes

---

## Running the Pipeline

```bash
# Docker (recommended)
docker compose up

# Conda (local)
snakemake --cores 1 --use-conda --snakefile workflow/snakefile

# Dry run
snakemake -n --reason --snakefile workflow/snakefile

# Synthetic data (for testing without real data)
snakemake --cores 1 --use-conda --snakefile workflow/snakefile \
  --configfile config/config_synthetic.yaml
```
