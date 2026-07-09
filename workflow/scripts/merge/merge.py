from typing import Any
import logging
import numpy as np
import pandas as pd
import xarray as xr

from datetime import datetime, timezone

from pathlib import Path

try:
    snakemake
except NameError:

    class snakemake:
        class params:
            flag_bits = {4: "low_flow"}
            thresholds = {"flow_indicator_min": 0.5}
            instrument = "anemometer"

        class input:
            nc_list = ["/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/anemometer.nc",
                       "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/aranet.nc",
                       "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/atmotube.nc",
                       "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/aulifants.nc",
                       "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/hhb.nc",
                       "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/lascar.nc",
                       "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/upas.nc"]

            df_metadata = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/0_synthetic/campaign_metadata.csv"

        class output:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/4_merged_synth/merge.nc"

        log = ["/dev/null"]

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ── merge logic ────────────────────────────────────────────────────────────────
def add_household_id(ds: xr.Dataset, df: pd.DataFrame, sensor_name: str) -> xr.Dataset:
    """Uses df as a lookup table to add household_id to dataset, and swap dims to match.
    Args:
        ds: xarray dataset to add household_id to, each ds is a flagged dataset
        df: pandas dataframe with household_id and sensor_id columns for each sensor at the household
        sensor_name: name of the sensor/instrument
    Returns:
        flagged dataset with household_id added, and swapped with sensor id
    """
    return ds.assign_coords(household_id=
                                    ('sensor', df.rename({f'{sensor_name}': 'sensor'}, axis=1).set_index('sensor').loc[:, 'household_id']),
                                    ).swap_dims({'sensor': 'household_id'}).drop_vars('sensor')

def rename_vars(ds: xr.Dataset, sensor_name: str) -> xr.Dataset:
    """Renames all variables in the dataset to include the sensor name. Temporary fix until we have a better solution
    for variables like temperature which gets measured by multiple sensors for different reasons.
    Args:
        ds: xarray dataset to rename variables in, iterate over all flagged datasets
        sensor_name: name of the sensor/instrument
    Returns:
        ds: xarray dataset with renamed variables
    """
    for var in ds.data_vars:
        ds = ds.rename_vars({var: f'{sensor_name}_{var}'})
    return ds

def update_metadata(ds: xr.Dataset, sensor_list:list) -> xr.Dataset:
    """Update metadata for merged dataset
    Args:
        ds: xarray dataset after merging all flagged datasets
        sensor_list: list of sensor/instrument names
    Returns:
        ds: xarray dataset with updated metadata
    """
    ds.attrs["stage"] = "merged"
    ds.attrs["merged"] = datetime.now(timezone.utc).isoformat()
    ds.attrs["sensor_list"] = " ".join([sensor.replace('_sensor_id', '') for sensor in sensor_list])
    return ds

def merge_datasets(list_ds: list[xr.Dataset], df: pd.DataFrame, sensor_list: list) -> xr.Dataset:
    """Merges a list of flagged datasets into a single dataset.
    Args:
        list_ds: list of xarray datasets to merge
        df: pandas dataframe with metadata - household_id and sensor_id columns for each sensor at the household
        sensor_list: list of sensor/instrument names
    """
    list_ds = [rename_vars(add_household_id(ds, df, sensor_name), sensor_name) for sensor_name, ds in zip(sensor_list, list_ds)]
    ds = xr.merge(list_ds, join='outer', combine_attrs='drop_conflicts')
    ds = update_metadata(ds, sensor_list)
    return ds

if __name__ == "__main__":
    # ── main ──────────────────────────────────────────────────────────────────────
    log.info("Starting merge")

    # load metadata
    df = pd.read_csv(Path(snakemake.input.df_metadata))
    list_sensors = df.filter(regex=r'[a-z]*_sensor_id').columns.tolist()
    log.info(f"Loaded metadata file")

    # netcdf
    out_path = Path(snakemake.output.nc)
    ds_merged = merge_datasets([xr.open_dataset(nc) for nc in snakemake.input.nc_list], df, list_sensors)
    log.info(f"Wrote {snakemake.output.nc}")