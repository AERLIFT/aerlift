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
            raw_dir  = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/0_raw'
            timezone = 'America/Los_Angeles'
        class output:
            nc  = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/aranet.nc'
            csv = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/aranet_summary.csv'
        log = ['/dev/null']

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

# ── functions ─────────────────────────────────────────────────────────────────
def get_files(raw_dir, ext='.csv'):
    path = Path(raw_dir.strip()) / 'aranet'
    files = list(path.glob(f'*{ext}'))
    assert len(files) > 0, f"No {ext} files found in {path}"
    return files

def parse_sensor_id(file):
    return file.stem.replace('Aranet4 ', '').split('_')[0]

def read_aranet_file(file, timezone):
    df = pd.read_csv(file)
    df.columns = ['datetime', 'co2', 'temperature', 'rh', 'pressure']
    df.index = (pd.to_datetime(df['datetime'], format='%d/%m/%Y %I:%M:%S %p')
                  .dt.tz_localize(timezone, ambiguous='NaT')
                  .dt.tz_convert('UTC')
                  .dt.tz_localize(None))
    df.index.name = 'datetime'
    df = df.drop(columns='datetime')
    df['sensor'] = parse_sensor_id(file)
    return df


def process_aranet(params):
    files = get_files(params.raw_dir)
    lst_df = [
        read_aranet_file(file, timezone=params.timezone)
        for file in files
    ]
    df = pd.concat(lst_df).reset_index()

    n_before = len(df)

    # sort by NaN count so most-complete row is first, then deduplicate
    df['n_nan'] = df.isnull().sum(axis=1)
    df = (df.sort_values('n_nan')
            .drop_duplicates(subset=['sensor', 'datetime'], keep='first')
            .drop(columns='n_nan'))

    log.info(f"Dropped {n_before - len(df)} duplicate rows, {len(df)} records remain")

    return df.set_index(['sensor', 'datetime']).to_xarray()

def add_metadata(ds, params):
    ds.attrs = {
        'campaign':       'AERLIFT',
        'instrument':     'Aranet4',
        'stage':          'munged',
        'created':        datetime.now().isoformat(),
        'script':         'workflow/scripts/munge/aranet.py',
        'timezone_local': params.timezone,
        'time_reference': 'UTC',
        'Conventions':    'CF-1.8',
        'institution':    'UC Berkeley School of Public Health',
        'creator_name':   'Mark Campmier, PhD',
    }
    if getattr(params, 'synthetic', None) == 'true':
        ds.attrs['SYNTHETIC'] = 'true'
    ds['co2'].attrs         = {'long_name': 'carbon dioxide mixing ratio',
                               'units': 'ppm', 'instrument': 'Aranet4'}
    ds['temperature'].attrs = {'long_name': 'ambient temperature',
                               'units': 'degC', 'instrument': 'Aranet4'}
    ds['rh'].attrs          = {'long_name': 'relative humidity',
                               'units': '%', 'instrument': 'Aranet4'}
    ds['pressure'].attrs    = {'long_name': 'atmospheric pressure',
                               'units': 'hPa', 'instrument': 'Aranet4'}
    return ds

# ── main ──────────────────────────────────────────────────────────────────────
log.info("Starting Aranet4 munging")

ds_aranet = process_aranet(snakemake.params)
log.info(f"Processed {len(get_files(snakemake.params.raw_dir))} files")

ds_aranet = add_metadata(ds_aranet, snakemake.params)

# summary csv
files = get_files(snakemake.params.raw_dir)
summary = pd.DataFrame({
    'n_files':        [len(files)],
    'n_records':      [ds_aranet.sizes['datetime']],
    'co2_mean':       [float(ds_aranet['co2'].mean())],
    'co2_max':        [float(ds_aranet['co2'].max())],
    'temp_mean':      [float(ds_aranet['temperature'].mean())],
    'rh_mean':        [float(ds_aranet['rh'].mean())],
})
summary.to_csv(snakemake.output.csv, index=False)
log.info(f"Wrote {snakemake.output.csv}")

# netcdf
out_path = Path(snakemake.output.nc)
out_path.parent.mkdir(parents=True, exist_ok=True)
ds_aranet.to_netcdf(
    out_path,
    encoding={v: {'zlib': True, 'complevel': 4}
              for v in ['co2', 'temperature', 'rh', 'pressure']}
)
log.info(f"Wrote {out_path}")