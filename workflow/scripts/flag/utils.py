import numpy as np
import xarray as xr
import pandas as pd

def apply_flag(flag_var, condition, bit):
    return (flag_var | xr.where(condition, bit, 0)).astype(np.int16)

def init_flag(ds, var):
    return xr.zeros_like(ds[var], dtype=np.int16)

def flag_summary(ds, flag_vars, flag_bits):
    rows = []
    for fv in flag_vars:
        for bit, name in flag_bits.items():
            count = int(((ds[fv] & bit) > 0).sum())
            total = int(ds[fv].count())
            rows.append({
                'flag_var':   fv,
                'bit':        bit,
                'flag_name':  name,
                'n_flagged':  count,
                'n_total':    total,
                'pct_flagged': round(100 * count / total, 2) if total > 0 else 0.0
            })
    return pd.DataFrame(rows)

def compute_flag_global(ds, flag_vars):
    flag_global = xr.zeros_like(ds[flag_vars[0]], dtype=np.int16)
    for fv in flag_vars:
        flag_global = flag_global | ds[fv]
    return flag_global
