from pathlib import Path
from datetime import datetime, timezone
import logging
import numpy as np
import xarray as xr
from typing import Any

try:
    snakemake
except NameError:

    class snakemake:
        class params:
            start = "2022-09-01"
            end = "2023-03-31"
            exclude = []
            instrument = "hhb"

        class input:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/hhb.nc"

        class output:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/2_trimmed/hhb.nc"

        log = ["/dev/null"]


# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ── functions ─────────────────────────────────────────────────────────────────
def get_encoding(
    ds: xr.Dataset, skip_extra: list[str] | None = None
) -> dict[str, dict]:
    """Get encoding dict for netCDF file. Skips extra variables from lab samples (e.g., UPAS filters)
    Args:
        ds: xarray Dataset to trim by time-index
        skip_extra: list of extra variables to skip
    Returns:
        encoding: dict of variables to time-index encode
    """
    skip = set(ds.coords) | {
        "SampleName",
        "LogFilename",
        "CartridgeID",
        "StartDateTimeUTC",
        "UserTZ",
    }
    if skip_extra:
        skip |= set(skip_extra)

    encoding = {
        v: {"zlib": True, "complevel": 4}
        for v in ds.data_vars
        if v not in skip and np.issubdtype(ds[v].dtype, np.number)
    }

    if "datetime" in ds.coords:
        encoding["datetime"] = {
            "dtype": "float64",
            "units": "seconds since 1970-01-01",
            "calendar": "proleptic_gregorian",
        }

    return encoding


def trim(ds: xr.Dataset, start: str, end: str, exclude: list[str]) -> xr.Dataset:
    """Trim operation to cut out unwanted data outside time bounds.
    Args:
        ds: xarray dataset to trim
        start: start date of time bounds
        end: end date of time bounds
        exclude: list of sensors/geographies to exclude from dataset
    Returns:
        ds: xarray dataset with time bounds and sensors/geography trimmed
    """
    n_before = ds.sizes["datetime"]

    # time bounds
    ds = ds.sel(datetime=slice(start, end))
    log.info(
        f"Time trim: {n_before} → {ds.sizes['datetime']} records "
        f"({n_before - ds.sizes['datetime']} removed)"
    )

    # sensor exclusion
    if exclude:
        sensors_before = list(ds.sensor.values)
        sensors_keep = [s for s in sensors_before if s not in exclude]
        sensors_dropped = [s for s in sensors_before if s in exclude]
        ds = ds.sel(sensor=sensors_keep)
        log.info(f"Excluded sensors: {sensors_dropped}")
        log.info(f"Retained sensors: {sensors_keep}")
    else:
        log.info("No sensors excluded")

    return ds


def update_metadata(ds: xr.Dataset, params: Any) -> xr.Dataset:
    """Update metadata with trim parameters.
    Args:
        ds: xarray dataset to update metadata on
        params: snakemake params object including start, end, and exclude
    Returns:
        ds: xarray dataset with updated metadata
    """
    ds.attrs["stage"] = "trimmed"
    ds.attrs["trim_start"] = params.start
    ds.attrs["trim_end"] = params.end
    ds.attrs["trim_excluded"] = str(params.exclude)
    ds.attrs["trimmed"] = datetime.now(timezone.utc).isoformat()
    return ds


if __name__ == "__main__":
    # ── main ──────────────────────────────────────────────────────────────────────
    log.info(f"Starting trim for {snakemake.params.instrument}")

    ds = xr.open_dataset(snakemake.input.nc)
    log.info(f"Loaded {snakemake.input.nc}: {dict(ds.sizes)}")

    ds = trim(
        ds,
        start=snakemake.params.start,
        end=snakemake.params.end,
        exclude=snakemake.params.exclude,
    )

    ds = update_metadata(ds, snakemake.params)

    # save
    out_path = Path(snakemake.output.nc)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ds.to_netcdf(out_path, encoding=get_encoding(ds))
    log.info(f"Wrote {out_path}")
