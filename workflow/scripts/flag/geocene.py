from pathlib import Path
from datetime import datetime, timezone
import logging
import numpy as np
import xarray as xr
import sys

sys.path.append(str(Path(__file__).parent))
from utils import flag_summary

try:
    snakemake
except NameError:

    class snakemake:
        class params:
            flag_bits = {}
            thresholds = {}
            instrument = "geocene"

        class input:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/2_trimmed/geocene.nc"

        class output:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged/geocene.nc"
            csv = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged/geocene_flags.csv"

        log = ["/dev/null"]


# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ── flag logic ────────────────────────────────────────────────────────────────
def flag_geocene(
    ds: xr.Dataset, thresholds: dict[str, float], flag_bits: dict[int, str]
) -> xr.Dataset:
    """Flag Geocene data (currently just identity/placeholder)
    Args:
        ds: xarray dataset with Geocene data
        thresholds: dictionary of thresholds for each flag
        flag_bits: dictionary of flag bit descriptions
    Returns:
        ds: xarray dataset
    """
    # For now, we don't have specific flags for Geocene events,
    # but we'll add a flag_global for consistency.
    ds["flag_global"] = xr.DataArray(
        np.zeros(ds["processor_name"].shape, dtype=np.uint32),
        coords=ds.coords,
        dims=ds["processor_name"].dims,
    )
    ds["flag_global"].attrs = {
        "long_name": "global quality flag — bitwise OR of all flag variables",
        "flag_bits": str({}),
    }

    return ds


def update_metadata(ds: xr.Dataset) -> xr.Dataset:
    """Update metadata for flagged Geocene dataset
    Args:
        ds: xarray dataset with Geocene flags added
    Returns:
        ds: xarray dataset with updated metadata
    """
    ds.attrs["stage"] = "flagged"
    ds.attrs["flagged"] = datetime.now(timezone.utc).isoformat()
    return ds


if __name__ == "__main__":
    # ── main ──────────────────────────────────────────────────────────────────────
    log.info("Starting Geocene flagging")

    ds = xr.open_dataset(snakemake.input.nc)
    log.info(f"Loaded {snakemake.input.nc}: {dict(ds.sizes)}")

    flag_bits = {int(k): v for k, v in snakemake.params.flag_bits.items()}
    thresholds = snakemake.params.thresholds

    ds = flag_geocene(ds, thresholds, flag_bits)
    ds = update_metadata(ds)

    # summary csv
    summary = flag_summary(
        ds,
        {},
    )
    summary.to_csv(snakemake.output.csv, index=False)
    log.info(f"Wrote {snakemake.output.csv}")

    # netcdf
    out_path = Path(snakemake.output.nc)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    num_vars = [
        v
        for v in ds.data_vars
        if ds[v].dtype
        in [np.float32, np.float64, np.int32, np.int64, np.int16, np.uint32]
    ]
    ds.to_netcdf(
        out_path, encoding={v: {"zlib": True, "complevel": 4} for v in num_vars}
    )
    log.info(f"Wrote {out_path}")
