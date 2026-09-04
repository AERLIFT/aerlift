from pathlib import Path
from datetime import datetime
import logging
import pandas as pd
import xarray as xr
from typing import Any

# ── dev shim ──────────────────────────────────────────────────────────────────
try:
    snakemake
except NameError:

    class snakemake:
        class params:
            raw_dir = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/0_raw"
            timezone = "America/Los_Angeles"

        class output:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/geocene.nc"
            csv = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/geocene_summary.csv"

        class input:
            events = "/Users/markcampmier/Downloads/d547dc0b-f4d0-48e9-a543-63ca18d769e2/events.csv"

        log = ["/dev/null"]


# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ── functions ─────────────────────────────────────────────────────────────────
def read_geocene_file(file: str, timezone: str) -> pd.DataFrame:
    """Reads the geocene events file and returns a pd.DataFrame.
    Args:
        file: file path to geocene events.csv file
        timezone: timezone to parse datetime in (though events are UTC)
    Returns:
        df: DataFrame with standardized columns
    """
    df = pd.read_csv(file)

    # Convert ISO8601 strings to datetime objects and remove timezone info (keep as UTC)
    df["start_time"] = (
        pd.to_datetime(df["start_time"]).dt.tz_convert("UTC").dt.tz_localize(None)
    )
    df["stop_time"] = (
        pd.to_datetime(df["stop_time"]).dt.tz_convert("UTC").dt.tz_localize(None)
    )

    # We might want to rename mission_id to sensor if that's the convention
    df = df.rename(columns={"mission_id": "sensor"})

    return df


def process_geocene(input_file: str, params: Any) -> xr.Dataset:
    """Parses & standardizes geocene events, and returns an xarray Dataset.
    Args:
        input_file: path to events.csv
        params: snakemake params object
    Returns:
        an xarray Dataset
    """
    df = read_geocene_file(input_file, params.timezone)

    # For events, we might have multiple events per sensor.
    # Standard munged files seem to be sensor-datetime indexed.
    # Since events have start and stop times, this is a bit different.
    # However, to keep it consistent with the pipeline, we'll index by sensor and start_time.

    df = df.set_index(["sensor", "start_time"])
    ds = df.to_xarray()
    return ds


def add_metadata(ds: xr.Dataset, params: Any) -> xr.Dataset:
    """Adds metadata to the geocene xarray dataset.
    Args:
        ds: xarray dataset to add metadata to
        params: snakemake params object
    Returns:
        ds: xarray dataset with metadata added
    """
    ds.attrs = {
        "campaign": "AERLIFT",
        "instrument": "Geocene",
        "stage": "munged",
        "created": datetime.now().isoformat(),
        "script": "workflow/scripts/munge/geocene.py",
        "timezone_local": params.timezone,
        "time_reference": "UTC",
        "Conventions": "CF-1.8",
        "institution": "UC Berkeley School of Public Health",
        "creator_name": "Mark Campmier, PhD",
    }

    ds["stop_time"].attrs = {
        "long_name": "event stop time",
    }
    ds["event_kind"].attrs = {
        "long_name": "kind of event",
    }
    ds["processor_name"].attrs = {
        "long_name": "name of processor that generated event",
    }
    ds["model_name"].attrs = {
        "long_name": "name of model that generated event",
    }

    return ds


if __name__ == "__main__":
    # ── main ──────────────────────────────────────────────────────────────────────
    log.info("Starting Geocene munging")

    ds_geocene = process_geocene(snakemake.input.events, snakemake.params)
    log.info(f"Processed Geocene events file")

    ds_geocene = add_metadata(ds_geocene, snakemake.params)

    # summary csv
    summary = pd.DataFrame(
        {
            "n_events": [ds_geocene.sizes["start_time"]],
            "n_sensors": [len(ds_geocene.coords["sensor"])],
            "event_kinds": [
                ", ".join(
                    map(str, pd.unique(ds_geocene["event_kind"].values.flatten()))
                )
            ],
        }
    )
    summary.to_csv(snakemake.output.csv, index=False)
    log.info(f"Wrote {snakemake.output.csv}")

    # netcdf
    out_path = Path(snakemake.output.nc)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds_geocene.to_netcdf(out_path)
    log.info(f"Wrote {out_path}")
