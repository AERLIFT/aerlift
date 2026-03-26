from pathlib import Path
from datetime import datetime, timezone
import logging
import numpy as np
import xarray as xr
import sys

sys.path.append(str(Path(__file__).parent))
from utils import apply_flag, init_flag, flag_summary, compute_flag_global

try:
    snakemake
except NameError:
    class snakemake:
        class params:
            flag_bits  = {4: 'co2_low', 8: 'co2_high'}
            thresholds = {
                'co2_min':         400.0,
                'co2_max':         5000.0,
                'temperature_min': -5.0,
                'temperature_max': 50.0,
                'rh_min':          0.0,
                'rh_max':          100.0,
                'pressure_min':    950.0,
                'pressure_max':    1050.0,
            }
            instrument = 'aranet'
        class input:
            nc = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/2_trimmed/aranet.nc'
        class output:
            nc  = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged/aranet.nc'
            csv = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged/aranet_flags.csv'
        log = ['/dev/null']

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

# ── flag logic ────────────────────────────────────────────────────────────────
def flag_aranet(ds, thresholds, flag_bits):
    t = thresholds

    # flag_co2
    f = init_flag(ds, 'co2')
    f = apply_flag(f, ds['co2'] < t['co2_min'],  4)   # co2_low
    f = apply_flag(f, ds['co2'] > t['co2_max'],  8)   # co2_high
    ds['flag_co2'] = f
    ds['flag_co2'].attrs = {
        'long_name': 'quality flag for co2',
        'flag_bits': str(flag_bits),
        'bit_4':     'co2_low',
        'bit_8':     'co2_high',
    }

    # flag_temperature
    f = init_flag(ds, 'temperature')
    f = apply_flag(f, ds['temperature'] < t['temperature_min'], 1)
    f = apply_flag(f, ds['temperature'] > t['temperature_max'], 1)
    ds['flag_temperature'] = f
    ds['flag_temperature'].attrs = {
        'long_name': 'quality flag for temperature',
        'bit_1':     'out_of_range',
    }

    # flag_rh
    f = init_flag(ds, 'rh')
    f = apply_flag(f, ds['rh'] < t['rh_min'], 1)
    f = apply_flag(f, ds['rh'] > t['rh_max'], 1)
    ds['flag_rh'] = f
    ds['flag_rh'].attrs = {
        'long_name': 'quality flag for rh',
        'bit_1':     'out_of_range',
    }

    # flag_pressure
    f = init_flag(ds, 'pressure')
    f = apply_flag(f, ds['pressure'] < t['pressure_min'], 1)
    f = apply_flag(f, ds['pressure'] > t['pressure_max'], 1)
    ds['flag_pressure'] = f
    ds['flag_pressure'].attrs = {
        'long_name': 'quality flag for pressure',
        'bit_1':     'out_of_range',
    }

    # flag_global
    flag_vars = ['flag_co2', 'flag_temperature', 'flag_rh', 'flag_pressure']
    ds['flag_global'] = compute_flag_global(ds, flag_vars)
    ds['flag_global'].attrs = {
        'long_name': 'global quality flag — bitwise OR of all flag variables',
        'flag_bits': str({1: 'out_of_range', **flag_bits}),
    }

    return ds

def update_metadata(ds):
    ds.attrs['stage']   = 'flagged'
    ds.attrs['flagged'] = datetime.now(timezone.utc).isoformat()
    return ds

# ── main ──────────────────────────────────────────────────────────────────────
log.info("Starting Aranet4 flagging")

ds = xr.open_dataset(snakemake.input.nc)
log.info(f"Loaded {snakemake.input.nc}: {dict(ds.sizes)}")

flag_bits  = {int(k): v for k, v in snakemake.params.flag_bits.items()}
thresholds = snakemake.params.thresholds

ds = flag_aranet(ds, thresholds, flag_bits)
ds = update_metadata(ds)

# summary csv
all_bits  = {1: 'out_of_range', **flag_bits}
flag_vars = ['flag_co2', 'flag_temperature', 'flag_rh', 'flag_pressure']
summary   = flag_summary(ds, flag_vars, all_bits)
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