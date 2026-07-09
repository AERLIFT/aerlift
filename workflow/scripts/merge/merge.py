# %%
import numpy as np
import xarray as xr
import pandas as pd

from pathlib import Path

# %%

def add_household_id(ds: xr.Dataset, df: pd.DataFrame, sensor_name: str) -> xr.Dataset:
    return ds.assign_coords(household_id=
                                    ('sensor', df.rename({f'{sensor_name}_id': 'sensor'}, axis=1).set_index('sensor').loc[:, 'household_id']),
                                    ).swap_dims({'sensor': 'household_id'}).drop_vars('sensor')

def rename_vars(ds: xr.Dataset, sensor_name: str) -> xr.Dataset:
    for var in ds.data_vars:
        ds = ds.rename_vars({var: f'{sensor_name}_{var}'})
    return ds

def merge_datasets(list_ds: list[xr.Dataset], df: pd.DataFrame) -> xr.Dataset:
    list_ds = [rename_vars(add_household_id(ds, sensor_name), sensor_name) for sensor_name, ds in zip(df.sensor, list_ds)]
    return xr.merge(list_ds, join='outer', combine_attrs='drop_conflicts')

# %%

df = pd.read_csv('/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/0_synthetic/campaign_metadata.csv')

dir = Path("/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/")

list_nc = list(dir.glob('*.nc'))

ds_merged = merge_datasets([xr.open_dataset(nc) for nc in list_nc], df)