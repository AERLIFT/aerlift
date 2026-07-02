from pathlib import Path
from datetime import datetime, timezone
import logging
import numpy as np
import xarray as xr
import pandas as pd
import sys

sys.path.append(str(Path(__file__).parent))
from utils import apply_flag, init_flag, flag_summary, compute_flag_global

try:
    snakemake
except NameError:

    class snakemake:
        class params:
            flag_bits = {4: "pm_negative", 8: "low_battery", 16: "pm_zero_run"}
            thresholds = {
                "pm_min": 0.0,
                "battery_min": 20,
                "pm_zero_run_mins": 10,
                "temperature_min": -5.0,
                "temperature_max": 50.0,
                "rh_min": 0.0,
                "rh_max": 100.0,
                "co2_min": 400.0,
                "co2_max": 5000.0,
                "voc_raw_min": 0.0,
                "nox_raw_min": 0.0,
            }
            instrument = "upas"

        class input:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/2_trimmed/upas.nc"

        class output:
            nc = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged/upas.nc"
            csv = "/Users/markcampmier/Library/Mobile Documents/com~apple~CloudDocs/aerlift/data/3_flagged/upas_flags.csv"

        log = ["/dev/null"]


# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=snakemake.log[0],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ── flag logic ────────────────────────────────────────────────────────────────
def get_zero_run_mask(ds, var, zero_run_mins):
    """Flag sustained runs of zeros exceeding zero_run_mins per sensor"""
    zero_run_td = pd.Timedelta(minutes=zero_run_mins)
    datetimes = pd.DatetimeIndex(ds.datetime.values)
    mask = xr.zeros_like(ds[var], dtype=bool)

    for sensor in ds.sensor.values:
        values = ds[var].sel(sensor=sensor).values
        is_zero = values == 0.0
        in_run = False
        run_start = None

        for dt, zero in zip(datetimes, is_zero):
            if zero and not in_run:
                in_run = True
                run_start = dt
            elif not zero and in_run:
                if dt - run_start >= zero_run_td:
                    run_mask = (datetimes >= run_start) & (datetimes < dt)
                    mask.loc[{"sensor": sensor}] = mask.loc[
                        {"sensor": sensor}
                    ] | xr.DataArray(run_mask, dims="datetime")
                in_run = False

        # catch run extending to end of record
        if in_run and (datetimes[-1] - run_start >= zero_run_td):
            run_mask = datetimes >= run_start
            mask.loc[{"sensor": sensor}] = mask.loc[{"sensor": sensor}] | xr.DataArray(
                run_mask, dims="datetime"
            )

    return mask


