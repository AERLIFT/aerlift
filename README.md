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
 
## Pipeline
 
```
0_raw → 1_munge → 2_trim → 3_flag → 4_merge → 5_network
```
 
| Stage | Description                                                                                        |
|---|----------------------------------------------------------------------------------------------------|
| munge | Parse raw formats, standardize datetime to UTC, rename variables, deduplicate, write CF-1.8 NetCDF |
| trim | Clip to campaign time bounds, drop excluded sensor IDs                                             |
| flag | Bitmask QA/QC per variable — flag but keep, all thresholds in config                               |
| merge | Join all instruments by household + datetime, preserve built-in resolution                         |
| network | Resample to minute/hour/integrated, exclude flagged, report mean + std + n                         |
 
---
 
## Project Structure
 
```
aerlift/
├── config/
│   ├── config.yaml              # paths, parameters, instrument settings
│   └── samples.tsv              # household → sensor deployment mapping
├── workflow/
│   ├── Snakefile                # entry point, rule all
│   ├── rules/
│   │   ├── munge.smk
│   │   ├── trim.smk
│   │   ├── flag.smk
│   │   ├── merge.smk
│   │   └── network.smk
│   ├── scripts/
│   │   ├── munge/
│   │   │   ├── anemometer.py
│   │   │   ├── aranet.py
│   │   │   ├── lascar.py
│   │   │   ├── hhb.R            # uses astr package
│   │   │   ├── hhb_to_nc.py
│   │   │   ├── upas.R           # uses astr package
│   │   │   └── upas_to_nc.py
│   │   ├── trim/
│   │   │   └── trim.py          # generic — runs for all instruments
│   │   ├── flag/
│   │   │   ├── utils_flag.py
│   │   │   ├── flag_anemometer.py
│   │   │   ├── flag_aranet.py
│   │   │   ├── flag_lascar.py
│   │   │   ├── flag_hhb.py
│   │   │   └── flag_upas.py
│   │   ├── merge/
│   │   │   └── merge.py
│   │   └── network/
│   │       ├── minute.py
│   │       ├── hour.py
│   │       └── integrated.py
│   └── envs/
│       ├── python.yaml          # all Python rules
│       └── r.yaml               # R rules (hhb.R, upas.R)
├── notebooks/                   # visualization & exploration (read-only)
├── logs/                        # per-rule logs (gitignored)
└── results/                     # pipeline outputs (gitignored)
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
├── 1_munged/        # one .nc + summary .csv per instrument
├── 2_trimmed/       # one .nc per instrument
├── 3_flagged/       # one .nc + flags .csv per instrument
├── 4_merged/        # merged.nc (household, datetime)
└── 5_network/       # minute.nc, hour.nc, integrated.nc
```
 
---
 
## Setup
 
```bash
# install snakemake into a base environment
conda create -n snakemake -c conda-forge snakemake
conda activate snakemake
 
# update paths in config/config.yaml
raw_dir:     '/path/to/data/0_raw'
munged_dir:  '/path/to/data/1_munged'
trimmed_dir: '/path/to/data/2_trimmed'
flagged_dir: '/path/to/data/3_flagged'
merged_dir:  '/path/to/data/4_merged'
network_dir: '/path/to/data/5_network'
```
 
Per-rule conda environments are defined in `workflow/envs/` and managed automatically by Snakemake — no manual environment setup required.
 
---
 
## Docker Setup (Recommended)

Docker bundles all Python and R dependencies into a single image — no conda, no manual environment setup. Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

**1. Clone the repo**

```bash
git clone https://github.com/AERLIFT/aerlift.git
cd aerlift
```

**2. Configure your data path**

```bash
cp .env.example .env
```

Edit `.env` and set `DATA_DIR` to the folder containing your `0_raw/` directory:

```bash
DATA_DIR=/path/to/your/data
```

If you just want to test the build without real data, leave it as `DATA_DIR=./data` and create an empty `data/` folder — the pipeline will build and validate the DAG, then fail gracefully with a missing-input message.

**3. Run**

```bash
docker compose up
```

Docker builds the image on first run (10–15 minutes — conda env build). Subsequent runs use the cached image and start in seconds.

**Notes**

- Raw data must be physically present on disk. If your data folder is in iCloud, right-click it in Finder → **Keep Downloaded** before running.
- Anemometer files may be organized in subdirectories (e.g. `0_raw/anemometer/E102/`) — this is handled automatically.
- All pipeline outputs are written back to your local `DATA_DIR` via the volume mount.
- To run a dry-run without executing jobs: `docker compose run --rm aerlift snakemake --dry-run --cores 1`
- The Docker image is rebuilt only when `Dockerfile` or `workflow/envs/*.yaml` change. Re-running `docker compose up` after a config or data change does not trigger a rebuild — Snakemake will only rerun rules whose inputs changed or outputs are missing.

---

## Running the Pipeline
 
```bash
# from repo root — always use --use-conda
 
# dry run — check DAG without executing
snakemake -n --reason --use-conda
 
# visualize DAG
snakemake --dag | dot -Tsvg > dag.svg && open dag.svg
 
# run full pipeline
snakemake --cores 1 --use-conda
 
# run a single target
snakemake --cores 1 --use-conda results/2_trimmed/aranet.nc
 
# lint rules
snakemake --lint
```
 
---
 
## Outputs
 
| Stage | File | Contents |
|---|---|---|
| munge | `1_munged/{instrument}.nc` | Full timeseries, CF-1.8, compressed |
| munge | `1_munged/{instrument}_summary.csv` | Record counts, key statistics |
| trim | `2_trimmed/{instrument}.nc` | Campaign-period data only |
| flag | `3_flagged/{instrument}.nc` | All data + bitmask flag variables |
| flag | `3_flagged/{instrument}_flags.csv` | Flag counts per bit per variable |
| merge | `4_merged/merged.nc` | All instruments, household dimension |
| network | `5_network/minute.nc` | 1-min resampled, unflagged only |
| network | `5_network/hour.nc` | 1-hr resampled, unflagged only |
| network | `5_network/integrated.nc` | Deployment totals, no time dim |
 
NetCDF files are indexed by `(sensor, datetime)` with datetime in UTC.
Original local timezone stored in global attributes (`timezone_local`).
 
---
 
## Configuration
 
Key `config.yaml` sections:
 
```yaml
campaign:
  name:     'AERLIFT'
  timezone: 'America/Los_Angeles'
  start:    '2022-09-01'
  end:      '2023-03-31'
  exclude:
    anemometer: []
    aranet:     []
    lascar:     []
    hhb:        []
    upas:       []
 
instruments:
  hhb:
    alphasense:
      position_1: 'NO2'   # update per campaign deployment
      position_2: 'O3'
 
flag:
  universal:
    temperature_min: -5.0
    temperature_max: 50.0
    rh_min:          0.0
    rh_max:          100.0
 
network:
  resample_method: 'mean'
```
 
Alphasense sensor positions must be updated in `config.yaml` to match the physical sensors installed in each HHB unit for a given campaign. All QA/QC thresholds are configurable without touching scripts.
 
---
 
## Conda Environments
 
| File | Used by |
|---|---|
| `workflow/envs/python.yaml` | All Python rules (munge, trim, flag, merge, network) |
| `workflow/envs/r.yaml` | R rules only (`hhb.R`, `upas.R`) |
 
Run with `--use-conda` to have Snakemake create and manage these automatically.
 
---

## Contact

Mark Campmier, PhD — UC Berkeley School of Public Health

Professor Ajay Pillarisetti, PhD, MPH — UC Berkeley School of Public Health

BIRCHE³ Lab / Division of Environmental Health Sciences
