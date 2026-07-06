from pathlib import Path
from datetime import datetime
import logging
import pandas as pd
import numpy as np

# ── dev shim ──────────────────────────────────────────────────────────────────
try:
    snakemake
except NameError:

    class snakemake:
        class params:
            timezone = "America/Los_Angeles"
            alphasense = {
                "position_1": "NO2",
                "position_2": "O3",
                "position_3": None,
                "position_4": None,
            }

        class input:
            csv = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/hhb_intermediate.csv"

        class output:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/hhb.nc"
            csv = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/1_munged/hhb_summary.csv"

        log = ["/dev/null"]


# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ── functions ─────────────────────────────────────────────────────────────────
def load_hhb(input_csv, alphasense):
    df = pd.read_csv(input_csv)

    # datetime
    df.loc[:, "DateTimeUTC"] = (
        pd.to_datetime(df["DateTimeUTC"], format="mixed")
        .dt.tz_localize("UTC")
        .dt.tz_localize(None)
    )

    # standardize column names
    df = df.rename(
        columns={
            "DateTimeUTC": "datetime",
            "HHBserial": "sensor",
            "SEN55_PM1.0": "sen_pm1_raw",
            "SEN55_PM2.5": "sen_pm25_raw",
            "SEN55_PM4.0": "sen_pm4_raw",
            "SEN55_PM10": "sen_pm10_raw",
            "SEN55_RH": "sen_rh",
            "SEN55_Temp": "sen_temperature",
            "SEN55_RawVOC": "sen_voc_raw",
            "SEN55_RawNOx": "sen_nox_raw",
            "G.SCD30_CO2": "scd30_co2",
            "G.Alphasense1_Algorithm1": f"{alphasense['position_1']}_algorithm1",
            "G.Alphasense2_Algorithm1": f"{alphasense['position_2']}_algorithm1",
        }
    )

    df = df.set_index("datetime")

    return df


def add_metadata(ds, params):
    ds.attrs = {
        "campaign": "AERLIFT",
        "instrument": "HHB",
        "stage": "munged",
        "created": datetime.now().isoformat(),
        "script": "workflow/scripts/munge/hhb_to_nc.py",
        "timezone_local": params.timezone,
        "time_reference": "UTC",
        "Conventions": "CF-1.8",
        "institution": "UC Berkeley School of Public Health",
        "creator_name": "Mark Campmier, PhD",
    }
    if getattr(params, "synthetic", None) == "true":
        ds.attrs["SYNTHETIC"] = "true"
    ds["sen_pm1_raw"].attrs = {
        "long_name": "Sensirion PM1.0 mass concentration",
        "units": "ug/m3",
    }
    ds["sen_pm25_raw"].attrs = {
        "long_name": "Sensirion PM2.5 mass concentration",
        "units": "ug/m3",
    }
    ds["sen_pm4_raw"].attrs = {
        "long_name": "Sensirion PM4.0 mass concentration",
        "units": "ug/m3",
    }
    ds["sen_pm10_raw"].attrs = {
        "long_name": "Sensirion PM10 mass concentration",
        "units": "ug/m3",
    }
    ds["sen_rh"].attrs = {"long_name": "relative humidity", "units": "%"}
    ds["sen_temperature"].attrs = {"long_name": "temperature", "units": "degC"}
    ds["sen_voc_raw"].attrs = {"long_name": "raw VOC index signal", "units": "1"}
    ds["sen_nox_raw"].attrs = {"long_name": "raw NOx index signal", "units": "1"}
    ds["scd30_co2"].attrs = {"long_name": "CO2 mixing ratio", "units": "ppm"}
    pos1 = params.alphasense.get("position_1")
    pos2 = params.alphasense.get("position_2")
    if pos1 and f"{pos1}_algorithm1" in ds:
        ds[f"{pos1}_algorithm1"].attrs = {
            "long_name": f"{pos1} concentration Algorithm 1",
            "units": "ppb",
            "instrument": "Alphasense B-series",
            "position": "1",
        }
    if pos2 and f"{pos2}_algorithm1" in ds:
        ds[f"{pos2}_algorithm1"].attrs = {
            "long_name": f"{pos2} concentration Algorithm 1",
            "units": "ppb",
            "instrument": "Alphasense B-series",
            "position": "2",
        }
    return ds


if __name__ == "__main__":
    # ── main ──────────────────────────────────────────────────────────────────────
    log.info("Starting HHB NetCDF conversion")

    df = load_hhb(snakemake.input.csv, alphasense=snakemake.params.alphasense)

    log.info(f"{len(df)} records, {df['sensor'].nunique()} sensors")

    ds_hhb = (
        df.reset_index().infer_objects().set_index(["sensor", "datetime"]).to_xarray()
    )
    ds_hhb = add_metadata(ds_hhb, snakemake.params)

    # summary csv
    summary = pd.DataFrame(
        {
            "n_records": [ds_hhb.sizes["datetime"]],
            "n_sensors": [ds_hhb.sizes["sensor"]],
            "pm25_mean": [float(ds_hhb["sen_pm25_raw"].mean())],
            "pm25_max": [float(ds_hhb["sen_pm25_raw"].max())],
            "temp_mean": [float(ds_hhb["sen_temperature"].mean())],
            "rh_mean": [float(ds_hhb["sen_rh"].mean())],
        }
    )
    summary.to_csv(snakemake.output.csv, index=False)
    log.info(f"Wrote {snakemake.output.csv}")

    # netcdf
    out_path = Path(snakemake.output.nc)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    num_vars = [
        v
        for v in ds_hhb.data_vars
        if ds_hhb[v].dtype in [np.float32, np.float64, np.int32, np.int64]
    ]
    ds_hhb.to_netcdf(
        out_path, encoding={v: {"zlib": True, "complevel": 4} for v in num_vars}
    )
    log.info(f"Wrote {out_path}")