def flag_upas(ds, thresholds, flag_bits):
    t = thresholds

    pm_mc_vars = ["upas_pm1_mc", "upas_pm25_mc", "upas_pm4_mc", "upas_pm10_mc"]
    pm_nc_vars = [
        "upas_pm05_nc",
        "upas_pm1_nc",
        "upas_pm25_nc",
        "upas_pm4_nc",
        "upas_pm10_nc",
    ]
    pm_all = pm_mc_vars + pm_nc_vars + ["upas_pm_typical_size"]

    # zero run mask on pm25_mc as representative variable
    zero_run_mask = get_zero_run_mask(ds, "upas_pm25_mc", t["pm_zero_run_mins"])
    log.info(f"Zero run mask: {int(zero_run_mask.sum())} records flagged")

    # ── PM mass concentration ─────────────────────────────────────────────────
    for var in pm_mc_vars:
        f = init_flag(ds, var)
        f = apply_flag(f, ds[var] < t["pm_min"], 4)  # pm_negative
        f = apply_flag(f, zero_run_mask, 16)  # pm_zero_run
        ds[f"flag_{var}"] = f
        ds[f"flag_{var}"].attrs = {
            "long_name": f"quality flag for {var}",
            "flag_bits": str(flag_bits),
            "bit_4": "pm_negative",
            "bit_16": "pm_zero_run",
        }

    # ── PM number concentration ───────────────────────────────────────────────
    for var in pm_nc_vars:
        f = init_flag(ds, var)
        f = apply_flag(f, ds[var] < t["pm_min"], 4)  # pm_negative
        f = apply_flag(f, zero_run_mask, 16)  # pm_zero_run
        ds[f"flag_{var}"] = f
        ds[f"flag_{var}"].attrs = {
            "long_name": f"quality flag for {var}",
            "flag_bits": str(flag_bits),
            "bit_4": "pm_negative",
            "bit_16": "pm_zero_run",
        }

    # ── PM typical size ───────────────────────────────────────────────────────
    f = init_flag(ds, "upas_pm_typical_size")
    f = apply_flag(f, zero_run_mask, 16)
    ds["flag_upas_pm_typical_size"] = f
    ds["flag_upas_pm_typical_size"].attrs = {
        "long_name": "quality flag for upas_pm_typical_size",
        "bit_16": "pm_zero_run",
    }

    # ── battery ───────────────────────────────────────────────────────────────
    f = init_flag(ds, "upas_pm25_mc")  # use as template for dimensions
    f = apply_flag(f, ds["BatteryCharge"] < t["battery_min"], 8)
    ds["flag_battery"] = f
    ds["flag_battery"].attrs = {
        "long_name": "quality flag for battery charge",
        "bit_8": "low_battery",
    }

    # ── met ───────────────────────────────────────────────────────────────────
    for var, vmin, vmax in [
        ("upas_atmo_temperature", t["temperature_min"], t["temperature_max"]),
        ("upas_atmo_rh", t["rh_min"], t["rh_max"]),
    ]:
        f = init_flag(ds, var)
        f = apply_flag(f, ds[var] < vmin, 1)
        f = apply_flag(f, ds[var] > vmax, 1)
        ds[f"flag_{var}"] = f
        ds[f"flag_{var}"].attrs = {
            "long_name": f"quality flag for {var}",
            "bit_1": "out_of_range",
        }

    # ── CO2 / gases (optional) ────────────────────────────────────────────────
    optional_flags = []
    for var, vmin, vmax in [
        ("upas_co2", t["co2_min"], t["co2_max"]),
        ("upas_voc_raw", t["voc_raw_min"], None),
        ("upas_nox_raw", t["nox_raw_min"], None),
    ]:
        if var in ds and not ds[var].isnull().all():
            f = init_flag(ds, var)
            f = apply_flag(f, ds[var] < vmin, 1)
            if vmax is not None:
                f = apply_flag(f, ds[var] > vmax, 1)
            ds[f"flag_{var}"] = f
            ds[f"flag_{var}"].attrs = {
                "long_name": f"quality flag for {var}",
                "bit_1": "out_of_range",
            }
            optional_flags.append(f"flag_{var}")
            log.info(f"Flagged optional variable {var}")
        else:
            log.info(f"Skipping {var} — all NaN or not present")

    # ── flag_global ───────────────────────────────────────────────────────────
    flag_vars = (
        [f"flag_{v}" for v in pm_all]
        + ["flag_battery", "flag_upas_atmo_temperature", "flag_upas_atmo_rh"]
        + optional_flags
    )
    ds["flag_global"] = compute_flag_global(ds, flag_vars)
    ds["flag_global"].attrs = {
        "long_name": "global quality flag — bitwise OR of all flag variables",
        "flag_bits": str({1: "out_of_range", **flag_bits}),
    }

    return ds, flag_vars


def update_metadata(ds):
    ds.attrs["stage"] = "flagged"
    ds.attrs["flagged"] = datetime.now(timezone.utc).isoformat()
    return ds


# ── main ──────────────────────────────────────────────────────────────────────
log.info("Starting UPAS flagging")

ds = xr.open_dataset(snakemake.input.nc)
log.info(f"Loaded {snakemake.input.nc}: {dict(ds.sizes)}")

flag_bits = {int(k): v for k, v in snakemake.params.flag_bits.items()}
thresholds = snakemake.params.thresholds

ds, flag_vars = flag_upas(ds, thresholds, flag_bits)
ds = update_metadata(ds)

# summary csv
all_bits = {1: "out_of_range", **flag_bits}
summary = flag_summary(ds, flag_vars, all_bits)
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
ds.to_netcdf(out_path, encoding={v: {"zlib": True, "complevel": 4} for v in num_vars})
log.info(f"Wrote {out_path}")
