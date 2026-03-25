from pathlib import Path
from datetime import datetime, timezone
import logging
import xarray as xr

try:
    snakemake
except NameError:
    class snakemake:
        class params:
            start   = '2022-09-01'
            end     = '2023-03-31'
            exclude = ['16A28']
            instrument = 'aranet'
        class input:
            nc = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/aranet.nc'
        class output:
            nc = '/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/2_trimmed/aranet.nc'
        log = ['/dev/null']

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

# ── functions ─────────────────────────────────────────────────────────────────
def trim(ds, start, end, exclude):
    n_before = ds.sizes['datetime']

    # time bounds
    ds = ds.sel(datetime=slice(start, end))
    log.info(f"Time trim: {n_before} → {ds.sizes['datetime']} records "
             f"({n_before - ds.sizes['datetime']} removed)")

    # sensor exclusion
    if exclude:
        sensors_before = list(ds.sensor.values)
        sensors_keep   = [s for s in sensors_before if s not in exclude]
        sensors_dropped = [s for s in sensors_before if s in exclude]
        ds = ds.sel(sensor=sensors_keep)
        log.info(f"Excluded sensors: {sensors_dropped}")
        log.info(f"Retained sensors: {sensors_keep}")
    else:
        log.info("No sensors excluded")

    return ds

def update_metadata(ds, params):
    ds.attrs['stage']         = 'trimmed'
    ds.attrs['trim_start']    = params.start
    ds.attrs['trim_end']      = params.end
    ds.attrs['trim_excluded'] = str(params.exclude)
    ds.attrs['trimmed']      = datetime.now(timezone.utc).isoformat()
    return ds

# ── main ──────────────────────────────────────────────────────────────────────
log.info(f"Starting trim for {snakemake.params.instrument}")

ds = xr.open_dataset(snakemake.input.nc)
log.info(f"Loaded {snakemake.input.nc}")

ds = trim(ds,
          start   = snakemake.params.start,
          end     = snakemake.params.end,
          exclude = snakemake.params.exclude)

ds = update_metadata(ds, snakemake.params)

# save
out_path = Path(snakemake.output.nc)
out_path.parent.mkdir(parents=True, exist_ok=True)

import numpy as np
num_vars = [v for v in ds.data_vars
            if ds[v].dtype in [np.float32, np.float64, np.int32, np.int64]]
ds.to_netcdf(
    out_path,
    encoding={v: {'zlib': True, 'complevel': 4} for v in num_vars}
)
log.info(f"Wrote {out_path}")