import logging
import numpy as np
import pandas as pd
import xarray as xr

from pathlib import Path
from datetime import datetime

try:
    snakemake
except NameError:

    class snakemake:
        class params:
            raw_dir = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/0_raw"
            skiprows = 6
            usecols = [0, 1, 3, 4]
            threshold = 0.5
            timezone = "America/Los_Angeles"

        class output:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/anemometer.nc"
            csv = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/anemometer_summary.csv"

        log = ["/dev/null"]


# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ── functions ─────────────────────────────────────────────────────────────────
def get_files(raw_dir, ext=".txt") -> list:
    """Finds all anemometer files in anemometer directory.
    Args:
        raw_dir: path to raw data directory
        ext: file extension to search for (default: .txt)
    Returns:
        files: list of file paths for each anemometer file
    Raises:
        No files found error if no files are found.
    """
    path = Path(raw_dir.strip()) / "anemometer"
    files = list(path.rglob(f"*{ext}"))
    assert len(files) > 0, f"No {ext} files found in {path}"
    return files


def parse_sensor_id(file) -> str:
    """Extracts sensor ID from file name.
    Args:
        file: file path with sensor ID in filename
    Returns:
        sensor ID
    """
    return file.stem.split("_")[1]


def parse_datetime(df, timezone) -> pd.DatetimeIndex:
    """Parses datetime from raw data.
    Args:
        df: dataframe with columns for each date/time value (year, month, day, etc.)
        timezone: timezone to parse datetime in
    Returns:
        a pd.DatetimeIndex of datetime values for easy indexing of the pd.DataFrame
    """
    df_date = df.iloc[:, 1].str.split("-", expand=True).astype(int)
    df_time = df.iloc[:, 2].str.split(":", expand=True).astype(int)
    return (
        pd.to_datetime(
            {
                "year": df_date.iloc[:, 2],
                "month": df_date.iloc[:, 1],
                "day": df_date.iloc[:, 0],
                "hour": df_time.iloc[:, 0],
                "minute": df_time.iloc[:, 1],
                "second": df_time.iloc[:, 2],
            }
        )
        .dt.tz_localize(timezone)
        .dt.tz_convert("UTC")
        .dt.tz_localize(None)  # strip tz for xarray/netcdf compat issues
    )


def read_anemometer_file(file, skiprows, usecols, threshold, timezone) -> pd.DataFrame:
    """Reads an anemometer file and returns a pd.DataFrame.
    Args:
        file: file path to anemometer file
        skiprows: number of rows to skip at the beginning of the file
        usecols: columns to use from the file
        threshold: flow threshold to flag active flow
        timezone: timezone to parse datetime in
    Returns:
        df: time-indexed DataFrame with columns for measured and derived values
    """
    df = pd.read_csv(file, skiprows=skiprows, header=None, index_col=0, usecols=usecols)
    df.index = parse_datetime(df, timezone)
    df = df.drop([3, 4], axis=1)
    df.columns = ["air_flow"]
    df["air_flow"] = df["air_flow"].astype(np.float64)
    df["flow_indicator"] = (df["air_flow"] >= threshold).astype(float)
    df["sensor"] = parse_sensor_id(file)
    return df


def process_anemometer(params) -> xr.Dataset:
    """Gathers anemometer files, parses & standardizes, and returns an xarray dataset.
    Args:
        params: snakemake params object contains directory path, skiprows, usecols, threshold, and timezone
    Returns:
        an xarray dataset with time-indexed values for each sensor, ready for netCDF writing
    """
    files = get_files(params.raw_dir)
    lst_df = [
        read_anemometer_file(
            file,
            skiprows=params.skiprows,
            usecols=params.usecols,
            threshold=params.threshold,
            timezone=params.timezone,
        )
        for file in files
    ]
    df = pd.concat(lst_df).reset_index().rename(columns={"index": "datetime"})
    return df.set_index(["sensor", "datetime"]).to_xarray()


def add_metadata(ds, params) -> xr.Dataset:
    """Adds metadata to the anemometer xarray dataset.
    Args:
        ds: xarray dataset to add metadata to
        params: snakemake params object contains threshold, and timezone
    Returns:
        ds: xarray dataset with metadata added
    """
    ds.attrs = {
        "campaign": "AERLIFT",
        "instrument": "anemometer",
        "stage": "munged",
        "created": datetime.now().isoformat(),
        "script": "workflow/scripts/munge/anemometer.py",
        "timezone_local": params.timezone,
        "time_reference": "UTC",
        "flow_threshold": params.threshold,
        "Conventions": "CF-1.8",
        "institution": "UC Berkeley School of Public Health",
        "creator_name": "Mark Campmier, PhD",
    }
    if getattr(params, "synthetic", None) == "true":
        ds.attrs["SYNTHETIC"] = "true"
    ds["air_flow"].attrs = {
        "long_name": "air velocity",
        "units": "m/s",
        "instrument": "anemometer",
    }
    ds["flow_indicator"].attrs = {
        "long_name": "flow active indicator",
        "units": "1",
        "flag_values": "0, 1",
        "flag_meanings": "inactive active",
        "threshold": params.threshold,
    }
    return ds


if __name__ == "__main__":
    # ── main ──────────────────────────────────────────────────────────────────────
    log.info("Starting anemometer munging")

    ds_flw = process_anemometer(snakemake.params)
    ds_flw = add_metadata(ds_flw, snakemake.params)

    # summary csv
    files = get_files(snakemake.params.raw_dir)
    summary = pd.DataFrame(
        {
            "n_files": [len(files)],
            "n_records": [ds_flw.sizes["datetime"]],
            "flow_active_pct": [float(ds_flw["flow_indicator"].mean()) * 100],
            "air_flow_mean": [float(ds_flw["air_flow"].mean())],
            "air_flow_max": [float(ds_flw["air_flow"].max())],
        }
    )
    summary.to_csv(snakemake.output.csv, index=False)
    log.info(f"Wrote {snakemake.output.csv}")

    # netcdf
    out_path = Path(snakemake.output.nc)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds_flw.to_netcdf(
        out_path,
        encoding={
            v: {"zlib": True, "complevel": 4} for v in ["air_flow", "flow_indicator"]
        },
    )
    log.info(f"Wrote {out_path}")
