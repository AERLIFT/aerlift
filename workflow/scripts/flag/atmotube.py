from pathlib import Path
from datetime import datetime, timezone
import logging
import numpy as np
import xarray as xr
import sys

sys.path.append(str(Path(__file__).parent))
from utils import apply_flag, init_flag, flag_summary, compute_flag_global

try:
    snakemake
except NameError:

    class snakemake:
        class params:
            flag_bits = {4: "pm_negative", 8: "voc_negative"}
            thresholds = {
                "pm_min": 0.0,
                "voc_raw_min": 0.0,
            }
            universal = {
                "temperature_min": -5.0,
                "temperature_max": 50.0,
                "rh_min": 0.0,
                "rh_max": 100.0,
                "pressure_min": 950.0,
                "pressure_max": 1050.0,
                "co2_min": 400.0,
                "co2_max": 5000.0,
            }
            instrument = "atmotube"

        class input:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/2_trimmed/atmotube.nc"

        class output:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged/atmotube.nc"
            csv = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged/atmotube_flags.csv"

        log = ["/dev/null"]


# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ── flag logic ────────────────────────────────────────────────────────────────
def flag_atmotube(
    ds: xr.Dataset, thresholds: dict[str, float], flag_bits: dict[int, str]
) -> tuple[xr.Dataset, list[str]]:
    """Flag AtmoTube data
    Args:
        ds: xarray dataset with AtmoTube data
        thresholds: dictionary of thresholds for each flag
        flag_bits: dictionary of flag bit descriptions
    Returns:
        ds: xarray dataset with AtmoTube flags added
        flag_vars: list of flag variable names
    """
    t = thresholds

    # flag_pm — any PM channel below zero
    f = init_flag(ds, "pm1")
    pm_neg = (
        (ds["pm1"] < t["pm_min"])
        | (ds["pm25"] < t["pm_min"])
        | (ds["pm10"] < t["pm_min"])
    )
    f = apply_flag(f, pm_neg, 4)
    ds["flag_pm"] = f
    ds["flag_pm"].attrs = {
        "long_name": "quality flag for PM channels",
        "flag_bits": str(flag_bits),
        "bit_4": "pm_negative",
    }

    # flag_voc — TVOC below zero
    f = init_flag(ds, "tvoc")
    f = apply_flag(f, ds["tvoc"] < t["voc_raw_min"], 8)
    ds["flag_voc"] = f
    ds["flag_voc"].attrs = {
        "long_name": "quality flag for VOC",
        "flag_bits": str(flag_bits),
        "bit_8": "voc_negative",
    }

    # flag_temperature
    f = init_flag(ds, "temperature")
    f = apply_flag(f, ds["temperature"] < t["temperature_min"], 1)
    f = apply_flag(f, ds["temperature"] > t["temperature_max"], 1)
    ds["flag_temperature"] = f
    ds["flag_temperature"].attrs = {
        "long_name": "quality flag for temperature",
        "bit_1": "out_of_range",
    }

    # flag_rh
    f = init_flag(ds, "rh")
    f = apply_flag(f, ds["rh"] < t["rh_min"], 1)
    f = apply_flag(f, ds["rh"] > t["rh_max"], 1)
    ds["flag_rh"] = f
    ds["flag_rh"].attrs = {
        "long_name": "quality flag for rh",
        "bit_1": "out_of_range",
    }

    # flag_pressure
    f = init_flag(ds, "pressure")
    f = apply_flag(f, ds["pressure"] < t["pressure_min"], 1)
    f = apply_flag(f, ds["pressure"] > t["pressure_max"], 1)
    ds["flag_pressure"] = f
    ds["flag_pressure"].attrs = {
        "long_name": "quality flag for pressure",
        "bit_1": "out_of_range",
    }

    # flag_co2 (optional — may be all-NaN on units without CO2 sensor)
    flag_vars = ["flag_pm", "flag_voc", "flag_temperature", "flag_rh", "flag_pressure"]
    if "co2" in ds and not ds["co2"].isnull().all():
        f = init_flag(ds, "co2")
        f = apply_flag(f, ds["co2"] < t["co2_min"], 1)
        f = apply_flag(f, ds["co2"] > t["co2_max"], 1)
        ds["flag_co2"] = f
        ds["flag_co2"].attrs = {
            "long_name": "quality flag for co2",
            "bit_1": "out_of_range",
        }
        flag_vars.append("flag_co2")

    ds["flag_global"] = compute_flag_global(ds, flag_vars)
    ds["flag_global"].attrs = {
        "long_name": "global quality flag — bitwise OR of all flag variables",
        "flag_bits": str({1: "out_of_range", **flag_bits}),
    }

    return ds, flag_vars


def update_metadata(ds: xr.Dataset) -> xr.Dataset:
    """Update metadata for flagged AtmoTube dataset
    Args:
        ds: xarray dataset with AtmoTube flags added
    Returns:
        ds: xarray dataset with updated metadata
    """
    ds.attrs["stage"] = "flagged"
    ds.attrs["flagged"] = datetime.now(timezone.utc).isoformat()
    return ds


if __name__ == "__main__":
    # ── main ──────────────────────────────────────────────────────────────────────
    log.info("Starting Atmotube flagging")

    ds = xr.open_dataset(snakemake.input.nc)
    log.info(f"Loaded {snakemake.input.nc}: {dict(ds.sizes)}")

    flag_bits = {int(k): v for k, v in snakemake.params.flag_bits.items()}
    thresholds = {**snakemake.params.universal, **snakemake.params.thresholds}

    ds, flag_vars = flag_atmotube(ds, thresholds, flag_bits)
    ds = update_metadata(ds)

    # summary csv
    per_var_bits = {
        "flag_pm": {1: "out_of_range", 4: "pm_negative"},
        "flag_voc": {1: "out_of_range", 8: "voc_negative"},
        "flag_temperature": {1: "out_of_range"},
        "flag_rh": {1: "out_of_range"},
        "flag_pressure": {1: "out_of_range"},
    }
    if "flag_co2" in ds:
        per_var_bits["flag_co2"] = {1: "out_of_range"}
    summary = flag_summary(ds, per_var_bits)
    summary.to_csv(snakemake.output.csv, index=False)
    log.info(f"Wrote {snakemake.output.csv}")
    log.info(f"\n{summary.to_string()}")

    # netcdf
    out_path = Path(snakemake.output.nc)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    num_vars = [
        v
        for v in ds.data_vars
        if ds[v].dtype in [np.float32, np.float64, np.int32, np.int64, np.int16]
    ]
    ds.to_netcdf(
        out_path, encoding={v: {"zlib": True, "complevel": 4} for v in num_vars}
    )
    log.info(f"Wrote {out_path}")
