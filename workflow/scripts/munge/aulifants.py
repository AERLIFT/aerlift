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
            nc  = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/aulifants.nc'
            csv = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/aulifants_summary.csv'
        log = ['/dev/null']

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

# ── functions ─────────────────────────────────────────────────────────────────
def get_files(raw_dir, ext='.CSV'):
    path = Path(raw_dir.strip()) / 'aulifants'
    files = [f for f in path.rglob(f'*{ext}')
             if f.name.upper().endswith('-D.CSV')]
    assert len(files) > 0, f"No *-D{ext} files found in {path}"
    return files, path

def parse_sensor_id(file):
    device, date = file.parent.stem.split('-Aulifant4-')
    return device, date

def _strip_units(series):
    """Extract leading numeric value from strings like '112.3Volt', '  0.00Amp', '$0.00 '."""
    return pd.to_numeric(
        series.astype(str).str.replace(r'[^\d.]', '', regex=True),
        errors='coerce'
    )

def read_aulifants_file(file, timezone):
    df = pd.read_csv(file,
                     header=None,
                     usecols=[0, 1, 2, 3, 4, 5, 6])
    df.columns = ['time', 'voltage', 'current', 'power', 'power_factor',
                  'cummulative_energy', 'cost']
    for col in ['voltage', 'current', 'power', 'cummulative_energy', 'cost']:
        df[col] = _strip_units(df[col])
    df['power_factor'] = pd.to_numeric(df['power_factor'], errors='coerce')
    device, date = parse_sensor_id(file)
    df['sensor'] = device
    df['datetime'] = pd.to_datetime(date +' '+ df['time'], format='%Y-%m-%d %H:%M:%S')
    df.index = (df['datetime']
                  .dt.tz_localize(timezone, ambiguous='NaT')
                  .dt.tz_convert('UTC')
                  .dt.tz_localize(None))
    df.index.name = 'datetime'
    df = df.drop(columns=['datetime', 'time'])
    return df

def process_aulifants(params):
    files, _ = get_files(params.raw_dir)
    lst_df = [
        read_aulifants_file(file, timezone=params.timezone)
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
        'instrument':     'Aulifants',
        'stage':          'munged',
        'created':        datetime.now().isoformat(),
        'script':         'workflow/scripts/munge/aulifants.py',
        'timezone_local': params.timezone,
        'time_reference': 'UTC',
        'Conventions':    'CF-1.8',
        'institution':    'UC Berkeley School of Public Health',
        'creator_name':   'Mark Campmier, PhD',
    }
    if getattr(params, 'synthetic', None) == 'true':
        ds.attrs['SYNTHETIC'] = 'true'
    ds['voltage'].attrs         = {'long_name': 'Voltage',
                               'units': 'V', 'instrument': 'Aulifants'}
    ds['current'].attrs = {'long_name': 'Current',
                               'units': 'A', 'instrument': 'Aulifants'}
    ds['power'].attrs = {'long_name': 'Power',
                       'units': 'W', 'instrument': 'Aulifants'}
    ds['power_factor'].attrs = {'long_name': 'Power Factor',
                       'units': '', 'instrument': 'Aulifants'}
    ds['cummulative_energy'].attrs = {'long_name': 'Cumulative energy',
                               'units': 'kWh', 'instrument': 'Aulifants'}
    ds['cost'].attrs          = {'long_name': 'Energy cost',
                               'units': 'USD', 'instrument': 'Atmotube'}
    return ds

# ── main ──────────────────────────────────────────────────────────────────────
log.info("Starting Aulifants munging")

ds_aulifants = process_aulifants(snakemake.params)
_auli_files, _ = get_files(snakemake.params.raw_dir)
log.info(f"Processed {len(_auli_files)} files")

ds_aulifants = add_metadata(ds_aulifants, snakemake.params)

# summary csv
_sum_files, _ = get_files(snakemake.params.raw_dir)
summary = pd.DataFrame({
    'n_files':        [len(_sum_files)],
    'n_records':      [ds_aulifants.sizes['datetime']],
    'voltage_mean':   [float(ds_aulifants['voltage'].mean())],
    'voltage_max':    [float(ds_aulifants['voltage'].max())],
    'current_mean':   [float(ds_aulifants['current'].mean())],
    'current_max':    [float(ds_aulifants['current'].max())],
    'power_mean':     [float(ds_aulifants['power'].mean())],
    'power_max':      [float(ds_aulifants['power'].max())],
    'power_factor_mean':[float(ds_aulifants['power_factor'].mean())],
    'power_factor_max':[float(ds_aulifants['power_factor'].max())],
    'cummulative_energy_mean':[float(ds_aulifants['cummulative_energy'].mean())],
    'cummulative_energy_max':[float(ds_aulifants['cummulative_energy'].max())],
})
summary.to_csv(snakemake.output.csv, index=False)
log.info(f"Wrote {snakemake.output.csv}")

# netcdf
out_path = Path(snakemake.output.nc)
out_path.parent.mkdir(parents=True, exist_ok=True)
ds_aulifants.to_netcdf(
    out_path,
    encoding={v: {'zlib': True, 'complevel': 4}
              for v in ['voltage', 'current', 'power', 'power_factor',
                        'cummulative_energy', 'cost']}
)
log.info(f"Wrote {out_path}")
