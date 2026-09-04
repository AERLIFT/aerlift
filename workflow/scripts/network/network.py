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


def apply_flags_to_var(ds: xr.Dataset, var: str) -> tuple[np.ndarray, int]:
    """Extract measurement variable values with flags applied as NaN.
    Args:
        ds: merged xarray dataset
        var: measurement variable name
    Returns:
        tuple of (numpy array of values with bad records as NaN, count of masked records)
    """
    da = ds[var]
    vals = da.values
    fv = flag_var_for(ds, var)
    n_masked = 0
    if fv is not None and fv in ds:
        bad = ds[fv].values > 0
        n_masked = int(bad.sum())
        if n_masked > 0:
            vals = np.where(~bad, vals, np.nan)
    return vals, n_masked


def deployment_start(ds: xr.Dataset, measurement_vars: list[str]) -> dict:
    """Return the first datetime with any valid (non-NaN) data per household.

    Reduces across all measurement variables so a household is considered
    "deployed" from the moment its earliest sensor reports anything.
    Args:
        ds: merged xarray dataset with household_id and datetime dims
        measurement_vars: measurement variables to evaluate
    Returns:
        dict mapping household_id → np.datetime64 (NaT if no valid data)
    """
    datetimes = ds["datetime"].values
    households = ds["household_id"].values
    any_valid = np.zeros((len(households), len(datetimes)), dtype=bool)
    for v in measurement_vars:
        vals, _ = apply_flags_to_var(ds, v)
        any_valid |= ~np.isnan(vals)

    t0 = {}
    for i, hh in enumerate(households):
        if any_valid[i].any():
            valid_dt = datetimes[any_valid[i]]
            t0[hh] = valid_dt[0]
        else:
            t0[hh] = np.datetime64("NaT")
    return t0


def native_interval_s(vals: np.ndarray, datetimes: np.ndarray) -> float:
    """Infer a variable's native sampling interval in seconds.

    Uses the median spacing between timestamps that carry at least one non-null
    value across households, so completeness is measured against the sensor's
    own cadence rather than the merged (union) grid.
    Args:
        vals: 2D numpy array of values (household_id x datetime)
        datetimes: 1D numpy array of timestamps
    Returns:
        median native interval in seconds, or NaN if fewer than two samples
    """
    present = np.any(~np.isnan(vals), axis=0) if vals.ndim > 1 else ~np.isnan(vals)
    present_times = datetimes[present]
    if len(present_times) < 2:
        return float("nan")
    return float(
        np.median(np.diff(present_times).astype("timedelta64[s]").astype(float))
    )


def resample_variable_binned(
    da: xr.DataArray,
    vals: np.ndarray,
    freq: str,
    completeness: float,
) -> xr.DataArray:
    """Resample a single variable to a fixed period, gated by completeness.
    Args:
        da: original DataArray
        vals: 2D numpy array of values
        freq: pandas resample frequency
        completeness: minimum required fraction of expected samples per bin
    Returns:
        gated resampled DataArray
    """
    datetimes = da["datetime"].values
    households = da["household_id"].values
    bin_seconds = pd.Timedelta(freq).total_seconds()
    dt = native_interval_s(vals, datetimes)
    expected = bin_seconds / dt if np.isfinite(dt) and dt > 0 else float("nan")

    df = pd.DataFrame(
        vals.T,
        index=datetimes,
        columns=households,
    )
    mean_df = df.resample(freq).mean()
    count_df = df.resample(freq).count()
    if not np.isfinite(expected) or expected <= 0:
        gated_vals = np.full(mean_df.shape, np.nan)
    else:
        coverage = count_df.values / expected
        gated_vals = np.where(coverage >= completeness, mean_df.values, np.nan)

    gated = xr.DataArray(
        gated_vals.T,
        dims=["household_id", "datetime"],
        coords={
            "household_id": households,
            "datetime": mean_df.index.values,
        },
    )
    gated.attrs = dict(da.attrs)
    gated.attrs["native_interval_s"] = dt
    gated.attrs["expected_samples_per_bin"] = expected
    gated.attrs["completeness_threshold"] = completeness
    return gated


def aggregate_variable_campaign(
    da: xr.DataArray,
    vals: np.ndarray,
    completeness: float,
) -> xr.DataArray:
    """Aggregate a single variable across the campaign, gated by completeness.
    Args:
        da: original DataArray
        vals: 2D numpy array of values
        completeness: minimum required fraction of expected samples over the campaign
    Returns:
        gated campaign DataArray
    """
    datetimes = da["datetime"].values
    households = da["household_id"].values
    span_seconds = float(
        (datetimes[-1] - datetimes[0]).astype("timedelta64[s]").astype(float)
    )
    dt = native_interval_s(vals, datetimes)
    expected = span_seconds / dt if np.isfinite(dt) and dt > 0 else float("nan")

    with np.errstate(all="ignore"):
        mean_vals = np.nanmean(vals, axis=-1)
        valid_count = np.sum(~np.isnan(vals), axis=-1)

    if not np.isfinite(expected) or expected <= 0:
        gated_vals = np.full(mean_vals.shape, np.nan)
    else:
        coverage = valid_count / expected
        gated_vals = np.where(coverage >= completeness, mean_vals, np.nan)

    gated = xr.DataArray(
        gated_vals,
        dims=["household_id"],
        coords={"household_id": households},
    )
    gated.attrs = dict(da.attrs)
    gated.attrs["native_interval_s"] = dt
    gated.attrs["expected_samples_per_campaign"] = expected
    gated.attrs["completeness_threshold"] = completeness
    return gated


