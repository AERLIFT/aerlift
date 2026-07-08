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


def flag_summary(
    ds: xr.Dataset, flag_vars: list[str], flag_bits: dict[int, str]
) -> pd.DataFrame:
    """Compute summary statistics for flagged variables
    Args:
        ds: xarray dataset with flags
        flag_vars: list of flag variable names
        flag_bits: dictionary of flag bit descriptions
    Returns:
        DataFrame with summary statistics for each flag variable and flag bit
    """
    rows = []
    for fv in flag_vars:
        for bit, name in flag_bits.items():
            count = int(((ds[fv] & bit) > 0).sum())
            total = int(ds[fv].count())
            rows.append(
                {
                    "flag_var": fv,
                    "bit": bit,
                    "flag_name": name,
                    "n_flagged": count,
                    "n_total": total,
                    "pct_flagged": round(100 * count / total, 2) if total > 0 else 0.0,
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
