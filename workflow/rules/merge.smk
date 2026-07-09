from pathlib import Path

SENSORS = ["anemometer", "aranet", "lascar", "hhb", "upas", "atmotube", "aulifants"]

rule merge:
    input:
        nc_list=expand(str(Path(config["flagged_dir"]) / "{sensor}.nc"), sensor=SENSORS),
        df_metadata=config["metadata_file"],
    output:
        nc=Path(config["merged_dir"]) / "merge.nc",
    log:
        "logs/merge/merge.log",
    conda:
        "../envs/python.yaml"
    script:
        "../scripts/merge/merge.py"
