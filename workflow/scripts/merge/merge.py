import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

try:
    snakemake
except NameError:

    class snakemake:
        class input:
            # order-independent: each file is keyed to its metadata column by
            # filename stem (e.g. anemometer.nc → anemometer_sensor_id)
            nc_list = [
                "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/anemometer.nc",
                "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/aranet.nc",
                "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/lascar.nc",
                "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/hhb.nc",
                "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/upas.nc",
                "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/atmotube.nc",
                "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged_synth/aulifants.nc",
            ]

            df_metadata = (
                "/Users/markcampmier/Library/Mobile Documents/"
                "com~apple~CloudDocs/aerlift/data/0_synthetic/campaign_metadata.csv"
            )

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
    lookup = df.set_index(sensor_name)["household_id"]
    return (
        ds.assign_coords(household_id=("sensor", lookup))
        .swap_dims({"sensor": "household_id"})
        .drop_vars("sensor")
    )


def rename_vars(ds: xr.Dataset, sensor_name: str) -> xr.Dataset:
    """Renames all variables in the dataset to include the sensor name. Temporary fix until we have a better solution
    for variables like temperature which gets measured by multiple sensors for different reasons.
    Args:
        ds: xarray dataset to rename variables in, iterate over all flagged datasets
        sensor_name: name of the sensor/instrument
    Returns:
        ds: xarray dataset with renamed variables
    """
    return ds.rename_vars({var: f"{sensor_name}_{var}" for var in ds.data_vars})


def update_metadata(ds: xr.Dataset, sensor_list: list) -> xr.Dataset:
    """Update metadata for merged dataset
    Args:
        ds: xarray dataset after merging all flagged datasets
        sensor_list: list of sensor/instrument names
    Returns:
        ds: xarray dataset with updated metadata
    """
    ds.attrs["stage"] = "merged"
    ds.attrs["merged"] = datetime.now(timezone.utc).isoformat()
    ds.attrs["sensor_list"] = " ".join(
        sensor.replace("_sensor_id", "") for sensor in sensor_list
    )
    return ds


def map_datasets_to_columns(
    nc_paths: list[str], sensor_columns: list[str]
) -> dict[str, xr.Dataset]:
    """Map each flagged NetCDF to its metadata sensor-id column by filename stem.

    Keying on the file stem (e.g. ``anemometer.nc`` → ``anemometer_sensor_id``)
    ties every dataset to its sensor by identity, so the merge no longer depends
    on the order of ``nc_paths`` or of the metadata columns lining up.
    Args:
        nc_paths: paths to the flagged per-sensor NetCDF files
        sensor_columns: metadata columns of the form ``<sensor>_sensor_id``
    Returns:
        mapping of sensor-id column name → opened dataset
    Raises:
        KeyError: if a file's derived column is absent from the metadata
    """
    columns = set(sensor_columns)
    datasets = {}
    for nc in nc_paths:
        sensor = Path(nc).stem
        column = f"{sensor}_sensor_id"
        if column not in columns:
            raise KeyError(
                f"{nc}: derived column '{column}' not in metadata {sorted(columns)}"
            )
        datasets[column] = xr.open_dataset(nc)
    return datasets


def merge_datasets(datasets: dict[str, xr.Dataset], df: pd.DataFrame) -> xr.Dataset:
    """Merges flagged datasets, each keyed to its metadata sensor-id column.
    Args:
        datasets: mapping of sensor-id column name → flagged dataset
        df: pandas dataframe with metadata - household_id and sensor_id columns for each sensor at the household
    Returns:
        ds: merged xarray dataset
    """
    prepared = [
        rename_vars(add_household_id(ds, df, sensor_name), sensor_name)
        for sensor_name, ds in datasets.items()
    ]
    ds = xr.merge(prepared, join="outer", combine_attrs="drop_conflicts")
    ds = update_metadata(ds, list(datasets.keys()))
    return ds


if __name__ == "__main__":
    # ── main ──────────────────────────────────────────────────────────────────────
    log.info("Starting merge")

    # load metadata
    df = pd.read_csv(Path(snakemake.input.df_metadata))
    sensor_columns = df.filter(regex=r"[a-z]*_sensor_id").columns.tolist()
    log.info(f"Loaded {snakemake.input.df_metadata}")

    # netcdf
    out_path = Path(snakemake.output.nc)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    datasets = map_datasets_to_columns(snakemake.input.nc_list, sensor_columns)
    log.info(f"Matched {len(datasets)} datasets to metadata columns: {list(datasets)}")
    ds_merged = merge_datasets(datasets, df)

    num_vars = [
        v for v in ds_merged.data_vars if np.issubdtype(ds_merged[v].dtype, np.number)
    ]
    ds_merged.to_netcdf(
        out_path, encoding={v: {"zlib": True, "complevel": 4} for v in num_vars}
    )
    log.info(f"Wrote {out_path}")
