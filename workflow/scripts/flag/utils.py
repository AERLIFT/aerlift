import numpy as np
import xarray as xr
import pandas as pd


def apply_flag(
    flag_var: xr.DataArray, condition: xr.DataArray, bit: int
) -> xr.DataArray:
    """Apply the flag to a variable based on a condition
    Args:
        flag_var: xarray DataArray to apply the flag to
        condition: xarray DataArray to use as condition
        bit: flag bit to apply
    Returns:
        applied flag to the variable of interest
    """
    return (flag_var | xr.where(condition, bit, 0)).astype(np.int16)


def init_flag(ds: xr.Dataset, var: str) -> xr.DataArray:
    """Initialize a flag variable with zeros
    Args:
        ds: xarray dataset to initialize the flag variable in
        var: name of the variable to initialize
    Returns:
        zeros-like DataArray with the same shape as the variable for the flag to hold memory space
    """
    return xr.zeros_like(ds[var], dtype=np.int16)


def _sample_dt_hours(ds: xr.Dataset) -> float:
    """Return median sample interval in hours, or NaN if time coord is absent/short."""
    for dim in ("time", "datetime"):
        if dim in ds.coords:
            t = ds[dim].values
            if len(t) < 2:
                return float("nan")
            return float(np.median(np.diff(t)) / np.timedelta64(1, "h"))
    return float("nan")


def flag_summary(
    ds: xr.Dataset, per_var_bits: dict[str, dict[int, str]]
) -> pd.DataFrame:
    """Compute per-sensor summary statistics for flagged variables.
    Args:
        ds: xarray dataset with flags
        per_var_bits: mapping of flag_var → {bit: name} — only the bits that
            apply to each variable, so the CSV shows correct flag names per row
    Returns:
        Tidy DataFrame with one row per (sensor, flag_var, bit). Columns:
        sensor, flag_var, bit, flag_name, n_flagged, n_total,
        uptime_hours, hours_flagged, proportion_flagged.
        sensor is None for datasets without a sensor coordinate.
    """
    dt_h = _sample_dt_hours(ds)
    sensors = list(ds["sensor"].values) if "sensor" in ds.coords else [None]
    rows = []
    for sensor in sensors:
        ds_s = ds.sel(sensor=sensor) if sensor is not None else ds
        for fv, flag_bits in per_var_bits.items():
            for bit, name in flag_bits.items():
                count = int(((ds_s[fv] & bit) > 0).sum())
                total = int(ds_s[fv].count())
                proportion = round(count / total, 4) if total > 0 else 0.0
                uptime_h = (
                    round(total * dt_h, 3) if not np.isnan(dt_h) else float("nan")
                )
                hours_flagged = (
                    round(count * dt_h, 4) if not np.isnan(dt_h) else float("nan")
                )
                rows.append(
                    {
                        "sensor": sensor,
                        "flag_var": fv,
                        "bit": bit,
                        "flag_name": name,
                        "n_flagged": count,
                        "n_total": total,
                        "uptime_hours": uptime_h,
                        "hours_flagged": hours_flagged,
                        "proportion_flagged": proportion,
                    }
                )
    return pd.DataFrame(rows)


def compute_flag_global(ds: xr.Dataset, flag_vars: list[str]) -> xr.DataArray:
    """Compute the global flag variable from a list of flag variables
    Args:
        ds: xarray dataset with flags
        flag_vars: list of flag variable names
    Returns:
        flag_global: DataArray with the global flag variable
    """
    flag_global = xr.zeros_like(ds[flag_vars[0]], dtype=np.int16)
    for fv in flag_vars:
        flag_global = flag_global | ds[fv]
    return flag_global
