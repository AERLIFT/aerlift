# Configuration Reference

All pipeline behavior is controlled by a single YAML file passed to Snakemake
via `--configfile`. Two configs ship with the repo:

| File | Purpose |
|---|---|
| `config/config.yaml` | Production campaign data |
| `config/config_synthetic.yaml` | Synthetic data (pipeline testing, no real data required) |

---

## Paths

```yaml
data_dir:    '/aerlift/data'
raw_dir:     '/aerlift/data/0_raw'
munged_dir:  '/aerlift/data/1_munged'
trimmed_dir: '/aerlift/data/2_trimmed'
flagged_dir: '/aerlift/data/3_flagged'
merged_dir:  '/aerlift/data/4_merged'
network_dir: '/aerlift/data/5_network'
results_dir: 'results'
log_dir:     'logs'
```

When running via Docker, paths are inside the container. `DATA_DIR` in `.env`
is mounted at `/aerlift/data`. Update paths only if running outside Docker.

---

## Campaign

```yaml
campaign:
  name:     'AERLIFT'
  timezone: 'America/Los_Angeles'
  start:    '2022-09-01'
  end:      '2023-03-31'
```

`timezone` is the local timezone of the deployment site — used to localize raw
timestamps before converting to UTC. `start` and `end` define the trim window
(inclusive on both ends).

---

## Synthetic Mode

```yaml
synthetic: 'true'
```

When present and set to `'true'`, all munge scripts stamp `SYNTHETIC: true` as
a global attribute on output NetCDF files. Useful for distinguishing test outputs
from real data.

---

## Instruments

Instrument-level settings control file parsing:

```yaml
instruments:
  anemometer:
    file_ext: '.txt'
    skiprows:  6
    usecols:   [0, 1, 3, 4]
    threshold:
      flow_indicator: 0.5

  aranet:
    file_ext: '.csv'

  lascar:
    file_ext: '.txt'
    usecols:  [1, 2, 3]

  atmotube:
    file_ext: '.csv'

  aulifants:
    file_ext: '.CSV'

  hhb:
    file_ext: '.csv'
    alphasense:
      position_1: 'NO2'   # update per campaign deployment
      position_2: 'O3'
      position_3: null
      position_4: null
    cols_keep: [...]       # columns forwarded from R → Python step

  upas:
    file_ext: '.txt'
    cols_keep: [...]       # columns forwarded from R → Python step
```

:::{important}
`instruments.hhb.alphasense` positions **must be updated** to match the
physical sensors installed in each HHB unit for the campaign. The variable
names in the output NetCDF (`no2_algorithm1`, `o3_algorithm1`, etc.) are
derived from these values.
:::

---

## Trim / Exclusions

```yaml
exclude:
  anemometer: []
  aranet:     ['16A28']   # drop this sensor ID from all downstream stages
  lascar:     []
  atmotube:   []
  aulifants:  []
  hhb:        []
  upas:       []
```

Sensor IDs listed here are dropped during the trim stage and do not appear
in any downstream output.

---

## Network / Aggregation

```yaml
network:
  completeness: 0.75    # min fraction of expected native samples per aggregation bin
```

`completeness` gates every aggregation bin: if fewer than this fraction of
expected samples are non-null (after flag masking), the bin is set to NaN.
Applies to all period tokens (`5min`, `1hour`, `1day`, `campaign`). For the
`campaign` period, expected samples are computed over the full campaign span
rather than a fixed bin width.

---

## Flag Thresholds

### Universal (applied to met variables across all instruments)

```yaml
flag:
  universal:
    temperature_min:  -5.0    # °C
    temperature_max:  50.0
    rh_min:           0.0     # %
    rh_max:           100.0
    pressure_min:     950.0   # hPa
    pressure_max:     1050.0
```

### Per-instrument

Each instrument block defines which bit represents which condition, and the
numeric thresholds that trigger each bit:

```yaml
flag:
  upas:
    bits:
      4:  'pm_negative'
      8:  'low_battery'
      16: 'pm_zero_run'
    thresholds:
      pm_min:           0.0
      battery_min:      20      # %
      pm_zero_run_mins: 10      # minutes of sustained zero before flagging
      temperature_min:  -5.0
      temperature_max:  50.0
      rh_min:           0.0
      rh_max:           100.0
      co2_min:          400.0
      co2_max:          5000.0
      voc_raw_min:      0.0
      nox_raw_min:      0.0
```

All threshold values are read at runtime — no values are hard-coded in
flag scripts. To tighten or loosen a threshold, edit `config.yaml` and
re-run the flag stage.
