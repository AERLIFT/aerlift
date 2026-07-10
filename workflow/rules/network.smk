from pathlib import Path

# period token → pandas resample frequency ("campaign" = campaign-integrated)
PERIOD_FREQ = {
    "5min": "5min",
    "1hour": "1h",
    "1day": "1D",
    "campaign": "campaign",
}


rule network:
    input:
        nc=Path(config["merged_dir"]) / "merge.nc",
    output:
        nc=Path(config["network_dir"]) / "network_{period}.nc",
    log:
        "logs/network/{period}.log",
    params:
        period=lambda wc: wc.period,
        freq=lambda wc: PERIOD_FREQ[wc.period],
        completeness=config["network"]["completeness"],
    wildcard_constraints:
        period="|".join(PERIOD_FREQ),
    conda:
        "../envs/python.yaml"
    script:
        "../scripts/network/network.py"
