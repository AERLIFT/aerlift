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
    conda:
        "../envs/python.yaml"
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
    conda:
        "../envs/python.yaml"
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
    conda:
        "../envs/python.yaml"
    script:
        "../scripts/trim.py"


rule trim_atmotube:
    input:
        nc=Path(config["munged_dir"]) / "atmotube.nc",
    output:
        nc=Path(config["trimmed_dir"]) / "atmotube.nc",
    log:
        "logs/trim/atmotube.log",
    params:
        instrument="atmotube",
        start=config["campaign"]["start"],
        end=config["campaign"]["end"],
        exclude=config["exclude"]["atmotube"],
    conda:
        "../envs/python.yaml"
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
    conda:
        "../envs/python.yaml"
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
    conda:
        "../envs/python.yaml"
    script:
        "../scripts/trim.py"


rule trim_aulifants:
    input:
        nc=Path(config["munged_dir"]) / "aulifants.nc",
    output:
        nc=Path(config["trimmed_dir"]) / "aulifants.nc",
    log:
        "logs/trim/aulifants.log",
    params:
        instrument="aulifants",
        start=config["campaign"]["start"],
        end=config["campaign"]["end"],
        exclude=config["exclude"]["aulifants"],
    conda:
        "../envs/python.yaml"
    script:
        "../scripts/trim.py"
