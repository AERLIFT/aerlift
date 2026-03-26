from pathlib import Path
from datetime import datetime, timezone
import logging
import numpy as np
import xarray as xr
import pandas as pd
import sys

sys.path.append(str(Path(__file__).parent))
from utils import apply_flag, init_flag, flag_summary, compute_flag_global

try:
    snakemake
except NameError:
    class snakemake:
        class params:
            flag_bits  = {4: 'pm_negative', 8: 'electrochemical_warmup'}
            thresholds = {
                'pm_min':           0.0,
                'warmup_minutes':   5,
                'temperature_min':  -5.0,
                'temperature_max':  50.0,
                'rh_min':           0.0,
                'rh_max':           100.0,
                'voc_raw_min':      0.0,
                'nox_raw_min':      0.0,
                'co2_min':          400.0,
                'co2_max':          5000.0,
            }
            alphasense = {'position_1': 'NO2', 'position_2': 'O3'}
            instrument = 'hhb'
        class input:
            nc = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/2_trimmed/hhb.nc'
        class output:
            nc  = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged/hhb.nc'
            csv = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged/hhb_flags.csv'
        log = ['/dev/null']

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

# ── flag logic ────────────────────────────────────────────────────────────────
def get_warmup_mask(ds, warmup_minutes):
    """Flag first N minutes per sensor session as warmup"""
    warmup_td = pd.Timedelta(minutes=warmup_minutes)
    datetimes = pd.DatetimeIndex(ds.datetime.values)
    mask = xr.zeros_like(ds['sen_pm25_raw'], dtype=bool)
    for sensor in ds.sensor.values:
        first_ts = datetimes.min()
        cutoff   = first_ts + warmup_td
        warmup   = datetimes < cutoff
        mask.loc[dict(sensor=sensor)] = xr.DataArray(warmup, dims='datetime')
    return mask

def flag_hhb(ds, thresholds, flag_bits, alphasense):
    t  = thresholds
    g1 = f"{alphasense['position_1']}_algorithm1"
    g2 = f"{alphasense['position_2']}_algorithm1"

    warmup_mask = get_warmup_mask(ds, t['warmup_minutes'])

    # ── PM variables ──────────────────────────────────────────────────────────
    for var in ['sen_pm1_raw', 'sen_pm25_raw', 'sen_pm4_raw', 'sen_pm10_raw']:
        f = init_flag(ds, var)
        f = apply_flag(f, ds[var] < t['pm_min'], 4)   # pm_negative
        f = apply_flag(f, warmup_mask,            8)   # electrochemical_warmup
        ds[f'flag_{var}'] = f
        ds[f'flag_{var}'].attrs = {
            'long_name': f'quality flag for {var}',
            'flag_bits': str(flag_bits),
            'bit_4':     'pm_negative',
            'bit_8':     'electrochemical_warmup',
        }

    # ── met ───────────────────────────────────────────────────────────────────
    for var, vmin, vmax in [
        ('sen_temperature', t['temperature_min'], t['temperature_max']),
        ('sen_rh',          t['rh_min'],          t['rh_max']),
    ]:
        f = init_flag(ds, var)
        f = apply_flag(f, ds[var] < vmin, 1)
        f = apply_flag(f, ds[var] > vmax, 1)
        ds[f'flag_{var}'] = f
        ds[f'flag_{var}'].attrs = {
            'long_name': f'quality flag for {var}',
            'bit_1':     'out_of_range',
        }

    # ── raw signals ───────────────────────────────────────────────────────────
    for var, vmin in [
        ('sen_voc_raw', t['voc_raw_min']),
        ('sen_nox_raw', t['nox_raw_min']),
    ]:
        f = init_flag(ds, var)
        f = apply_flag(f, ds[var] < vmin, 1)
        ds[f'flag_{var}'] = f
        ds[f'flag_{var}'].attrs = {
            'long_name': f'quality flag for {var}',
            'bit_1':     'out_of_range',
        }

    # ── CO2 ───────────────────────────────────────────────────────────────────
    f = init_flag(ds, 'scd30_co2')
    f = apply_flag(f, ds['scd30_co2'] < t['co2_min'], 1)
    f = apply_flag(f, ds['scd30_co2'] > t['co2_max'], 1)
    ds['flag_scd30_co2'] = f
    ds['flag_scd30_co2'].attrs = {
        'long_name': 'quality flag for scd30_co2',
        'bit_1':     'out_of_range',
    }

    # ── electrochemical ───────────────────────────────────────────────────────
    for var in [g1, g2]:
        f = init_flag(ds, var)
        f = apply_flag(f, warmup_mask, 8)   # electrochemical_warmup
        ds[f'flag_{var}'] = f
        ds[f'flag_{var}'].attrs = {
            'long_name': f'quality flag for {var}',
            'bit_8':     'electrochemical_warmup',
        }

    # ── flag_global ───────────────────────────────────────────────────────────
    flag_vars = [
        'flag_sen_pm1_raw', 'flag_sen_pm25_raw',
        'flag_sen_pm4_raw', 'flag_sen_pm10_raw',
        'flag_sen_temperature', 'flag_sen_rh',
        'flag_sen_voc_raw', 'flag_sen_nox_raw',
        'flag_scd30_co2',
        f'flag_{g1}', f'flag_{g2}',
    ]
    ds['flag_global'] = compute_flag_global(ds, flag_vars)
    ds['flag_global'].attrs = {
        'long_name': 'global quality flag — bitwise OR of all flag variables',
        'flag_bits': str({1: 'out_of_range', **flag_bits}),
    }

    return ds, flag_vars

def update_metadata(ds):
    ds.attrs['stage']   = 'flagged'
    ds.attrs['flagged'] = datetime.now(timezone.utc).isoformat()
    return ds

# ── main ──────────────────────────────────────────────────────────────────────
log.info("Starting HHB flagging")

ds = xr.open_dataset(snakemake.input.nc)
log.info(f"Loaded {snakemake.input.nc}: {dict(ds.sizes)}")

flag_bits  = {int(k): v for k, v in snakemake.params.flag_bits.items()}
thresholds = snakemake.params.thresholds
alphasense = snakemake.params.alphasense

ds, flag_vars = flag_hhb(ds, thresholds, flag_bits, alphasense)
ds = update_metadata(ds)

# summary csv
all_bits = {1: 'out_of_range', **flag_bits}
summary  = flag_summary(ds, flag_vars, all_bits)
summary.to_csv(snakemake.output.csv, index=False)
log.info(f"Wrote {snakemake.output.csv}")
log.info(f"\n{summary.to_string()}")

# netcdf
out_path = Path(snakemake.output.nc)
out_path.parent.mkdir(parents=True, exist_ok=True)

num_vars = [v for v in ds.data_vars
            if ds[v].dtype in [np.float32, np.float64,
                                np.int32, np.int64, np.int16]]
ds.to_netcdf(
    out_path,
    encoding={v: {'zlib': True, 'complevel': 4} for v in num_vars}
)
log.info(f"Wrote {out_path}")