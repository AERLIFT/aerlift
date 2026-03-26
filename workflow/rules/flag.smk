from pathlib import Path


rule flag_anemometer:
    input:
        nc=Path(config["trimmed_dir"]) / "anemometer.nc",
    output:
        nc=Path(config["flagged_dir"]) / "anemometer.nc",
        csv=Path(config["flagged_dir"]) / "anemometer_flags.csv",
    log:
        "logs/flag/anemometer.log",
    params:
        instrument="anemometer",
        flag_bits=config["flag"]["anemometer"]["bits"],
        thresholds=config["flag"]["anemometer"]["thresholds"],
    script:
        "../scripts/flag/anemometer.py"


rule flag_aranet:
    input:
        nc=Path(config["trimmed_dir"]) / "aranet.nc",
    output:
        nc=Path(config["flagged_dir"]) / "aranet.nc",
        csv=Path(config["flagged_dir"]) / "aranet_flags.csv",
    log:
        "logs/flag/aranet.log",
    params:
        instrument="aranet",
        flag_bits=config["flag"]["aranet"]["bits"],
        thresholds=config["flag"]["aranet"]["thresholds"],
    script:
        "../scripts/flag/aranet.py"


rule flag_lascar:
    input:
        nc=Path(config["trimmed_dir"]) / "lascar.nc",
    output:
        nc=Path(config["flagged_dir"]) / "lascar.nc",
        csv=Path(config["flagged_dir"]) / "lascar_flags.csv",
    log:
        "logs/flag/lascar.log",
    params:
        instrument="lascar",
        flag_bits=config["flag"]["lascar"]["bits"],
        thresholds=config["flag"]["lascar"]["thresholds"],
    script:
        "../scripts/flag/lascar.py"


rule flag_hhb:
    input:
        nc=Path(config["trimmed_dir"]) / "hhb.nc",
    output:
        nc=Path(config["flagged_dir"]) / "hhb.nc",
        csv=Path(config["flagged_dir"]) / "hhb_flags.csv",
    log:
        "logs/flag/hhb.log",
    params:
        instrument="hhb",
        flag_bits=config["flag"]["hhb"]["bits"],
        thresholds=config["flag"]["hhb"]["thresholds"],
        alphasense=config["instruments"]["hhb"]["alphasense"],
    script:
        "../scripts/flag/hhb.py"


rule flag_upas:
    input:
        nc=Path(config["trimmed_dir"]) / "upas.nc",
    output:
        nc=Path(config["flagged_dir"]) / "upas.nc",
        csv=Path(config["flagged_dir"]) / "upas_flags.csv",
    log:
        "logs/flag/upas.log",
    params:
        instrument="upas",
        flag_bits=config["flag"]["upas"]["bits"],
        thresholds=config["flag"]["upas"]["thresholds"],
    script:
        "../scripts/flag/upas.py"
