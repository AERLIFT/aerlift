from pathlib import Path
from datetime import datetime, timezone
import logging
import numpy as np
import pandas as pd
import xarray as xr

# ── dev shim ──────────────────────────────────────────────────────────────────
try:
    snakemake
except NameError:

    class snakemake:
        class params:
            period = "1hour"
            freq = "1h"
            completeness = 0.75

        class input:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/4_merged_synth/merge.nc"

        class output:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/5_network_synth/network_1hour.nc"

        log = ["/dev/null"]


# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ── constants ─────────────────────────────────────────────────────────────────
# merge.py renames every variable as "{sensor}_sensor_id_{var}", so the token
# below marks the boundary between the sensor prefix and the measurement name.
SENSOR_MARKER = "_sensor_id_"


# ── network logic ─────────────────────────────────────────────────────────────
def select_measurement_vars(ds: xr.Dataset) -> list[str]:
    """Select the numeric measurement variables to carry into the network stage.

    Flag variables (anything containing ``_flag_``) and non-numeric columns
    (e.g. SampleName, CartridgeID) are dropped — the flags are applied first and
    then discarded to save space.
    Args:
        ds: merged xarray dataset
    Returns:
        list of measurement variable names to aggregate
    """
    measurement = []
    for v in ds.data_vars:
        if "_flag_" in v:
            continue
        if not np.issubdtype(ds[v].dtype, np.number):
            continue
        measurement.append(v)
    return measurement


def flag_var_for(ds: xr.Dataset, var: str) -> str | None:
    """Resolve the flag variable that governs a measurement variable.

    Prefers the per-variable flag (``{prefix}_flag_{suffix}``); if none exists
    falls back to the instrument's ``{prefix}_flag_global`` bitwise-OR flag.
    Args:
        ds: merged xarray dataset
        var: measurement variable name
    Returns:
        name of the governing flag variable, or None if the sensor prefix or
        flag is absent
    """
    i = var.find(SENSOR_MARKER)
    if i == -1:
        return None
    prefix = var[: i + len(SENSOR_MARKER)]
    suffix = var[i + len(SENSOR_MARKER) :]

    specific = f"{prefix}flag_{suffix}"
    if specific in ds:
        return specific

    flag_global = f"{prefix}flag_global"
    return flag_global if flag_global in ds else None


def apply_flags(ds: xr.Dataset, measurement_vars: list[str]) -> tuple[xr.Dataset, int]:
    """Mask flagged records (0 = good, any set bit = bad) to NaN and drop flags.
    Args:
        ds: merged xarray dataset with measurement and flag variables
        measurement_vars: measurement variables to keep and flag
    Returns:
        ds_masked: dataset holding only measurement variables, bad records NaN'd
        n_masked: number of (household, time) records set to NaN
    """
    ds_masked = ds[measurement_vars].copy()
    n_masked = 0
    for v in measurement_vars:
        fv = flag_var_for(ds, v)
        if fv is None:
            continue
        bad = ds[fv] > 0  # NaN > 0 is False → gaps stay untouched (already NaN)
        ds_masked[v] = ds_masked[v].where(~bad)
        n_masked += int(bad.sum())
    return ds_masked, n_masked


def native_interval_s(da: xr.DataArray) -> float:
    """Infer a variable's native sampling interval in seconds.

    Uses the median spacing between timestamps that carry at least one non-null
    value across households, so completeness is measured against the sensor's
    own cadence rather than the merged (union) grid.
    Args:
        da: measurement DataArray with a ``datetime`` dimension
    Returns:
        median native interval in seconds, or NaN if fewer than two samples
    """
    other_dims = [d for d in da.dims if d != "datetime"]
    present = da.notnull().any(other_dims) if other_dims else da.notnull()
    times = da["datetime"].values[present.values]
    if len(times) < 2:
        return float("nan")
    return float(np.median(np.diff(times).astype("timedelta64[s]").astype(float)))


def gate_by_completeness(
    mean: xr.DataArray,
    valid_count: xr.DataArray,
    expected: float,
    completeness: float,
) -> xr.DataArray:
    """Blank aggregated bins that fall below the completeness threshold.
    Args:
        mean: aggregated (mean) values per bin
        valid_count: number of non-null native samples per bin
        expected: expected number of native samples per bin
        completeness: minimum required fraction of expected samples [0, 1]
    Returns:
        mean with under-sampled bins set to NaN
    """
    if not np.isfinite(expected) or expected <= 0:
        return xr.full_like(mean, np.nan)
    coverage = valid_count / expected
    return mean.where(coverage >= completeness)


