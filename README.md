# AERLIFT

Multi-instrument personal exposure monitoring pipeline built with Snakemake. Ingests raw data from seven sensor platforms, standardizes to NetCDF4 (CF-1.8), and prepares merged exposure datasets for analysis.
 
---
 
## Instruments
 
| Instrument | Measurements | Format |
|---|---|---|
| Anemometer (CP202526) | Air flow, flow indicator | `.txt` |
| Aranet4 | CO₂, temperature, RH, pressure | `.csv` |
| Lascar EL-USB | CO | `.txt` |
| Atmotube Pro | PM1/2.5/10, AQS, TVOC, NOx index, CO₂, temperature, RH, pressure, GPS | `.csv` |
| Aulifants | Voltage, current, power, power factor, cumulative energy | `.CSV` |
| Geocene | Cookstove use (cooking events) | `events.csv` |
| Home Health Box (HHB v2) | PM, CO₂, NO₂, O₃, VOC, NOx, met | `.csv` |
| UPAS v2.1 | PM (mass + number), met, light, accel | `.txt` |
 
---
 
## Pipeline
 
```
0_raw → 1_munge → 2_trim → 3_flag
```
 
| Stage | Description                                                                                        | Status |
|---|---|---|
| munge | Parse raw formats, standardize datetime to UTC, rename variables, deduplicate, write CF-1.8 NetCDF | ✓ |
| trim | Clip to campaign time bounds, drop excluded sensor IDs                                             | ✓ |
| flag | Bitmask QA/QC per variable — flag but keep, all thresholds in config                               | ✓ |
| merge | Join all instruments by household + datetime, preserve built-in resolution                         | planned |
| network | Resample to minute/hour/integrated, exclude flagged, report mean + std + n                         | planned |
 
---
 
## Project Structure
 
```
aerlift/
├── config/
│   ├── config.yaml              # paths, parameters, instrument settings
│   └── config_synthetic.yaml    # synthetic data paths for pipeline testing
├── workflow/
│   ├── snakefile                # entry point, rule all
│   ├── rules/
│   │   ├── munge.smk
│   │   ├── trim.smk
│   │   └── flag.smk
│   ├── scripts/
│   │   ├── munge/
│   │   │   ├── anemometer.py
│   │   │   ├── aranet.py
│   │   │   ├── lascar.py
│   │   │   ├── atmotube.py
│   │   │   ├── aulifants.py
│   │   │   ├── geocene.py
│   │   │   ├── hhb.R            # uses astr package
│   │   │   ├── hhb.py
│   │   │   ├── upas.R           # uses astr package
│   │   │   └── upas.py
│   │   ├── trim.py              # generic — runs for all instruments
│   │   └── flag/
│   │       ├── utils.py
│   │       ├── anemometer.py
│   │       ├── aranet.py
│   │       ├── lascar.py
│   │       ├── atmotube.py
│   │       ├── aulifants.py
│   │       ├── geocene.py
│   │       ├── hhb.py
│   │       └── upas.py
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
│   ├── atmotube/
│   ├── aulifants/
│   ├── geocene/
│   ├── hhb/
│   └── upas/
├── 1_munged/        # one .nc + summary .csv per instrument
├── 2_trimmed/       # one .nc per instrument
└── 3_flagged/       # one .nc + flags .csv per instrument
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
```
 
Per-rule conda environments are defined in `workflow/envs/` and managed automatically by Snakemake — no manual environment setup required.
 
---
 
## Docker Setup (Recommended)

Docker is the easiest way to run the pipeline because it bundles all dependencies (Python, R, and system libraries) into a single container. You don't need to worry about installing specific versions of Python or R on your computer.

