rule munge_anemometer:
    input:
        files=lambda wc: list(
            (Path(config["raw_dir"].strip()) / "anemometer").glob("*.txt")
        ),
    output:
        nc=Path(config["munged_dir"]) / "anemometer.nc",
        csv=Path(config["munged_dir"]) / "anemometer_summary.csv",
    log:
        "logs/munge/anemometer.log",
    params:
        raw_dir=config["raw_dir"],
        skiprows=config["instruments"]["anemometer"]["skiprows"],
        usecols=config["instruments"]["anemometer"]["usecols"],
        threshold=config["instruments"]["anemometer"]["threshold"]["flow_indicator"],
        timezone=config["campaign"]["timezone"],
    conda:
        "../envs/python.yaml"
    script:
        "../scripts/munge/anemometer.py"

rule munge_aranet:
    input:
        files=lambda wc: list(
            (Path(config["raw_dir"].strip()) / "aranet").glob("*.csv")
        ),
    output:
        nc=Path(config["munged_dir"]) / "aranet.nc",
        csv=Path(config["munged_dir"]) / "aranet_summary.csv",
    log:
        "logs/munge/aranet.log",
    params:
        raw_dir=config["raw_dir"],
        timezone=config["campaign"]["timezone"],
    conda:
        "../envs/python.yaml"
    script:
        "../scripts/munge/aranet.py"


rule munge_lascar:
    input:
        files=lambda wc: list(
            (Path(config["raw_dir"].strip()) / "lascar").glob(
                f"*{config['instruments']['lascar']['file_ext']}"
            )
        ),
    output:
        nc=Path(config["munged_dir"]) / "lascar.nc",
        csv=Path(config["munged_dir"]) / "lascar_summary.csv",
    log:
        "logs/munge/lascar.log",
    params:
        raw_dir=config["raw_dir"],
        timezone=config["campaign"]["timezone"],
        usecols=config["instruments"]["lascar"]["usecols"],
        file_ext=config["instruments"]["lascar"]["file_ext"],
    conda:
        "../envs/python.yaml"
    script:
        "../scripts/munge/lascar.py"


rule munge_hhb_r:
    input:
        files=lambda wc: list((Path(config["raw_dir"].strip()) / "hhb").glob("*.csv")),
    output:
        csv=Path(config["munged_dir"]) / "hhb_intermediate.csv",
    log:
        "logs/munge/hhb_r.log",
    params:
        raw_dir=config["raw_dir"],
        timezone=config["campaign"]["timezone"],
        cols_keep=config["instruments"]["hhb"]["cols_keep"],
    conda:
        "../envs/r.yaml"
    script:
        "../scripts/munge/hhb.R"


rule munge_hhb:
    input:
        csv=Path(config["munged_dir"]) / "hhb_intermediate.csv",
    output:
        nc=Path(config["munged_dir"]) / "hhb.nc",
        csv=Path(config["munged_dir"]) / "hhb_summary.csv",
    log:
        "logs/munge/hhb_nc.log",
    params:
        timezone=config["campaign"]["timezone"],
        alphasense=config["instruments"]["hhb"]["alphasense"],
    conda:
        "../envs/python.yaml"
    script:
        "../scripts/munge/hhb.py"


rule munge_upas_r:
    input:
        files=lambda wc: list((Path(config["raw_dir"].strip()) / "upas").glob("*.txt")),
    output:
        csv=Path(config["munged_dir"]) / "upas_intermediate.csv",
    log:
        "logs/munge/upas_r.log",
    params:
        raw_dir=config["raw_dir"],
        timezone=config["campaign"]["timezone"],
        cols_keep=config["instruments"]["upas"]["cols_keep"],
    conda:
        "../envs/r.yaml"
    script:
        "../scripts/munge/upas.R"


rule munge_upas:
    input:
        csv=Path(config["munged_dir"]) / "upas_intermediate.csv",
    output:
        nc=Path(config["munged_dir"]) / "upas.nc",
        csv=Path(config["munged_dir"]) / "upas_summary.csv",
    log:
        "logs/munge/upas_nc.log",
    params:
        timezone=config["campaign"]["timezone"],
    conda:
        "../envs/python.yaml"
    script:
        "../scripts/munge/upas.py"