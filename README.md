# AERLIFT

Multi-instrument personal exposure monitoring pipeline built with Snakemake. Ingests raw data from five sensor platforms, standardizes to NetCDF4 (CF-1.8), and prepares merged exposure datasets for analysis.

---

## Instruments

| Instrument | Measurements | Format |
|---|---|---|
| Anemometer (CP202526) | Air flow, flow indicator | `.txt` |
| Aranet4 | CO₂, temperature, RH, pressure | `.csv` |
| Lascar EL-USB | CO | `.txt` |
| Home Health Box (HHB v2) | PM, CO₂, NO₂, O₃, VOC, NOx, met | `.csv` |
| UPAS v2.1 | PM (mass + number), met, light, accel | `.txt` |

---

## Project Structure

```
aerlift/
├── config/
│   ├── config.yaml          # paths, parameters, instrument settings
│   └── samples.tsv          # participant/sample sheet
├── workflow/
│   ├── Snakefile            # entry point, rule all
│   ├── rules/
│   │   └── munge.smk        # all stage 1 rules
│   ├── scripts/
│   │   └── munge/
│   │       ├── anemometer.py
│   │       ├── aranet.py
│   │       ├── lascar.py
│   │       ├── hhb.R            # uses astr package
│   │       ├── hhb.py
│   │       ├── upas.R           # uses astr package
│   │       └── upas.py
│   └── envs/
│       └── munge.yaml
├── notebooks/               # visualization & exploration (read-only consumers)
├── logs/                    # per-rule logs (gitignored)
└── results/                 # pipeline outputs (gitignored)
```

---

## Data Layout

Raw data lives **outside** the repo, referenced via `config.yaml`:

```
data/
├── 0_raw/
│   ├── anemometer/
│   ├── aranet/
│   ├── lascar/
│   ├── hhb/
│   └── upas/
└── 1_munged/               # stage 1 outputs — one .nc per instrument
```

---

## Setup

```bash
# create and activate environment
conda env create -f workflow/envs/munge.yaml
conda activate aerlift

# R dependencies (for HHB and UPAS)
Rscript -e "install.packages('astr'); install.packages('dplyr')"

# update paths in config/config.yaml
raw_dir:    '/path/to/data/0_raw'
munged_dir: '/path/to/data/1_munged'
```

---

## Running the Pipeline

```bash
# from repo root

# dry run — check DAG without executing
snakemake -n --reason

# visualize DAG
snakemake --dag | dot -Tsvg > dag.svg && open dag.svg

# run all stage 1 (munging)
snakemake --cores 1

# run a single instrument
snakemake results/1_munged/aranet.nc
```

---

## Outputs

Each instrument produces:

| File | Contents |
|---|---|
| `1_munged/{instrument}.nc` | Full timeseries, CF-1.8 compliant, compressed |
| `1_munged/{instrument}_summary.csv` | Record counts, key variable means/maxima |

NetCDF files are indexed by `(sensor, datetime)` with datetime in UTC.
Original local timezone stored in global attributes (`timezone_local`).

---

## Configuration

Key `config.yaml` sections:

```yaml
campaign:
  name:     'AERLIFT'
  timezone: 'America/Los_Angeles'

instruments:
  hhb:
    alphasense:
      position_1: 'NO2'   # update per campaign deployment
      position_2: 'O3'
```

Alphasense sensor positions must be updated in `config.yaml` to match
the physical sensors installed in each HHB unit for a given campaign.

---

## Dependencies

- Python: `snakemake`, `pandas`, `numpy`, `xarray`, `netCDF4`, `pyyaml`
- R: `astr`, `dplyr`

---

## Contact

Mark Campmier, PhD — UC Berkeley School of Public Health
Professor Ajay Pillarisetti — UC Berkeley School of Public Health
BIRCHE^{3} Lab / Division of Environmental Health Sciences
