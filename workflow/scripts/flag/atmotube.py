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
) -> xr.Dataset:
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

    ds["flag_global"] = compute_flag_global(ds, ["flag_pm", "flag_voc"])
    ds["flag_global"].attrs = {
        "long_name": "global quality flag — bitwise OR of all flag variables",
        "flag_bits": str({1: "out_of_range", **flag_bits}),
    }

    return ds


def update_metadata(ds: xr.Dataset) -> xr.Dataset:
    ds.attrs["stage"] = "flagged"
    ds.attrs["flagged"] = datetime.now(timezone.utc).isoformat()
    return ds


if __name__ == "__main__":
    # ── main ──────────────────────────────────────────────────────────────────────
    log.info("Starting Atmotube flagging")

    ds = xr.open_dataset(snakemake.input.nc)
    log.info(f"Loaded {snakemake.input.nc}: {dict(ds.sizes)}")

    flag_bits = {int(k): v for k, v in snakemake.params.flag_bits.items()}
    thresholds = snakemake.params.thresholds

    ds = flag_atmotube(ds, thresholds, flag_bits)
    ds = update_metadata(ds)

    # summary csv
    all_bits = {1: "out_of_range", **flag_bits}
    summary = flag_summary(ds, ["flag_pm", "flag_voc"], all_bits)
    summary.to_csv(snakemake.output.csv, index=False)
    log.info(f"Wrote {snakemake.output.csv}")

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
