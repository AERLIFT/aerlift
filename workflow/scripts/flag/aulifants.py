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
            flag_bits  = {4: 'voltage_negative', 8: 'voltage_high'}
            thresholds = {
                'voltage_min': 0.0,
                'voltage_max': 240.0,
            }
            instrument = 'aulifants'
        class input:
            nc = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/2_trimmed/aulifants.nc'
        class output:
            nc  = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged/aulifants.nc'
            csv = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged/aulifants_flags.csv'
        log = ['/dev/null']

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

# ── flag logic ────────────────────────────────────────────────────────────────
def flag_aulifants(ds, thresholds, flag_bits):
    t = thresholds

    f = init_flag(ds, 'voltage')
    f = apply_flag(f, ds['voltage'] < t['voltage_min'], 4)
    f = apply_flag(f, ds['voltage'] > t['voltage_max'], 8)
    ds['flag_voltage'] = f
    ds['flag_voltage'].attrs = {
        'long_name': 'quality flag for voltage',
        'flag_bits': str(flag_bits),
        'bit_4':     'voltage_negative',
        'bit_8':     'voltage_high',
    }

    ds['flag_global'] = compute_flag_global(ds, ['flag_voltage'])
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
log.info("Starting Aulifants flagging")

ds = xr.open_dataset(snakemake.input.nc)
log.info(f"Loaded {snakemake.input.nc}: {dict(ds.sizes)}")

flag_bits  = {int(k): v for k, v in snakemake.params.flag_bits.items()}
thresholds = snakemake.params.thresholds

ds = flag_aulifants(ds, thresholds, flag_bits)
ds = update_metadata(ds)

# summary csv
all_bits = {1: 'out_of_range', **flag_bits}
summary  = flag_summary(ds, ['flag_voltage'], all_bits)
summary.to_csv(snakemake.output.csv, index=False)
log.info(f"Wrote {snakemake.output.csv}")

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
