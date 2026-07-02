from pathlib import Path
from datetime import datetime
import logging
import pandas as pd

# ── dev shim ──────────────────────────────────────────────────────────────────
try:
    snakemake
except NameError:
    class snakemake:
        class params:
            raw_dir = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/0_raw'
            timezone = 'America/Los_Angeles'
            usecols = [1, 2, 3]
            file_ext = '.txt'
        class output:
            nc  = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/lascar.nc'
            csv = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/lascar_summary.csv'
        log = ['/dev/null']

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

# ── functions ─────────────────────────────────────────────────────────────────
def get_files(raw_dir, ext):
    path = Path(raw_dir.strip()) / 'lascar'
    files = list(path.glob(f'*{ext}'))
    assert len(files) > 0, f"No {ext} files found in {path}"
    return files

def parse_sensor_id(df):
    return df['Serial Number'].dropna().astype(int).astype(str).iloc[0]

def read_lascar_file(file, timezone, usecols):
    df = pd.read_csv(file, usecols=usecols)

    sensor = parse_sensor_id(df)
    df = df.drop(columns='Serial Number')
    df.columns = ['datetime', 'co']

    df.index = (pd.to_datetime(df['datetime'])
                  .dt.tz_localize(timezone)
                  .dt.tz_convert('UTC')
                  .dt.tz_localize(None))
    df.index.name = 'datetime'
    df = df.drop(columns='datetime')
    df['sensor'] = sensor
    return df

def process_lascar(params):
    files = get_files(params.raw_dir, params.file_ext)
    lst_df = [
        read_lascar_file(file, timezone=params.timezone, usecols=params.usecols)
        for file in files
    ]
    df = pd.concat(lst_df).reset_index()

    n_before = len(df)
    df['n_nan'] = df.isnull().sum(axis=1)
    df = (df.sort_values('n_nan')
            .drop_duplicates(subset=['sensor', 'datetime'], keep='first')
            .drop(columns='n_nan'))
    log.info(f"Dropped {n_before - len(df)} duplicate rows, {len(df)} records remain")

    return df.set_index(['sensor', 'datetime']).to_xarray()

def add_metadata(ds, params):
    ds.attrs = {
        'campaign':       'AERLIFT',
        'instrument':     'Lascar',
        'stage':          'munged',
        'created':        datetime.utcnow().isoformat(),
        'script':         'workflow/scripts/munge/lascar.py',
        'timezone_local': params.timezone,
        'time_reference': 'UTC',
        'Conventions':    'CF-1.8',
        'institution':    'UC Berkeley School of Public Health',
        'creator_name':   'Mark Campmier, PhD',
    }
    if getattr(params, 'synthetic', None) == 'true':
        ds.attrs['SYNTHETIC'] = 'true'
    ds['co'].attrs = {
        'long_name':  'carbon monoxide mixing ratio',
        'units':      'ppm',
        'instrument': 'Lascar',
    }
    return ds

# ── main ──────────────────────────────────────────────────────────────────────
log.info("Starting Lascar munging")

ds_lascar = process_lascar(snakemake.params)
ds_lascar = add_metadata(ds_lascar, snakemake.params)

# summary csv
files = get_files(snakemake.params.raw_dir, snakemake.params.file_ext)

summary = pd.DataFrame({
    'n_files':   [len(files)],
    'n_records': [ds_lascar.sizes['datetime']],
    'co_mean':   [float(ds_lascar['co'].mean())],
    'co_max':    [float(ds_lascar['co'].max())],
})
summary.to_csv(snakemake.output.csv, index=False)
log.info(f"Wrote {snakemake.output.csv}")

# netcdf
out_path = Path(snakemake.output.nc)
out_path.parent.mkdir(parents=True, exist_ok=True)
ds_lascar.to_netcdf(
    out_path,
    encoding={v: {'zlib': True, 'complevel': 4} for v in ['co']}
)
log.info(f"Wrote {out_path}")