rule trim_anemometer:
    input:
        nc=Path(config["munged_dir"]) / "anemometer.nc",
    output:
        nc=Path(config["trimmed_dir"]) / "anemometer.nc",
    log:
        "logs/trim/anemometer.log",
    params:
        instrument="anemometer",
        start=config["campaign"]["start"],
        end=config["campaign"]["end"],
        exclude=config["exclude"]["anemometer"],
    script:
        "../scripts/trim.py"


rule trim_aranet:
    input:
        nc=Path(config["munged_dir"]) / "aranet.nc",
    output:
        nc=Path(config["trimmed_dir"]) / "aranet.nc",
    log:
        "logs/trim/aranet.log",
    params:
        instrument="aranet",
        start=config["campaign"]["start"],
        end=config["campaign"]["end"],
        exclude=config["exclude"]["aranet"],
    script:
        "../scripts/trim.py"


rule trim_lascar:
    input:
        nc=Path(config["munged_dir"]) / "lascar.nc",
    output:
        nc=Path(config["trimmed_dir"]) / "lascar.nc",
    log:
        "logs/trim/lascar.log",
    params:
        instrument="lascar",
        start=config["campaign"]["start"],
        end=config["campaign"]["end"],
        exclude=config["exclude"]["lascar"],
    script:
        "../scripts/trim.py"


rule trim_hhb:
    input:
        nc=Path(config["munged_dir"]) / "hhb.nc",
    output:
        nc=Path(config["trimmed_dir"]) / "hhb.nc",
    log:
        "logs/trim/hhb.log",
    params:
        instrument="hhb",
        start=config["campaign"]["start"],
        end=config["campaign"]["end"],
        exclude=config["exclude"]["hhb"],
    script:
        "../scripts/trim.py"


rule trim_upas:
    input:
        nc=Path(config["munged_dir"]) / "upas.nc",
    output:
        nc=Path(config["trimmed_dir"]) / "upas.nc",
    log:
        "logs/trim/upas.log",
    params:
        instrument="upas",
        start=config["campaign"]["start"],
        end=config["campaign"]["end"],
        exclude=config["exclude"]["upas"],
    script:
        "../scripts/trim.py"