def aggregate_binned(
    ds: xr.Dataset,
    measurement_vars: list[str],
    freq: str,
    completeness: float,
) -> tuple[xr.Dataset, int]:
    """Resample every variable to a fixed period, gated by completeness.
    Args:
        ds: merged xarray dataset
        measurement_vars: measurement variables to aggregate
        freq: pandas resample frequency (e.g. "5min", "1h", "1D")
        completeness: minimum required fraction of expected samples per bin
    Returns:
        tuple of (aggregated xarray dataset on resampled grid, total masked records)
    """
    aggregated = {}
    total_masked = 0

    for v in measurement_vars:
        da = ds[v]
        vals, n_masked = apply_flags_to_var(ds, v)
        total_masked += n_masked
        aggregated[v] = resample_variable_binned(da, vals, freq, completeness)

    return xr.Dataset(aggregated), total_masked


def aggregate_campaign(
    ds: xr.Dataset,
    measurement_vars: list[str],
    completeness: float,
) -> tuple[xr.Dataset, int]:
    """Collapse the whole campaign to a single value per household, gated by completeness.
    Args:
        ds: merged xarray dataset
        measurement_vars: measurement variables to aggregate
        completeness: minimum required fraction of expected samples over the campaign
    Returns:
        tuple of (aggregated xarray dataset with datetime reduced away, total masked records)
    """
    datetimes = ds["datetime"].values
    aggregated = {}
    total_masked = 0

    for v in measurement_vars:
        da = ds[v]
        vals, n_masked = apply_flags_to_var(ds, v)
        total_masked += n_masked
        aggregated[v] = aggregate_variable_campaign(da, vals, completeness)

    ds_campaign = xr.Dataset(aggregated)
    ds_campaign.attrs["campaign_start"] = pd.Timestamp(datetimes[0]).isoformat()
    ds_campaign.attrs["campaign_end"] = pd.Timestamp(datetimes[-1]).isoformat()
    return ds_campaign, total_masked


def add_deployment_hours(ds_net: xr.Dataset, t0: dict, period: str) -> xr.Dataset:
    """Add ``deployment_hours`` — cumulative hours since first valid observation.

    For binned periods each bin gets the elapsed hours from that household's
    deployment start to the bin datetime (NaN before deployment starts).
    For the campaign period each household gets a single total-hours value.
    Args:
        ds_net: aggregated network dataset
        t0: mapping of household_id → deployment start datetime (from deployment_start)
        period: period token ("5min", "1hour", "1day", "campaign")
    Returns:
        ds_net with ``deployment_hours`` variable added
    """
    households = ds_net["household_id"].values

    if period == "campaign":
        t_end = np.datetime64(ds_net.attrs["campaign_end"])
        hours = [
            (
                float((t_end - t0[hh]) / np.timedelta64(1, "h"))
                if not np.isnat(np.array(t0[hh], dtype="datetime64"))
                else np.nan
            )
            for hh in households
        ]
        da = xr.DataArray(
            hours,
            dims=["household_id"],
            coords={"household_id": households},
        )
    else:
        datetimes = ds_net["datetime"].values
        data = np.full((len(households), len(datetimes)), np.nan)
        for i, hh in enumerate(households):
            start = t0[hh]
            if not np.isnat(np.array(start, dtype="datetime64")):
                elapsed = (datetimes - start) / np.timedelta64(1, "h")
                data[i, :] = np.where(elapsed >= 0, elapsed, np.nan)
        da = xr.DataArray(
            data,
            dims=["household_id", "datetime"],
            coords={"household_id": households, "datetime": datetimes},
        )

    da.attrs = {
        "long_name": "cumulative hours since first valid observation",
        "units": "hours",
        "comment": "deployment start taken as first non-NaN timestamp across all variables",
    }
    ds_net["deployment_hours"] = da
    return ds_net


def aggregate(
    ds: xr.Dataset,
    measurement_vars: list[str],
    period: str,
    freq: str,
    completeness: float,
) -> tuple[xr.Dataset, int]:
    """Dispatch to binned or campaign-integrated aggregation.
    Args:
        ds: merged xarray dataset
        measurement_vars: measurement variables to aggregate
        period: period token ("5min", "1hour", "1day", "campaign")
        freq: pandas resample frequency, or "campaign" for the integrated case
        completeness: minimum required fraction of expected samples
    Returns:
        tuple of (aggregated xarray dataset, total masked records)
    """
    if period == "campaign":
        return aggregate_campaign(ds, measurement_vars, completeness)
    return aggregate_binned(ds, measurement_vars, freq, completeness)


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

    # select measurement vars
    measurement_vars = select_measurement_vars(ds)

    # deployment start per household (before aggregation collapses the time axis)
    t0 = deployment_start(ds, measurement_vars)
    log.info(f"Deployment starts: {dict((k, str(v)) for k, v in t0.items())}")

    # aggregate with completeness gate
    ds_net, n_masked = aggregate(ds, measurement_vars, period, freq, completeness)
    ds_attrs = dict(ds.attrs)
    ds.close()
    log.info(
        f"Kept {len(measurement_vars)} measurement vars, "
        f"masked {n_masked} flagged records"
    )
    ds_net = add_deployment_hours(ds_net, t0, period)
    ds_net.attrs = {**ds_attrs, **ds_net.attrs}
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