def aggregate_binned(
    ds_masked: xr.Dataset, freq: str, completeness: float
) -> xr.Dataset:
    """Resample every variable to a fixed period, gated by completeness.
    Args:
        ds_masked: flag-masked measurement dataset
        freq: pandas resample frequency (e.g. "5min", "1h", "1D")
        completeness: minimum required fraction of expected samples per bin
    Returns:
        aggregated xarray dataset on the resampled datetime grid
    """
    bin_seconds = pd.Timedelta(freq).total_seconds()
    aggregated = {}
    for v in ds_masked.data_vars:
        da = ds_masked[v]
        dt = native_interval_s(da)
        expected = bin_seconds / dt if np.isfinite(dt) and dt > 0 else float("nan")

        mean = da.resample(datetime=freq).mean()
        valid_count = da.notnull().resample(datetime=freq).sum()
        gated = gate_by_completeness(mean, valid_count, expected, completeness)

        gated.attrs = dict(da.attrs)
        gated.attrs["native_interval_s"] = dt
        gated.attrs["expected_samples_per_bin"] = expected
        gated.attrs["completeness_threshold"] = completeness
        aggregated[v] = gated
    return xr.Dataset(aggregated)


def aggregate_campaign(ds_masked: xr.Dataset, completeness: float) -> xr.Dataset:
    """Collapse the whole campaign to a single value per household, gated by completeness.
    Args:
        ds_masked: flag-masked measurement dataset
        completeness: minimum required fraction of expected samples over the campaign
    Returns:
        aggregated xarray dataset with the datetime dimension reduced away
    """
    times = ds_masked["datetime"].values
    span_seconds = float((times[-1] - times[0]).astype("timedelta64[s]").astype(float))
    aggregated = {}
    for v in ds_masked.data_vars:
        da = ds_masked[v]
        dt = native_interval_s(da)
        expected = span_seconds / dt if np.isfinite(dt) and dt > 0 else float("nan")

        mean = da.mean("datetime")
        valid_count = da.notnull().sum("datetime")
        gated = gate_by_completeness(mean, valid_count, expected, completeness)

        gated.attrs = dict(da.attrs)
        gated.attrs["native_interval_s"] = dt
        gated.attrs["expected_samples_per_campaign"] = expected
        gated.attrs["completeness_threshold"] = completeness
        aggregated[v] = gated

    ds = xr.Dataset(aggregated)
    ds.attrs["campaign_start"] = pd.Timestamp(times[0]).isoformat()
    ds.attrs["campaign_end"] = pd.Timestamp(times[-1]).isoformat()
    return ds


def aggregate(
    ds_masked: xr.Dataset, period: str, freq: str, completeness: float
) -> xr.Dataset:
    """Dispatch to binned or campaign-integrated aggregation.
    Args:
        ds_masked: flag-masked measurement dataset
        period: period token ("5min", "1hour", "1day", "campaign")
        freq: pandas resample frequency, or "campaign" for the integrated case
        completeness: minimum required fraction of expected samples
    Returns:
        aggregated xarray dataset
    """
    if period == "campaign":
        return aggregate_campaign(ds_masked, completeness)
    return aggregate_binned(ds_masked, freq, completeness)


def update_metadata(
    ds: xr.Dataset, period: str, freq: str, completeness: float
) -> xr.Dataset:
    """Update metadata for the network dataset.
    Args:
        ds: aggregated xarray dataset
        period: period token
        freq: pandas resample frequency (or "campaign")
        completeness: applied completeness threshold
    Returns:
        ds: xarray dataset with updated metadata
    """
    ds.attrs["stage"] = "network"
    ds.attrs["network_period"] = period
    ds.attrs["network_freq"] = str(freq)
    ds.attrs["completeness_threshold"] = completeness
    ds.attrs["networked"] = datetime.now(timezone.utc).isoformat()
    return ds


if __name__ == "__main__":
    # ── main ──────────────────────────────────────────────────────────────────────
    period = snakemake.params.period
    freq = snakemake.params.freq
    completeness = float(snakemake.params.completeness)
    log.info(
        f"Starting network aggregation: period={period} completeness={completeness}"
    )

    ds = xr.open_dataset(snakemake.input.nc)
    log.info(f"Loaded {snakemake.input.nc}: {dict(ds.sizes)}")

    # apply and drop flags
    measurement_vars = select_measurement_vars(ds)
    ds_masked, n_masked = apply_flags(ds, measurement_vars)
    ds_masked.attrs = dict(ds.attrs)
    log.info(
        f"Kept {len(measurement_vars)} measurement vars, "
        f"masked {n_masked} flagged records"
    )

    # aggregate with completeness gate
    ds_net = aggregate(ds_masked, period, freq, completeness)
    ds_net.attrs = {**dict(ds.attrs), **ds_net.attrs}
    ds_net = update_metadata(ds_net, period, freq, completeness)
    log.info(f"Aggregated to {period}: {dict(ds_net.sizes)}")

    # netcdf
    out_path = Path(snakemake.output.nc)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    num_vars = [
        v for v in ds_net.data_vars if np.issubdtype(ds_net[v].dtype, np.number)
    ]
    encoding = {v: {"zlib": True, "complevel": 4} for v in num_vars}
    if "datetime" in ds_net.coords:
        encoding["datetime"] = {
            "dtype": "float64",
            "units": "seconds since 1970-01-01",
            "calendar": "proleptic_gregorian",
        }
    ds_net.to_netcdf(out_path, encoding=encoding)
    log.info(f"Wrote {out_path}")
