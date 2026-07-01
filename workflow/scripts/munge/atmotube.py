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
            nc  = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/atmotube.nc'
            csv = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/atmotube_summary.csv'
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
    path = Path(raw_dir.strip()) / 'atmotube'
    files = list(path.glob(f'*{ext}'))
    assert len(files) > 0, f"No {ext} files found in {path}"
    return files

def parse_sensor_id(file):
    return file.stem.split('_')[0]

def read_atmotube_file(file, timezone):
    df = pd.read_csv(file)
    df.columns = ['datetime','aqs', 'pm1', 'pm25', 'pm10',
                  'temperature', 'rh', 'pressure', 'tvoc_index', 'tvoc',
                  'nox_index', 'co2', 'latitude', 'longitude', 'altitude',
                  'position_error', 'battery', 'charging', 'motion', 'phone_gps']
    df.index = (pd.to_datetime(df['datetime'], format='%d/%m/%Y %H:%M')
                  .dt.tz_localize(timezone)
                  .dt.tz_convert('UTC')
                  .dt.tz_localize(None))
    df.index.name = 'datetime'
    df = df.drop(columns='datetime')
    df['sensor'] = parse_sensor_id(file)
    return df


def process_atmotube(params):
    files = get_files(params.raw_dir)
    lst_df = [
        read_atmotube_file(file, timezone=params.timezone)
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
        'instrument':     'Atmotube',
        'stage':          'munged',
        'created':        datetime.now().isoformat(),
        'script':         'workflow/scripts/munge/atmotube.py',
        'timezone_local': params.timezone,
        'time_reference': 'UTC',
        'Conventions':    'CF-1.8',
        'institution':    'UC Berkeley School of Public Health',
        'creator_name':   'Mark Campmier, PhD',
    }
    ds['aqs'].attrs         = {'long_name': 'air quality score',
                               'units': 'None', 'instrument': 'Atmotube'}
    ds['pm1'].attrs = {'long_name': 'PM1 mass concentration',
                               'units': 'µg/m3', 'instrument': 'Atmotube'}
    ds['pm25'].attrs = {'long_name': 'PM2.5 mass concentration',
                       'units': 'µg/m3', 'instrument': 'Atmotube'}
    ds['pm10'].attrs = {'long_name': 'PM10 mass concentration',
                       'units': 'µg/m3', 'instrument': 'Atmotube'}
    ds['temperature'].attrs = {'long_name': 'temperature',
                               'units': '°C', 'instrument': 'Atmotube'}
    ds['rh'].attrs          = {'long_name': 'relative humidity',
                               'units': '%', 'instrument': 'Atmotube'}
    ds['pressure'].attrs    = {'long_name': 'atmospheric pressure',
                               'units': 'hPa', 'instrument': 'Atmotube'}
    ds['tvoc_index'].attrs  = {'long_name': 'total VOC index',
                               'units': 'None', 'instrument': 'Atmotube'}
    ds['tvoc'].attrs    = {'long_name': 'total VOC concentration',
                               'units': 'ppm', 'instrument': 'Atmotube'}
    ds['nox_index'].attrs  = {'long_name': 'NOx index',
                               'units': 'None', 'instrument': 'Atmotube'}
    ds['co2'].attrs    = {'long_name': 'CO2 concentration',
                               'units': 'ppm', 'instrument': 'Atmotube'}
    return ds

# ── main ──────────────────────────────────────────────────────────────────────
log.info("Starting atmotube munging")

ds_atmotube = process_atmotube(snakemake.params)
log.info(f"Processed {len(get_files(snakemake.params.raw_dir))} files")

ds_atmotube = add_metadata(ds_atmotube, snakemake.params)

# summary csv
files = get_files(snakemake.params.raw_dir)
summary = pd.DataFrame({
    'n_files':        [len(files)],
    'n_records':      [ds_atmotube.sizes['datetime']],
    'aqs_mean':       [float(ds_atmotube['aqs'].mean())],
    'pm1_mean':       [float(ds_atmotube['pm1'].mean())],
    'pm1_max':        [float(ds_atmotube['pm1'].max())],
    'pm25_mean':      [float(ds_atmotube['pm25'].mean())],
    'pm25_max':       [float(ds_atmotube['pm25'].max())],
    'pm10_mean':      [float(ds_atmotube['pm10'].mean())],
    'pm10_max':       [float(ds_atmotube['pm10'].max())],
    'tvoc_mean':      [float(ds_atmotube['tvoc'].mean())],
    'tvoc_max':       [float(ds_atmotube['tvoc'].max())],
    'tvoc_index_mean':[float(ds_atmotube['tvoc_index'].mean())],
    'nox_index_mean': [float(ds_atmotube['nox_index'].mean())],
    'co2_mean':       [float(ds_atmotube['co2'].mean())],
    'co2_max':        [float(ds_atmotube['co2'].max())],
    'temp_mean':      [float(ds_atmotube['temperature'].mean())],
    'rh_mean':        [float(ds_atmotube['rh'].mean())],
    'pressure_mean':  [float(ds_atmotube['pressure'].mean())]
})
summary.to_csv(snakemake.output.csv, index=False)
log.info(f"Wrote {snakemake.output.csv}")

# netcdf
out_path = Path(snakemake.output.nc)
out_path.parent.mkdir(parents=True, exist_ok=True)
ds_atmotube.to_netcdf(
    out_path,
    encoding={v: {'zlib': True, 'complevel': 4}
              for v in ['aqs', 'pm1', 'pm25', 'pm10', 'temperature', 'rh', 'pressure',
                        'tvoc_index', 'tvoc', 'nox_index', 'co2']}
)
log.info(f"Wrote {out_path}")