### Prerequisites
1.  **Install Docker Desktop**: Download and install it for [Mac](https://www.docker.com/products/docker-desktop/), [Windows](https://www.docker.com/products/docker-desktop/), or [Linux](https://docs.docker.com/engine/install/).
2.  **Open Docker Desktop**: Make sure it's running in the background.

### Step-by-Step Setup

**1. Get the Code**
Open your terminal and run:
```bash
git clone https://github.com/AERLIFT/aerlift.git
cd aerlift
```

**2. Point to Your Data**
The pipeline looks for data in a folder on your computer. You tell Docker where this folder is using a `.env` file.
1.  Create the file from the template:
    ```bash
    cp .env.example .env
    ```
2.  Open the `.env` file in a text editor.
3.  Change `DATA_DIR` to the full path of your data folder (the one containing `0_raw/`):
    *   *Example (Mac):* `DATA_DIR=/Users/name/Documents/aerlift-data`
    *   *Example (Windows):* `DATA_DIR=C:/Users/name/Documents/aerlift-data`
    *   *Note:* If your data is in iCloud, right-click the folder in Finder and select **"Keep Downloaded"** first.

**3. Start the Pipeline**
Run the following command to build the environment and start processing:
```bash
docker compose up
```
*   **First Run**: Docker will download dependencies and build the image. This takes 10–15 minutes depending on your internet speed.
*   **Subsequent Runs**: Starts instantly using the cached image.

### When to Update or Rebuild

As the project evolves, you'll need to update your local copy.

**1. Pulling Latest Changes**
To get the latest code from GitHub:
```bash
git pull origin main
```

**2. Rebuilding the Container**
If you pull new code and the `Dockerfile` or any files in `workflow/envs/` have changed, you **must** rebuild the container to update the internal dependencies:
```bash
docker compose build
```
*Tip: If things aren't working as expected after a `git pull`, try building again.*

**3. Updating Configuration**
If you edit `config/config.yaml`, you do **not** need to rebuild. Just run `docker compose up` again. Snakemake will automatically detect the changes and only rerun the necessary parts of the pipeline.

### GitHub Actions
This repository uses **GitHub Actions** to automatically build and test the Docker image whenever code is pushed to the main branch. This ensures that the environment is always stable and ready for use.

---

## Running Specific Commands

Sometimes you might want to run a specific Snakemake command instead of the whole pipeline.

```bash
# Dry run: See what Snakemake would do without actually running it
docker compose run --rm aerlift snakemake -n

# Run a specific instrument only (e.g., Aranet)
docker compose run --rm aerlift snakemake /aerlift/data/1_munged/aranet.nc

# Unlock the directory (if a previous run crashed)
docker compose run --rm aerlift snakemake --unlock
```
*Note: We use `--rm` to automatically clean up the temporary container after the command finishes.*

---

## Running the Pipeline
 
```bash
# from repo root — always use --use-conda (or use Docker, see above)
 
# dry run — check DAG without executing
snakemake -n --reason --use-conda --snakefile workflow/snakefile
 
# visualize DAG
snakemake --dag --snakefile workflow/snakefile | dot -Tsvg > dag.svg && open dag.svg
 
# run full pipeline
snakemake --cores 1 --use-conda --snakefile workflow/snakefile
 
# run a single target
snakemake --cores 1 --use-conda --snakefile workflow/snakefile /path/to/data/2_trimmed/aranet.nc
 
# lint rules
snakemake --lint --snakefile workflow/snakefile
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
  atmotube:   []
  aulifants:  []
  geocene:    []
  hhb:        []
  upas:       []
 
instruments:
  hhb:
    alphasense:
      position_1: 'NO2'   # update per campaign deployment
      position_2: 'O3'
      position_3: null
      position_4: null
 
flag:
  universal:
    temperature_min: -5.0
    temperature_max: 50.0
    rh_min:          0.0
    rh_max:          100.0
  atmotube:
    thresholds:
      co_min: 0.0
      co_max: 200.0
      voc_raw_min: 0.0
      pm_min: 0.0
  aulifants:
    thresholds:
      voltage_min: 0.0
      voltage_max: 240.0
```
 
Alphasense sensor positions must be updated in `config.yaml` to match the physical sensors installed in each HHB unit for a given campaign. All QA/QC thresholds are configurable without touching scripts.
 
---
 
## Conda Environments
 
| File | Used by |
|---|---|
| `workflow/envs/python.yaml` | All Python rules (munge, trim, flag) |
| `workflow/envs/r.yaml` | R rules only (`hhb.R`, `upas.R`) |
 
Run with `--use-conda` to have Snakemake create and manage these automatically.
 
---

## Contact

Mark Campmier, PhD — UC Berkeley School of Public Health

Professor Ajay Pillarisetti, PhD, MPH — UC Berkeley School of Public Health

BIRCHE³ Lab / Division of Environmental Health Sciences
